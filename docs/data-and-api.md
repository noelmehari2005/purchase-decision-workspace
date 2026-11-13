# Data model and API contract draft

Status: review draft, not an implemented API or frozen schema.

## Record structure

All owned records have an opaque ID, owner ID, creation/update timestamps, schema version, and revision where editable. Child records also reference their decision. The backend derives ownership from authentication, never a client-supplied owner field.

| Record | Fields / embedded structures |
| --- | --- |
| User | Stable internal ID, provider issuer/subject reference, lifecycle state, deletion request/deadline, minimal preferences. No local password field. |
| Decision | Title, category=`laptop`, selected/custom tasks, tool needs, current/upcoming dates, requirement list, preferences, current-device observations/specs, optional budget, base plan, one alternative, working reasoning. |
| Candidate | Product identity, separate seller offer, confirmed revision, optional pending draft revision. Frozen revisions referenced by snapshots cannot be silently overwritten. |
| Import draft | Source input, resolved identity, source result, mapped specs, originals, reviewed edits, missing fields, conflicts, draft revision, optional refresh target. |
| Evaluation | Consistent decision/candidate revision set, per-requirement results, preference tradeoffs, plan results, assumptions/warnings, calculation/assessment/guidance versions. Working evaluations need not all become permanent history. |
| Snapshot | Explicitly saved inputs and results, candidate revision identity, reasoning and unresolved issues, versions, creation date. The November 12 provider clarification permits the described Open Icecat historical specification storage; retain attribution and dated provenance. |
| Application session | User reference, expiry, revocation state. Session secrets are never returned in normal record APIs or logged. |

Embed small related arrays such as expenses and preferences. Reference growing candidates and snapshots rather than accumulating unlimited history inside one MongoDB document. Detailed collections/indexes and maximum record sizes need final specification.

## Shared field contracts

- **Money:** integer cents with explicit `USD`; finite, nonnegative input unless the value is a calculated signed balance. Missing input is null/unknown, never zero. Reject excess precision or require explicit UI rounding, never silent truncation.
- **Date:** contribution and target calendar dates use an explicit user timezone. Store event timestamps separately in UTC. Distinguish date-only inputs from event timestamps.
- **Measurement:** normalized value/unit plus original raw value/unit. Store display text as evidence, not the arithmetic source.
- **Evidence:** provider, source URL/product ID, retrieval timestamp, source update time where available, source claim/measurement context, original value, user edit, issues. Avoid retaining unnecessary marketing prose or raw responses.
- **Requirement:** stable key, field/tool context, operator, threshold/allowed values, origin (`user` or documented suggestion), user confirmation, evidence/rule version. v1 operators are constrained comparisons, not executable expressions.
- **Preference:** supported key and importance (`high`, `medium`, `low`, `ignored`); no numeric overall score.
- **Check:** `met`, `failed`, or `unknown`, with reason codes, field references, and evidence references. Known failure dominates unknowns for group assignment.
- **Offer:** seller/source link, configuration identity, item/tax/shipping/other costs, currency, observed time, conditional-price context, optional provisional total and its origin. Never combine component prices with an overriding provisional total implicitly.

## Icecat mapping observed during research

These identifiers were present in the sample responses; mapping stability still needs controlled tests. Imported `Mandatory` metadata is Icecat's catalog metadata, not Alex's mandatory requirements.

| App field | Sample Icecat feature ID | Handling |
| --- | --- | --- |
| Processor model | 47 | Combine with manufacturer/family, not a performance score. |
| Installed RAM | 11381 | Separate from maximum. |
| Maximum RAM | 1452 | Upgradeability context only. |
| Total storage | 3318 | Use raw unit; 1000 GB may display as 1 TB. |
| Display diagonal | 944 | Preserve raw inches vs localized cm display. |
| Display resolution | 1585 | Parse dimensions when supplied. |
| OS installed | 3233 | Unknown if absent. |
| Weight | 94 | Sample raw grams/display kilograms; normalize explicitly. |
| Battery capacity | 8519 | Wh, not runtime. |

Identity comes from `GeneralInfo.IcecatId`, `Brand`, and `BrandPartCode`. Confirm the actual returned identity matches the requested candidate. Product names alone are insufficient.

## Endpoint outline

API prefix proposed: `/api/v1`. Versioning this URL is distinct from versioning financial/assessment models.

| Method and path | Purpose / response |
| --- | --- |
| `GET /decisions` | Paginated current user's decisions, without financial detail in list summaries. |
| `POST /decisions` | Create working decision; return ID/revision. |
| `GET /decisions/{id}` | Read owned working decision. |
| `PATCH /decisions/{id}` | Validate update against expected revision; return new revision. |
| `DELETE /decisions/{id}` | After explicit UI confirmation, delete the decision and associated candidates, plans, and snapshots. No individual-decision 30-day recovery window in v1. |
| `POST /decisions/{id}/import-drafts` | Accept Icecat product link or brand + part code/product ID; return draft/outcome/issues. Unsupported seller links lead to manual-entry draft without arbitrary fetching. |
| `GET`, `PATCH /decisions/{id}/import-drafts/{draftId}` | Read/edit draft. |
| `POST /decisions/{id}/import-drafts/{draftId}/confirm` | Confirm expected draft revision and atomically publish candidate revision. Repeated request must not duplicate it. |
| `POST /decisions/{id}/candidates` | Create manually reviewed candidate through the same confirmation rules. |
| `POST /decisions/{id}/candidates/{candidateId}/revisions` | Create a revision draft for manual edits. |
| `POST /decisions/{id}/candidates/{candidateId}/refresh-drafts` | Request refreshed source information as a proposed revision; preserve corrections for review. |
| `DELETE /decisions/{id}/candidates/{candidateId}` | Remove from working comparison; preserve earlier snapshots only as permitted by retention policy. |
| `POST /decisions/{id}/evaluations` | Evaluate a consistent revision set and return explained results. |
| `POST`, `GET /decisions/{id}/snapshots` | Explicitly save / list snapshots. |
| `GET /decisions/{id}/snapshots/{snapshotId}` | Retrieve owned historical snapshot. |
| `POST /account/deletion-request` | After fresh authentication, enter pending deletion; record deadline and notification status. |
| `POST /account/restore` | Cancel pending deletion explicitly before deadline. |
| `GET /account/export` | JSON export of user-owned inputs, decisions, plans, reasoning, and permitted Open Icecat specifications with attribution/provenance. |

Identity-provider callbacks, logout/reset flows, session endpoints, and verification handling need a final provider-specific contract. Pending-deletion sessions can access restoration/lifecycle operations only, not ordinary workspaces.

## Request/response rules

- Updates carry an expected revision. Use conditional persistence and return `409 revision_conflict` when stale. Define snapshot consistency across records before implementation; sequential reads alone are not enough.
- Confirmation requires product name and configuration identity. Numeric validation errors block; missing specifications do not. Resolve conflicting selections by choosing evidence or explicitly leaving unknown.
- Proposed success envelope includes `data`, current revision, and warnings. Error envelope includes a stable `code`, user-safe message, field errors, retryability, and request ID; never echo credentials or full provider payloads.
- Typical HTTP responses: `201` created, `200` read/update/evaluation, `204` deletion, `401` session needed, `403` account verification/state restriction, `404` nonexistent or inaccessible record, `409` stale revision, `422` invalid inputs, `429` rate limit, `502/503/504` external-service failures as appropriate.
- Import completeness is a domain outcome, not a server crash. A persisted draft can return `partial`, `not_found`, `unsupported`, `ambiguous`, `restricted`, or `temporary_failure`. Retry rules must be explicit.
- Freeze input revisions before evaluating/snapshotting, or reject changed revisions; do not claim atomicity from a transaction that was never designed/tested.
