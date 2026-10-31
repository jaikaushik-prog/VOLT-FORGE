# VOLT-FORGE v4: independent simulated first-use review

Date: 31 October 2026. Reviewed code snapshot: `c2339a569876da5fc20969ea578a91ae57f33384`, isolated at `tmp/round1_review_20261031/repo`.

This is an independent **simulated first-time-user / heuristic review**, not a human usability trial, an engineering sign-off, or a report of participant feedback. No participant was recruited and no completion time, satisfaction score, quotation, or observed success rate is claimed. I did not run or alter the application, automate its browser, call an AI provider, or inspect previous audits or other agents' reviews. Source-level findings below describe implemented paths and predicted consequences; live browser confirmation is outstanding unless an explicitly attributed observation is added.

## Judgment

The current product has a credible, understandable core: an editable electrical drawing, recognizable selectable cells, a three-step application setup, saved simulation results, finite failure investigations, and a route to a smaller design. The slide screenshots communicate this much better than a generic dashboard would. The next frontend work should protect input intent, result provenance, recovery, and evidence comprehension. A large 3D or framework rewrite before submission would distract from these issues.

Five issues deserve attention before claiming the complete first-use workflow is verified: clearing a numeric field can silently mean zero; the AI approval card omits the available full change set; the model explanation can describe the current design while an old result is selected; keyboard chart probing does not expose the visible exact-value panel; and save-conflict recovery asks the user to reopen through routes that first retry the failed save. These are specific source findings, not fabricated user failures.

## Evidence and scope

Read inputs:

- User-supplied `requirements/USER_REQUIREMENTS.md`, `requirements/official/Official_Case_Study_2.txt`, and original `Official_Case_Study_2.pdf`. Review-machine locator: `tmp/round1_review_20261031/handoff/requirements/`. The official brief calls for a manageable scope, an application, subsystem interactions and traceability, and at least two alternatives against a starting design. It permits calculations and simulation; this review does not invent a laboratory prerequisite. Original attachments are not redistributed with this report.
- [V4_RELEASE.md](https://github.com/jaikaushik-prog/VOLT-FORGE/blob/c2339a569876da5fc20969ea578a91ae57f33384/V4_RELEASE.md), current `web/editor/studio*` modules, and relevant `src/voltforge/studio` contracts in the pinned snapshot. `index.html:11-12` loads `studio.css` / `studio.js`. The older `FRONTEND_CONTRACT.md` and `EDITOR_GUIDE.md` were read but their old capability restrictions were not imposed on v4.
- [Repository product-design skill, preserved copy](design_reference/SKILL.md), used for visual intent, plus supplied Product Vision page-5/page-9 images. See the copy's provenance README: the original guide came from the older workspace and is absent from the pinned friend's V4. Its dated four-cell-only inventory does not justify removing v4 topology, thermal, cell, AI, or sizing capabilities.
- User-supplied submission slide, rendered as `slide_1.png` and `slide_2.png` under review-machine locator `tmp/round1_review_20261031/pdf/`. Visual judgments concern those images, not live application rendering. The submission artifact is not redistributed with this report.

**Runtime boundary:** persistence and local-provider statements below describe the inspected local-server source. I did not inspect or execute the public demo's WebAssembly runtime, proxy or persistence. The supplied `STATE_OF_WORK.md:11` says that public work is lost when the tab closes and that its separate AI connection needs a Gemini key. Those are handoff claims, not fresh verified public-runtime observations. Do not transfer the local disk-store or local-provider behavior to the public site.

Source locators below are relative to the isolated repository unless stated otherwise. `W` means `web/editor`; `B` means `src/voltforge/studio`. Line numbers refer to the frozen snapshot. A source finding establishes code behavior, but it does not establish how often a person encounters it.

Severity: **P1** risks a wrong input/result interpretation or blocks recovery of authorized work; **P2** adds substantial confusion or prevents a required comparison from being understood; **P3** is polish. No P0 or hardware-safety conclusion is assigned by this UX review.

## Two personas, kept distinct

| Simulated persona | First job | What would establish understanding | Likely friction to investigate, not observed feedback |
| --- | --- | --- | --- |
| Electrical-engineering student, new to battery tradeoffs | Open an example; predict which cell carries most current; change one real connection; explain the result | Can distinguish series from parallel, starting charge from capacity, room from cell temperature, a drawing move from a circuit edit, and a numerical check from hardware acceptance | The guided example is a 12 A benchmark while the Pi 5 application is reached through New design; unexplained zero/default assumptions can dominate learning; a chart that moves without exposing numbers gives weak feedback |
| Working engineer evaluating a conditional backup design | State the mission, compare 4/3/2 cells under common conditions, locate the first violated requirement, retain an auditable recommendation | Can identify the saved test and revision, inspect load approximation and limits, distinguish model boundary from component/target failure, compare cost/mass/current/voltage margin, and reopen/export the exact evidence | Repeated test names, pair-only comparison, hidden mismatch flags, current-model text beside old results, and conflict recovery reduce confidence in what was actually evaluated |

The student needs progressive explanation and concrete cause-and-effect. The engineer needs explicit scope and provenance without hunting through every disclosure. These can coexist in the current canvas-led layout.

## Prioritized observations

### UX-01 / P1: blank numeric inputs can become physical zero

**Evidence: direct source finding.** The selected-cell numeric fields and direct connection resistance field are not `required` (`W/studio.js:88-89`). Their change handlers check native validity, then call `Number(el.value)` (`:301-304`). An empty optional number input is valid; `Number('')` is zero. The backend permits zero connection resistance (`B/network.py:123`), and treats zero as an ideal connection (`:175`). Clearing starting temperature or relaxation voltage can similarly create zero; clearing heat capacity can instead cause a save rejection. The targets form deliberately maps blank to `null`, which is the appropriate separate semantic (`W/studio.js:127,322`).

**User impact.** A student clearing `1.0 mΩ` to replace it can unintentionally save an ideal connection. An engineer can believe an assumption is unset when it has become a specific physical input. The backend cannot infer that the zero arose from an unfinished edit.

**Desired interaction/copy.** Keep a draft distinct from the last saved number. For mandatory physical values use: **“Enter a connection resistance in mΩ. Leave the existing value unchanged, or explicitly enter 0 for an ideal connection.”** Show an inline error and retain the text until corrected or cancelled. For truly optional limits, keep **“Not set; this check is off.”** Accept unit-bearing pasted input only if it is explicitly parsed and converted; otherwise state the required unit and do not save.

**Acceptance.** For direct resistance, starting temperature, charge, polarization, heat capacity, and cooling, try empty, whitespace, `abc`, `1 mΩ`, `NaN`, negative and boundary values. No invalid/empty mandatory edit changes saved physics, starts a test, or silently turns into zero. A deliberate numeric zero in a supported field remains possible and receives its meaning. Refresh after a rejected edit preserves the last valid saved value. Optional limits remain `null` when cleared. These are acceptance cases to run, not executed results.

### UX-02 / P1: AI approval omits the complete change preview already returned by the backend

**Evidence: direct source finding.** `proposalHtml` renders only `p.changes` and Apply changes (`W/studio.js:95`). The backend also supplies the full `diff` and preflight `readiness` (`B/copilot.py:133-137`). A template action resets the graph and model defaults and changes the load (`:187-194`), while its friendly labels do not enumerate every resulting cell state, thermal contact, output, or model change. A connection-resistance label says only “Connection resistance: …” rather than naming the actual connection (`:214-218`). Existing-design mutations do have an explicit Apply action and version checks; preserve those controls.

**User impact.** Approval is real, but the person may not know the complete object they approve. This directly affects the user's requirement for a complete preview, especially for multi-action proposals and template alternatives.

**Desired interaction/copy.** Show a compact, human-readable before/after table from `diff`, grouped by components, wiring, preparation, load and limits. Include changed connection endpoints, units, removed dependent objects, whether a copy is created, and result invalidation. Add **“Review N changes. Applying updates this design and makes its previous tests historical”** or **“Creates a separate design; your baseline stays saved.”** Show preflight problems next to Apply. Provide Cancel proposal. New Home construction may still open automatically as the explicitly requested editable draft.

**Acceptance.** Use a deterministic fixture proposal rather than paid/provider inference: change two connections, change a load, remove a cell with thermal contacts, and create a template alternative. Every field in the backend diff appears with readable identity and old/new value; no unintended field is hidden. Cancel produces no mutation. Apply once creates exactly the approved change set. A stale proposal fails with a refresh/review path; it never silently overwrites another edit. Home creation remains a clearly labelled editable draft.

### UX-03 / P1: historical result model explanation is taken from the current design

**Evidence: direct source finding.** Results use `S.test.graph` and correctly display “Earlier design version” (`W/studio.js:79-80`). However, the Results “About this model” action calls `modelDialog`, which selects models using `S.graph.cells`, the live editable design (`:199,205`). Its model cards come from the current catalog. It does not use the selected saved test's graph/model cards.

**User impact.** After changing a cell model, an engineer can inspect a historical curve and be told about the new model. The primary results remain snapshot-bound, but their explanation does not. This is a provenance defect even if both models are individually supported.

**Desired interaction/copy.** Make the results dialog **“Model used for [saved test name, date/time]”**, populated exclusively from saved test model cards/metadata. If current design details are useful, show an explicitly separate **“Current design differs”** link. A Build-page dialog may describe the current design.

**Acceptance.** Run a design using one integrated family, change it to the other supported family or a versioned custom model, and select the old test. Chart, inspector, model explanation, AI test context, export, and displayed assumptions all refer to the same old test. The current model appears only when requested. Repeat after a software/model update; do not relabel an old model as current evidence.

### UX-04 / P1: keyboard chart probing moves the cursor without exposing its exact-value panel or event side

**Evidence: direct source finding.** The time slider calls `probe(index)` without `clientX` (`W/studio.js:300`). `probe` fills the tooltip but only adds its visible class inside `if(clientX!==undefined)` (`:282-285`); the tooltip is otherwise `display:none` (`W/studio.css:9`). The time readout and slider `aria-valuetext` contain only time. “Before/after load change” and protection-event side are supplied only by `pointValues` (`W/studio-charts.mjs:48-52`). Both one-sided samples are retained and reachable by index, which is good; their distinction is not exposed through this keyboard path. A separately opened assembly/cell inspector provides some numbers, but requires additional discovery and also omits event side.

**User impact.** A keyboard user can fulfill the apparent act of probing while being unable to read what changed. Two saved points at the same timestamp can sound and look identical in the time control despite different electrical values. This is material to the explicit exact-values/event-sides requirement.

**Desired interaction/copy.** Add a persistent small **“Saved sample”** table immediately below the chart, synchronized for hover, touch and keyboard. Label **“60.00 s · before load change”** and **“60.00 s · after load change”**. Include each visible cell's value and unit; add precise values on request rather than rounding away distinctions. Offer previous/next saved sample and previous/next event actions. Announce selected time/event side politely without reading the whole table on every pointer move.

**Acceptance.** Starting with no mouse hover, Tab to the slider and use arrows/Home/End through a two-interval test and a protection disconnect. Read exact saved timestamp, event side and per-cell values entirely by keyboard. Both sides of a duplicate timestamp are distinguishable; no interpolated value is represented as saved. Repeat at 390 px and with a screen reader. Legend changes and metric changes preserve an understandable selected sample.

### UX-05 / P1: save-conflict recovery can trap navigation; save status disappears on mobile

**Evidence: source finding with interaction consequence to confirm.** A stale version is rejected with “This design changed in another window. Reopen it before saving” (`B/store.py:325`). `persist` keeps the local draft dirty on rejection (`W/studio.js:64`). `openDesign`, Home, and My designs all await `persist` before opening anything (`:115,149,156`), so the same conflict blocks the offered recovery route. No conflict-specific keep-copy/reload/discard dialog is implemented there. At widths at or below 780 px, `.save-status` is hidden (`W/studio.css:14`); generic error toasts expire after seven seconds (`W/studio.js:37`). Server-side persisted designs and `beforeunload` protection for dirty/saving state are positive foundations (`:330`).

**User impact.** Both personas may be unable to follow “reopen” without refreshing and discarding local work. A mobile user can miss the transient error and later assume the design was saved.

**Desired interaction/copy.** Show a persistent conflict banner: **“Another window saved a newer version. Your unsaved changes are still here.”** Actions: **Review differences**, **Save my draft as a copy**, **Reload saved version**. Reload should explicitly disclose discarding the local draft and bypass retrying the conflicted save. For offline failure: **“Not saved on this computer yet. Retry save.”** Preserve status on narrow screens in a compact visible form. Persist a bounded recoverable local draft if appropriate, separately from authoritative saved results.

**Acceptance.** In two tabs, edit the same design in both and save A before B. B must retain its draft, offer a usable reload/copy path, and never overwrite A silently. Repeat with server unavailable during autosave, restoration of connection, and browser refresh. Saved history remains exact. At 390 px, unsaved/saving/error/recovered state remains visible after the toast expires. Declining any discard keeps the draft.

### UX-06 / P2: the default guided route does not teach the visible v4 application

**Evidence: direct source finding and static first-use heuristic.** Home prioritizes Try the guided example (`W/studio.js:71`). Both guided creation and Open four-cell example omit `mission` (`:118,238`). The backend assigns a 12 A parallel benchmark when mission is absent (`B/store.py:304-314`). `application_view` returns `None` without a mission (`B/loads.py:128-131`), so the explanatory application record and load block are absent. New design instead defaults to the Pi 5 25 W / 10 minute mission (`W/studio-mission.mjs:11`) highlighted in v4 and the submission slide.

**User impact.** The student follows the most prominent route and sees a different problem from the pitch. The engineer may spend time reconciling 12 A versus the application's derived current. This does not mean the 12 A benchmark should be removed.

**Desired interaction/copy.** Make the default guided example **“Pi 5 backup: 25 W for 10 minutes”** with the same mission contract as New design. Keep the harder benchmark under **“12 A stress example”**. On the first Test screen show one compact sentence: **“We approximate this 25 W load with 8.42 A at the battery, using an assumed 90% converter efficiency and 3.3 V floor.”** Preserve the detailed sourced/assumed/custom table below it. Explain starting charge, cell temperature, and cooling as separate assumptions.

**Acceptance.** From fresh first-use state, the guided CTA produces the same mission, application label, load block and baseline settings as the corresponding new-design preset. A participant can state the next action and identify the load and two assumptions without opening AI. The 12 A example is explicitly labelled a stress condition. Changing any preset value updates its basis to custom.

### UX-07 / P1: comparison hides some mismatch signals; P2: three-option decision is fragmented

**Evidence: direct source finding.** The backend comparison returns `model_versions_match`, `solver_versions_match`, `requirements_match`, design/settings changes and duration status (`B/store.py:449-464`). The displayed notice is only its `note`, generated from settings equality, plus duration mismatch (`W/studio.js:86`). Matching settings can therefore say “Same test settings” even with a model/software difference; those flags do not get their own visible status. Test selection labels are name-only, without date/version/current status (`:84`; `W/studio-state.mjs:44`), so repeated identical test names are hard to disambiguate. Comparison accepts two tests; the sizing table does show multiple counts and qualifications (`W/studio-mission.mjs:69-73`). The product therefore has a route to 4/3/2 comparison, but no single saved three-option decision view linking its evidence and explaining common conditions.

**User impact.** The working engineer can attribute a delta to a design while models or requirements also changed. A student may choose unrelated saved runs because the selectors offer the global test list. Repeating pair comparisons imposes memory work on a brief that asks for two alternatives against baseline.

**Desired interaction/copy.** Always show **“Same load and duration / preparation changed / model differs / requirements differ / partial duration”** as separate readable statuses. Expand changed assumptions by default when they prevent a controlled comparison. Use labels such as **“4-cell baseline · 10 min, 8.42 A · 31 Oct 13:10 · earlier version”**, with exact IDs available in details. Keep pair comparison, and add **“Compare 4, 3 and 2 cells”** from a completed sizing study with baseline pinned, common conditions stated, per-option status, cost/mass/current/voltage margin, and a short conditional recommendation. Do not automatically declare every smaller design better.

**Acceptance.** Compare a baseline with each of: changed load, cell starting charge, cooling, requirements, model version, solver version, and a stopped run. Each mismatch appears before the deltas and is represented in the exported decision. Comparing 4/3/2 cells from one study shows all three under the recorded load and identifies intentionally changed cell-count/wiring assumptions. Repeated equal run names remain uniquely understandable without exposing raw backend IDs in the main selector.

### UX-08 / P2: numerical completion, target checks and model limits need one concise interpretation near the verdict

**Evidence: static interpretation risk, not a claim of a false safety-pass implementation.** The four verdict rows use checks for full backup time and configured minimum voltage, and label temperature “Rough estimate” (`W/studio-mission.mjs:46-59`). Missing voltage correctly reads “No target set.” `targetChecks` disappears entirely when no checks exist (`W/studio.js:82`). The underlying assessment records `physical_clearance=False` (`B/network.py:434-437`), while qualification is scoped to the evaluated parallel arrangements (`B/failure_search.py:9-10,47-54`). Failure investigation distinguishes model boundary, component limit, design target and protection; that distinction should remain. The top phrase “Where does it break?” can still prime a novice to interpret a model-domain stop as a battery failure.

**User impact.** A student may generalize a green service/voltage check into “this battery is safe,” or a model boundary into “the cell failed.” The engineer needs the precise conditional meaning before carrying a result into a recommendation. Existing simulation labels and detailed disclaimers reduce this risk but do not eliminate the comprehension question.

**Desired interaction/copy.** Under the verdict: **“Calculated service met for this saved test. [N] design targets checked; [N] not set. Hardware acceptance is not assessed.”** For the thermal output retain an explicit estimate label and link directly to the selected run's evidence limitations. Rename or subtitle the investigation **“Find a design limit or model boundary.”** For a domain stop use **“Calculation stopped at the model's supported boundary; this is not a measured battery failure.”** Preserve the last supported time and give **Review supported range** / **Open case** actions. For an unset target say **“Set a target to assess this requirement”**, never pass.

**Acceptance.** Exercise no targets, voltage-only target, electrical-only custom cell, domain stop, preflight refusal, protective disconnect, and a completed nominal case. Distinct states remain distinguishable in text, not only color. In the real-user protocol, ask what the displayed check proves and what it does not; record answers without coaching. No user-study success is claimed here.

### UX-09 / P2: AI availability is not represented before a request

**Evidence: direct source finding.** The copilot reports `available`, provider and last error (`B/copilot.py:49-53`). The panel always draws a status dot styled green and uses “Local account connection” when provider is absent (`W/studio.js:93`; `W/studio.css:10`). The Home prompt remains an ordinary invitation. Errors appear only after asking. The walkthrough permits Skip step, which is a useful escape route (`W/studio.js:235`).

**User impact.** A first-time student may read the green dot as a working AI connection. An engineer can lose time composing a request before learning that local inference is unavailable. This is not evidence that the AI itself is fake: real provider calls, bounded saved-test context and approval logic exist in source.

**Desired interaction/copy.** Bind the indicator to actual capability: **“AI unavailable on this computer. Connect a supported local account to use it; you can continue building and testing.”** Preserve drafts on transient failure, provide Retry, and distinguish unavailable, busy, quota error and answered states. Keep the AI step optional for completing the guided non-AI workflow. When available, show exactly which saved test/comparison the request will include before sending.

**Acceptance.** With an unavailable-provider fixture, no green connected indicator appears and no external request is attempted. The user can continue the example and export. With a failed-response fixture, the prompt remains recoverable. A stale response never attaches to the new design. Preview/apply behavior remains separately verified as in UX-02. No real provider call was made for this review.

### UX-10 / P2: exported evidence is stronger than the visible save/export story

**Evidence: source and visual heuristic.** Designs persist in the server's local store; browser storage is used for walkthrough state (`W/studio-walkthrough.mjs:13-19`). On page startup no last-open design is restored (`W/studio.js:331`); Home offers recent designs. Export sends the selected test and downloads a generic `volt-forge-experiment.zip` (`:223`). The package contains report HTML, exact experiment, models, CSV, evidence and replay code (`B/store.py:552-586`). The UI gives a short toast but does not present an export contents/read-first panel. There is no evidence in this review of a general ZIP-to-project reimport flow; numerical replay and reopening a saved local design are different tasks.

**User impact.** The student may not know where work lives after refresh; the engineer may confuse a reproducibility bundle with a portable editable project or overwrite similarly named downloads. These are discoverability limits, not proof that saved designs disappear.

**Public-runtime qualification.** The handoff's explicit tab-close loss claim creates a separate recovery question for the public demo. Confirm which save wording the public shell actually displays and whether a durable project/export recovery path exists. If that runtime is intentionally temporary, say **“Temporary browser session. Export before closing this tab”** prominently and accurately. Do not show the local “saved on this computer” promise unchanged for volatile work. This public behavior was not inspected by this reviewer.

**Desired interaction/copy.** Keep Home's local-save statement but specify **“Saved by this running workspace on this computer”** and expose last-open design/test with a Resume action. Export confirmation should say **“Saved test: [name/date]. Open report.html to read; results.csv for data; replay.py reproduces this calculation.”** Use a safe readable design/test/date filename. State whether editable-project import is supported; do not promise reopen-from-ZIP unless implemented. Give a separate project-backup path if portability is required.

**Acceptance.** On the local server, save a design, run it, refresh, close/reopen the browser, and restart the server on the same workspace. Reopen the same design and saved test with exact values. Clear/deny browser localStorage: saved designs still reopen while only walkthrough convenience may reset. Separately exercise public-demo refresh/tab-close/reopen against its actual storage contract, with no assumed disk persistence. Export an explicitly selected old test and verify the bundle is that test, not the current design. The read-first instructions distinguish report, replay, and editable-project recovery.

## Task and edge-case coverage ledger

This is a review map, **not a test-pass report**. No row below has been interactively executed by this reviewer.

| Task / edge case | Student emphasis | Engineer emphasis | Static evidence / pending confirmation |
| --- | --- | --- | --- |
| First open and start | Guided next action, terminology | Visible application and scope | Guided steps exist; route differs from Pi preset (UX-06). Confirm first-use overlays never obstruct primary actions |
| Choose application/load | Amps vs watts explanation | Approximation, efficiency/floor provenance | Three-step setup and sourced/assumed/custom rows exist. Confirm edits and multi-interval custom cycles retain truthful mission wording |
| Edit supported cell/link | Recognizable cell, units, feedback | Named endpoints, source, supported range | Cell illustration, integrated/custom models, direct/dimensioned conductors exist. Empty/invalid draft semantics require UX-01 |
| Run and understand warning | Predict then inspect | Owner, completeness, model coverage | Run captures design/context; inline Test errors exist. Confirm zero-sample refusal and old-result presentation after failed rerun |
| Compare 2/3/4 under common conditions | More cells vs cost/current/voltage | Baseline plus two alternatives, matching assumptions | Sizing table exists; pair comparison omits some mismatch flags (UX-07) |
| Failure and recovery | Model boundary is not physical failure | Identify component, condition, time and requirement | Case highlighting/opening, finite scope and resume exist. Confirm no-limit versus unconfigured wording; conflict recovery UX-05 |
| Save, refresh, reopen | Find my work | Exact saved version/result | Disk store and recent designs exist; walkthrough-only browser persistence. Execute refresh/restart/blocked-storage checks in UX-10 |
| Stale result ownership | “Earlier design version” meaning | All explanation surfaces share snapshot | Async run/context checks exist (`W/studio.js:130,136-140`); historical model dialog violates this boundary (UX-03) |
| Camera/display vs physics | Moving a cell does not rewire it | No invalidation from layout | `samePhysics` removes names/positions; backend `physics` does likewise (`W/studio-state.mjs:45-49`, `B/network.py:39-48`). Confirm identical numerical fingerprint after drag/view change and changed fingerprint after real wire edit |
| Invalid units / empty / nonnumeric | Recover without losing input | No implicit unit or value conversion | Unit labels and native validity present; blank conversion defect UX-01. Confirm paste/blur/navigation behavior, not only backend API rejection |
| Model domain / unset assumptions | Supported range explained | Unset and unsupported never qualify silently | Input model bounds, preflight, domain stops and qualification states exist. Confirm boundary values and thermal-data absence in UI and report |
| Plot keyboard / phone viewport | Exact saved value without hover | Event side and quantitative inspection | Native slider, SVG selection, focus styles and reduced-motion rules exist; exact-value path UX-04. No live 390/768/1024/1440 px layout claim |
| AI unavailable / preview / approval | Honest availability; easy continuation | Exact context and complete diff | Real AI path exists; fixture-only tests needed for UX-02 and UX-09. No provider was invoked |
| Misleading pass language | Explain what a check means | Conditional recommendation | Simulation/rough-estimate labels exist; enhance near-verdict unconfigured/model-boundary summary (UX-08). No blanket accusation of a safety badge |

## Visual review of the supplied slide images

Slide 1 is an event/team cover. Slide 2 gives an identifiable application, an actual circuit/inspector screenshot, a four-cell versus two-cell comparison, a measurable decision, and prominent simulation assumptions. This is a useful product story. The screenshot's quiet light shell, named cells, blue selection and generous circuit area broadly respect the design guide's canvas-first intent. It does not require mimicking the concept's elaborate exploded 3D assembly.

At the supplied image scale, the surrounding body paragraphs and small metric tables compete for attention. The sentence “Same 25 W job” is a useful orientation cue; the two screenshots should continue to carry the action/result story. For the official baseline-plus-two-options requirement, a compact **4 / 3 / 2 cells** row showing cell count, voltage margin, peak current, listed cell cost/mass and qualification would make the third option visible rather than only stated in prose. Keep the conditional 90% converter / 3.3 V floor and simulation status adjacent to the recommendation, not only in the bottom strip.

The exact counts, validation comparisons, cost/business figures and broader scientific conclusions on the slide are not independently verified by this UX review. The statement that students cannot afford alternatives and engineers cannot wait is a desirability hypothesis until supported by research; do not convert this simulated review into evidence for it. The slide is user-owned, and no slide changes were made.

## Ethical 20-minute real-user protocol

Recruit actual participants separately from this report: a small formative set from each persona (for example, 3-4 students and 3-4 working engineers, disclosed as a convenience sample). This is a plan, not completed recruitment or representative market validation. Use a fresh disposable project, a known local model set and a pre-seeded result for time-limited recovery/comparison tasks. Do not ask participants to connect hardware, enter proprietary designs, supply account credentials, or spend AI credits. If AI must be evaluated, use consented access or a clearly labelled deterministic fixture; never present a fixture answer as live AI performance.

| Time | Moderator task wording | Record |
| --- | --- | --- |
| 0:00-2:00 | Explain: “We are testing the interface, not you. These are simulated results. You may stop at any time.” Obtain recording consent separately, explain storage/deletion, and collect only relevant experience | Persona/experience; consent. No identifying workplace/client data |
| 2:00-4:00 | “You want to explore a battery for a ten-minute Pi gateway outage. Start wherever you would naturally start. Tell me what you think will happen next.” | First action, time to useful design, help needed, stated application/assumptions |
| 4:00-7:00 | “Inspect one cell and one connection. Make one meaningful change and run a test. Explain whether moving the drawing would have made the same change.” | Selection/edit/run completion; unit interpretation; accidental edits; drawing/physics understanding |
| 7:00-10:00 | “Find the cell carrying the largest current. Use the keyboard to inspect the values immediately before and after this saved load change. Explain the warning shown.” | Exact values/event sides found; keyboard barrier; model-boundary versus physical-failure interpretation |
| 10:00-14:00 | “Compare the 4-, 3- and 2-cell options for the same backup job. Which would you investigate next, and which assumptions could change your choice?” | Chosen baseline/options; common-condition recognition; current/voltage/cost tradeoffs; conditional reasoning, without judging one preset answer as universal |
| 14:00-17:00 | “Open the affected case and show how you would investigate an improvement. Now recover from this prepared save conflict or connection failure.” | Affected part/condition/requirement located; recovery path; lost draft; help required. Use one prepared failure, counterbalanced across participants |
| 17:00-19:00 | “Export the evidence you would share. Refresh, reopen your design and find the test you exported. Review this prepared AI proposal; explain what applying it would change.” | Selected export identity, read-first discovery, saved-state confidence, full-diff comprehension; no live provider call required |
| 19:00-20:00 | “What does this result let you conclude? What would you still need before building hardware? Which one change would most help you?” | Verbatim consented responses, unsupported confidence, highest-friction issue; optional single ease/confidence rating with its scale recorded |

Use neutral prompts; do not point to the desired control before recording an unassisted attempt. Mark completion as unassisted / assisted / not completed, record elapsed time per task and critical misinterpretations, and separate interface failure from incorrect task setup. Record the exact build, viewport, input device and fixture. Stop a task after its allotted time and move to the seeded state so one blockage does not erase later evidence. An observer may take notes; do not invent quotations from memory. Report denominators and raw task outcomes, not a statistically generalized conversion/satisfaction claim from a small sample. Do not treat successful simulation navigation as proof of engineering expertise or hardware safety.

Success criteria for the product, set before the session: no accidental physical mutation from blank input; correct old/current test identification; keyboard access to both event sides; recovery without silent data loss; and an explanation that separates simulation completion, configured targets, model support and hardware evidence. Use participant outcomes to prioritize refinement, not to retroactively select only favorable tasks.

## Next frontend sprint

Keep the current canvas, SVG assembly/circuit and backend numerical authority. Implement and review these bounded changes in order:

1. **Input and recovery integrity:** UX-01 and UX-05; explicit valid/draft/unsaved/conflict states, persistent narrow-screen status, non-destructive recovery. Reuse server version checks rather than bypassing them.
2. **One saved-test context across explanations:** UX-03 and mismatch presentation in UX-07; model cards, result labels, AI context and export must agree on the selected saved test.
3. **Exact sample inspection and approval preview:** UX-04 and UX-02; persistent accessible sample table and readable complete backend diff. Use deterministic fixtures for proposal tests.
4. **Application-led first use and truthful capability:** UX-06, UX-08 and UX-09; guide the Pi mission, retain stress examples, explain only the relevant assumptions/limits, bind AI status to availability.
5. **Reviewable decision and handoff:** a small 4/3/2 summary from existing sizing records plus UX-10 export/resume copy. Do not substitute a dashboard or a recommendation unsupported by the stored results.

Definition of done: run the acceptance scenarios above on the isolated build, capture fresh screenshots at desktop and 390 px, complete a keyboard-only saved-sample path, verify conflict/refresh/reopen against the real local store, and match every displayed/exported result to its saved identity. Then conduct the real-user protocol and report its actual outcomes. Existing test receipts or this static review alone do not satisfy that definition.

Do not expand this sprint into photorealistic 3D, CAD, CFD, manufacturing export, a frontend framework migration, or removal of supported v4 features based on the older guide. Clear inputs, honest model context and a recoverable comparison loop have higher submission value.

## Live-observation status and handoff boundary

The parent reviewer reported that the browser host was unavailable and that automatic approval review rejected binding to an unrelated native browser target because it could expose private messages. No workaround was attempted by this reviewer. **There are no verified live browser observations in this report.** All interaction consequences remain source-derived or explicitly heuristic; the supplied slide/concept images are the only visuals assessed. This limitation is a reason to execute the listed manual checks, not to label them passed or failed in advance.

No previous audit findings were used. This reviewer wrote only this new report and, when separately requested, the reusable `prompts/03_USER_EXPERIENCE_FRESH_SESSION.md`. No claim of a real user trial should be added without actual participants and records. Writes stop at handoff.
