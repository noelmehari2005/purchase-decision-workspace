# Milestone 11 — hosted refresh session continuity

Status: implementation and automated checks complete, November 18, 2026. Not yet published or verified in the hosted browser. Free services only; controlled staging with fictional data remains the deployment scope.

## Owner-confirmed hosted results

After correcting the MongoDB URI's password encoding privately and redeploying, the owner confirmed hosted sign-in. Adding the Icecat server configuration enabled imports. The owner saved a workspace, refreshed, signed back in and reopened the saved workspace: persistence works. Refreshing currently loses the browser's in-memory app credential and requires login; it does not delete the saved workspace.

## Change

Retain only the opaque 256-bit application credential in this tab's `sessionStorage`, keyed by the full deployment identity. Auth0 access/ID tokens stay in SDK memory. A refresh restores the existing app credential and lets AuthShell validate `/auth/session` before any private workspace renders. It skips provider bootstrap for that existing session, including when third-party cookies prevent the SDK's silent check. It does not issue a new session, update activity or alter the original authentication, idle or absolute timestamps. New sign-in and provider callbacks discard an earlier stored credential. All existing `setBearer(null)` paths now clear it, including sign-out, expiry, session rejection, account closure and failed account checks. Blocked/quota-limited storage falls back without breaking memory-only sign-in; a failed replacement discards the older credential.

The storage key prevents accidental cross-deployment use, not access by malicious same-origin scripts. Compared with memory-only storage this extends the credential's exposure to XSS and to browser-restored tabs. Other projects on the same GitHub Pages hostname share the origin. The staging guide records this limitation, shared-device sign-out guidance and a dedicated-origin/HttpOnly-cookie direction for wider release. No backend lifetime, credential-revocation, deletion freshness or CSRF protections are relaxed.

## Remaining hosted acceptance

Validation: all 35 frontend tests pass, including same-tab credential restoration, sign-out clearing, provider callback identity separation, deployment key separation, malformed/provider-token rejection and restricted/full storage fallback. TypeScript and the staging production build pass. `git diff --check` passes. No backend behavior or dependency versions changed. A temporary fictional browser harness could not start because the execution sandbox denied binding a local server (`EPERM`); its files were removed. Browser refresh/logout acceptance remains pending on the hosted build; automated checks are not a claim of a live Auth0 test.

After Pages publication: sign in once with the updated build, save a fictional workspace, refresh and reopen without another login. Verify sign-out followed by refresh stays signed out; expired/revoked sessions require fresh login; password-reset revocation and account recovery still hold. Check in a browser with third-party cookies blocked. Closing/reopening or restoring a tab is subject to browser behavior and server-enforced expiry, not a promise of persistent login. Unsaved workspace edits are still not preserved by refresh.

Other work remains: hosted email/account checks, bounded protected scheduled maintenance and queued notifications, encrypted backups/deletion replay/restore/expiry verification, independent usability, and the unresolved dependency review. This milestone does not certify production readiness.
