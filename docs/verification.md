# Verification and traceability

This is a plan, not a test report. No production implementation, automated application tests, usability study, or professional review exists yet.

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

Implementation references will be added once code exists. Do not invent line references, completed checks, or coverage percentages before then.

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

Check keyboard-only navigation, focus after errors and screen changes, visible labels, dynamic announcements, small-screen overflow, and non-color status indicators. Set concrete accessibility/performance release targets before implementation review; don't claim compliance from a wireframe.

## Release evidence

Required: passed meaningful unit/integration/user-flow checks, source coverage findings and failures, dependency/security configuration checks, restore exercise, documented unresolved limitations, and a complete requirement-to-evidence index. Tests around calculations/domain behavior come before wiring the full interface. Routine documentation edits need link/status checks, not an application test suite.
