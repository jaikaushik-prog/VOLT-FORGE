# Evidence and edit-preview panel

The existing local four-cell editor now exposes the implemented evidence
contract. It reads the selected component, design revision and saved run;
shows assumptions and citations; and previews supported edits before a separate
manual Apply revision action. It does not invent physical results, call a
language model or execute an optimizer. The LG M50T 1s4p ladder and frozen v2
models remain the editor's electrical system.

The parallel [reference-origin investigation](../p45b_reference_origin_v1/DECISION.md)
is complete with no new model adopted. More P45B fitting is paused pending
per-record physical-cell/preparation mapping, traceable charge history and
reference-axis compatibility evidence. Conditional published-model reproduction
remains available. No P45B component was substituted into the LG workspace.

## Open and use the workspace

From the repository root:

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\run_editor.py --open
```

Open `http://127.0.0.1:8765` if the browser does not open automatically. Working
projects stay in ignored `workspace/editor_project`. Existing projects and
previous runs are retained.

1. Select A0 and a cell or connection. Open **Evidence**. Without a selected
   run, the panel shows configuration evidence and no simulated output.
2. Click **Run simulation**. The panel can now show saved module outputs,
   selected-component samples, initial-state assumptions, fitted parameters,
   requirements, coverage and exact source references.
3. Expand **Source details** to inspect the backend field, revision, run,
   snapshot and context identity. Displayed scalar numbers use up to six
   significant digits; the expandable exact record preserves full values.
   Selected samples are paged evidence, not a complete waveform assessment.
4. Create a named variant. Select a rail, change its proposed resistance and
   click **Preview change**. The inspector shows current and proposed inputs,
   provenance, and which owned runs would become outdated. It calculates no
   predicted improvement and writes nothing to the project.
5. Click **Apply revision** to save the edit. The context is checked again
   immediately before applying. The run button is a separate action. Existing
   Compare and Export results controls retain their original backend contract.

Changing an edit, component, run or variant invalidates the captured preview.
Changing and then reverting a field still requires a new preview. A concurrent
design change rejects the old preview. An inherited run stays historical under
its owning variant. Keyboard/display moves change selection and layout without
changing the physics revision or making a current run outdated.

## Result and evidence states

| State | What the panel says and does |
| --- | --- |
| Configuration only | Inputs, fitted models and evidence; no saved numerical output. |
| Completed/current | Saved output tied to its immutable run/snapshot; current dependencies do not establish experimental accuracy. |
| Historical/outdated | Explicit historical label and reasons; current design inputs are labeled separately from saved output. |
| Failed/partial | Exact solver stop reason and partial-output limitations; never reported as completed service. |
| Stale/malformed/unavailable | Read-only error and Refresh evidence action; no mutation or substituted result. |
| Requirement unset | **requirement not configured**; never a pass. |
| Unsupported design decision | **insufficient evidence**; experimental module validation remains awaiting suitable measurements. |

Current, charge, SOC, voltage, power, energy and electrical losses are saved
solver results. Electrical losses do not predict temperature. Fitting amplitude
coverage does not establish sustained-load or waveform accuracy. Changing a
resistance remains hypothetical until its physical implementation is established.
The earlier illustrative 3.50 V alarm and 25 mV budget were not installed as
requirements.

## Frontend and HTTP handoff

- [evidence-panel.mjs](../../web/editor/evidence-panel.mjs) renders the panel and
  manages transport; it does not calculate physics.
- [evidence-state.mjs](../../web/editor/evidence-state.mjs) checks response
  shape, exact selection/edit identity, source citations, units and async epochs.
- [HTTP_CONTRACT.md](backend/HTTP_CONTRACT.md) documents the two real local
  POST routes, session/origin controls, read-only behavior and exact errors.
- The frozen [context interface](../backend_context_v1/INTERFACE.md) and
  [copilot contract](../copilot_contract_v1/README.md) remain unchanged. Future
  conversational AI can produce structured proposals against this boundary;
  it must obtain outcomes from the backend.

The browser JSON roundtrip changes Python `1.0` to JavaScript `1`. An HTTP-only
bridge rebuilds the authoritative context and checks every value before passing
that exact server context to the unchanged contract. Only exact finite numeric
equivalence is allowed, with no tolerance; booleans, changed hashes, one-ULP
changes and unsafe integers remain rejected. This fixes browser transport
without relaxing the frozen contract or trusting browser evidence.

One frozen preview field, `simulation.dt_s`, has no unit in its original
numeric before-claim. Only the exact supported schema field receives a display
unit of seconds. Source details explicitly disclose the schema-derived unit
and retain the untouched original claim. Arbitrary unitless numeric claims
still fail validation. Resistance, SOC and polarization quantity objects retain
their recorded units. No unit conversion or physical value adjustment is
performed by this evidence adapter.

## Verification and preserved history

The complete current Python suite passed **387 tests**, including **46 real
HTTP/server checks** and the new **26 reference-origin checks**. The separate
JavaScript suite passed **22 tests**. See [pytest.xml](pytest.xml),
[backend receipt](backend/verification.json) and
[Node receipt](node_tests_final.txt). These are software verification counts,
not independent experimental validation.

The [real-browser receipt](browser_005/verification.json) covers a full reference
run, configuration/current/historical/failed evidence, component identity,
late-response handling, keyboard layout, byte-preserving previews, stale-context
rejection, manual apply without automatic run and escaped untrusted provenance.
Screenshots cover 1920, 1440, 1024 and 390 pixel widths. Browser projects use
isolated temporary profiles and synthetic fault edits; no protected experimental
outcomes are opened. The extreme-load fixture exists only to exercise a failed
run, not to represent a supported operating condition.

Failed attempts are retained: browser_001 could not start Chrome under the
sandbox; browser_002 exposed the number serialization problem; browser_003
exposed long-citation phone overflow; browser_004 exposed the timestep preview's
missing original unit. Each issue was resolved before the final check.

The [plan](PLAN.md) and five living-file copies were frozen in commit
`350a953` before the new electrical analysis. The
[preservation map](preservation_map.json) pins their previous bytes. The new
verifier checks historical frontend hashes against those explicit archived
versions and current frontend files separately. It does not replace historical
receipts, numerical sources or measurements. All 114 artifacts in the preceding
parallel-release receipt are checked. The earlier numerical/provenance chain,
new reference-origin outputs and current HTTP/browser evidence are also checked.

Raw data, sealed v1/v2/published P45B artifacts, nine unused LG cells, 48 unused
P45B members / 40 families, the charge table/validation workbook and 13 unused
FreeTwinEV records are preserved. No outreach was sent. No private source PDF
is included in the release.

## Reproduce checks

Use fresh output paths; saved reports are not overwritten. The editor and
synthetic tests use reference assets. Full numerical/provenance verification
also requires the already-downloaded locked measurement files locally.

```powershell
$env:PYTHONPATH = 'src;scripts'
& C:\Users\DELL\anaconda3\python.exe -B -m pytest -q --junitxml=tmp/evidence_panel_tests.xml
& 'C:\Program Files\nodejs\node.exe' --test tests/evidence_state.test.mjs tests/editor_state.test.mjs
& C:\Users\DELL\anaconda3\python.exe -B scripts\check_evidence_browser.py --out tmp/evidence_browser_check
& C:\Users\DELL\anaconda3\python.exe -B scripts\verify_evidence_panel.py --browser reports/evidence_panel_v1/browser_005 --out tmp/evidence_panel_verification.json
```

The browser check uses an isolated installed Chrome and `websocket-client`.
It starts and closes its own loopback server. Pass `--chrome` if the executable
is elsewhere. [verification.json](verification.json) records the checked
release hashes; use the final command above to independently recompute the
checks without altering it.

## Next engineering action

The frontend can now connect users to real saved evidence and reviewed edits.
The next product milestone is a focused walkthrough of configure, preview,
apply, simulate, compare and export, followed by usability fixes. A future
conversational layer should be evaluated against these same deterministic
claims and manual-action boundaries before integration.

The model cannot be made experimentally complete by more interface work or
continued fitting to the same uncertain records. Seek existing documentation
for the preparation/reference links named in the electrical decision. If it
does not exist, retain conditional predictions and obtain suitable new evidence
before module accuracy, voltage-limit or repair-benefit claims. The independent
module-current discrepancy remains unresolved.

For a student: the workspace can now show both a simulation and where its
numbers came from. It can help compare declared assumptions. It cannot yet
prove a real four-cell pack is safe or that a proposed change improves battery
performance. The next physical step is evidence about starting state, reference
voltage and synchronized module measurements, not another guessed parameter.
