"""Read-only snapshot capture primitive; not connected to a hosted job or CLI."""
import time

from bson import BSON
import pymongo
from pymongo import ReadPreference

from .backup_archive import BackupError, COLLECTIONS, MAX_BYTES, MAX_ROWS, seal


def capture_archive(database,encryption_key,source_id,*,clock=None):
    """Read the four allowed collections from a single MongoDB snapshot.

    Requires a snapshot-capable replica set/server and a read-only database
    credential supplied by the caller. Unsupported/expired snapshots fail;
    there is deliberately no fallback to independent ordinary reads.
    """
    stamp=time.time() if clock is None else clock
    # Validate key/source/timestamp before contacting the database.
    seal({name:[] for name in COLLECTIONS},encryption_key,source_id,clock=stamp)
    rows={name:[] for name in COLLECTIONS}
    # Reserve metadata room; final serialization has an exact independent cap.
    estimated_bytes=4096
    try:
        db=database.with_options(read_preference=ReadPreference.PRIMARY)
        with pymongo.timeout(35), database.client.start_session(snapshot=True) as session:
            for name in COLLECTIONS:
                with db[name].find({},session=session).batch_size(100).max_time_ms(20_000) as cursor:
                    for row in cursor:
                        # Includes conservative BSON array index/type overhead.
                        estimated_bytes+=len(BSON.encode(row))+32
                        if estimated_bytes>MAX_BYTES or len(rows[name])>=MAX_ROWS:
                            raise BackupError('Backup capture bounds exceeded.')
                        rows[name].append(row)
        return seal(rows,encryption_key,source_id,clock=stamp)
    except BackupError:
        raise
    except Exception:
        raise BackupError('Consistent backup capture failed.') from None
