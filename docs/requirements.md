# Requirements and acceptance criteria

Accepted product behavior is summarized here. Contracts that implement it remain design drafts. IDs support traceability; they are not implementation task completion markers.

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| R01 | Guided needs | Select general tasks, add custom needs, identify upcoming work and optional tools/deadlines. No silent hardware minimum follows from selecting a task. |
| R02 | Current-device assessment | Accept known specs and task experience, including "I'm not sure." Distinguish observations from documented requirements and diagnosis. |
| R03 | Candidate entry | Support manual entry, Icecat product links, and brand + exact part-code lookup. Retain unsupported seller links for manual completion. |
| R04 | Partial imports | Keep retrieved fields when other fields are missing. Failure preserves the supplied identity/link and offers retry/manual entry. |
| R05 | Review gate | Confirm product/configuration before a revision enters comparisons. Unknown specs may remain unknown. Later edits/refreshes create a reviewable revision. |
| R06 | Evidence | Preserve original and normalized values, units, source identity, retrieval date, user corrections, and detected conflicts. Review confirmation is not independent verification. |
| R07 | Mandatory eligibility | Each check is met/failed/unknown with reasons. Any failure makes the option ineligible; otherwise an unknown leaves it unconfirmed. All met means eligible. |
| R08 | Grouped comparison | Show meets / needs verification / does not meet groups. Keep the owned device visible as a baseline. Changes explain group movement. |
| R09 | Preferences | High/medium/low/ignored importance; supported comparisons for workload evidence, portability, battery, repairability/upgradeability, optional lower cost. No overall numerical score in v1. Missing evidence is not zero. |
| R10 | Independent cost controls | Optional maximum total purchase price and separate lower-cost preference. No ceiling does not remove other mandatory requirements. |
| R11 | Cost uncertainty | Track price, tax, shipping, and other stated purchase costs separately. Unknown is not free. Allow explicitly provisional totals; show assumptions and unconfirmed conclusions. |
| R12 | Savings plan | Purchase savings, chosen contribution, optional target date and contribution start date. Distinguish target-required amount from modeled budget capacity and personal choice. |
| R13 | Optional budget | Monthly take-home income, broad expense categories, other goals, and user-chosen unallocated buffer. Purchase savings exclude protected funds by user designation. Do not double-count goals or buffer as expenses. |
| R14 | Contribution support | Explain the accepted suggestion direction in calculations. The user can choose another amount; flag shortfalls without asserting the contribution is safe or affordable. |
| R15 | Scenario | One saved alternative alongside the original. User chooses category reduction and purchase allocation; reject reductions exceeding that category. Never mutate the base budget. |
| R16 | Saved decisions | Tentative/undecided outcomes permitted, including failed/unconfirmed candidates with issues retained. Save explicit immutable snapshots and revisable working drafts. |
| R17 | Private accounts | Email/password, optional financial inputs, owner-only access, account-free fictional demo. Provider implementation must not mix budgets into identity profiles. |
| R18 | Account deletion | 30-day pending-deletion recovery window and notification email. Restore requires explicit cancellation. Then purge active associated records; backup copies removed within the following 30 days, subject to verified infrastructure support. |
| R19 | Stable historical meaning | Retain input/result/model version identity. Re-evaluation under newer rules creates a new result. Product-content retention remains subject to the unresolved license decision. |
| R20 | Extensibility | Separate imports, domain calculations, assessment, storage, and interface. New sources produce the same draft contract. Category expansion is not implemented speculatively. |

## Nonfunctional requirements

- **Accessibility:** Keyboard-operable controls, associated labels, accessible errors and updates, no color-only eligibility indication. Small-screen layouts must retain essential information. Detailed accessibility checks are specified in verification.
- **Integrity:** Exact monetary arithmetic and explicit units. Finite numeric values only. Field-level validation on both UI and backend; backend results are authoritative.
- **Concurrency:** Stale edits produce a conflict, not a silent overwrite. Snapshots represent a consistent set of revisions.
- **Privacy:** No financial payloads or credentials in routine logs. A session expiry must not leave private data displayed. Do not promise persistence of unsaved edits.
- **Reliability:** Bounded external requests, useful errors, retries that do not duplicate candidates, and visible save status. Timeouts and retention jobs require measurable operating targets before release.
- **Maintainability:** Versioned schema/rules, source adapters with controlled samples, meaningful automated checks, documented migrations and architecture decisions.

## Flow states to cover

| Screen | States and recovery |
| --- | --- |
| Needs/current laptop | Empty, partial, unknown, invalid units, incompatible documented requirement, reported difficulties without known cause. |
| Import review | Loading, complete, partial, unsupported link, ambiguous identifier, restricted access, not found, timeout, conflict, corrected, confirmation required. |
| Comparison | Every group populated/empty, no confirmed suitable option, ties/tradeoffs, unknown preference evidence, optional ceiling, essential deadline unmet. |
| Purchase plan | No budget, incomplete/provisional cost, zero contribution, negative budget balance, already funded, no contribution before deadline, invalid scenario. |
| Save/revise | Saving, saved, failed save, stale revision, changed model, unavailable/removed source. Preserve the last confirmed candidate until replacement confirmation. |
| Account | Unverified email, invalid login, neutral recovery response, expired session, pending deletion, restored account, completed deletion. |

Wireframes illustrate selected states only. They do not yet implement all these requirements.
