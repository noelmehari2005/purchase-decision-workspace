# Encrypted backup and isolated restore preparation

Status: the first real encrypted staging snapshot was uploaded and its isolated local restore verified on November 20, 2026. Physical expiration has not yet been verified; no recurring backup/expiry guarantee is enabled. The hosted app and its check-only scheduler are unchanged.

## Off-site storage setup progress

The owner created a B2 account without adding payment details. The console shows daily storage/download caps of $0.00 (10 GB storage and 1 GB downloads), Class B/C limits of 2,500 per day, and email alerts enabled. Editing caps requires a credit card, so these defaults were left unchanged. These are the observed account controls, not a promise about future pricing or all possible charge classes.

Created private bucket `pdw-staging-backups-noelmehari-20261119`, ID `dda850c39930f979ac190c13`, endpoint `s3.us-east-005.backblazeb2.com`. The console confirms encryption enabled and Object Lock disabled. It received a fictional transport probe and subsequently the first real encrypted staging archive.

A custom lifecycle rule was saved after explicit owner approval and verified by reopening the settings: prefix `archives/`, hide after 27 days from upload, delete one day after hiding. B2 applies rules daily, so normal processing adds delay; the margin is intended to keep archive copies below the policy's 30-day ceiling, but actual expiry and delayed-job alerts still need verification. Other prefixes, including separately preserved current controls, are outside this rule. Permanent deletion removes aged archive versions from recovery. The bucket overview confirms “Custom lifecycle rules.” This is configuration evidence, not proof that any uploaded archive has expired.

Storage references checked November 19, 2026: [B2 pricing](https://www.backblaze.com/cloud-storage/pricing), [caps and alerts](https://www.backblaze.com/docs/cloud-storage-create-and-manage-caps-and-alerts), [lifecycle timing and versions](https://www.backblaze.com/docs/cloud-storage-lifecycle-rules).

## Next proof: one fictional encrypted upload

Prepared November 20: `backend.app.backup_storage` authenticates with B2's Native v4 API, requires a key restricted to the exact staging bucket and `archives/` prefix, and uploads an authenticated, unexpired PDW archive. It sends no encryption key, account identifiers or workspace titles in object names. It rejects redirects, unexpected endpoint hosts, oversized responses and mismatched upload acknowledgements. Failures use fixed safe text and never retry automatically: a timeout can leave an accepted object, which must be inspected before retrying. Seven mocked transport tests pass; together with the archive tests, 19 non-database checks pass and one opt-in database exercise skips in the coding environment. The owner's earlier 13-case MongoDB result remains the separate real restore evidence.

For the first transport probe, use a new standard key restricted to this bucket, Write Only, prefix `archives/`, duration `86400` seconds. Do not use the master key or enable list-all-bucket-names. The owner must create and handle the credential privately. The console's granted capabilities must be reviewed before any long-lived deployment key is selected; the transport enforces bucket/prefix/write permission but does not claim that the key has no additional capabilities.

After creating the temporary key, the owner can run:

```sh
cd ~/Documents/Portfolio/purchase-decision-workspace
.venv/bin/python -m backend.app.backup_storage --upload-fixture
```

The command describes the destination and requires typing `UPLOAD FIXTURE`, then prompts for the keyID and full applicationKey with hidden input. It does not load `.env`, read MongoDB, save credentials, create a recurring job or deploy changes. It uploads one small fictional encrypted object. Its temporary encryption key is discarded, so this probe is intentionally not a recoverable app backup. Success checks B2's returned bucket, name, size and checksum and prints a SHA-256 fingerprint; it does not establish a download/restore round trip or physical expiration. The object falls under the approved archive lifecycle rule. Inspect the bucket after an uncertain result before permitting another attempt. Keep all credentials out of chat and screenshots.

API references checked November 20: [authorization](https://www.backblaze.com/apidocs/b2-authorize-account), [upload URL](https://www.backblaze.com/apidocs/b2-get-upload-url), [file upload](https://www.backblaze.com/apidocs/b2-upload-file), [key scoping](https://www.backblaze.com/docs/en/cloud-storage-application-keys).

Owner-run transport result, November 20: `archives/3b4fe0d6dbc647c189690f3cb6c60327.pdwbackup`, 311 bytes, SHA-256 `9c5572aed7349424a9d82f8ca15e5e5d2eb416aa3a9deaa767054899b45bd8df`, `upload_acknowledged=true`, `restore_verified=false`, `expiry_verified=false`. The B2 bucket overview independently confirms one file totaling 311 bytes. The local test key was prepared with a one-day expiry; no secret was read or stored by the agent. The fixture's encryption key was intentionally discarded.

Subsequent permission review found the console's Write Only preset includes `deleteFiles`, `listBuckets`, `writeBucketEncryption`, `writeBucketLifecycleRules`, `writeBucketLogging`, `writeBucketNotifications`, `writeBucketReplications` and `writeFiles`. This was broader than needed, despite the bucket/prefix restriction. The temporary preset key must not be used for real backups; the upload transport now rejects additional capabilities beyond `listBuckets` and `writeFiles`. The owner no longer has that temporary secret, so a replacement is needed.

Prepared `backend.app.backup_keys --create-pair` for owner-run private provisioning. It uses a master credential only in memory to authorize directly with B2 and create two exact-scoped keys: writer (`listBuckets`, `writeFiles`) and reader (`listBuckets`, `listFiles`, `readFiles`), both restricted to this bucket, prefix `archives/`, expiry 90 days. Neither grants permanent deletion, bucket modification or key management. It verifies the returned account, capabilities, bucket, prefix and expiry before showing NEW credentials privately in the owner's interactive Terminal. It refuses redirected/noninteractive output and never prints/persists the master credential. It has no upload, source-database or hosted activation behavior. Key creation is not retried automatically; after a failure the owner must inspect for partial creation. New secrets must be saved privately and must not be pasted into chat. The 90-day credentials will need rotation and expiry monitoring before unattended operation is considered complete.

If no master credential is available privately, its generation is an owner action in B2. Generating a new master key invalidates an existing master key; standard application keys remain separate. Do not generate/rotate it silently or put it into Render. The owner now reports completing private creation and saving both custom key pairs. No credential values were shared. The classic console list showed only the earlier probe key; this is inconclusive for v4-created keys, because older listing versions omit Multi-Bucket keys. Do not generate duplicates solely because of this UI result. Effective writer permissions will be checked by authorization before any archive upload; reader verification remains part of download testing. Four mocked creation tests plus the existing backup modules pass 36 local tests with one opt-in database test skipped. [B2 custom key API](https://www.backblaze.com/apidocs/b2-create-key) documents exact capabilities and duration; [key-listing versions](https://www.backblaze.com/apidocs/b2-list-keys) document the differences in returned keys. The console may use an older listing method; that explanation is an inference, not a verified implementation detail of its UI.

## Consistent capture preparation

The owner generated a separate 64-hex-character AES-256 backup key and confirmed saving it in their password manager, outside Render and B2. The value has not been read by the agent or installed in hosting. Keep this key distinct from database passwords and B2 application keys; preserve it before any recoverable archive is created.

The owner created `pdw_staging_backup` with a separate private password. The Atlas user list confirms `read@pdw_staging`, restricted to one cluster; the form selected only `pdw-staging` and no global built-in role. Existing application credentials and network rules remain unchanged. Atlas also confirms the current computer's address is already allowlisted alongside the two Render ranges, so no network expansion was needed. The subsequent owner-run capture check verified the effective authenticated principal/read-only role and real snapshot-session support.

The owner-run command below performs that check without saving or uploading an archive:

```sh
cd ~/Documents/Portfolio/purchase-decision-workspace
.venv/bin/python -m backend.app.backup_staging --check-capture
```

Type `CHECK STAGING CAPTURE`, then privately paste the saved backup encryption key and the separate `pdw_staging_backup` password into the two hidden prompts. The command uses the Atlas-confirmed host `pdw-staging.avzq5pq.mongodb.net`, TLS with certificate verification, the fixed staging database and username, and percent-encodes the original password exactly once. It checks its own authenticated principal and requires exactly `read@pdw_staging` before capture. It never loads `.env`, writes the source, sends notices, calls Auth0 or B2, stores credentials, or saves a local archive. Its safe output contains aggregate record counts and encrypted size, never document contents. Failure text identifies the phase without raw exception details. Snapshot support or role failures stop the attempt; there is no weaker-read fallback.

The owner ran `--capture-and-upload` after explicit `BACK UP STAGING` confirmation. It additionally asks for B2 writer credentials. It must not be enabled as a recurring backup or treated as a verified restore until independently preserved current controls, restore/download and expiration checks are complete. At that stage all four initial backup modules discovered 33 tests, with 32 passing and the existing opt-in database exercise skipped here.

Owner-run staging capture check, November 20: `source_role_verified=true`, `consistent_snapshot_captured=true`, `archive_roundtrip_verified=true`, `encrypted_bytes=8025`; aggregate records: users 2, decisions 1, snapshots 0, deletion ledger 0. The result explicitly reports `durable_backup_created=false` and `uploaded=false`. This proves capture and local in-memory encryption/decryption on the real staging deployment; it does not prove B2 download/restore, durable archive availability or expiration. No document bodies, encryption keys or database credentials were shared with the agent.

Owner-run real upload result, November 20: `archives/86eae9ce58624621ab87a2ea2869dee0.pdwbackup`, 8,025 bytes, SHA-256 `0b07cbdd63e124cddf581a86d8d01b0bde9c09b018c5048a809e9c56e77d6cd2`. Upload acknowledged, source role verified, consistent snapshot captured; restore, expiry and recurring scheduling explicitly false. This also verifies the actual writer credential passed the restricted bucket/prefix/capability checks. Keep the saved encryption key: unlike the probe, this archive is intended to be recoverable. A download/restore result remains necessary to prove recovery.

## Real archive download and disposable restore drill

Prepared `backend.app.backup_recovery` to download the exact archive and check its saved SHA-256 fingerprint before authenticating/decrypting. Reader authentication requires exactly `listBuckets`, `listFiles`, `readFiles` for this bucket and `archives/`; tokens remain in headers, never URLs. Redirects, unexpected hosts, wrong fingerprints and oversized downloads fail closed. No file is saved locally by the command.

The drill then reads fresh current controls from Atlas using the dedicated read-only principal and a separate consistent capture. Their actual capture timestamp is used for the freshness check. Suppression planning precedes target writes. It restores only to a new random `pdw_restore_test_<UUID>` on local MongoDB, with live access disabled. Verification compares all planned records, checks workspace schema/state/revisions and historical-review retrieval, denies cross-owner/tombstone access, and excludes sessions/login flows. It removes only its own target bearing the matching reservation; existing targets are neither overwritten nor dropped. A failed cleanup prevents a success report. No Atlas writes, provider calls, mail, B2 deletion or live app connection change occurs.

Start Docker Desktop for this drill, then run:

```sh
cd ~/Documents/Portfolio/purchase-decision-workspace
docker compose up -d mongodb
.venv/bin/python -m backend.app.backup_recovery --file archives/86eae9ce58624621ab87a2ea2869dee0.pdwbackup --sha256 0b07cbdd63e124cddf581a86d8d01b0bde9c09b018c5048a809e9c56e77d6cd2
```

Type `RESTORE LOCAL DRILL`, then privately enter the saved encryption key, read-only Atlas password, B2 reader keyID and full reader applicationKey. Share only the final safe summary. Docker can stop after completion. This creates a temporary local decrypted copy of staging data for verification, then logically removes that disposable database; it does not claim secure media erasure. Do not connect the app to the quarantine target. If the drill reports possible remaining local data, inspect ownership before cleanup rather than deleting arbitrary databases.

Seven additional mocked recovery tests pass. Across six backup modules, 44 tests are discovered: 43 pass locally and one opt-in database exercise skips here. The owner completed the real downloaded restore: download SHA-256 verified, archive authenticated, restore verified, one visible workspace, zero reviews, zero restored sessions, current controls applied, live access disabled, no Atlas writes requested, and disposable target removed. Expiry and recurring scheduling remain false. The earlier 13-case fictional MongoDB exercise remains separate evidence, including historical-review and newer-deletion cases absent from this real archive. Current control preservation still depends on the live Atlas source, so this drill is not proof of primary-database-loss recovery; independently durable current controls remain required before release or automated recovery. [B2 private download API](https://www.backblaze.com/apidocs/b2-download-file-by-name) checked November 20.

`backend.app.backup_capture.capture_archive` is a read-only primitive using a single PyMongo snapshot session for all four allowed collections, primary reads, a 35-second operation budget and incremental row/byte bounds before final archive serialization. Unsupported/expired snapshots and partial capture errors fail closed with no ordinary-read fallback. It does not load credentials, choose a live database, upload files or install a hosted route. A dedicated read-only database identity still needs provisioning before live use.

Six mocked capture tests verify shared snapshot use, source immutability, partial failure, redacted errors, row/byte bounds and orphan rejection. At that stage the capture, transport and archive modules had 25 passing local checks with one opt-in MongoDB case skipped. The later owner-run staging capture and real restore verified this mechanism on the actual replica set. The earlier disposable Docker fixture is quiescent and does not itself prove snapshot-session support. [PyMongo snapshot sessions](https://pymongo.readthedocs.io/en/stable/api/pymongo/client_session.html) document the consistent-read mechanism.

## First proof: a disposable local restore

Start Docker Desktop, then run in your own Terminal:

```sh
cd ~/Documents/Portfolio/purchase-decision-workspace
docker compose up -d mongodb
PDW_TEST_MONGO_URI=mongodb://127.0.0.1:27017 .venv/bin/python -m unittest backend.tests.test_backup_archive -v
```

This runs the encrypted archive tests and a real MongoDB exercise. It creates two new random databases named `pdw_backup_test_<UUID>` and `pdw_restore_test_<UUID>`, containing fictional users, four workspaces, historical reviews and fake transient login records. It writes an encrypted sample archive to a temporary private file, decrypts it, applies newer account/workspace deletion decisions and restores into the separate target. It then verifies one surviving workspace/review, suppression of deleted or overdue data, absence of restored sessions/login flows, and unchanged source records during restoration. Only its own fixture databases and temporary file are removed afterward. Existing local databases and Atlas are not targeted. No Auth0, SMTP or Icecat request occurs.

The owner ran this command on November 19, 2026: all 13 tests passed in 1.235 seconds, including the real MongoDB exercise, with no skips. This confirms the fictional encrypted restore, newer-deletion suppression and session exclusion. The fixture includes fictional budgets, confirmed candidates, candidate revisions and a historical review; the restore is checked through the application's repository and saved-state validator. The initial backend regression discovered 217 tests: 180 passed and 37 opt-in MongoDB cases skipped.

The coding environment cannot access the Docker socket, so this database evidence comes from the owner's Terminal output. Docker is needed for this test only and may now be stopped; the hosted app remains independent. This sample result does not establish recovery of the hosted database or physical backup expiration.

An optional direct exercise prints only a safe summary:

```sh
.venv/bin/python -m backend.app.backup_archive --exercise
```

The CLI accepts only a single `localhost` or `127.0.0.1` MongoDB endpoint without credentials, database path or query options. It does not load `backend/.env`. It has no live backup or live restore subcommand. The successful result explicitly reports `durable_live_backup_created=false`; the exercise archive/key are temporary and cannot recover the real app later.

## Archive and restore boundaries

- AES-256-GCM authenticates/encrypts BSON with a fresh random 96-bit nonce. The archive format identifier is authenticated associated data. Wrong keys, changed ciphertext, malformed envelopes and unsupported/expired archives are rejected. BSON types are preserved. The existing pinned `cryptography` and PyMongo dependencies are used; no new package is required.
- The prototype is bounded to 32 MiB of plaintext and 100,000 rows per collection. It is an in-memory implementation for small staging datasets, not a streaming backup of an entire cluster. Oversized inputs fail rather than silently truncate. The original sequential fixture capture is consistent because its random source is quiescent; the new snapshot-session primitive was subsequently verified by the owner against real staging and is used by the one-time staging capture commands.
- Only `users`, `decisions`, `snapshots` and `deletion_ledger` are allowed. Sessions, login flows, rate limits, import receipts, replay nonces, job locks and status records are excluded. Imported evidence already embedded in a saved workspace remains in that workspace. The archive can contain private account/workspace information and must remain encrypted; generated archive/key suffixes are ignored by Git as an additional precaution.
- Restore planning requires a separate matching current control set with account lifecycle state and the deletion ledger, captured within five minutes. The local exercise reads it directly from the same fixture source after making newer deletion decisions. Matching labels/timestamps alone do not prove an external control set's authority; this helper must not be exposed as a user-facing endpoint. Independently protected live control/ledger preservation remains necessary before live restores.
- Account/workspace suppression from both the archive and current controls is preserved. New pending deletion deadlines override older active state; the exact recovery cutoff stays closed. Current restoration can cancel obsolete pending state. Previously recorded purge/backup deadlines are never extended by a later control copy. Missing current owners fail closed. Provider cleanup retry state remains quarantined for later review, rather than being falsely marked completed.
- Deleted workspace bodies and their reviews are suppressed; tombstones remain to prevent old IDs from recreating them. Restored lifecycle generations are replaced. Queued email state and active purge leases are removed, so restoring an archive does not itself resend notices or reuse old leases. The module never sends email or deletes provider identities.
- Only a brand-new `pdw_restore_test_<UUID>` database can receive a restore. Existing targets and the live database name are rejected before writes. A unique manifest reserves the target; a partial failure remains quarantined. Required application indexes are rebuilt. The prototype never changes the app's connection string or reopens access to restored data.

## Expiration probe preparation

The real restore drill passed, and Docker may be stopped. The next retention test targets only the original fictional 311-byte transport probe: `archives/3b4fe0d6dbc647c189690f3cb6c60327.pdwbackup`. After explicit owner approval, a second B2 rule was saved and its values verified after reload: this full file-name prefix, hide after one day, permanently delete one day after hiding. The existing `archives/` rule remains 27 days plus one. B2 applies the shortest applicable values, so only this disposable probe gets accelerated expiration. No real workspace archive matches the extra prefix. Daily lifecycle processing means this is a multi-day check, not an immediate test. Custom upload timestamp backdating was not used; B2 documents that it requires support activation for migrations.

`backend.app.backup_retention --check-probe` is a read-only check using the saved reader keyID and applicationKey. It requests a complete file-version listing for this specific prefix and distinguishes upload versions from hide markers; a hidden object is not treated as removed. Pagination, denied/not-found requests, unexpected results and errors cannot count as successful expiration. It never requests deletion, downloads real app bodies or uses the Master credential. Empty complete listings provide logical object-version removal evidence for this known uploaded probe, not physical media-erasure proof or automatic verification of every real archive's age. The real-archive expiry field stays false.

```sh
cd ~/Documents/Portfolio/purchase-decision-workspace
.venv/bin/python -m backend.app.backup_retention --check-probe
```

After the extra rule is approved/saved, record an initial listing and a later completed removal result. Real-archive expiration auditing, independently durable current controls, recurring capture and backup alerts remain separate unfinished work. Four new retention tests pass; all seven backup modules discover 48 tests, 47 passing locally and one opt-in database case skipped. [Lifecycle scheduling](https://www.backblaze.com/docs/cloud-storage-lifecycle-rules) and [custom upload timestamp restrictions](https://www.backblaze.com/apidocs/b2-upload-file) checked November 20.

The owner recorded the initial listing on November 20: probe versions 1, uploaded versions 1, hide markers 0, probe expiry false, real-archive expiry false, deletion requested by command false. This is the baseline before daily lifecycle processing; no removal result has been observed yet. Separately, a disabled daily upload job and independent backup Worker are now prepared in [scheduled-backups-setup.md](scheduled-backups-setup.md); they are not deployed or activated.

## What remains before unattended backups

The agreed deletion policy is still 30 days for account recovery, active-data purge afterward, and backup-copy removal within 30 further days after actual active purge. Rejecting an expired archive during restore does **not** remove the underlying backup file/object. No physical retention process is claimed by this test.

The next deployment work is to verify the B2 transport and granted key capabilities, choose encryption-key custody/recovery separately from archives, implement a consistent live capture with least-privilege read access, preserve the current suppression ledger/control state independently, and schedule uploads with verified all-version expiration. Failures/missed backups need their own independent monitor. Finally, restore a real encrypted staging backup into an isolated target, verify ownership/revisions/reviews and suppression, and prove actual object expiry. Never restore over the live database to test a backup, and never use the old snapshot's deletion ledger as the only current authority.

Atlas's optional Free-cluster managed snapshot feature is a billed preview, so it was not enabled for this free-only setup. Local encrypted exercises are not an unattended off-site service.

References checked November 19:

- [MongoDB Atlas backup options](https://www.mongodb.com/docs/atlas/backup-restore-cluster/)
- [MongoDB dump/restore behavior and version matching](https://www.mongodb.com/docs/database-tools/mongodump/mongodump-behavior/)
- [PyMongo transactions and consistency](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/crud/transactions/)
- [Cryptography authenticated encryption API](https://cryptography.io/en/latest/hazmat/primitives/aead/)
