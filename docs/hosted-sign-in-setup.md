# Controlled staging: GitHub Pages and Render

Status: implementation prepared for provider setup and live tests, not published or release-ready. Use fictional plans and sample financial values only. The independent usability session, scheduler, backup/restore verification and unresolved build dependency advisory remain open. See [dependency review](dependency-review-2026-11-17.md).

The existing local `.env`, Auth0 application and Docker database stay separate. Nothing in this guide requires buying a domain or upgrading a plan. Do not paste secrets into chat, commit `.env` files, or put secrets in `VITE_*` variables. No existing local records are migrated.

## 1. Create the hosted Auth0 client and API

In the existing tenant, create a **Single Page Application** named `Purchase Decision Workspace — staging`. Enable only the existing email/password database connection. Do not change the local Regular Web Application.

Set these exact URLs for the repository's current GitHub Pages address:

| Auth0 setting | Value |
| --- | --- |
| Allowed Callback URLs | `https://noelmehari2005.github.io/purchase-decision-workspace/` |
| Allowed Logout URLs | `https://noelmehari2005.github.io/purchase-decision-workspace/` |
| Allowed Web Origins | `https://noelmehari2005.github.io` |

Do not use wildcards. The Web Origin has no repository path. If the repository/account/domain changes, update these values and both deployment configurations together.

Create an Auth0 API named `Purchase Decision Workspace — staging API`, identifier `https://purchase-decision-workspace-staging-api`, using **RS256** signing. This identifier is an audience, not a website to deploy. The frontend SDK requests this audience using Authorization Code with PKCE, `openid email profile`, `prompt=login` and `max_age=0`. Leave refresh-token persistence disabled; the integration uses memory caching.

Record the tenant domain, public SPA Client ID and API identifier. These three values are public configuration; no SPA client secret belongs in the browser. Backend profile checks still need a separate `read:users` Management API client. Cleanup, when configured later, must use its separate `delete:users` client. The existing local web-client secret is not used by hosted sign-in.

## 2. Prepare separate free database and API services

Create an Atlas **Free** cluster and a database user restricted to `readWrite` on `pdw_staging`. Use a new application password, the TLS-enabled `mongodb+srv://` URI and a database name distinct from local development. Atlas credentials stay in Render environment settings. Restrict Atlas network access to Render's documented outbound ranges for the assigned service; do not default to `0.0.0.0/0`. Verify actual connectivity after provisioning. Do not enable the paid Free-cluster backup add-on.

`render.yaml` describes a Free native Python web service in Virginia, locked backend dependencies, a health check and manual deploys. The template has no MongoDB/Auth0 credentials. The API uses Render's documented `RENDER_EXTERNAL_URL` process environment when `PDW_API_ORIGIN` is unset, applying the same strict HTTPS-origin validation. This lets the first service creation use its actual assigned hostname without guessing an available name. An explicit `PDW_API_ORIGIN`, if provided, takes precedence. Use the actual assigned HTTPS origin without a path or trailing slash in the frontend settings; the template's service name is not a reservation.

For manual service creation, enter staging values individually or import only the staging public block. Do not bulk-import the local `backend/.env`, which enables local storage and uses loopback URLs. Add the Atlas URI and the existing **read:users** Management API client's ID/secret privately in Render. The SPA Client ID is not the Management API client ID. Render's outbound ranges become available on the service details page after creation; add those ranges to Atlas before exercising database-backed requests. A passing health check alone does not require or establish database connectivity.

Supply all prompted variables. `PDW_TESTER_EMAILS` is a comma-separated allowlist of verified email addresses. Start with only your own app-user email, especially while Resend's testing sender can deliver only to its account address. Staging refuses local demonstration ownership, ignores session cookies, and requires this allowlist on sign-in and subsequent private requests. The API host is restricted to `PDW_API_ORIGIN`'s hostname; CORS permits only the exact Pages origin, without credentialed cookies.

Render will run only the API. Its health check does not prove Atlas, Auth0, email or maintenance is working. A Free service may take about a minute to wake; do not expose the Vite development server as the hosted frontend.

## 3. Build the Pages frontend

Copy `frontend/.env.example` to ignored `frontend/.env.staging`, replace placeholders with the public values above, then run from `frontend`:

```sh
npm test
npm run build -- --mode staging
```

Use only the generated `frontend/dist` directory for Pages. The Vite base path is `/purchase-decision-workspace/`; the backend origin contains no path. `.github/workflows/pages-staging.yml` is a manual-only publishing workflow; it has not been run. Configure Pages to use GitHub Actions and add these **repository variables**, containing public configuration only: `PDW_API_ORIGIN`, `PDW_AUTH0_DOMAIN`, `PDW_AUTH0_SPA_CLIENT_ID`, `PDW_AUTH0_API_AUDIENCE`. The workflow validates settings, runs frontend tests and uploads only `dist`, then publishes through the `github-pages` environment. Review the unresolved dependency advisory and hosted acceptance checks before dispatching. Do not change repository visibility as part of setup without reviewing the repository's contents first.

Local `npm run dev` remains local because Vite does not load `.env.staging` in development mode. Never copy the staging example to the general frontend `.env` if you intend to keep local mode.

## Session behavior and live acceptance checks

The SDK validates the browser redirect with state/nonce and PKCE. The API separately verifies RS256 signatures, issuer, API audience, SPA audience, authorized party, matching identity and original signed `auth_time`. An ID token by itself does not authorize an API session. Refreshed access-token issue times cannot replace the original sign-in time for deletion/restoration freshness checks.

Successful bootstrap returns an opaque application token held only in memory. MongoDB stores its hash. Normal requests use `Authorization: Bearer`, plus the existing CSRF value for mutations. Idle expiry, absolute expiry, password-reset revocation and account recovery rules remain server-enforced. Provider tokens, passwords and secrets never enter URLs or application exports. Reloading or reopening the browser may require another top-level sign-in; no session is persisted in localStorage/sessionStorage.

Before inviting testers, verify in a browser with third-party cookies blocked: fresh sign-in; rejection of an unapproved/unverified identity; explicit save and reopen; imports and source confirmation; JSON export; logout; password-reset revocation; idle expiry; and explicit account restoration with a new normal session. Exercise destructive recovery only with a disposable account under the documented recovery policy, never by shortening a real account's deadline. Verify Pages path handling after callbacks and workspace deletion.

The current automated tests cover signed token rejection, origin/allowlist gates, cookie exclusion, bootstrap response privacy and preservation of local behavior. They use controlled providers; no live hosted login or database connection is claimed.

## Email and remaining operations

Render Free blocks standard SMTP ports 25/465/587. The transport now also supports Resend's documented implicit-TLS port **2465**, retaining certificate/hostname checks. This must be connectivity-tested from Render; local delivery on 465 does not prove hosted delivery. The Pages base path is included in hosted deletion notices. Keep local settings unchanged; use separate Render settings. Do not claim arbitrary-recipient delivery while using Resend's test sender.

No Cloudflare scheduler, privileged maintenance endpoint, B2 bucket, encrypted archive or restore drill has been created by this sign-in implementation. Prepare and verify those pieces next. Do not advertise production deletion/backup guarantees until the scheduler and retention controls are operationally verified.

References: [Auth0 React SDK](https://auth0.com/docs/libraries/auth0-react), [JWT signature and claims validation](https://jose.authlib.org/en/guide/jwt/), [Vite Pages paths](https://vite.dev/guide/static-deploy.html#github-pages), [Render configuration](https://render.com/docs/blueprint-spec), [Render Free constraints](https://render.com/docs/free), [Resend SMTP TLS ports](https://resend.com/docs/send-with-smtp).
