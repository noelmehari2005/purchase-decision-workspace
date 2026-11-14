# Purchase Decision Workspace

A purchase decision and planning application, beginning with laptops for programming. Help users assess their current laptop, compare replacements against their needs, and explore a purchase plan they control.

**Status: local implementation, milestones 1–4.** React/TypeScript and Python/FastAPI support the fictional/manual laptop journey, comparison, and savings plans. MongoDB now stores working decisions and immutable historical reviews. Auth0 email/password accounts, verified owner access, session handling, and the local save/sign-out/re-login journey are now verified; see the [account setup guide](docs/auth0-setup.md) and [milestone 3 evidence](docs/implementation-milestone-3.md). Reviewed Icecat imports now support links, IDs, and exact brand/part-number lookup; see [milestone 4](docs/implementation-milestone-4.md) for configuration and limits. Export and deployment remain pending; version 1 is still in progress.

Start with the [local development guide](docs/development.md), then review [milestone 1 evidence](docs/implementation-evidence.md) and [saved-workspace evidence and limitations](docs/implementation-milestone-2.md).

## Design package

Read in this order:

1. [Product brief and Alex's journey](docs/product.md)
2. [Requirements and acceptance criteria](docs/requirements.md)
3. [Architecture and change scenarios](docs/architecture.md)
4. [Data model and API contract draft](docs/data-and-api.md)
5. [Calculation rules and account lifecycle](docs/calculations-and-lifecycle.md)
6. [Verification and traceability](docs/verification.md)
7. [Decision log and future backlog](docs/decisions-and-backlog.md)
8. [Research evidence and unresolved issues](docs/research-and-open-questions.md)
9. [Development and human/AI contribution process](docs/process.md)

Implemented slices: [manual flow](docs/implementation-milestone-1.md) and [local persistence/history](docs/implementation-milestone-2.md)

The [wireframe sources](docs/wireframes/README.md) preserve the interactive design previews discussed during planning. They use fictional data and are not production frontend code.

## Working stack

- React + TypeScript frontend.
- Python + FastAPI backend with REST APIs.
- MongoDB for application records.
- Docker for eventual local packaging; AWS is an eventual hosting direction, not a selected deployment architecture.
- Email-and-password authentication through an established provider; Auth0 is the recommended integration direction, pending configuration and plan checks.
- Open Icecat for API-first specification imports, with manual completion for missing or unavailable information.

MongoDB persistence is local and uses server-derived account ownership in Auth0 mode. An explicit legacy local mode retains the earlier fictional development records separately; it never becomes a fallback on authentication failure. Docker Compose supplies the local database. The manual evaluator can still run without it. Dependency locks and automated tests are included. No cloud infrastructure has been provisioned or code deployed.

## Provider clarification and remaining work

Start with the open-issues table in [research and unresolved issues](docs/research-and-open-questions.md). On November 12, the user supplied an Icecat reply permitting private/historical storage, normalization/corrections, and JSON export of Open Icecat content. This resolves the principal data-use questions for those described uses; attribution, provenance, freshness labeling, and coverage checks remain implementation requirements. No professional financial validation or production readiness is claimed.

Design baseline consolidated November 11, 2026; first implementation verified November 12. The design package also describes intended v1 and future work, which should not be mistaken for functionality already delivered. Older accepted decisions retain their recorded status.
