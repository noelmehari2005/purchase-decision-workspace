# Free deployment proposal — November 17, 2026

Status: proposal for a test deployment, not a selected/provisioned service or public production release. The owner requires free services only and has deferred the independent usability session. No service account, paid subscription, domain, public database or scheduled cleanup job has been created by this proposal.

Implementation update — November 17: the owner approved the GitHub Pages / Render Free / Atlas Free direction, with Cloudflare-triggered maintenance and B2 backup preparation still pending. Hosted sign-in, exact-origin/bearer-session transport, tester allowlisting, Pages base paths, a manual publishing workflow and Render template are now implemented for controlled testing. The owner has created the separate Auth0 SPA; URL/client/API configuration and live hosted verification are in progress. Follow [the concrete setup guide](hosted-sign-in-setup.md). The proposal text below records the earlier alternatives and must not be read as evidence of provisioned infrastructure or completed backup/scheduler work.

## Latest hosting preference

The owner selected a controlled test deployment with sign-in and saved sample workspaces, then suggested GitHub Pages as the preferred host. Pages can serve the React build, but cannot run FastAPI, MongoDB or the maintenance process. A Pages frontend therefore still needs a separate hosted Python API, Atlas database and worker strategy. It does not replace the services in the table below.

The current frontend uses relative `/api` URLs and same-origin cookies, including the export and account-recovery flows. With a `github.io` frontend and a separately hosted API, configuring Vite's repository base path is necessary but insufficient: all API/auth links, exact CORS/origin policy and session transport need a design and tests. Cross-site cookies can be blocked by browsers even when SameSite=None and Secure are set. Do not claim this split deployment is ready merely because the static build uploads to Pages. One-origin hosting remains the simpler alternative for the existing session design; the owner's Pages preference should be discussed before selecting the final topology.

References: [GitHub Pages is static hosting](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [Vite Pages deployment/base path](https://vite.dev/guide/static-deploy.html#github-pages), and [browser cookie behavior](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Cookies).

## Proposed starting point

| Component | Free option to evaluate | Constraint to verify |
| --- | --- | --- |
| Web app | One Render Free web service serving the built React assets and FastAPI under one HTTPS origin | Sleeps on inactivity, can take about a minute to wake, ephemeral disk, shared usage limits; not always-on hosting. |
| Database | MongoDB Atlas Free cluster, separate from local Docker data | Restricted network access, TLS and a database-specific application user; no broad internet allowlist by default. |
| Email | Existing Resend free account | The testing sender is limited to its account email; public recipients require a verified sender domain. Current SMTP port 465 is blocked on Render Free. Resend supports implicit TLS on 2465 too; this option needs explicit TLS-mode handling and a hosted connectivity test before adoption. HTTPS API is another adapter option if needed. |
| Authentication | Existing Auth0 email/password integration, with a separate hosted application configuration | Exact HTTPS callback/logout/origin settings; secure cookies, host/origin enforcement and private-account restrictions. Retain local configuration separately. |
| Maintenance | Evaluate a free external scheduler separately | A sleeping web process is not a scheduler. Do not claim reliable recurring cleanup from the successful local one-shot run. GitHub scheduled workflows may be delayed/dropped and do not meet the current one-minute operator guidance unchanged. |
| Backups | Provider-independent encrypted exports and isolated restore preparation | Atlas's optional Free-cluster snapshot service is paid/private-preview. A free database does not establish a verified free backup/retention service. Select storage, access, expiration and monitoring before retaining hosted personal data under a production promise. |

The recommended initial scope is a test deployment using fictional/sample data. The owner needs to decide whether this should initially be a public demo without private account storage, or a controlled account-enabled staging environment. The Resend testing-domain restriction means email delivery to arbitrary testers is not ready. Buying a custom domain is not part of the free-only plan.

## Additional free candidates researched

- **Cloudflare Workers Free Cron Trigger:** a small scheduled worker could call an authenticated, bounded maintenance endpoint on the Python backend. It would trigger the existing Python work, not run the Python application itself. Free Workers have CPU/request limits; network wait is separate from CPU time. We must implement overlap control, timeout/failure handling, monitoring and secret storage, and verify cold-start behavior. No endpoint or scheduler exists yet. References: [cron triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/), [limits](https://developers.cloudflare.com/workers/platform/limits/).
- **cron-job.org:** free minute-level HTTP scheduling is another option, but its documented 30-second timeout conflicts with Render cold starts/long batches, and its FAQ says its fetches do not check TLS certificates. It is not the preferred caller for a privileged maintenance endpoint without resolving that security/timeout design. [FAQ](https://cron-job.org/en/faq/).
- **Backblaze B2:** its first 10 GB of object storage is free, making a private bucket a candidate for encrypted MongoDB archives. Storage, request and download allowances/caps must all be checked; avoid enabling billable overages. B2 is backup storage, not a MongoDB backup engine: generation, scheduling, consistent captures, isolated restores, separate suppression-ledger preservation and verified expiration still need implementation. Lifecycle rules can hide and delete older file versions; retention must remove the underlying versions, not merely hide objects. References: [pricing](https://www.backblaze.com/cloud-storage/pricing), [caps](https://www.backblaze.com/docs/cloud-storage-data-caps-and-alerts), [lifecycle rules](https://www.backblaze.com/docs/cloud-storage-lifecycle-rules).
- **Local encrypted archives:** suitable for initial sample-data restore exercises at no additional service cost, but dependent on the owner's computer and not a verified unattended off-site backup service.

The leading candidate combination for the requested controlled sample-data deployment is GitHub Pages + Render Free + Atlas Free + a Cloudflare scheduling trigger + private B2 encrypted backup storage. It remains a proposal, not an implemented, tested or selected production system. The Pages/API authentication design and free-tier constraints remain explicit gates.

## Shared code preparation

1. Package a reproducible build: Node builds the frontend; the Python runtime serves API routes and built frontend assets. Keep unknown API routes as API errors rather than returning the SPA HTML. No environment files or credentials in build context/image.
2. Replace loopback-only assumptions with an explicit opt-in hosted configuration. Validate one canonical HTTPS origin, derive allowed host names, preserve local defaults and CSRF/account isolation, configure secure cookies and trusted proxy handling for the selected platform. Merely binding to 0.0.0.0 is insufficient.
3. Keep hosted/local data and credentials separate. Do not upload the current local database or copy all development credentials into a public service. Decide the test-account restrictions before exposing private routes.
4. Support cold starts without misreporting a sign-in failure. Verify login/reset/logout/cookie expiry on the hosted origin before enabling private persistence.
5. Verify maintenance scheduling, worker overlap/failure detection and operator alerts. Do not expose an unauthenticated web endpoint that runs deletion jobs, and do not enable recurring real cleanup merely by deploying the web app.
6. Implement and exercise isolated backup restoration: preserve the current deletion ledger separately, apply account/workspace suppression before access, revoke restored sessions/login flows, and check actual copy expiration against the agreed retention policy. Define suppression-marker retention from this design.

## Release gates

- Independent usability feedback remains pending; signed-in import VoiceOver and local manual checks have their own dated evidence.
- The proposed free environment is staging/demo until hosted security, recurring jobs, live email scope, backups/restore and actual expiration are verified.
- The 30-day recovery cutoff remains enforced by server timestamps. Job delays must not reopen recovery or move a recorded backup-removal deadline.
- No production data migration, paid upgrade, DNS change, new security grant or public release is authorized solely by this proposal. Prepare the concrete deployment settings and review the resulting scope before activating services.

## Official references checked

- [Render Free service limits](https://render.com/docs/free): sleeping, ephemeral files, usage and SMTP-port restrictions.
- [MongoDB Atlas Free limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/).
- [Atlas Free-cluster backups](https://www.mongodb.com/docs/atlas/backup/cloud-backup/free-cluster-backup/): optional paid private-preview snapshots; availability cannot be assumed.
- [Resend SMTP](https://resend.com/docs/send-with-smtp): standard and alternate SMTP/TLS ports.
- [Resend testing-domain restrictions](https://resend.com/docs/knowledge-base/403-error-resend-dev-domain).
- [GitHub schedule event](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule): timing/availability limits.

Pricing, free limits and preview availability must be rechecked when provisioning. Free-tier billing eligibility and optional paid features must remain explicit; a provider account does not authorize an upgrade.
