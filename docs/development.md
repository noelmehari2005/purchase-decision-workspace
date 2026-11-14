# Local development

## What runs today

The React/TypeScript manual decision workspace uses Python/FastAPI evaluation and optional MongoDB persistence. You can explicitly save/open workspaces and retain read-only historical reviews. Unsaved changes are lost on reload. Auth0 email/password accounts and the core private save/sign-out/re-login journey are implemented and verified locally; use the [account setup guide](auth0-setup.md) for configuration and broader verification. Live imports, JSON export, and deployment remain unfinished. Use fictional data until the full account milestone is verified. Product source links are references only.

Docker Desktop is needed for the provided MongoDB setup. Icecat credentials are not needed. Auth0 credentials are needed only for private account mode. You can leave storage disabled and use only the manual evaluator without Docker.

## Setup

Verified on macOS with Python 3.14.1, Node 24.15.0, and npm 11.12.1. Use Node 24 LTS; the frontend requires at least Node 22.18 for its native TypeScript test support. Python 3.12+ is the intended baseline; only 3.14.1 was tested in this change.

From a fresh checkout:

```sh
cd /Users/noelmehari/Documents/Portfolio/purchase-decision-workspace
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock.txt
cd frontend
npm ci
```

The Python lock records the installed and tested dependency versions, including Authlib and python-dotenv. `backend/requirements.txt` records direct dependency ranges. The npm lock records frontend dependency versions. Refresh locks intentionally and rerun checks when updating dependencies. Do not commit virtual environments, node_modules, credentials, or environment files.

## Start the app

Start MongoDB once from the repository root, with Docker Desktop open:

```sh
docker compose up -d mongodb
```

For the previous single-user demonstration without Auth0, keep the backend running in one terminal using the explicit local mode below. For private accounts, follow the Auth0 setup guide and use `PDW_AUTH_MODE=auth0` in the ignored backend configuration instead:

```sh
cd /Users/noelmehari/Documents/Portfolio/purchase-decision-workspace
PDW_AUTH_MODE=local PDW_LOCAL_STORAGE=1 .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Keep the frontend running in a second terminal:

```sh
cd /Users/noelmehari/Documents/Portfolio/purchase-decision-workspace/frontend
npm run dev
```

Open [the local workspace](http://127.0.0.1:5173). The frontend forwards `/api` requests to port 8000. Backend API documentation is at [the local API docs](http://127.0.0.1:8000/docs). These are loopback development servers, not a public deployment setup. Stop each with Control-C when finished. `docker compose stop mongodb` stops the database while retaining its named volume. Do not remove the volume if you want to retain saved workspaces.

If a port is already in use, reuse the existing project server or stop it in its own terminal. Vite fails rather than silently switching ports. If calculations fail, check the backend terminal and use the on-screen retry button; inputs remain in the current tab.

## Try Alex's example

1. Review the programming tasks, explicit mandatory requirements, and preferences. Tasks do not generate hardware rules.
2. Confirm the current laptop, leaving uncertain fields unknown.
3. Review Candidate A. For this fictional demonstration, select evidence of required-tool compatibility, then confirm it. Confirm Candidate B with compatibility unknown to see known price failure take precedence over missing evidence.
4. Open Compare & plan. Candidate A costs $800, with $300 savings and $150 monthly contributions: four contributions, finishing April 30, 2027.
5. Enable the optional budget and spending-change scenario. A $40 transportation reduction allocated toward the purchase produces a separate $190 contribution plan: three contributions, finishing March 31. The original remains four. Candidate B's corresponding counts are six and five.
6. Edit a candidate without confirming: comparison continues to use its last confirmed revision. Confirm the revision to apply it.
7. Use Save workspace / Save changes above the flow to persist your inputs. Reopening its URL after reload restores the saved revision. Unconfirmed candidate drafts are saved too, but comparisons still use confirmed revisions.
8. Open Decision history and choose Save review to history. This captures server-evaluated inputs/results for the saved revision. Change and save your working contribution, then reopen the older review: its original numbers remain unchanged.
9. The separate in-tab preview under Your decision is temporary. Use Decision history for durable reviews. A stale save from another tab reports a conflict; save a separate copy or explicitly reopen the saved version instead of overwriting it silently.

A selection claiming compatibility is the user's recorded evidence, not independent validation. The sample products and budget are fictional. The UI does not diagnose slowdowns or infer CPU performance.

## Verify changes

From the repository root:

```sh
.venv/bin/python -m unittest discover -s backend/tests -v
```

From `frontend`:

```sh
npm test
npm run build
```

For real MongoDB integration checks (database must be running):

```sh
PDW_TEST_MONGO_URI=mongodb://127.0.0.1:27017 .venv/bin/python -m unittest backend.tests.test_storage.MongoStorageTests -v
```

Run this from the repository root. Tests create and remove only fresh databases named `pdw_test_<random UUID>`, leaving application data intact. Normal discovery skips real-database tests when this environment variable is absent.

The frontend tests exercise money parsing, unknown values, candidate confirmation payloads, source-link validation, and scenario separation. Backend tests exercise calendar/cost rules, eligibility, budget/scenario behavior, and the actual ASGI request/response contract without opening a server port. The production build includes TypeScript checking. `npm run preview` previews a build but does not provide the development API proxy; use `npm run dev` for the integrated local journey.

The installed Starlette emits a TestClient/httpx deprecation warning. Tests currently pass; review migration to its replacement test client when updating dependencies. This is not a suppressed failure.

## Code map and extension points

- `backend/app/domain.py`: pure arithmetic, anchored calendar dates, eligibility, preference evidence, and version identifiers. No provider, database, browser, or clock dependencies.
- `backend/app/schemas.py`: validated HTTP input/output models. Monetary inputs are strict integer cents; unknown optional fields are null.
- `backend/app/main.py`: versioned health/evaluation routes and API error handling.
- `backend/app/workspaces.py`: bounded workspace schemas, confirmation-revision rules, and authoritative snapshot creation.
- `backend/app/repositories.py`: MongoDB reads, atomic expected-revision updates, and immutable snapshot inserts.
- `backend/app/storage_api.py`: explicit storage/export/deletion routes with server-derived account ownership and an isolated local demonstration mode.
- `frontend/src/WorkspaceStorage.tsx`: explicit saves/opening, conflict messages, and historical review display.
- `frontend/src/model.ts`: typed form state, exact decimal-to-cents conversion, and confirmed-revision payload preparation.
- `frontend/src/api.ts`: evaluation transport, errors, and cancellation.
- `frontend/src/components.tsx`: candidate review and plan display.
- `frontend/src/App.tsx`: the five-step in-memory journey and stale-result/review handling.

Change rules behind these boundaries and increment model versions when behavior changes. Future adapters and storage changes belong behind these boundaries without moving financial arithmetic into components. Evaluation requests contain selected calculation inputs; explicit workspace saves additionally send the bounded full working state, including drafts, notes, and source references, to the local database. No credentials are embedded. Account mode loads the ignored `backend/.env`; never commit that file or share its values in chat. Storage is disabled unless `PDW_LOCAL_STORAGE=1`; optional backend settings are `PDW_MONGO_URI` (default `mongodb://127.0.0.1:27017`) and `PDW_MONGO_DATABASE` (default `purchase_decision_workspace`). Do not point this local development setup at a shared or production database.

## Account verification checks

After installing the current backend requirements, run all local checks as above. The signed OIDC fixture tests use Authlib and mock only provider HTTP responses; no account credentials are needed for them. To run real MongoDB ownership/session checks in fresh test databases:

```sh
PDW_TEST_MONGO_URI=mongodb://127.0.0.1:27017 .venv/bin/python -m unittest backend.tests.test_storage.MongoStorageTests backend.tests.test_auth_mongo.MongoAccountTests -v
```

Live provider signup, verification, and password reset require the account holder and are recorded separately from automated fixtures.


## Read-only readiness checks

```sh
.venv/bin/python -m backend.app.readiness
.venv/bin/python -m backend.app.readiness --check-database
```

The first command inspects configuration presence/shape only. The optional database check pings MongoDB and reads the maintenance heartbeat and overdue-work counts. It never sends mail, calls Auth0/Icecat, runs cleanup, or changes records/indexes. Output excludes secret values, identities, budgets and connection strings. `configured_unverified` means the command did not exercise the external service; dated milestone reports record prior live checks separately.

Exit 1 means missing/invalid local configuration, unavailable database, or maintenance attention is required. Exit 0 means those requested local checks passed; it is not permission to deploy. `release_ready` remains false while the documented release blockers exist. SMTP/deletion-client missing statuses are expected before following the [setup guide](deletion-and-email-setup.md).

The maintenance command records a bounded singleton heartbeat (run ID, progress phase and timestamps/status). Notification and account-cleanup progress refresh it; no user-specific content is stored there. Diagnostics flag a running job without progress for five minutes and a last completed job older than three minutes. These thresholds are operator signals, not proof a process is dead or that a scheduler is installed. A failed database write can leave a heartbeat stale; check the scheduler and storage before rerunning destructive maintenance.

Dependency advisory scans require registry access. Audit the locked Python dependencies in an isolated tool environment using [pip-audit](https://pypi.org/project/pip-audit/) and run `npm audit` in the frontend. Review findings and compatible updates; do not treat a network failure or an uninstalled audit tool as a clean audit.
