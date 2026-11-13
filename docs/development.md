# Local development

## What runs today

The React/TypeScript manual decision workspace uses Python/FastAPI evaluation and optional MongoDB persistence. You can explicitly save/open workspaces and retain read-only historical reviews. Unsaved changes are lost on reload. Accounts, live imports, JSON export, and deployment are not implemented. Use fictional inputs: saved data belongs to a single local development owner without account protection. Product source links are references only.

Docker Desktop is needed for the provided MongoDB setup. No Icecat or identity-provider credentials are needed. You can leave storage disabled and use only the manual evaluator without Docker.

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

The Python lock records the versions actually tested; `backend/requirements.txt` records direct dependency ranges. The npm lock records frontend dependency versions. Refresh locks intentionally and rerun checks when updating dependencies. Do not commit virtual environments, node_modules, credentials, or environment files.

## Start the app

Start MongoDB once from the repository root, with Docker Desktop open:

```sh
docker compose up -d mongodb
```

Keep the backend running in one terminal:

```sh
cd /Users/noelmehari/Documents/Portfolio/purchase-decision-workspace
PDW_LOCAL_STORAGE=1 .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
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
- `backend/app/storage_api.py`: opt-in local storage routes and server-owned development identity.
- `frontend/src/WorkspaceStorage.tsx`: explicit saves/opening, conflict messages, and historical review display.
- `frontend/src/model.ts`: typed form state, exact decimal-to-cents conversion, and confirmed-revision payload preparation.
- `frontend/src/api.ts`: evaluation transport, errors, and cancellation.
- `frontend/src/components.tsx`: candidate review and plan display.
- `frontend/src/App.tsx`: the five-step in-memory journey and stale-result/review handling.

Change rules behind these boundaries and increment model versions when behavior changes. Later milestones can add persistence and import adapters without moving financial arithmetic into components. Evaluation requests contain selected calculation inputs; explicit workspace saves additionally send the bounded full working state, including drafts, notes, and source references, to the local database. No credentials are embedded. Storage is disabled unless `PDW_LOCAL_STORAGE=1`; optional backend settings are `PDW_MONGO_URI` (default `mongodb://127.0.0.1:27017`) and `PDW_MONGO_DATABASE` (default `purchase_decision_workspace`). Do not point this local development setup at a shared or production database.
