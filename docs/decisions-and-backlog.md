# Decision log and future backlog

Consolidated from planning through November 11, 2026. Dates are approximate conversation milestones where noted, not invented commit history. Accepted directions do not imply completed implementation.

## Decision log

| ID | Status | Decision and rationale |
| --- | --- | --- |
| D01 | Accepted | Independent repository in `Portfolio/purchase-decision-workspace`, separate from website and mini-games. Website remains the portfolio hub. Working title: Purchase Decision Workspace. |
| D02 | Accepted | Laptop-only v1, fictional programming persona Alex. Complete a useful journey before broad category expansion. |
| D03 | Accepted | Include current-device assessment and keep-device baseline. Avoid assuming purchase is necessary. |
| D04 | Accepted | Guided programming tasks, custom needs, explicit unknowns. Course numbering is not a hardware/urgency rule. |
| D05 | Accepted | Manual assessment; automatic hardware scan/diagnosis deferred. Browser/user-entered data doesn't establish cause of slowness. |
| D06 | Accepted | Mandatory requirements separate from high/medium/low/ignored preferences. Three eligibility groups; no overall numerical score in v1. |
| D07 | Accepted | Optional maximum price, independent lower-cost preference, visible product tradeoffs and timing. Costlier is not automatically better. |
| D08 | Accepted | Optional income/expense budget, contribution support, user chooses actual amount. One user-directed spending alternative preserves original. |
| D09 | Accepted | Import draft → review/correct → confirm → compare. Missing data permitted. Confirmation isn't independent verification. |
| D10 | Accepted | Open Icecat planned source; API-first, manual completion/failure fallback, no page parser in v1. Read-only samples succeeded. November 12 provider reply supplied by user permits the described retained-data/export uses; see D21. |
| D11 | Accepted | Icecat product links and exact brand/part-code lookup. Arbitrary retailer link resolution deferred; seller links retained. |
| D12 | Accepted | React/TypeScript + FastAPI/Python + MongoDB modular architecture. Docker eventual packaging, AWS eventual hosting direction. No speculative microservices. |
| D13 | Accepted | Email/password only; no Google sign-in in v1. Auth0 remains recommended provider direction, unconfigured. |
| D14 | Accepted | Revisable working decisions and multiple historical snapshots. Explicit versions and source assumptions preserve meaning. License caveat applies. |
| D15 | Accepted | 30-day account recovery period with scheduled-deletion email and explicit restore. Purge active data afterward; residual backups removed within 30 further days, subject to operational verification. |
| D16 | Accepted direction | Contribution suggestion bounded by complete modeled capacity and deadline need, with user-selected unallocated buffer. No universal savings percentage; no professional validation claimed. |
| D17 | Accepted | Email verification gating, one-hour idle/24-hour absolute sessions, password recovery/application-session invalidation, sign-out preserving saved work, and no inactivity-based account deletion. Accepted in the six-default review. |
| D18 | Accepted | Monthly anchor with last-day fallback and return to original day; incomplete-budget handling; explicit provisional-total selection; no-requirements explanation; JSON export; confirmed whole-decision deletion without the account's recovery period. Licensed export content remains open. |
| D19 | Proposed technical detail | Detailed endpoints/schema, exact purge execution, deletion-record retention, concurrency and retry mechanisms need implementation-level specification/verification. Product approval is not a claim those mechanisms exist. |
| D20 | Research update | User supplied an Icecat reply describing a paid Full Icecat quote/coverage process. No paid subscription requested by this project; the message does not clarify free Open Icecat historical-data/export terms. |
| D21 | Provider clarification supplied by user, November 12 | Follow-up permits private/historical specification storage, normalization/corrections with attribution, JSON export, and server storage for Open Icecat. API-first/manual fallback stays unchanged; this email does not deny specification access or require a paid upgrade. No authorization to begin application coding follows from this update alone. |

## Alternatives deliberately deferred

- Automatic scraping/search/product catalogs: larger sourcing and maintenance problem than one reviewed candidate import.
- Simultaneous page parser and API: duplicate extraction complexity without measured need after sample API success.
- Universal CPU/GHz/performance ranking: comparable workload evidence is missing; model names and RAM are not benchmarks.
- Universal personal finance rule: individual commitments and choices matter; exact arithmetic is separate from guidance.
- Multi-category engine, rules language, distributed services: no requirements justify that machinery for v1.

## Future feature backlog

These preserve ideas, not release promises. V2/V3 allocation requires validation and separate scoping.

| Area | Preserved ideas | Dependency / concern |
| --- | --- | --- |
| System assessment | Hardware detection, CPU/RAM/storage/network checks, benchmarks, deeper diagnostics | OS permissions, native tooling, privacy, evidence and cause attribution |
| Data sources | Additional retailer/manufacturer adapters, permitted page parsing, feeds, price refresh/monitoring | Exact configurations, source terms, cost, freshness |
| Product catalog | Automatically present real products matched to needs, browse/filter/select without finding links | Discoverable catalog, coverage, maintained records/offers, licensing |
| Role profiles | CS student, programmer outside school, graphic designer, journalist, overlapping/customizable roles | Role is a starting task profile, not a universal hardware requirement |
| Purchase scenarios | Repair vs replace, refurbished alternatives, buy now vs wait, lifespan, maintenance, energy/running costs, financing, total ownership cost | Category-specific research, uncertainty and scope |
| Financial planning | More detailed income/spending/debt/reserves, multiple goals, milestones, irregular contributions, adverse scenarios | Data minimization, model validity, user control |
| Spending suggestions | Proactive optional category reductions with user-defined flexibility/limits | Essential expenses must not be assumed discretionary |
| Categories | Other electronics/appliances after laptops; vehicles first major new category; housing later | Separate researched models, jurisdiction and local assumptions |
| Specialized extensions | Investment strategies, renovating/reselling property | Exploratory only; expert research/review and downside models required |
| Other brainstorms | Home improvements, education, travel/events, subscriptions, work/hobby equipment | Unselected categories, no implementation commitment |

AI features, bank integrations, paid subscriptions, and hosting budget are unresolved possibilities/choices, not requested MVP features. Do not import features from the abandoned job-market intelligence idea.
