"""Transactional deletion notices. Delivery is explicit, leased and retryable."""
from datetime import datetime,timezone
from email.message import EmailMessage
from email.utils import parseaddr
import os
import secrets
import smtplib
import ssl
import time
from .workspaces import StorageError


def smtp_send(recipient,requested_at,deadline):
    host=os.environ.get('PDW_SMTP_HOST','').strip()
    sender=os.environ.get('PDW_SMTP_FROM','').strip()
    if not host or not sender:
        raise StorageError(503,'email_unconfigured','Configure SMTP before delivering account notifications.')
    for address in (recipient,sender):
        if '\r' in address or '\n' in address or '@' not in parseaddr(address)[1]:
            raise ValueError('Invalid mail address')
    port=int(os.environ.get('PDW_SMTP_PORT','465'))
    origin=os.environ.get('PDW_APP_ORIGIN','http://127.0.0.1:5173')
    if origin not in ('http://127.0.0.1:5173','http://localhost:5173'):
        raise ValueError('Unsupported app origin')
    date=lambda stamp:datetime.fromtimestamp(stamp,timezone.utc).strftime('%B %d, %Y at %H:%M UTC')
    message=EmailMessage();message['From']=sender;message['To']=recipient
    message['Subject']='Purchase Decision Workspace: account deletion requested'
    message.set_content(f'Account deletion was requested on {date(requested_at)}.\n\n'
        f'You can recover your saved data by signing in and explicitly choosing Restore account before {date(deadline)}. '
        'Signing in alone does not cancel deletion. After that deadline, recovery is no longer available.\n\n'
        'After active deletion, older system backups may remain for up to a further 30 days under the backup-retention policy. Backups are not a user recovery option.\n\n'
        f'Open Purchase Decision Workspace: {origin}/\n\n'
        'If you already restored your account, no further action is needed. '
        'If you did not request deletion, sign in, restore the account, and reset your password.\n')
    context=ssl.create_default_context()
    connection=smtplib.SMTP_SSL(host,port,timeout=10,context=context) if port==465 else smtplib.SMTP(host,port,timeout=10)
    with connection as client:
        if port!=465:client.starttls(context=context)
        username=os.environ.get('PDW_SMTP_USERNAME','')
        if username:client.login(username,os.environ.get('PDW_SMTP_PASSWORD',''))
        if client.send_message(message):raise RuntimeError('Recipient refused')


def deliver_pending(database,send=smtp_send,limit=25,clock=None):
    from pymongo import ReturnDocument
    stamp=time.time() if clock is None else clock
    counts={'sent':0,'retry_pending':0}
    for _ in range(limit):
        lease=secrets.token_hex(16)
        user=database.users.find_one_and_update({'state':'pending_deletion','delete_after':{'$gt':stamp},
            'deletion_notice.next_attempt':{'$lte':stamp},'$or':[
                {'deletion_notice.status':'queued'},
                {'deletion_notice.status':'sending','deletion_notice.lease_until':{'$lte':stamp}}]},
            {'$set':{'deletion_notice.status':'sending','deletion_notice.lease':lease,
                     'deletion_notice.lease_until':stamp+120},'$inc':{'deletion_notice.attempts':1}},
            return_document=ReturnDocument.AFTER)
        if not user:break
        query={'_id':user['_id'],'deletion_notice.id':user['deletion_notice']['id'],
               'deletion_notice.lease':lease,'deletion_notice.status':'sending'}
        try:
            send(user['email'],user['delete_requested_at'],user['delete_after'])
            database.users.update_one(query,{'$set':{'deletion_notice.status':'sent','deletion_notice.sent_at':stamp}})
            counts['sent']+=1
        except Exception:
            delay=min(3600,60*2**min(user['deletion_notice']['attempts'],6))
            database.users.update_one(query,{'$set':{'deletion_notice.status':'queued','deletion_notice.next_attempt':stamp+delay}})
            counts['retry_pending']+=1
    return counts
