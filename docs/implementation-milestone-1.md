# First implementation milestone — proposed scope

## Outcome

Demonstrate one fictional/manual laptop decision end to end locally: needs and current-device inputs, manual candidate review, mandatory eligibility groups, preference evidence, and original/alternative savings plans. The user can see and explain the calculated results.

## Work

1. Set up the React/TypeScript and Python/FastAPI structure inside this repository, with local configuration and an initial development guide. Verify current supported package/tool versions before selecting them.
2. Implement pure domain functions for exact cents, anchored monthly dates, contributions, provisional costs, signed budget capacity, and one spending alternative. Add meaningful boundary tests first.
3. Implement requirement checks with explicit unknowns and failure dominance. Initially use user-confirmed numeric/compatibility inputs; do not invent software prerequisite rules or performance benchmarks.
4. Define request/response schemas and a stateless evaluation API. Expose only fictional/local development data in this milestone; unauthenticated endpoints are not a public deployment design.
5. Connect a minimal manual-entry frontend to the API, following the approved flow and clear save limitations. Any working state held only in memory is labeled as such; historical snapshots are not claimed until persistence exists.

## Acceptance evidence

- Alex's $800/$1,100 examples return the expected contribution counts at $150 and $190.
- Jan 31 → February end → Mar 31, target-date inclusion, no contributions before deadline, zero contribution, already funded, and cents rounding pass tests.
- Missing values don't become zero or passes. Explicitly empty requirements are explained.
- Known failure excludes eligibility; removing the ceiling only changes relevant cost checks.
- Original budget survives scenario edits unchanged; impossible reductions are rejected.
- Partial manual candidates can be confirmed with unknown fields and compared with qualifications.
- Keyboard-operable forms and visible validation errors work through the minimal journey.
- Record actual checks and limitations in the contribution/evidence log.

## Deferred to subsequent milestones

MongoDB persistence and immutable snapshots; authenticated private workspace and full account lifecycle; live Icecat storage/import integration after data-use resolution; additional brand coverage; documented automated tool checks; deployment/hosting/backup operations.

These remain required parts of the intended v1; sequencing them later does not remove them from scope. No paid provider, AWS provisioning, Git commit/push, or external publication is included in this milestone.

## Authorization state

Product defaults are approved. This file makes initial coding scope reviewable; application scaffolding and code changes have not yet been authorized or performed.
