# Controlled staging maintenance scheduler

Status: check-only scheduling deployed and verified November 18, 2026. Render is running commit `5f6e012`; Cloudflare Worker `pdw-staging-maintenance` is enabled with the owner-approved minute trigger. No notification or cleanup mode is enabled. Backups/restore and independent testing remain separate release work.

## Hosted check evidence

- The owner privately saved the same independent signing secret in Render and an encrypted Cloudflare binding. Its value was not read or recorded. Render's non-secret flags were inspected: `PDW_MAINTENANCE_ENABLED=1`, `PDW_MAINTENANCE_MODE=check`.
- Public workers.dev and preview URLs are disabled. The production origin points to the staging Render API, with `PDW_SCHEDULE_ENABLED=1` after explicit owner activation approval. Cloudflare shows Workers Free.
- Actual scheduled runs on November 18 at 22:48:37 and 22:49:38 Pacific returned `event=pdw-maintenance`, `status=ok`, `mode=check`. The latter invocation reported `outcome=ok`, CPU time 1 ms and wall time 1,596 ms. This verifies the scheduled caller, signature acceptance and completed backend check; it is not evidence of mail delivery, account deletion or backup readiness.
- Initial scheduled attempts failed before any HTTP request because Workers rejects Fetch's `redirect: 'error'` option. The deployed source now uses `manual` and rejects non-2xx responses without following redirects. Regression coverage includes both health and signed-POST redirect responses. Safe failure diagnostics expose only a fixed phase, numeric HTTP status and a fixed cause category.
- Final verified Worker revision: `d5b030ae-58c4-4a95-aebf-ce6733704947`. Seven Node tests pass, including signing, destination restrictions, redirects, global fetch binding and sanitized failures.
- Cold-start recovery after a true Render sleep, hosted simultaneous/busy runs, independent failure alerts, SMTP delivery and backup/restore remain unverified. Local MongoDB tests cover lease contention and replay; check-only success does not refresh the full-cleanup heartbeat.

## What is prepared

The existing recovery/purge and notification worker now has a shared MongoDB lease used by both the CLI and the hosted trigger. Only one run can own it at a time; renewal and release match a random owner token. An interrupted run can be reclaimed after its 180-second lease expires. Per-notice and per-account leases remain in place. Recovery deadlines and backup-removal timestamps are not shortened or moved by retries.

`POST /api/v1/maintenance/run` is unavailable unless staging runtime and `PDW_MAINTENANCE_ENABLED=1` are both configured. It accepts server-to-server HMAC-SHA256 signatures, a timestamp within 120 seconds and a random 128-bit nonce. It rejects browser Origin headers, URL query parameters, unsigned/user-token requests and replays before doing work. Only a hash of each authenticated nonce is retained for five minutes with a TTL index. The endpoint is omitted from OpenAPI; obscurity is not its access control. The secret never belongs in frontend settings, request URLs or Git.

The server chooses its operating mode; callers cannot select a more privileged mode in a header or body:

| `PDW_MAINTENANCE_MODE` | Behavior |
| --- | --- |
| `check` (default) | Reports configuration presence and aggregate database/job diagnostics. Writes only scheduler control metadata, not user/workspace data. No SMTP, Auth0 deletion or cleanup. |
| `notify` | Processes queued deletion-notice email only. No account or workspace purges. |
| `cleanup` | Processes notices, accounts past their existing recovery deadlines, deleted-workspace children and expired transient records. Can permanently delete due data and Auth0 identities. |

HTTP runs process at most one item per phase, with a 35-second cooperative budget and a 90-second MongoDB operation context. No new item is claimed after the budget is exhausted. An in-flight network operation can overrun the cooperative budget; SMTP/HTTP operations have finite transport timeouts and a longer global lease. A timed-out caller does not bypass that lease. `partial`, failures and retry-pending results are surfaced as failed scheduler invocations. There is no claim of a hard real-time completion or deletion deadline.

Full-cleanup heartbeat remains `system_status/maintenance`. Check/notify runs use separate records, so successful probes cannot make full cleanup appear operational. Read-only readiness still reports missing/stale cleanup or overdue data. Aggregate output and fixed error messages exclude addresses, subjects, financial data, secret values and raw provider errors.

## Local database verification first

The automated regression without a test database discovered 200 tests: 164 passed and 36 MongoDB integration cases skipped. Four Node scheduler tests passed. The critical real-database lease/replay and existing lifecycle cases must also pass before enabling actual hosted processing. The coding sandbox cannot access the Docker socket.

Owner-run verification completed November 18, 2026: the command below ran all 37 selected tests against local MongoDB in 1.342 seconds, with `OK` and no skipped cases. This includes concurrent lease claims, stale-owner fencing, replay protection, lifecycle recovery/purge/retry and readiness checks. The Terminal output included a Starlette/httpx deprecation warning; it did not fail the tests. Hosted deployment and scheduled invocations remain unverified.

Start Docker Desktop, then run in your own Terminal:

```sh
cd ~/Documents/Portfolio/purchase-decision-workspace
docker compose up -d mongodb
PDW_TEST_MONGO_URI=mongodb://127.0.0.1:27017 .venv/bin/python -m unittest backend.tests.test_maintenance_trigger backend.tests.test_lifecycle backend.tests.test_readiness -v
```

These integration tests create/drop only their own random `pdw_test_*` local databases and inject fake mail/provider callbacks. They do not use Atlas, send real email or delete real Auth0 users. The two scheduler cases exercise simultaneous MongoDB lease acquisition, stale-owner fencing and the actual unique-key replay guard. No existing local workspace database is dropped. Docker may be stopped again after verification.

## First hosted rollout: check only

1. Commit/push the reviewed backend and `ops/cloudflare` changes. Manually deploy the latest commit to Render. No Pages deployment is required for this backend/scheduler change. The endpoint remains disabled by default.
2. Privately generate a new independent signing secret in your Terminal:

   ```sh
   python3 -c 'import secrets; print(secrets.token_hex(32))'
   ```

   Treat the output as a credential. Store it only as `PDW_MAINTENANCE_SECRET` in Render and as an encrypted Cloudflare Worker secret with the same name. Never paste it into chat, source code, a Worker plaintext variable, or a URL. Do not reuse MongoDB/Auth0/SMTP credentials.
3. In Render set `PDW_MAINTENANCE_MODE=check`. Enabling `PDW_MAINTENANCE_ENABLED=1` creates privileged scheduler access and requires the owner's reviewed approval. The initial approved scope must remain check-only. Save/redeploy and verify healthy startup and rejection of unsigned trigger requests.
4. Create a free Cloudflare Worker named `pdw-staging-maintenance` from [the worker source](../ops/cloudflare/maintenance-worker.mjs), using the account holder's free Workers plan. No custom domain, KV, database credentials, paid CPU setting or public run endpoint is required. The owner handles registration terms, password entry and secrets. Use [wrangler.jsonc](../ops/cloudflare/wrangler.jsonc) as the configuration reference if deploying through a CLI; deployment tooling itself is not installed or executed by these changes.
5. Set the public Worker variable `PDW_API_ORIGIN=https://purchase-decision-workspace.onrender.com`. Keep `PDW_SCHEDULE_ENABLED=0` during upload and secret setup. Add the encrypted signing secret, then the `* * * * *` cron trigger (UTC). The source also returns 404 for every ordinary HTTP request. Disable workers.dev and preview URLs when using the supplied configuration.
6. After owner approval, set `PDW_SCHEDULE_ENABLED=1`. Verify several real scheduled invocations with `status=ok, mode=check`, API probe records, cold-start behavior and global-lease busy behavior. The worker wakes Render before signing, follows no redirects, permits only a validated HTTPS Render origin and sanitizes failures. Any stale full-cleanup warnings in check mode are expected; no real processing is claimed.

The caller makes at most two outbound requests per enabled invocation: an unsigned health wake-up and one signed POST. One-minute scheduling is approximately 1,440 invocations/day, below the documented free request quota, but shared account usage still matters. Workers Free has a 10 ms CPU limit per cron invocation; real deployed CPU usage needs checking. Network waiting does not count as CPU. Cloudflare says Cron Trigger changes may take up to 15 minutes to propagate. Do not select a paid plan to resolve a failed check without explicit approval.

## Enable actual work separately

Before switching to `notify`, verify the hosted SMTP configuration/transport and recipient coverage. Auth0 verification/reset emails are independent and do not establish backend SMTP delivery. The current development sender may only send to its own provider account email, so a different disposable test recipient must not be assumed supported. Do not use deletion of the main account as an email probe. Do not enable real processing just to test the signature or cron.

Before switching to `cleanup`, verify the dedicated Auth0 deletion client's least-privilege scope, review all due/retry work, verify the disposable lifecycle test and preserve the existing recovery deadlines. Enabling this mode is an explicitly reviewed activation of irreversible scheduled work. Backups, isolated restore, suppression replay and actual backup expiry remain outstanding; they are not implemented by this scheduler.

Worker errors are visible in Cloudflare logs and API failures are redacted. Independent failure alerts and an end-to-end operator response drill are not yet configured. They remain a release requirement; logs alone are not an alerting system. The existing one-minute guidance is a scheduling target, not an availability guarantee from either free provider.

## Pause, rotate and recover

Set `PDW_SCHEDULE_ENABLED=0` to pause calls and `PDW_MAINTENANCE_ENABLED=0` to reject them at Render. A request already in progress may finish its current item; do not manually remove an active lease. Let its owner release it or its 180-second deadline expire. The owner can rotate the shared secret privately in both services while the scheduler is paused, then resume check mode before real processing. Replays are not retried with the same signature; each scheduled invocation generates a new timestamp and nonce. A restored database must invalidate app sessions/login flows, preserve/apply the current deletion ledger and clear stale scheduler control records before reopening; the isolated restore procedure is still pending.

## Official references checked November 18

- [Cloudflare Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/)
- [Workers Free limits, including CPU and network waiting](https://developers.cloudflare.com/workers/platform/limits/)
- [Encrypted Worker secrets](https://developers.cloudflare.com/workers/configuration/secrets/)
- [Render Free constraints](https://render.com/docs/free)
