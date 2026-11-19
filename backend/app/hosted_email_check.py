"""Explicit one-attempt hosted SMTP test; no account or queued-notice processing."""
import logging
import os
import re
import time
from email.utils import parseaddr
from pymongo.errors import DuplicateKeyError
from .email_check import send_test_message,delivery_error
from .workspaces import StorageError


def run(database):
    recipient=os.environ.get('PDW_EMAIL_TEST_TO','').strip()
    test_id=os.environ.get('PDW_EMAIL_TEST_ID','')
    if (not re.fullmatch(r'[0-9a-f]{32}',test_id) or '\r' in recipient or '\n' in recipient or
            parseaddr(recipient)[1]!=recipient or recipient.count('@')!=1 or
            not all(recipient.split('@'))):
        raise StorageError(503,'email_test_unconfigured','Configure the explicit email test recipient and ID.')
    record_id='email_test_'+test_id
    try:
        # Claim before SMTP. Even an ambiguous failure/crash is never retried
        # automatically by later cron calls with the same test ID.
        database.system_status.insert_one({'_id':record_id,'status':'attempted','started_at':time.time()})
    except DuplicateKeyError:
        return {'status':'ok','mode':'email-test','delivery':'already_attempted'}
    try:
        send_test_message(recipient)
    except Exception as error:
        diagnostic=delivery_error(error)
        logging.getLogger('pdw.email_test').warning('Hosted email test failed: %s',diagnostic)
        database.system_status.update_one({'_id':record_id},{'$set':{
            'status':'failed','finished_at':time.time(),'diagnostic':diagnostic}})
        raise StorageError(503,'email_test_failed','The email test failed. Check the safe server diagnostics.') from None
    database.system_status.update_one({'_id':record_id},{'$set':{'status':'accepted','finished_at':time.time()}})
    return {'status':'ok','mode':'email-test','delivery':'accepted'}
