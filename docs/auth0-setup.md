# Email/password setup — local account milestone

Do not share account passwords, application secrets, Management API tokens, or recovery codes in chat or commit them. Fill only the ignored local configuration file. The account holder completes registration terms, password entry, email verification, and password-reset submission themselves.

## Application settings

Create a Development tenant and a **Regular Web Application** named Purchase Decision Workspace. Use the standard Auth0 database connection (`Username-Password-Authentication` unless you rename it). Enable it for this application and disable social/enterprise/passwordless connections for this application. Use email/password, with no username field required. Keep signups enabled if you want to test creating accounts. Use Auth0's hosted Universal Login.

In application Settings → Application URIs / URLs:

| Setting | Exact value |
| --- | --- |
| Allowed Callback URLs | `http://127.0.0.1:5173/api/v1/auth/callback` |
| Allowed Logout URLs | `http://127.0.0.1:5173/` |
| Allowed Web Origins | `http://127.0.0.1:5173` |

Save Changes. Use the same `127.0.0.1` hostname when opening the app; do not mix it with localhost during a login flow. The frontend forwards `/api` to FastAPI. The callback is registered on the frontend origin deliberately, so the browser uses the same origin before/after login. No wildcard callbacks, secret in frontend code, or API audience for financial data is needed.

## Account status checks

For this project’s existing tenant, the owner confirmed the read-only client currently appears as **Machine to Machine Applications**. Identify it by its Auth0 Management API grant with **read:users only**; the suggested display name below is not a requirement. The separate Workspace Cleanup app and staging API Test Application are different clients.

Create a separate **Machine to Machine Application**, named Purchase Decision Account Checks. Authorize **Auth0 Management API**, with only the **read:users** permission. Do not grant create/update/delete-user permissions. This server-only integration checks current email verification, blocked status, and last password reset before allowing private workspace operations. It does not receive budget data. It avoids needing a public webhook/tunnel for this local milestone.

This also means a provider/database outage or quota error closes private access rather than trusting stale account status. It adds provider calls to authenticated activity/session/workspace requests; quotas and a production strategy must be measured before deployment. Management access tokens are cached briefly in backend memory, not returned to the browser or saved in workspace documents.

## Local configuration

First install dependencies in a separate terminal:

```sh
cd /Users/noelmehari/Documents/Portfolio/purchase-decision-workspace
.venv/bin/python -m pip install -r backend/requirements.txt
```

Copy the configuration template once (do not overwrite an existing configuration):

```sh
cp -n backend/.env.example backend/.env
chmod 600 backend/.env
```

Open `backend/.env` in your editor and fill:

- `PDW_AUTH0_DOMAIN`: the Regular Web Application's Domain, e.g. `dev-example.us.auth0.com` — hostname only, no `https://` or slash.
- `PDW_AUTH0_CLIENT_ID`: Regular Web Application Client ID.
- `PDW_AUTH0_CLIENT_SECRET`: Regular Web Application Client Secret.
- `PDW_AUTH0_MANAGEMENT_CLIENT_ID`: Machine to Machine application's Client ID.
- `PDW_AUTH0_MANAGEMENT_CLIENT_SECRET`: Machine to Machine application's Client Secret.
- `PDW_AUTH0_CONNECTION`: your database connection name, if different from the default.

Keep the template's `PDW_AUTH_MODE=auth0`, `PDW_LOCAL_STORAGE=1`, and `PDW_APP_ORIGIN=http://127.0.0.1:5173`. The backend loads `backend/.env`; existing terminal environment variables take precedence. Neither passwords nor session-signing secrets belong in this file: user passwords stay with Auth0, and application sessions use random opaque cookies with server-side records.

With Docker/MongoDB and the frontend still running, stop/restart the backend after changing environment settings:

```sh
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Live verification with the account holder

1. Open the local app. It should offer Sign in / Create account and retain an account-free fictional demo.
2. Create a test app account using your email and a unique password on Auth0's hosted page. Complete any CAPTCHA yourself. Unverified email must not unlock persistent workspace access.
3. Verify the email in your inbox, then use “I've verified my email” or sign in again. Create/save a workspace, reload, and confirm it reopens.
4. Sign out. Private inputs, saved lists, and historical reviews must disappear immediately; saved records remain in MongoDB. Sign in again and reopen the workspace.
5. Test a second app account: it must not list/read/update the first account's workspace or reviews, even if its URL is known.
6. Request a password reset. The app's response must not reveal whether the account exists. The account holder completes the reset link/new password themselves. On the next account check, any app session authenticated before the password change must be revoked. Signing in again must work with the new password.
7. Check idle and absolute expiry using controlled test clocks in automated tests; do not wait a full day manually.

The earlier local demonstration records remain under `local-development-user`; they are never silently assigned to the first person who signs in. An explicit local-only `PDW_AUTH_MODE=local` can still reopen the previous demonstration database. New signed-in workspaces are isolated under issuer/subject-derived owners. No migration or deletion of old records occurs automatically.

## Limits before public use

This milestone is intentionally loopback-only. Cookies use HttpOnly/SameSite=Lax and development HTTP; production HTTPS, secure-cookie enforcement, deployment origin configuration, email delivery, and operational hardening are still required. Auth0's built-in email provider is for development/testing, not production email delivery. Account deletion/recovery/purge and JSON export are separate unfinished v1 work.

Sources checked November 12, 2026: [database accounts](https://dev.auth0.com/docs/connections/database), [password changes](https://auth0.com/docs/authenticate/database-connections/password-change), [application-session revocation guidance](https://auth0.com/docs/customize/actions/explore-triggers/post-change-password), [email-provider limits](https://support.auth0.com/center/s/article/Emails-to-Gmail-from-Auth0-never-arrive), [current pricing](https://auth0.com/pricing).

## Troubleshooting observed during implementation

If signup reports a generic error, check the provider logs before repeating account creation: signup may already have succeeded. Use Log in for an existing app account. The current tenant policy requires at least 15 password characters. Password changes and reset links remain with the account holder.

The backend prints only `Sign-in failed: stage=... type=... provider_status=...` on callback failures. Do not paste secrets or full logs in chat. A bad profile query caused a real HTTP 400 during integration and was corrected in the adapter; changing credentials or broadening permissions was not needed. Fresh-login password timestamps are pinned with fractional precision to avoid rejecting a just-created account.
