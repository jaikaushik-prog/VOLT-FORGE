# Frontend handoff: make the engineering decision readable

31 October 2026 · Review baseline `c2339a569876da5fc20969ea578a91ae57f33384` · Recommendations, not implemented UI changes.

## Direction and scope

Keep the current V4 editor and simulation contract. Improve the sequence **open a design → understand its application → edit one supported property → run → inspect the result → compare → export**. Do not rebuild the app or add a general CAD system before Round 1.

Use the original `web/editor/skills/volt-forge-product-design/SKILL.md` as a visual guide, with the capability correction below. It is absent from the reviewed friend's V4, so an unchanged copy is supplied in [design_reference/SKILL.md](design_reference/SKILL.md); read its accompanying provenance note. The supplied `VOLT_FORGE_Product_Vision.pdf` is a concept reference: page 5 establishes a dominant assembly and contextual inspector; page 9 links time-series values to components; page 11 makes comparisons share conditions. Its example numbers, rendered geometry and thermal contours are not evidence about the current model.

The older skill's capability inventory describes an earlier release. V4 already has additional circuits, thermal calculations, protection and a bounded sizing search. Inspect `V4_RELEASE.md`, the current backend and current tests before offering a control. Do not regress V4 to the old four-cell-only interface, and do not make unsupported outputs available because the vision shows them.

This brief combines direct inspection of the vision and supplied slide with current source inspection and the independent UX review. The public app was **not** successfully exercised: browser automation was unavailable, and access to the existing private Chrome window was blocked. Layout and interaction proposals therefore require live verification. The separate UX report labels source-derived findings individually.

## Before cosmetic work

1. Fix verdicts that imply qualification without essential limits, and make board recommendations conditional on actual wiring/voltage and charging compatibility. The electrical report has synthetic reproducers. A prettier green verdict would amplify these defects.
2. Keep old-result model information tied to the saved run, not the current edited design. Fix stale ownership and incomplete proposal previews before relying on them in a demonstration.
3. Provide a recovery path for failed or conflicting saves, and prevent an empty resistance field from silently becoming a physical zero. Preserve a deliberate, explicitly entered ideal zero if that is a supported calculation mode.
4. Explain public-browser persistence honestly at entry and export. Do not label a volatile browser session “saved” in the same way as a durable project.

The detailed reproduction/acceptance requirements are in `ELECTRICAL_REVIEW.md` and `USER_EXPERIENCE_REVIEW.md`. Their proposed tests are not evidence that a fix has passed.

## One workspace, three views

Keep Build / Results / Compare recognizably connected by project, revision, scenario and run identity. Show a compact application strip across all three views. Use the same cell IDs, colors and ordering in the canvas, inspector, charts and comparison rows.

Proposed desktop composition, adapting the existing components rather than introducing a new routing framework:

```text
VOLT-FORGE   Pi backup / A0 / rev 3      Build  Results  Compare    Export
25 W · 600 s · 23 °C · initial SOC 70%   [assumptions]   [edit application]
────────────────────────────────────────────────────────────────────────
Library / tools   |       assembly or circuit        | Selected component
(collapsible)     | C1     C2     C3     C4            | C2 · LG M50T
                  | explicit + / − output terminals | value / unit / source
                  | labeled connections and load    | editable assumptions
                  |                                 | [validate] [apply]
────────────────────────────────────────────────────────────────────────
Run state · revision · simulated evidence · unresolved requirements   Run
```

At smaller widths, use one inspector drawer and a readable single-column result table. Never shrink source labels, units or failure text to preserve a desktop screenshot. No fake 3D battery render is necessary for this handoff.

### Build

- Display topology, output terminal locations and the load block on the same canvas. Assembly/circuit toggles must represent the same electrical graph.
- A selected wire exposes resistance in mΩ and its origin: direct assumed value or calculated from geometry/material. If geometry drives resistance, preview the derived change before applying it; screen positions alone must not change physics.
- A selected cell exposes the actual model identity, initial conditions and supported edits. Show fitted/source values separately from exploratory overrides. Provide a clear revert action; never overwrite a sealed artifact.
- Validate both on editing and at simulation submission. Invalid values stay visible with a nearby reason and a correction path. Do not turn missing text into zero or reset the user silently.
- Show what a proposed AI/local-command edit changes: cells, connectivity, output terminals, model, SOC, polarization, temperature, thermal assumptions, mission, load and protection. A count summary is not a complete approval preview. Changes stay a draft until applied.
- When the provider is unavailable, keep manual actions and the local workflow usable. Do not promise an active cloud copilot or make a provider call during a review without authorization.

### Results

Use four separate meanings, rendered in one compact status area rather than a wall of badges:

| Dimension | Example text | Meaning |
|---|---|---|
| Execution | Completed / Refused / Failed / Partial | Did the calculation finish, and what portion exists? |
| Freshness | Current for A0 rev 3 / Outdated: resistance changed | Does this run match the selected design? |
| Evidence | Simulated; measured accuracy unresolved | What supports the physical prediction? |
| Requirements | Meets configured simulated limits / Not configured / Insufficient evidence | Can the intended decision actually be made? |

Never collapse these into one “safe” or “validated” indicator. A completed run can be outdated, outside evidence coverage, or missing a requirement. Present refusal as useful information with a cause, not an empty screen.

Prioritize four questions: did the declared service complete; what was the lowest terminal voltage; which cell carried the most current; which limits/evidence gaps matter? Use computed values from the saved run, with units and definitions. Temperature is a **simulated lumped-cell temperature** only where the current solver supplies it. Do not draw a spatial thermal field, cooling-fluid flow or mechanical stress from a lumped model.

Below the summary, put a substantial chart next to or above the assembly probe. Selecting C2 highlights C2 in both. A single time control changes all shown values. At current transitions, expose the pre/post convention and exact timestamp. Every number reachable through hover must also be reachable by keyboard/touch in a persistent readout. Explain undefined ideal-link currents as indeterminate, not 0 A.

Open “Evidence and assumptions” from the result itself. It should show this run's model hash, scenario, declared limits and their origins, source locators, coverage findings and replay/export information. Keep optional mathematical detail behind disclosure; make decision-changing limitations visible without opening it.

Suggested result sentence:

> The simulation completed the declared 10-minute case under the displayed assumptions. This does not establish board compatibility or measured module accuracy. Review the limits and evidence below before choosing hardware.

Use that sentence only when the actual run completed. Avoid substituting generic boilerplate for returned refusal reasons.

### Compare

Show the baseline and at least two alternatives for the competition story, preferably 4 / 3 / 2 LG M50T cells under the same declared mission. Keep topology/output differences explicit. The existing two-way view can remain; add a compact three-row summary for the slide or an export, rather than building a large comparison framework now.

Put a **conditions comparison** above performance deltas: load/service, duration, initial state, ambient/thermal assumptions, solver/model version and protection. If conditions differ, list the differences and label the result as a mixed-condition comparison. Do not imply equal service if reduced load is responsible for lower current or temperature.

Rows should include completion/refusal, delivered service, minimum terminal voltage, peak and worst-required-case cell current, simulated temperature, cell mass/cell-only cost, protection/redundancy assumptions and evidence gaps. State whether a value belongs to the nominal run or a scenario envelope. Use “lower cell purchase cost” rather than “50% battery improvement”; exclude enclosure/board/labor costs explicitly when absent.

Do not decorate one column as a universal winner. “Smallest qualifying simulated option in the declared set” is a conditional study conclusion. Expose the margin and trade-offs of 3 and 4 cells so users can disagree rationally.

### Export and recover

- Export configuration snapshots, result arrays, source/model/solver identity, assumptions, limits, coverage and a human-readable summary together.
- Clearly distinguish stored result replay from a newly executed simulation.
- Provide an export route even if saving to the local server conflicts. Recovery should offer reload, save a copy or export unsaved work without overwriting another revision.
- Explain the exact public-demo lifetime and local-server persistence behavior. Do not claim recovery until a reload/round-trip test passes in that mode.

## Visual language

Use the existing quiet editor as the base. The vision calls for warm neutral surfaces, a dominant technical assembly, blue cells, copper conductors and modest typographic hierarchy. It does not require an ornate landing page or copied decorative gradients.

Suggested compatible tokens, to adapt to existing CSS instead of replacing the stylesheet wholesale:

| Role | Value | Use |
|---|---|---|
| Shell | `#F5F2EC` | Workspace surround |
| Panel | `#FFFDFA` | Inspector/dialog surfaces |
| Canvas | `#EEEAE3` | Quiet assembly stage |
| Ink | `#202327` | Main text |
| Border | `#DDD8CF` | Restrained separators |
| Action | `#245EA8` | Selection and primary action |

Retain a legible sans serif; use IBM Plex Sans only if the project can load it reliably, otherwise the existing Segoe UI/system stack. Use tabular numerals for engineering values. Color must never be the only state indicator. Preserve visible focus and readable text at 200% zoom. Test actual contrast rather than assuming a proposed token combination passes. Keep 44-pixel touch targets where practical, with compact desktop controls remaining usable by keyboard.

## Implementation order and acceptance

| Order | Change | Observable completion condition |
|---|---|---|
| 0 | Verdict/BOM and result-identity correctness | Electrical reproducers become regression tests; undefined evidence remains explicit; historical results keep their own model/graph. |
| 1 | Input and save recovery | Blank/invalid/valid resistance, concurrent-save failure and navigation tests preserve user work and explain recovery. |
| 2 | Result hierarchy and linked probe | A user can identify the scenario, busiest cell and caveat without hunting; keyboard and touch reveal the same numeric values as mouse hover. |
| 3 | Fair comparison/export | 4/3/2 summary shows identical mission or explicit differences; export/replay preserves assumptions and results; no false gain on reduced service. |
| 4 | Visual polish | Review at 1440×900, 1280×720 and 390×844, plus keyboard, 200% zoom and reduced motion. Capture actual screenshots and distinguish them from concept art. |

Do not redesign everything the night before submission. Fix misleading outcomes and slide readability first; make larger navigation/visual changes after a tested commit and short human walkthrough. “A simulated persona liked it” is not user evidence.

## Brief for your frontend teammate

Work on a new branch from the pinned V4 source. Read the electrical and UX defects before styling. Implement one coherent slice, add the targeted regression checks, capture before/after screens and report the remaining unsupported states. Use `prompts/04_FRONTEND_IMPLEMENTER.md` for the detailed instruction set. No new optimizer, provider integration, thermal model or 3D framework is authorized by this brief.
