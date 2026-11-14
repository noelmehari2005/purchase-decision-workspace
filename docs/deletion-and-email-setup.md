# Local deletion, recovery and notification setup

The user selected an email integration plus a setup guide; no email-service account was created or subscription purchased. The local deletion/recovery code works with the existing Auth0 account. Actual notification delivery and permanent Auth0 cleanup require the configuration below. Production scheduling and backup deletion remain deployment work.

## Notification delivery

Use your chosen service's SMTP settings in ignored `backend/.env`:

```dotenv
PDW_SMTP_HOST=
PDW_SMTP_PORT=465
PDW_SMTP_FROM=
PDW_SMTP_USERNAME=
PDW_SMTP_PASSWORD=
```

Use a sender address authorized by that service. Complete any sender/domain verification required by the service. Keep credentials local; do not paste them into chat, source files or Git. Port 465 uses implicit TLS; other ports require STARTTLS. Certificate checks remain enabled and an SMTP error never downgrades to plaintext. A provider may require an app-specific password or a generated SMTP credential rather than the normal account password.

The deletion notice states when the request was made, the exact recovery deadline in UTC, how to sign in and explicitly restore the account, and the policy allowing older backup copies for up to a further 30 days after active deletion. It contains the normal application URL, never a bearer recovery token. Signing in alone does not restore data. The message also covers the case where restoration happened before a delayed notice arrived. Local URLs work only on the machine running the app; a real deployment needs its final HTTPS origin before public email delivery is enabled.

A request queues its notice atomically inside the user record. The UI distinguishes queued/sending/sent and warns when SMTP is unconfigured. `sent` means the SMTP server accepted the recipient, not proof the message reached an inbox. Temporary failures retry with increasing delays, capped at one hour. Delivery is at least once: if the process dies after SMTP acceptance but before recording success, a retry can send a duplicate. Restoration cancels notices that have not begun sending; a notice already in flight can still arrive.

## Dedicated Auth0 cleanup client

Keep the existing read-only Management API client unchanged. Create a **separate Machine to Machine application**, authorize it for Auth0 Management API with **`delete:users` only**, and enter its credentials locally:

```dotenv
PDW_AUTH0_DELETION_CLIENT_ID=
PDW_AUTH0_DELETION_CLIENT_SECRET=
```

This client grants irreversible user deletion. The developer should configure it deliberately in the Auth0 Dashboard; the coding session did not create credentials, broaden existing grants, or delete a real Auth0 identity. The worker uses the existing configured tenant and server-side client-credentials exchange, requests `delete:users`, sends the access token in an Authorization header, and deletes only the stored database-connection subject selected by the due account job. It does not search users or delete by email.

The implementation follows [Auth0 Delete a User](https://auth0.com/docs/api/management/v2/users/delete-users-by-id). Successful 204 responses (including already-absent users) and 404 are treated as completed cleanup; other statuses retry. Auth0 documents the [204 behavior for repeated deletion](https://support.auth0.com/center/s/article/auth0-management-api-delete-endpoint-returns-204-instead-of-404-for-non-existent-users). No real provider cleanup was exercised during automated tests; the HTTP contract uses controlled fake responses.

## Running maintenance

Restart the backend after changing its environment. Maintenance is a separate operator command:

```sh
cd /Users/noelmehari/Documents/Portfolio/purchase-decision-workspace
.venv/bin/python -m backend.app.maintenance --run-once
```

**This command applies real due deletions to the configured database.** It is not a preview. It sends queued notices, claims accounts whose recovery deadline has passed, removes their associated local records, attempts provider cleanup, and repeats workspace-child cleanup. No 30-day wait is shortened by this command. Ordinary frontend access does not run the worker.

For a deployed service, supervise this command at least once a minute using the selected hosting scheduler. No operating-system job or hosted scheduler was installed here. A nonzero exit indicates storage failure or retry-pending notification/provider work. Output contains counts and a safe status rather than identities, emails, credentials or raw provider errors. Alert on queued notices, failed/stalled jobs and delayed purges; `next_attempt` and lease deadlines are available in the private database for operator diagnosis. The command processes bounded batches, so high volume requires sufficient scheduling throughput.

Database tests use fresh `pdw_test_*` databases and injected fake email/provider callbacks. Do not shorten recovery dates on real accounts to test cleanup. For a manual live account test, use a specifically disposable app account and perform the account deletion and restoration actions yourself. Keep the sample workspaces/account intact unless explicitly choosing to delete them.

## Backup retention and restoration

The agreed policy remains: 30-day account recovery, then active-data deletion, then backup-copy removal within a further 30 days after actual active-data purge. The ledger records `active_purged_at` and `backup_removal_due` once; retries do not move that deadline. If provider cleanup is unavailable, private workspace data is still removed and the remaining provider subject stays in a restricted retry record until cleanup completes.

No backup service or retention settings have been selected or provisioned, and this local command cannot delete infrastructure backups. Before public release, configure and verify retention/expiration, monitor actual expiry (including failed/delayed deletion), and test restoration. Do not promise the backup deadline as operationally verified until those checks pass.

Minimal suppression markers retain owner hashes, workspace identifiers where needed, timestamps and deletion status; they do not contain budgets, notes, email or provider credentials. They prevent old request IDs from recreating deleted working records and help apply deletion decisions after a backup restore. Their final retention needs the chosen backup/restore design; this implementation does not expire them automatically.

A backup restore must preserve the current deletion ledger separately from the backup being restored, apply account and workspace suppression before reopening access, revoke restored sessions/login flows, and rerun cleanup. Account suppression markers are checked on sign-in/session use even if an older user row is restored. Workspace suppression still requires the restore procedure to apply the ledger; a hosted restore workflow is not implemented yet. Do not reopen an old database snapshot directly. These are release requirements, not a claim that restoring a database alone already enforces deletion policy.
