# Daily encrypted staging backups: deployment preparation

Status, November 20, 2026: prepared locally, disabled by default, not deployed or activated. One manual staging upload and isolated downloaded restore passed; scheduled backup operation and its independent alert remain unverified. Existing account-maintenance scheduling remains check-only and unchanged. The fictional retention probe is still present (one upload version, no hide markers); its faster lifecycle rule is saved, but expiration has not yet occurred.

## Prepared behavior

- A separate cron-only Worker, `pdw-staging-backups`, calls `POST /api/v1/backups/run` once daily using an independent HMAC signing secret. Proposed cron `0 3 * * *` means 03:00 UTC daily. Its public handler always returns 404, workers.dev/previews are disabled, and its default schedule flag is 0. It is distinct from the existing minute-by-minute maintenance Worker.
- The API rejects disabled/local, unsigned, browser-origin, stale and replayed calls before backup work. Signatures bind the exact backup path. Its signing secret must differ from both the encryption key and maintenance signing secret. Request bodies cannot select a mode or change the source/target.
- A fenced `backup` lease serializes uploads. A unique UTC-date status record is inserted before capture/upload, so concurrent and repeated calls cannot upload twice that day. A failure or ambiguous upload is not automatically retried on the same date; inspect private status/B2 before deciding how to recover it. The lease is separate from account maintenance, and release is owner-fenced.
- Source capture uses the dedicated read-only staging principal and verified snapshot-session mechanism. Only the four allowlisted collections are encrypted with the saved recovery key. B2 writer authorization requires the exact bucket/prefix and only `listBuckets`/`writeFiles`. No source data is changed. There is no restore, email or deletion code in the job.
- Private `system_status/backup_run_YYYY-MM-DD` records contain attempt times, safe phase/status, encrypted object name/size/fingerprint and writer-expiry diagnostics. They do not contain archive bodies, identities, passwords, tokens or the encryption key. Transport errors never return raw provider messages.
- Only a fresh acknowledged upload with a writer key valid for at least 14 more days yields a healthy result. Busy, duplicate, disabled, failed and rotation-needed results cannot send a backup heartbeat. Near-expiry uploads continue, but the independent monitor is intentionally not refreshed so the operator can rotate the credential.
- The new Worker requires a distinct Healthchecks ping URL before it attempts any upload. It sends only an empty completion POST to the validated hc-ping.com URL, never app records or credentials. Proposed monitor: `PDW staging daily backups`, period 24 hours, grace 2 hours, owner email alerts. The existing minute scheduler monitor must not be reused for this signal.

The Worker wakes Render before signing. Health wake timeout is 75 seconds, backup request timeout 150 seconds, and monitor timeout 10 seconds. These are transport bounds, not proof of successful operation on the free instance; verify actual runtime/CPU/memory after deployment. Source capture has a 35-second operation budget and the 32-MiB archive ceiling. It is an in-memory small-staging implementation, not a streaming full-cluster backup.

## Required configuration (not entered yet)

Keep all newly added backup enable flags at **0** until the deployment and monitor are reviewed. Preserve unrelated environment settings, including `PDW_MAINTENANCE_MODE=check`.

Render:

| Variable | Value |
| --- | --- |
| `PDW_BACKUP_ENABLED` | `0` during preparation |
| `PDW_BACKUP_ENCRYPTION_KEY` | Saved 64-character recovery key, entered privately |
| `PDW_BACKUP_MONGO_PASSWORD` | Original password for `pdw_staging_backup`, not an encoded URI |
| `PDW_BACKUP_WRITER_KEY_ID` | Custom `pdw-staging-archive-writer` keyID |
| `PDW_BACKUP_WRITER_APPLICATION_KEY` | That writer's full applicationKey |
| `PDW_BACKUP_SIGNING_SECRET` | New separate 64-character random hex secret |

Do not install the B2 Master credential in Render. The reader key is not needed by this upload-only job. All secret entry/save steps are owner actions; never paste values into chat or repository files. The owner should preserve the new signing secret separately in their password manager when generating it, then enter the identical signing value in Render and the new Worker.

New Cloudflare Worker only:

| Variable | Value |
| --- | --- |
| `PDW_API_ORIGIN` | `https://purchase-decision-workspace.onrender.com` |
| `PDW_BACKUP_SCHEDULE_ENABLED` | `0` until activation approval |
| `PDW_BACKUP_SIGNING_SECRET` | Encrypted secret, same independent signing value as Render |
| `PDW_BACKUP_MONITOR_PING_URL` | Encrypted secret copied privately from the new daily monitor |

Source/config: `ops/cloudflare/backup-worker.mjs`, `ops/cloudflare/wrangler.backup.jsonc`. No worker, monitor or hosted credential has been provisioned as part of local preparation. No Render/frontend deployment has happened for these changes.

## Checks and activation sequence

Local Python checks cover job configuration, claims, busy/repeated attempts, safe failures, lease release, writer expiry, replay protection, exact route signatures, independent flags/secrets and rejection of secret reuse. Existing maintenance checks continue to pass. All 18 Worker tests pass, including the 12 existing maintenance tests and six new backup tests. The owner ran the following command on November 20: all 26 tests passed in 0.349 seconds, with no skips, including the real MongoDB backup concurrency, scheduler lease and replay-guard cases:

```sh
cd ~/Documents/Portfolio/purchase-decision-workspace
docker compose up -d mongodb
PDW_TEST_MONGO_URI=mongodb://127.0.0.1:27017 .venv/bin/python -m unittest backend.tests.test_backup_job backend.tests.test_maintenance_trigger -v
```

It creates only random disposable local fixtures, with fake capture/upload calls. It does not use Atlas or real credentials. Docker can now stop. The observed result proves one upload under simultaneous callers, no same-day automatic retry, and preserved lease/replay guards. Remaining rollout: commit/push reviewed backup changes; deploy backend with backup disabled; provision the separate daily monitor and Worker with scheduling disabled; have the owner enter/save secrets privately; review the concrete activation; then enable the backup API and schedule with required browser confirmation. Verify an actual newly created archive, successful independent ping, expected next-run timing and a later isolated restore. Configuration alone is not operational verification.

## Remaining recovery and retention requirements

The current restore drill obtains fresh deletion controls from live Atlas. Independent durable control preservation remains unfinished, so recovery from complete Atlas loss is not proven. All restores remain quarantined and fail closed without fresh matching controls; this job does not enable automatic recovery or reopen app access.

The archive lifecycle rule and accelerated fictional probe are documented in [backup-restore-setup.md](backup-restore-setup.md). The upload heartbeat does not audit actual expiration or every archive version; retention and overdue-version alerts still need separate verification. The 90-day writer key needs rotation before expiry, with corresponding monitor verification. These remaining items must not be reported as complete when daily uploads first work.
