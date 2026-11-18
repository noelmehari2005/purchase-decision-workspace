# Verification and traceability

Status: local verification index, updated November 16, 2026. The application and automated tests now exist. This document separates implemented/local evidence from outstanding release work; no production deployment, independent usability study, or formal accessibility/security certification has been completed.

## Requirement → design → CS concept → evidence

| Requirements | Design decision | CS/engineering concept | Planned evidence |
| --- | --- | --- | --- |
| R01–R02 | Explicit unknowns and observation/evidence separation | Typed state modeling; three-valued reasoning | Unknown inputs complete the journey without becoming passes/failures. |
| R03–R06 | Adapter produces a review draft | Parsing, normalization, provenance, interface boundaries | Controlled JSON responses map to expected values; confirmation and retry tests. |
| R07–R10 | Eligibility separate from preferences/timing | Constraint satisfaction, deterministic rules | Failure dominance; permutation-independent checks; optional ceiling transitions. |
| R11–R14 | Exact cents and calendar schedule | Numerical correctness, boundary conditions | Hand-calculated examples, date/currency edge tests, invariant tests. |
| R15 | Alternative references unchanged base plan | Immutable inputs, scenario modeling | Base remains byte-for-byte unchanged after scenario evaluation. |
| R16/R19 | Frozen revisions and model versions | Optimistic concurrency, reproducibility | Stale updates rejected; repeat evaluation with same inputs/version matches. |
| R17–R18 | Ownership and explicit lifecycle | Authentication vs authorization; state machines; failure recovery | Cross-account denial, session revocation, recovery boundary and purge tests. |
| R20 | Domain functions separate from external systems | Separation of concerns, dependency inversion | Change a formula/source without rewriting unrelated user flows. |

## Current implementation evidence

| Requirements | Implemented evidence | Practical limit |
| --- | --- | --- |
| R01–R02 | [App needs/current-device flow](../frontend/src/App.tsx), [model tests](../frontend/tests/model.test.mjs), [domain tests](../backend/tests/test_domain.py); local keyboard/mobile walkthrough. | No automatic system diagnosis or task-to-hardware inference. |
| R03–R06 | [Icecat adapter](../backend/app/icecat.py), [import tests](../backend/tests/test_imports.py), [live import evidence](implementation-milestone-4.md). | One HP configuration verified live; source coverage across other brands remains unestablished. |
| R07–R10 | [Domain rules](../backend/app/domain.py), domain/API/model tests and [comparison evidence](implementation-milestone-1.md). | Performance/repairability remain evidence notes; direct preference tradeoffs require comparable measurements. No overall winner score. |
| R11–R15 | Domain calendar/cost/budget/scenario tests; frontend decimal parsing and payload tests. | The plan models entered assumptions, not future prices, interest, financing, or independently validated affordability. |
| R16/R19 | [Storage tests](../backend/tests/test_storage.py), [exports](../backend/tests/test_exports.py), [milestones 2](implementation-milestone-2.md) and [5](implementation-milestone-5.md). | Choose a confirmed candidate or keep the decision undecided; unconfirmed drafts remain preserved but excluded from comparisons. Export is a read window with revision checks, not an account-wide transaction. |
| R17 | [Auth0 provider tests](../backend/tests/test_auth_provider.py), [signed OIDC tests](../backend/tests/test_oidc.py), [account tests](../backend/tests/test_auth.py), [Mongo account tests](../backend/tests/test_auth_mongo.py), [live account evidence](implementation-milestone-3.md). | Database account isolation uses controlled provider responses; a second live Auth0 account was not exercised. Deployment remains loopback-only. |
| R18 | [Lifecycle tests](../backend/tests/test_lifecycle.py), [recovery UI rendering](../frontend/tests/lifecycle-view.test.mjs), [deletion evidence](implementation-milestone-6.md), [live SMTP and disposable-provider cleanup evidence](implementation-milestone-9.md). | Local test email reached the inbox and an explicitly disposable Auth0-only identity was deleted and verified absent. Queued-notice delivery, supervised/scheduled lifecycle operation and infrastructure backup expiry/restore remain outstanding. |
| R20 | Separate domain/schemas/repositories/provider/import/lifecycle/frontend modules; independent schema and calculation versions. | Extensibility is an architectural boundary, not evidence that other product categories are implemented. |

Read dated milestone reports for exact commands and results. No code-coverage percentage is claimed. Historical reports describe their own implementation date and may list work completed by later milestones.

## Calculation cases

- $300 saved, $800 total, $150 contributions → 4 contributions; $190 → 3.
- $300 saved, $1,100 total, $150 → 6; $190 → 5.
- $500 remaining over three contribution dates → $166.67 monthly required; verify cents and final deposit.
- Already funded, missing/provisional cost, $0 contribution, zero/negative budget balance, one cent short, overfunding, invalid NaN/infinity/negative values.
- First contribution after deadline, contribution exactly on deadline, same-day funding, leap year, month-end anchors, timezone boundaries.
- Monthly buffer and other goals subtracted exactly once; incomplete budget yields no confident capacity.
- Reduction and allocation independently validated; base changes can invalidate an existing scenario.

## Assessment and import cases

- Failure dominates unknown; unknown does not become zero or a pass.
- Lower price cannot compensate for incompatible required software.
- No ceiling changes price checks only. An essential deadline affects plan feasibility separately.
- Missing preference data cannot create a false winner; incompatible benchmark/battery contexts remain distinct.
- Match requested/returned brand and part code; preserve regional suffixes. No fuzzy-name auto-confirmation.
- Map installed vs maximum RAM, raw grams vs localized kilograms, 1000 GB vs displayed 1 TB, individual missing display properties.
- Flag source contradictions such as unusual CPU base/boost relationships; no silent repair or GHz ranking.
- Untrusted product text never executes. Unsupported URLs never trigger arbitrary network requests.
- Success, partial, not found, ambiguous, restricted, rate limit, timeout, malformed provider response, user correction, stale draft, repeated confirmation, reviewed refresh.

Use small controlled response fixtures for repeatable adapter tests, retaining only content permitted by the source. Live account checks are a separate limited integration check, not a dependency of every test run. Do not store private URLs, tokens, or unnecessary marketing material as fixtures.

## Persistence and lifecycle cases

- One user cannot read/edit/evaluate/delete/export another user's resources, including nested IDs.
- Edits in two tabs yield a revision conflict rather than lost updates.
- Snapshot creation captures one consistent revision set. Updated source/model data leaves historical outputs unchanged where retention permits.
- Verification gating, wrong/expired/reset links, neutral recovery messages, logout/session expiry, and password-reset invalidation of backend sessions.
- Deletion request revokes access and queues email. Delivery failure is visible/retryable.
- Explicit restore just before deadline succeeds; at/after deadline fails. A delayed purge job cannot reopen recovery.
- Purge/delete retries are idempotent. Failure of external identity removal does not grant data access.
- Backup restore replays pending/final deletions and invalidates obsolete sessions before reopening access.
- Demonstrate actual backup expiry/removal and handling of failed deletion before claiming the 30-day post-deletion maximum.

## User-facing checks

Walk the fictional Alex scenario with someone who has not designed it. Ask them to explain eligible/unconfirmed/failed status, source confirmation, provisional costs, and base vs alternative plan. Observe rather than instruct them through mistakes. Record actual findings and iterate.

Local checks on November 13 exercised all five steps at 320 CSS pixels, a 180-character unbroken product name, keyboard step activation and heading focus, a functioning skip link, visible field labels/hints, candidate-validation alerts, and keyboard scrolling inside source tables. The page stayed within the viewport; source tables scroll within their own focusable region. Temporary edits were restored and the saved workspace remained unchanged. See [milestone 7](implementation-milestone-7.md).

Release targets: retain essential controls and information at 320 CSS pixels without page-wide horizontal scrolling; let source tables scroll in labeled regions; make primary flows keyboard-operable with visible focus and associated labels; announce validation errors and async results; retain text eligibility labels alongside color. These local observations do not establish full WCAG conformance. Broader authentication/recovery keyboard coverage, native-control/forced-color checks and independent usability feedback remain open. No runtime performance score or latency percentile is claimed.

November 16 guided checks passed for candidate focus/validation, skip-link activation, 200% zoom on Needs/Candidates/Compare, and basic VoiceOver field/confirmation announcements; see [milestone 8](implementation-milestone-8.md). Signed-in VoiceOver checks also passed for the RAM correction checkbox and source-table region. Import-result/close focus and 40 authored color pairs were reviewed, and faint input boundaries were darkened; see [milestone 9](implementation-milestone-9.md) and [contrast review](contrast-review.md). The owner will arrange an independent participant using the [tester brief](independent-usability-brief.md); results remain pending.

## Dependency advisory evidence

On November 13, the user ran pip-audit 2.10.1 against the pinned backend lockfile in an isolated tool environment: no known vulnerabilities found. The full frontend `npm audit` reported zero vulnerabilities. No app dependency was changed. Package-advisory results are time-specific and do not replace code/configuration, application-security or supply-chain review. See [milestone 7](implementation-milestone-7.md).

## Release evidence

Required: passed meaningful unit/integration/user-flow checks, source coverage findings and failures, dependency/security configuration checks, restore exercise, documented unresolved limitations, and a complete requirement-to-evidence index. Tests around calculations/domain behavior come before wiring the full interface. Routine documentation edits need link/status checks, not an application test suite.
