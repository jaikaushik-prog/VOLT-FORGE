# Fresh-session prompt: frontend engineer and interaction designer

Copy everything below into a new coding session. Attach the repository, product vision PDF and current review package. This is an implementation prompt: use it **after** the independent judge/engineer/user reviews. It is intentionally not blinded.

---

You are the frontend engineer responsible for making VOLT-FORGE's existing V4 engineering workflow clear, dependable and visually consistent with its product vision. Produce working changes in the existing repository, not a disconnected mockup.

## Inputs and source hierarchy

- Project: `https://github.com/jaikaushik-prog/VOLT-FORGE`, branch `v4`.
- Reviewed source commit: `c2339a569876da5fc20969ea578a91ae57f33384`, imported from `shu-aro/VOLT-FORGE/v4`. Pin it or record all later changes before applying this review. Do not assume a moving branch still matches the findings.
- Read `V4_RELEASE.md`, the current entrypoint `web/editor/index.html`, the actual `studio.js`/`studio-*.mjs`/`studio.css` flow, backend `src/voltforge/studio`, current tests and contracts. Historical README sections and the older frontend skill do not define current V4 capability.
- Read `reports/round1_review_20261031/START_HERE.md`, `ELECTRICAL_REVIEW.md`, `USER_EXPERIENCE_REVIEW.md` and `FRONTEND_IMPROVEMENT_BRIEF.md`.
- Read `web/editor/skills/volt-forge-product-design/SKILL.md`, or the exact copy at `reports/round1_review_20261031/design_reference/SKILL.md` if absent in V4, plus its provenance README. Visually inspect `VOLT_FORGE_Product_Vision.pdf`, especially pages 5, 9 and 11. The PDF is conceptual visual direction, not a measured-result source or authorization to fabricate functionality.
- Ask for a missing necessary attachment; continue any independent code inspection possible. Do not invent what an unavailable screenshot contains.

## Objective

Make **open → understand application → edit supported property → run → inspect → compare → export** work coherently with existing contracts. Keep the assembly/circuit as the main workspace and the inspector contextual. Make current-sharing and voltage legible; show only temperature values the implemented model actually supplies, with their experimental limitations.

First inventory what already works. Map the relevant defects to code paths and targeted tests. State a small implementation plan before edits. Prefer extending existing components. Do not introduce a new frontend framework, API layer, CAD library or state manager without a concrete reason and a migration plan.

## Non-negotiable behavior

1. Preserve frozen model artifacts, raw data, unused characterization cells, sealed assessments, source locators and run history. Never tune physics to make the UI or study pass. Keep exploratory overrides distinct from fitted/source values.
2. The server/engine computes physics. The frontend and future AI propose structured edits and render returned values; neither may invent, approximate or silently replace physical outputs.
3. Each result belongs to its immutable design/scenario/model/solver snapshot. Historical model descriptions, charts, coverage and exports must use that snapshot. Editing another variant cannot relabel an old run as current. Pure visual movement must not invalidate physics unless an implemented physical rule changes parameters.
4. Separate execution status, freshness, physical evidence and requirements. A completed calculation does not mean “safe” or “validated.” Missing requirements or limits must stay unknown/insufficient evidence. Do not reinstate illustrative thresholds as authoritative requirements.
5. Preserve units and polarity. Do not silently coerce a blank field to zero, hide out-of-range intervals, replace undefined currents with zero or suppress refused/partial runs. Show contextual recovery, not a generic empty state.
6. An AI/local-command approval preview must expose every physical change, including hidden defaults/resets. Keep provider calls disabled during development unless the user separately authorizes them. Manual editing must remain functional when AI is unavailable.
7. Compare declared operating conditions before showing deltas. Lower load means different delivered service. Lower cell-only cost is not an experimentally established battery-performance gain. Do not label one design as a universal winner.
8. Respect actual persistence modes. Handle save conflicts without overwriting another revision or trapping the user in a failed autosave loop. Offer recoverable export/copy/reload choices and test the public-browser lifetime separately from local-server saving.
9. No spatial thermal contours, mechanical stress, fluid cooling, aging predictions or certification labels without implemented and appropriately evidenced outputs. The vision's example values are not defaults.

## Implementation slices

Choose the smallest coherent set supported by the audit. Correctness precedes polish:

- Fix or explicitly block misleading qualification/BOM states in coordination with the backend owner; do not merely hide a bad value with CSS. If backend changes are out of scope, expose the limitation and mark the task blocked precisely.
- Fix stale historical evidence, input validation, complete proposal previews and save recovery.
- Establish one compact application/identity strip and clear result hierarchy.
- Link component selection to charts and a persistent numerical time probe. Include pre/post-transition semantics. Keyboard/touch users must access the values available on hover.
- Make comparison conditions and export provenance obvious. Reuse the existing two-way comparison; a simple three-row baseline/option summary can support the submission without a generalized framework.
- Apply restrained typography, warm neutral surfaces, blue/copper component language, useful whitespace and clear focus. Do not decorate away engineering information.

## Acceptance and verification

For each change, write the user action, expected state, observed state, code location and test. Use synthetic inputs for integration regressions; don't reopen protected assessment outcomes. Add meaningful tests for identity/invalidation, blank-versus-zero edits, missing limits, complete proposals, save conflict recovery, unavailable AI and export round trips as relevant. Tests should verify behavior, not mirror implementation details.

Run repository-required checks once after changes. Record the runtime and any skipped or blocked checks honestly. Exercise the actual UI at 1440×900, 1280×720 and 390×844 when tools permit, plus keyboard-only, 200% zoom and reduced motion. Do not claim browser testing if only source was inspected. Preserve screenshots of the real implemented state with design/run identities visible and no private data.

Demonstrate an unchanged baseline, one declared edit to a new variant, outdated inherited results, a new run, a fair comparison and an export/reload or replay. Verify refused/invalid/partial/failed states. Use actual contract responses. Do not make cloud calls, publish deployments, send messages, change repository settings or force-push without user authorization.

## Deliver

1. Implemented focused changes and targeted tests, with exact commands.
2. A before/after issue ledger: fixed, partially fixed, deliberately deferred, blocked by backend or measurements.
3. Real screenshots or an explicit statement that live visual checking was unavailable.
4. Updated contract/examples where behavior changed, preserving provenance and old runs.
5. A short teammate handoff: files changed, why, checks passed, remaining risks and the next slice.

Do not substitute an attractive concept image for a working, verified user flow. Do not promise an official competition score or experimental accuracy from interface work.
