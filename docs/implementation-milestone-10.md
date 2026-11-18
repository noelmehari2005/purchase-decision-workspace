# Milestone 10 — controlled hosted test preparation

Status: in progress; not published, not production-ready. Free services only. The owner prefers GitHub Pages, selected controlled sign-in/sample workspaces and deferred independent usability testing.

## Implemented

- Explicit local/staging runtime. Staging requires HTTPS origins, a separate named TLS-enabled Atlas SRV connection, Auth0 SPA/API configuration and verified tester email allowlisting. It cannot enable local demo ownership. Local defaults remain available.
- Official Auth0 React SDK with Authorization Code/PKCE and memory caching. API bootstrap separately validates RS256 signatures, fixed-issuer JWKS, API/SPA audiences, authorized party, matching subjects and original signed authentication time. Only an opaque application session token is returned, kept in browser memory and hashed in MongoDB. Normal private requests retain server-owned identity, expiry, password-reset revocation and CSRF checks. Cookie authentication is ignored in staging.
- Exact-origin noncredentialed CORS, trusted API host, backend origin configuration for calculations/storage/imports/exports, Pages base paths, hosted restoration-token replacement and repository-path preservation after workspace deletion. A visible staging notice requests sample data only; this is usage guidance, not automatic detection of personal data.
- Render Free native-Python template and manual-only GitHub Pages publishing workflow, with public configuration separated from server secrets. No service, workflow, visibility change or public deployment has been executed.
- Resend's documented implicit-TLS alternate port 2465 is supported with certificate/hostname checks retained. Hosted notification links include the Pages path. Port connectivity and hosted delivery remain unverified.

## Evidence

- Backend regression: 182 tests discovered, 148 passed, 34 opt-in database integration tests skipped in the restricted session. Includes new signed-token/allowlist/origin/bootstrap privacy checks and alternate SMTP TLS test; no real provider calls or deletion.
- Frontend: 29 tests passed. Local and staging compilation/builds passed. A staging build with synthetic public configuration produced repository-prefixed asset URLs.
- Browser read-only observation: the local app remained signed in with its private workspace controls and needs form visible after these changes. No Save, export or deletion action was taken during that check.
- Owner created the separate staging Auth0 SPA; its URL/connection settings and public client configuration are the next handoff. No secrets were requested in chat.

## Outstanding

Auth0 custom API and hosted client settings; Atlas/Render setup; live cross-origin browser tests with third-party cookies blocked; hosted email check; Cloudflare scheduler plus bounded, protected/leased maintenance; encrypted B2 backups, deletion-ledger replay and isolated restore/expiration checks; independent usability and remaining release evidence. The picomatch advisory remains unresolved and documented in [dependency review](dependency-review-2026-11-17.md). Provider free-tier limits and account requirements must be rechecked during provisioning. No paid upgrade is authorized.

See [hosted setup](hosted-sign-in-setup.md) for exact URLs and operator steps.

## Hosted client setup follow-up

The owner supplied the new SPA’s public tenant domain and Client ID after completing the URL/connection setup step. These public values were added to ignored `frontend/.env.staging`; no client secret was requested or written. The API origin is still unset until Render provisioning. The custom Auth0 API identifier is prepared in the frontend configuration but must still be created/confirmed in Auth0. No provider token, live hosted login or public deployment has been verified.

The owner confirmed creation of the custom staging Auth0 API using the requested identifier and RS256. Application/API registration is now owner-confirmed; token issuance and hosted sign-in remain unverified. Next is a separate Atlas Free project/cluster and restricted database user, followed by Render outbound-range setup. No cloud database, credentials, network grants or paid service were created by this confirmation.

## Manual Render setup follow-up

The owner supplied screenshots of the manual Render form: the correct repository/main/Python/Free plan, blank environment settings and default commands. Corrected command/root-directory/health-check instructions were supplied, and the owner confirmed applying them. The template now explicitly selects Virginia to match Atlas. First service creation may use Render’s assigned RENDER_EXTERNAL_URL when PDW_API_ORIGIN is absent; both sources receive the same HTTPS-origin validation, with explicit configuration taking precedence. Direct runtime checks passed for the Render-assigned origin, explicit-origin precedence and invalid-origin rejection. The broader targeted test rerun is delayed by cloud-only dependency/package files (dataless flags observed), so it is not recorded as passing. Environment entry, GitHub push, service creation and live verification are still pending.

## Final local checks before GitHub push

After the owner downloaded the offloaded files again, the backend regression discovered 183 tests: 149 passed and 34 opt-in MongoDB integration cases were skipped. All 29 frontend tests and the production build passed. Staged credential-pattern review found only the synthetic placeholder MongoDB URI in a test fixture; real backend/.env and frontend/.env.staging remain ignored and excluded. The owner reported entering the Render environment values; those secrets were not shared or inspected. The read-only M2M client display name was confirmed as Machine to Machine Applications, with read:users. Hosted deployment, Atlas network access and live hosted verification remain pending.
