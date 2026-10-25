---
name: volt-forge-product-design
description: Shape the VOLT-FORGE frontend to match its Product Vision reference screens while connecting to the existing engineering backend. Use for the workspace shell, assembly view, inspector, simulation setup, results and comparison experience. This does not authorize model development, a thermal solver, an optimizer or a frontend rebuild during backend work.
---

# VOLT-FORGE product design skill

Version 1.0 · 25 October 2026 · **Future frontend implementation guide**

Use this file when frontend work resumes. Creating this guide does not start that work. Physics, evidence and backend development can continue separately. This is a repository-local skill; it has not been installed into the user's global skill catalogue.

## Invoke this guide

Give a future coding assistant this instruction, choosing the milestone you want implemented:

> Read `web/editor/skills/volt-forge-product-design/SKILL.md`, the current frontend contract and the latest engineering decisions. Implement the next agreed frontend milestone using the Product Vision's visual language. Preserve the working electrical workflow, immutable results and evidence labels. Use the frontend-design skill if available. Show the implemented screens and verify interactions against the real backend; do not use concept figures as results.

Work from the actual repository state at that time. This document's capability inventory is dated, not a permanent restriction on future supported models. Add controls for new capabilities only after their contracts and evidence exist.

## Source of the design

The visual reference is **VOLT_FORGE_Product_Vision.pdf**, 19 pages, supplied locally in the repository root. Its images establish the intended appearance. The PDF is not bundled by this guide. The tracked [Product Vision](../../../../VOLT_FORGE_Product_Vision.md) preserves the written direction, but its `assets/*.png` links are not a guaranteed asset bundle.

| PDF pages | Use as a reference for |
| --- | --- |
| 4 | Project entry and project previews |
| 5 | Main workspace, exploded assembly, library and inspector |
| 7–8 | Component library and simulation setup |
| 9 | Assembly overlays, plots and result inspection |
| 11–13 | Variant comparison, optional AI panel and reports |
| 18 | Overall screen family and consistency |

Inspect those actual images before a visual implementation. If the PDF is unavailable, use the specification below and describe the work as an approximation until the reference can be checked. Do not claim screenshot fidelity from text alone.

Use the PDF for visual intent and the **current implemented contract** for supported operations. Read [FRONTEND_CONTRACT.md](../../../../FRONTEND_CONTRACT.md), [EDITOR_GUIDE.md](../../../../EDITOR_GUIDE.md), [MVP_SCOPE.md](../../../../MVP_SCOPE.md) and [SIMULATION_READINESS.md](../../../../SIMULATION_READINESS.md). Consult the latest model/evidence decisions when displaying scientific claims. Old concept-stage statements can be superseded by those decisions.

The reference's Samsung cells, temperatures, stress/current-density imagery, costs and improvement percentages are illustrative. Never copy them into a working result. The first supported design is **four LG M50T cells**, identities **P7, P17, P19, P13**, with the frozen v2 models and explicit same-side-terminal 1s4p connections. A0 is a proposed simulation case, not a validated reconstruction of a measured module. Separate P45B research and measurement views do not make P45B a supported drop-in cell for this module.

## Visual identity

**The assembly is the focal point.** Build a quiet, warm engineering workspace around it. The reference combines direct manipulation, precise component information and restrained application chrome.

- Use an ivory application shell, light panels, near-black text and primary actions, and restrained blue selection accents.
- Give most space to the assembly or electrical diagram. Library, inspector, plots and assistance support that view and can collapse.
- Use compact outline icons, thin separators and moderate corner rounding. Reserve shadows for floating tools, dialogs and assembly depth.
- Put detailed geometry and deliberate material contrast in the assembly: blue cell sleeves, copper-colored conductors, restrained metal parts where represented. Keep the rest visually quiet.
- Prefer aligned property rows, tables and tool panels to repeated dashboard cards. Project previews may use cards, as in the reference.
- Keep actions concrete: “Run simulation”, “Create variant”, “Apply edit”, “Compare runs”, “Export results”. Use sentence case.

Avoid a dark neon dashboard, giant marketing headings inside the editor, decorative gradients, glass panels and oversized metric tiles. Do not replace the engineering canvas with a chat interface.

### Proposed design tokens

These are implementation starting points selected to match the reference's character, **not sampled exact colors from the PDF**. Review them against rendered screens before finalizing.

| Token | Value | Use |
| --- | --- | --- |
| `--vf-shell` | `#F5F2EC` | Application background |
| `--vf-panel` | `#FFFDFA` | Inspector, library, menus |
| `--vf-canvas` | `#EEEAE3` | Viewport background |
| `--vf-ink` | `#202327` | Text and primary action fill |
| `--vf-line` | `#DDD8CF` | Quiet separators, not sole control boundaries |
| `--vf-accent` | `#245EA8` | Selection, links, keyboard focus |

Use distinct semantic states: neutral for simulated, amber for unsupported/outdated, red for failed or a numerical requirement violation. A completed run may use a success mark, but it must not imply engineering acceptance. State labels and icons must carry meaning without color. Validate text/control contrast in the actual combinations; decorative separators need not serve as interactive boundaries.

Proposed typography: **IBM Plex Sans** for controls, body and headings, with `Segoe UI, sans-serif` fallback. Bundle a licensed font only when implementing; otherwise use the system fallback. Use tabular numerals in metrics and property values. Reserve monospace for code, hashes and raw identifiers. Start at 14 px for controls/body, 12–13 px for secondary metadata and 18–24 px for pane titles. Avoid dense, tiny uppercase labels.

Use a 4 px spacing base with 8/12/16/24 px groups. Start with 6–8 px control radii and 10–12 px floating-panel radii. Keep unit labels and numeric fields consistently aligned. These dimensions are proposals, not requirements that override usability.

## Workspace composition

Target a desktop workspace first, with a useful narrow-screen fallback. At approximately 1440 px wide, begin with a 48 px navigation rail, 220–240 px library, flexible central viewport and 280–320 px inspector. The results dock expands only when needed.

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ Project / variant / revision       Design  Simulate  Analyze  Compare  Run │
├────┬──────────────┬────────────────────────────────────┬──────────────────┤
│Nav │ Components   │  View tools: 2D / 3D / exploded    │ Inspector        │
│    │ Search       │                                    │ Selected object  │
│    │ Cells        │        FOUR-CELL ASSEMBLY          │ Properties/units │
│    │ Connections  │        or electrical diagram       │ Source and model │
│    │ Evidence     │                                    │ Apply edit       │
│    │              │  Selection / run / evidence label  │                  │
├────┴──────────────┼────────────────────────────────────┤ Optional details │
│ Variants / runs  │  Results dock: timeline + plots     │ or future AI     │
├──────────────────┴────────────────────────────────────┴──────────────────┤
│ Run status · result freshness · model coverage · requirement status       │
└───────────────────────────────────────────────────────────────────────────┘
```

The wireframe describes hierarchy, not a requirement to display every panel simultaneously. Preserve a large unobstructed viewport. At smaller desktop widths collapse the library before squeezing the assembly. Use drawers for the inspector on tablets. On phones provide a scrollable 2D diagram, accessible component list, forms and results tabs; do not shrink the entire desktop into unreadable columns. Keep important warnings next to their inputs/results as well as in the status area.

### Screen behavior

| Surface | Desired experience | Capability boundary |
| --- | --- | --- |
| Project entry | Clear reference-module preview, recent work when supported, explicit template identity | A multi-project catalogue, blank assembly and AI-generated designs need backend support; do not imply they work now. |
| Design | Assembly/diagram, selectable library entries, contextual inspector | Show the four supported cells and six defined rails. No arbitrary placement-to-connect behavior. |
| Simulate | Load intervals, starting states, assumptions, numerical settings, requirement inputs | Show temperature as an assumption; no cooling setup or predicted temperature without a thermal model. |
| Analyze | Exact-time current/voltage/SOC inspection, synchronized plots, evidence drawer | Only expose fields returned by the selected run. |
| Compare | A0/A1 context, explicit changed properties, aligned plots, compact metric table | Common-condition checks come from the backend. No automatic winner or validated-repair badge. |
| Export | Selected variants/runs, configurations, tables, evidence and reproducibility contents | Offer formats actually produced. Do not advertise manufacturing CAD or PDF export merely because the concept shows it. |
| Investigator / AI | Later, structured proposals and explanations of cited results | Keep unavailable until implemented. An editable prompt box must not masquerade as a working copilot. |

Unavailable features can be described in a compact capabilities panel. Do not fill the main navigation with nonfunctional controls. When a visible control is unavailable, give its reason and preserve a usable supported path.

## Assembly and electrical truth

Retain a usable **2D electrical view** even after adding 3D. Both views select the same stable component IDs and open the same inspector.

- Map cell meshes to `cell_1`…`cell_4`; map conductor objects to `rail_p_1`…`rail_p_3` and `rail_n_1`…`rail_n_3`.
- Each cell connects `pk` to `nk`. Rail segment k joins positions k and k+1 on its rail. Module terminals are `p1` and `n1`. Derive rendered connections from project data rather than maintaining an unrelated visual graph.
- Begin 3D with representative cylindrical geometry, clear terminal markers and six selectable rail segments. Decorative enclosure/fastener detail is secondary. Label unsourced geometry “representative geometry”; do not suggest dimensional or manufacturing accuracy.
- Orbit, pan, zoom, selection, exploded offsets and display position changes are visual operations. They do not change resistance, wiring, SOC or model results. Display coordinates are not millimetres.
- Touching meshes do not create connections. Moving a cell does not lengthen a modeled conductor or recompute its resistance. A future geometry-to-physics rule needs explicit units, provenance, schema and backend implementation first.
- Highlight selection with an outline/halo that remains legible over data colors. Keep positive/negative terminal labels visible without relying only on red/black color.
- A cell current, voltage or SOC overlay is a **per-cell scalar**, not a continuous field inside the cell. Rail thickness or arrow animation must not imply current density, speed or measured flow. Explain any visual encoding.
- Use licensed assets or procedural geometry. Preserve model/asset sources and licenses. Never place a reference screenshot behind clickable controls and call it a functioning editor.

For a future 3D milestone, a small Three.js renderer alongside the current interface is a reasonable option. Avoid a framework migration solely to add 3D. Check current official installation/addon documentation and use consistent dependency versions when implementing. Orbit controls and ray-based selection are sufficient initially; transforms, sectioning and CAD import should be added only for a defined supported interaction. If WebGL fails, keep the 2D workflow available.

## Inspector and edits

Read the editable-property catalogue returned by `inspect`; use it as the authority. At this guide's creation, supported edits are:

| Property | Meaning and presentation |
| --- | --- |
| Rail resistance | Effective segment resistance with source/classification. UI may show mΩ but must explicitly convert to API `ohm`. |
| Cell initial SOC | Relative SOC for the fixed reference. UI may show percent; API uses fraction. Respect mathematical support. |
| Cell initial polarization | Assumed one-RC state in V; preserve sign. |
| Module load profile | Contiguous time intervals with discharge-positive A and seconds. Show duration and delivered-service implications. |
| Temperature assumptions | Ambient and surface metadata in °C. Clearly state that editing this does not apply a temperature law. |
| Solver time step | Seconds, numerical setting rather than a physical component property. |
| Voltage requirement | Minimum terminal V, allowed contiguous excursion seconds and documented source; unknown values stay unset. |

Cell identities, chemistry, capacity, reference anchors and fitted R0/R1/tau are read-only in this editor. Existing declared sensitivity scenarios can be shown as **sensitivity scenarios**, not ordinary fitted-model edits or calibrated confidence intervals. Do not create hidden overrides that overwrite a sealed model.

Show a readable label, value, unit, classification and source. Keep sources available without making raw hashes dominate the form. A draft is distinct from an applied edit. Validate through `validate_edit`, show changed inputs and invalidated results, then call `apply_edit` with `expected_revision`. On a revision conflict, refresh context and let the user review their draft; never silently overwrite a concurrent change.

## Results and evidence presentation

Bind every displayed result to **variant, revision, scenario, run, snapshot and component**. Use `current_runs_by_scenario` and backend freshness; never select the most recent run globally.

Keep these independent:

| Dimension | Display behavior |
| --- | --- |
| Execution | Running job, completed run or failed run. HTTP success alone is not simulation success. Use adapter job states without inventing percentage progress or cancellation. |
| Freshness | Current or outdated. An inherited A0 run shown in A1 is historical, not A1's current result. |
| Evidence | Measured data, fitted parameter, assumed input or simulated output. Unsupported transfer/extrapolation flags remain visible. |
| Requirement | “Requirement not configured” when unset; numerical screen when configured; experimental acceptance still depends on evidence. |

Preserve historical and partial results with their labels. A stopped run must show the stop reason and last supported time. Do not extend curves through undefined intervals, silently clip SOC, or hide coverage warnings. On a failed rerun, do not leave the old overlay looking newly computed.

Show module and per-cell current/voltage plots, relative SOC, polarization, node/rail quantities, power, energy and electrical resistive losses only where returned. **Electrical loss is not predicted temperature.** Actual measured temperatures in the separate measurement viewer retain their source and cannot be presented as simulation output.

Synchronize the time cursor, assembly overlay, plots and inspected values. Prefer exact saved samples and display the selected timestamp. If visual interpolation is added, label it and never use it to claim a different threshold crossing or solver result. Preserve narrow peaks when downsampling plots. Use shared axes/color scales for comparisons, with unit-bearing legends and an accessible numeric table.

Distinguish fitting/assessment evidence from unsupported module waveform transfer. An amplitude within observed bounds does not validate its contiguous duration or waveform. “Model validated in range” needs evidence for the particular model, observable and range; it is not an automatic badge for the whole module. No 3.50 V alarm or 25 mV allowance becomes an authoritative default. Show “insufficient evidence” with a concrete reason where engineering acceptance is unsupported.

Comparisons show both configurations, declared differences, operating conditions and absolute metrics before percentages. A reduced load changes delivered service and is not a like-for-like interconnect comparison. Respect backend comparison rejections instead of hiding mismatches. Describe A0/A1 results as a **simulation comparison**, not a battery-performance improvement.

## Reuse the implementation

Start with [index.html](../../index.html), [style.css](../../style.css), [app.js](../../app.js) and [state.mjs](../../state.mjs). Keep the established project contract and local server in [run_editor.py](../../../../scripts/run_editor.py). Use the current [generated API examples](../../../../reports/product_integration_v1/FRONTEND_EXAMPLES.md); do not invent request fields from the concept images.

The existing adapter provides `/api/request`, asynchronous `/api/jobs`, job lookup and session handling. Inspect its current implementation before extending it. Reuse `inspect`, edit validation/application, variants, display updates, runs, series, comparisons and exports. The backend remains the numerical authority; do not port electrical calculations to JavaScript for instant feedback.

Keep layout state separate from physics state. Use `update_display` for supported camera/selection/position data. Preserve immutable run snapshots and compute invalidation through the backend. Keep visual code outside the electrical source tree where possible; that tree contributes to solver fingerprints. Do not rewrite sealed reports, historical verification receipts, frozen models or raw measurements as a side effect of UI work.

The future AI assistant may propose structured supported edits and explain returned evidence. Preview changes, show sources/unsupported requests and obtain approval before applying its proposals. Physical outcomes come from actual solver runs, with run IDs; prose generation does not supply calculated values. Building this assistant is a separate milestone.

## Frontend implementation sequence

Implement one agreed milestone at a time once frontend work resumes. All stages reuse the same project state.

1. **Workspace shell and 2D refinement.** Apply the palette/type/layout, library, inspector and results dock to the working four-cell flow. Preserve editing, variants, run ownership, coverage and export. This establishes the screen family without waiting for 3D.
2. **Linked 3D assembly.** Add representative four-cell geometry, explicit conductor objects, selection and camera controls, then visual exploded mode. Verify the same IDs/inspector and 2D fallback. No physics changes from geometry.
3. **Analysis and comparison.** Add synchronized assembly overlays, saved-time inspection, contextual evidence and A0/A1 comparison within the new shell. Show outdated/failed/unconfigured states as deliberately as success states.
4. **Project and report experience.** Expand project entry, recent work and export presentation only where persistence/output contracts exist. Keep one continuous open → edit → run → investigate → compare → export journey.
5. **New engineering capabilities.** Add broader assembly, thermal views, AI proposals or search only after their backend, evidence and user-facing semantics are implemented and separately scoped.

Before coding a milestone, state its screens, actual API operations and visual plan. After coding, render it and compare with the PDF. Do not treat a static mockup as completion of an interactive milestone.

## Acceptance checks for future frontend work

Use existing editor integration/browser checks, extending them only for changed behavior. Store new screenshots/receipts in a new versioned location; never overwrite historical assessment outputs. Document which checks were actually run.

**Appearance and usability**

- Compare real screenshots with PDF pages 5, 9 and 18: warm shell, restrained chrome, dominant assembly, coherent inspector and results hierarchy.
- Review at 1440 and 1920 px desktop widths, 1024 px and approximately 390 px. Check overflowing fields, drawers, legends and tables rather than merely checking page load.
- Verify keyboard component selection, visible focus, labeled controls, validation messages, readable contrast and non-color status cues. Provide alternatives to dragging. Respect reduced motion; no automatic assembly spinning.
- Test unavailable WebGL and empty/loading/error/no-result states. Every primary action has an implemented outcome.

**Engineering workflow**

- Load A0, inspect the actual LG identities and six rails, run it and bind results to its saved snapshot.
- Create A1, change one declared rail resistance through validation, show inherited results outdated, rerun and compare under identical conditions.
- Change camera/selection/display positions and verify no physics revision or result invalidation.
- Switch variants while work is running; completion must attach to its owner and must not overwrite the other variant's displayed current results.
- Trigger an invalid edit, revision conflict, unsupported request and failed/domain-stopped run; preserve the correct feedback and history.
- Leave requirements unset and verify the UI does not show a pass. Verify simulated, measured, assumed and unsupported labels against their returned data.
- Export the selected runs and confirm their IDs/configurations/evidence match the visible selection. Reuse the existing export/replay checks when relevant.

The milestone is complete when its declared interaction works end to end, the reference comparison is documented, and the user can trace every displayed physical value to its source or saved run. Remaining visual gaps and measurement limitations should be stated separately.
