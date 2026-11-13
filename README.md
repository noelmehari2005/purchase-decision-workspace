# Purchase Decision Workspace

A purchase decision and planning application, beginning with laptops for programming. Help users assess their current laptop, compare replacements against their needs, and explore a purchase plan they control.

**Status: design phase.** The repository contains a reviewable design baseline, not a working application. Product direction, architecture direction, and initial import boundaries have been accepted in planning. Detailed proposals and unresolved questions are identified in the documents below. Final implementation authorization has not been given.

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

For the next step: [proposed first coding milestone](docs/implementation-milestone-1.md) and [draft Icecat clarification email](docs/icecat-clarification-draft.md).

The [wireframe sources](docs/wireframes/README.md) preserve the interactive design previews discussed during planning. They use fictional data and are not production frontend code.

## Working stack

- React + TypeScript frontend.
- Python + FastAPI backend with REST APIs.
- MongoDB for application records.
- Docker for eventual local packaging; AWS is an eventual hosting direction, not a selected deployment architecture.
- Email-and-password authentication through an established provider; Auth0 is the recommended integration direction, pending configuration and plan checks.
- Open Icecat for API-first specification imports, with manual completion for missing or unavailable information.

No application has been scaffolded, dependencies installed, infrastructure provisioned, or code deployed. No Git commit or push is implied by preparing these documents.

## Review before implementation

Start with the open-issues table in [research and unresolved issues](docs/research-and-open-questions.md). On November 12, the user supplied an Icecat reply permitting private/historical storage, normalization/corrections, and JSON export of Open Icecat content. This resolves the principal data-use questions for those described uses; attribution, provenance, freshness labeling, and coverage checks remain implementation requirements. No professional financial validation or production readiness is claimed.

Baseline consolidated: November 11, 2026. New detailed contracts are proposals until reviewed; older accepted decisions retain their recorded status.
