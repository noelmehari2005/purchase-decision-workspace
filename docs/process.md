# Process, learning, and contribution evidence

## Current phase

First local implementation milestone, authorized November 12, 2026. React/TypeScript and Python/FastAPI now support the fictional/manual journey. Automated checks and browser observations are recorded in [implementation evidence](implementation-evidence.md). The HTML fragments preserve earlier design previews. Milestone 2 adds local MongoDB saved workspaces and immutable reviews; see [its evidence](implementation-milestone-2.md). Milestone 3 now implements account boundaries and has passed local automated and core live Auth0 verification; see [its evidence and limits](implementation-milestone-3.md). No deployment or live import integration exists yet.

## Human and AI contributions

- **Human:** Established the practical purchase-planning concept and learning goals; chose electronics/appliances then laptops; insisted on current-device assessment, user control, unknown answers, broad expense categories, spending scenarios, future role profiles/catalog, link-assisted import, email/password, extensibility, and deletion recovery. Reviewed and steered wireframes, selected Icecat, created/verified its account, and created/moved the GitHub repository.
- **AI:** Proposed scoped journeys, comparison states, modular architecture, candidate/evidence contracts, calculations, research and tradeoffs; authored fictional interactive previews; performed authorized read-only page/API inspections; consolidated this design package; implemented the authorized first local slice, boundary tests, and browser checks. The user installed backend dependencies and started local servers when session restrictions prevented those operations.
- **Corrections:** Initially inferred that missing detailed specs plus an upgrade banner implied access trouble. Later observation showed specs and API responses; that inference was withdrawn. Source/version records must preserve this limitation rather than convert early assumptions into facts.
- **Not established:** Independent professional financial review, legal validation, user testing, measured extraction accuracy, broad API coverage, production security, or deployment readiness.

## Development sequence after authorization

1. Create local project structure and development configuration inside this repository only.
2. Implement pure calculation and assessment behavior with meaningful boundary tests.
3. Add persistence/API with ownership, revision, and snapshot-consistency checks.
4. Connect the frontend to a complete manual-entry journey.
5. Add the Icecat adapter/review flow after resolving its data lifecycle.
6. Integrate email/password and account lifecycle; test deletion/restore and private data handling.
7. Validate the complete journey and accessibility; iterate from observed user feedback.
8. Decide hosting/budget and perform deployment only when separately authorized.

The first manual/stateless coding slice is authorized and implemented; subsequent slices remain to be scoped. The approved first milestone intentionally connects the frontend before persistence. Slice work so the user can understand and demonstrate each result. Explain unfamiliar concepts in the context of the requirement they serve.

## Evidence for each meaningful change

Record the problem, requirement IDs, alternatives/tradeoff, human choices, AI contribution, implementation references, verification performed, results, and limitations. Update the decision log when behavior changes. Keep selected prompt excerpts only when they illuminate reasoning; do not dump private transcripts or credentials.

Git commits support history but do not replace this evidence. A concise portfolio case study should eventually show the journey from requirement to design, implementation, and demonstrated behavior. Do not label AI-generated code as unaided work or claim checks that were not run.

## Review gates

- Product decisions already accepted remain accepted unless explicitly revised.
- The six product defaults, including date/session conventions, are now approved. Technical contracts and operating guarantees still require specification/verification; do not request the same product approval again.
- Implement Open Icecat attribution/provenance and the November 12 provider clarification for the described storage/export uses. Re-evaluate permissions for new sources or uses.
- Keep hosting costs, credentials, migrations, and publishing reviewable before executing consequential external actions.
