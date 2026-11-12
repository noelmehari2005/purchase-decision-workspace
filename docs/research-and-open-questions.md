# Research evidence and unresolved issues

Historical research ledger, consolidated November 11, 2026. Linked guidance and terms can change. Recheck before relying on them for implementation or public promises. Observations are not professional legal/financial validation.

## Open Icecat read-only feasibility observations

During November 9 planning (client-local date), the user registered their own free channel-partner account. Browser inspection showed Open Icecat data access. Three direct read-only Product JSON requests in Chrome returned `msg: OK` with matching product identities and `DemoAccount: false`. No new token, paid plan, or application integration was created.

| Product code | Icecat ID | Observed fields | Gaps / issues |
| --- | --- | --- | --- |
| HP 9TV68ES | 78602571 | Intel i5-8265U, 16 GB RAM, 1000 GB SSD displayed as 1 TB, 15.6-inch screen, 2 kg, 45 Wh | OS and resolution absent from inspected structured fields |
| HP BP0W1UA#ABA | 145924859 | Snapdragon X1-26-100, 16 GB RAM, 512 GB SSD, 14-inch 1920×1200, Windows 11 Pro, 1.46 kg, 56 Wh | No seller price/runtime established |
| HP BP8C1UA#ABA | 145924721 | AMD Ryzen 5 230, 16 GB RAM, 512 GB SSD, 14-inch 1920×1200, Windows 11 Pro, 1.4 kg, 56 Wh | Processor frequency/boost values appeared questionable (4.9/3.5 GHz); do not silently repair or rank on them |

The API supplied installed vs maximum memory separately and raw/display units. Samples are three HP configurations, not broad catalog coverage, uptime evidence, or an implemented importer. Seller pricing was not supplied in those responses. No raw credential-bearing URLs or account passwords are included here.

An English-upgrade banner appeared on product pages. Initially missing detailed Specs later became visible. The earlier inference of blocked specifications was withdrawn; the banner alone did not establish API or language restriction.

Public product pages:

- [HP 9TV68ES](https://icecat.biz/en/p/hp/9tv68es/probook-laptops-450+g6-78602571.html)
- [HP BP0W1UA](https://icecat.biz/en/p/hp/bp0w1ua-aba/probook+4-laptops-probook+4+g1q+next+gen+ai+wolf+pro+security+edition-145924859.html)
- [HP BP8C1UA](https://icecat.biz/en/p/hp/bp8c1ua-aba/probook+4-laptops-probook+4+g1a+ai+wolf+pro+security+edition-145924721.html)

## Primary sources consulted

| Source | Applicability and finding |
| --- | --- |
| [Icecat Product JSON manual](https://iceclog.com/manual-for-icecat-json-product-requests/) | Interface observed as version 3.0, updated Oct 13, 2026. Product IDs, brand/code/GTIN lookup, structured groups/units, subscription-dependent availability. Docs are not proof that every requested product is covered. |
| [Open Icecat license](https://iceclog.com/open-content-license/) and [fair-use policy](https://iceclog.com/open-icecat-fair-use-policy/) | License observed as version 1.4, Feb 11, 2026. Attribution, modifications, redistribution/freshness conditions need mapping to our storage/export/history. Account required; no assumption of unrestricted use. |
| [Best Buy API terms](https://developer.bestbuy.com/legal) | Published terms observed limit content storage/caching to 72 hours. Not chosen as the retained-evidence source. |
| [Framework terms](https://www.iubenda.com/terms-and-conditions/55865674) | Reuse restrictions mean readable specifications alone do not establish permission for a parser. Page parsing is deferred. |
| [Dell U.S. sample](https://www.dell.com/en-us/shop/laptop-computers/spd/dell14sds14270) | Several configuration sections illustrated matching risk. A retrieved UK terms page was not treated as definitive for U.S. access. |
| [Framework 13 specs](https://frame.work/laptop13?tab=specs), [Framework 16 specs](https://frame.work/laptop16?tab=specs) | Installed vs maximum capacities and hardware-dependent weight illustrated normalization/context issues. |
| [VS Code requirements](https://code.visualstudio.com/Docs/supporting/requirements) | Editor-specific recommendations; not combined-workload performance evidence. Needs version/OS applicability captured before rule implementation. |
| [Docker Windows requirements](https://docs.docker.com/desktop/setup/install/windows-install/) | OS, architecture/backend, memory, virtualization conditions. No universal Docker-on-all-laptops rule inferred. Other platforms require their own sources. |
| [CFPB toolkit](https://www.consumerfinance.gov/consumer-tools/educator-tool/your-money-your-goals/toolkit/) and [savings worksheet](https://files.consumerfinance.gov/f/documents/cfpb_your-money-your-goals_savings_plan_tool_2018-11_ADA.pdf) | U.S. educational material; target divided by periods supports transparent goal arithmetic, not our exact contribution-suggestion formula. |
| [CFPB expense worksheet](https://files.consumerfinance.gov/f/documents/cfpb_your-money-your-goals_cutting-expenses_tool.pdf) | User-selected realistic spending changes. Does not validate affordability or automatic cuts. |
| [Auth0 database accounts](https://auth0.com/docs/authenticate/database-connections), [verification](https://auth0.com/docs/manage-users/user-accounts/verify-emails), [reset](https://auth0.com/docs/authenticate/database-connections/password-change), [sessions](https://auth0.com/docs/manage-users/sessions) | Email/password and recovery direction. Provider session revocation alone must not be assumed to revoke our backend sessions. |
| [Auth0 pricing](https://auth0.com/pricing) | Free offering observed; actual enabled features, email limits, and future costs must be checked at setup. No subscription created. |
| [FastAPI modular routes](https://fastapi.tiangolo.com/tutorial/bigger-applications/), [MongoDB modeling](https://www.mongodb.com/docs/manual/data-modeling/best-practices/) | Support the proposed implementation boundaries; not proof of architecture superiority. |
| [OWASP SSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) | Apply URL/destination controls if backend requests external resources. |
| [AWS backup deletion](https://docs.aws.amazon.com/aws-backup/latest/devguide/deleting-backups.html) | Expiration can be delayed or fail; operating guarantees require validation. AWS Backup is not selected/provisioned. |

No claim is made that API access resolves content-retention permission, that correcting values removes license obligations, or that a different extraction method bypasses restrictions.

## Open-issues register

| ID | Remaining issue | Needed resolution before |
| --- | --- | --- |
| O01 | Icecat historic snapshots, redistribution/export, modifications, freshness, attribution, source removal | Final retained-evidence/export design and importing real content into persistent app storage |
| O02 | Broader source coverage and unsupported/restricted products | Advertising specific supported coverage; test additional brands and configurations |
| O03 | Exact assessment rule set for VS Code/Docker across supported OS/versions | Implementing automated tool checks; retain unknown otherwise |
| O04 | Product defaults resolved: original monthly anchor/last-day fallback, incomplete budgets, explicit provisional-total choice, empty-requirement explanation. Boundary tests still required. | Calculation/assessment implementation |
| O05 | Verification gate/session settings accepted. Provider final configuration, password-reset integration, and email delivery remain to verify. | Account implementation and public registration |
| O06 | JSON format and individual item deletion accepted. Licensed export content, precise retention execution remain open. | Final privacy flows/contracts |
| O07 | Hosting budget/services, backups, purge jobs, provider deletion, deletion-record retention and restore handling | Deployment and deletion-time promises |
| O08 | Concrete accessibility/performance/reliability targets, size limits and abuse controls | Final release criteria |
| O09 | Snapshot consistency and idempotent confirmation mechanism | Persistence implementation |
| O10 | Consolidated design-package review and explicit implementation authorization | Scaffolding/application development |

## Next bounded work

1. Six remaining product defaults have been accepted; apply them to detailed contracts and tests rather than asking for the same approval again.
2. Resolve O01 with applicable source documentation or the [clarification draft](icecat-clarification-draft.md). Do not send messages externally without authorization.
3. Specify the first tool rules and remaining technical contracts with boundary examples. "Documented tool checks" means prerequisites for software such as VS Code/Docker, not an Icecat subscription check.
4. Review the [first implementation milestone](implementation-milestone-1.md), then authorize application development. User-created GitHub repository does not authorize a push, paid service, or deployment.

## User-supplied Icecat correspondence

The user supplied an email saying Icecat received their registration and a full-access request. The sender asked how the user discovered Icecat, explained Full Icecat is paid, offered product coverage analysis using brand/MPN and optional GTIN, and offered related commerce services/a call.

This is a sales/coverage reply, not confirmation that our free API access has failed or that a paid upgrade is required. Earlier free-account read-only API samples remain the actual access evidence. It also does not answer historical snapshots, normalized-field modifications, attribution, or private JSON exports under the free license. No marketing/tracking links, private contact details, or email identifiers are retained here.
