# Local commands are connected; thermal mathematics is a separate prototype

26 October 2026. The user completed the electrical walkthrough, authorized three
parallel agents and chose **local command mode with no external AI calls**.
The existing editor now supports a constrained command workflow. The thermal
workstream provides a standalone synthetic heat-balance implementation and a
source-backed feasibility decision. Frozen LG v2 and published P45B electrical
models remain unchanged; no unused measurement outcome was opened.

## What now works

| Workstream | Implemented | Limit |
| --- | --- | --- |
| Local assistant | Help, saved-evidence explanation, explicit rail/SOC/polarization/timestep preview and explicit two-run comparison | Fixed grammar; no language model, free-form reasoning or automatic execution. |
| Editor handoff | Dismissible/resizable command sheet, exact selection binding, inspector review, manual apply and separate run | No arbitrary topology, fitted-parameter, requirement, thermal or load changes inferred from text. |
| Backend | Guarded read-only HTTP route, source references, stale-state rejection, comparison conditions and export/replay demonstration | Software correctness does not establish module accuracy. |
| Thermal prototype | Exact one-node heat balance, signed heat/energy accounting, explicit synthetic inputs, plots and replay | No real-cell applicability, electrothermal coupling, spatial temperature or safety prediction. |

The new command interface wraps the existing deterministic evidence/preview
contract and actual Project.compare implementation. It performs only declared
input-unit conversions; it never calculates physical outcomes from prose.
Unknown requirements stay **requirement not configured**. Module acceptance
and repair-benefit decisions remain **insufficient evidence**.

## Try the implemented commands

Run from the repository root:

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\run_editor.py --open
```

Open `http://127.0.0.1:8765`, then use the **Commands** button. The sheet starts
closed and can be closed using its close button or Escape. Desktop resizing is
purely visual. It does not invalidate physics results.

| Preparation | Complete command |
| --- | --- |
| Any implemented component selected | `help` |
| Explicit saved run selected, or configuration-only view | `explain this result` |
| Positive rail 1 selected | `preview change positive rail 1 to 0.5 mOhm` |
| A rail selected | `preview change selected rail to 0.5 mOhm` |
| A cell selected | `preview selected cell SOC to 69.5%` |
| A cell selected | `preview change selected polarization to -5 mV` |
| Module selected | `preview change timestep to 0.5 s` |
| Two runs explicitly selected in the existing Compare tab | `compare selected runs` |

All example values are syntax examples, not measurements or recommendations.
Keywords ignore case; engineering unit symbols retain their meaning and case.
Missing units, unsupported syntax, compound commands and target-selection
mismatches are rejected. The [interface](../local_assistant_v1/INTERFACE.md)
documents the full grammar and exact Python/CLI request format.

For an edit, **Review request** first returns the old/proposed input, sources
and invalidation information. **Review in inspector** checks that context again
and transfers the exact edit to the existing inspector. It still writes nothing
to the project. **Apply revision** is the separate explicit mutation, and
**Run simulation** is a separate action again. A command cannot invoke either.

Changing the command, selected component, variant, revision, run or comparison
pair discards the corresponding response. Delayed responses cannot replace a
new selection. Changing and reverting a command during inspector revalidation
also cancels the old handoff. A concurrent external revision rejects a stale preview. The
historical/current, failed/partial and unset-requirement distinctions remain
available in explanations and source records. Pure display movement does not
change the physics revision or saved run freshness.

The command sheet summarizes saved module metrics, with selected-component
evidence available through **Open full evidence** and the exact source record.
It does not claim to infer physical causes or invent an explanation for thermal
behavior. Comparisons retain both owners, viewed variants, snapshots, statuses,
declared conditions and source pointers. Display rounding does not alter stored
values; summary values use up to six significant digits and compact comparison
cells up to four. Exact values remain expandable.

## Reproducible integration demonstration

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\demonstrate_local_assistant.py
```

This verifies the saved demonstration. To create a new complete demonstration,
choose a fresh path:

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\demonstrate_local_assistant.py --out tmp/local_command_demo
```

The [saved result](../local_assistant_integration_v1/backend/demo_002/result.json)
contains 12 passing workflow checks and **133 claims/references checked against
actual backend responses**. Both 14.55 A, 360-second A0/A1 exported runs replayed
successfully. The declared A1 change is positive rail 1 from 1 to 0.5 mOhm;
operating conditions are unchanged. Variant creation, apply, run and export
are explicitly recorded orchestration steps standing in for manual UI actions,
never actions executed by the command service.

The unsuccessful first demonstration directory is preserved with its attempted
script and failure note. It exposed a demonstration-helper argument-name
collision after A0 explanation. That helper was corrected before demo_002;
no solver or command-service change was needed.

## Thermal result and remaining physical evidence

The [thermal decision](../thermal_feasibility_v1/DECISION.md) and
[source audit](../thermal_feasibility_v1/SOURCE_AUDIT.md) distinguish actual M50T
literature from the synthetic mathematical example. A published base-to-cap
cooling coefficient does not supply the missing node-to-ambient conductance
for our module. No M50, M50LT, P45B or generic property was silently substituted.

The prototype requires heat capacity in J/K, conductance in W/K, initial/ambient
temperature and a signed prescribed heat profile. Its constant-input intervals
are solved analytically. Electrical resistor losses are not automatically used
as a complete electrochemical heat source. Reversible heat, spatial gradients,
cooling geometry and heat-transfer paths remain outside this implementation.

**39 synthetic tests** cover heating/cooling, zero conductance, transitions,
energy conservation, an independent heat-flow integral and parameter-scale
nonidentifiability. All **242 exported rows** replay; the energy residual is
at most **4.13e-13 J**, and shared temperatures are identical for 10 and 2.5 s
reporting. These checks establish mathematical consistency, not battery accuracy.

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\thermal_prototype.py verify reports/thermal_feasibility_v1/run_001
& C:\Users\DELL\anaconda3\python.exe scripts\thermal_prototype.py run --config configs/thermal_feasibility_v1.json --out tmp/thermal_trial
```

The [plot](../thermal_feasibility_v1/run_001/synthetic_heat_balance.png) is labelled
synthetic. Real M50T heat capacity, module cooling conductance and total cell
heat input remain null in [readiness.json](../thermal_feasibility_v1/readiness.json).
No temperature overlay or thermal control was added to the module editor.

The next external evidence lead is the authors' [public M50T cooling archive](https://zenodo.org/records/6421061).
Only metadata was reviewed. The next engineering task is documentation and file
inventory, followed by a prospective development/assessment allocation if the
heat input, sensor locations, specimen preparation and cooling definitions are
usable. Its laboratory fixture may support a narrower demonstrator; it would
not automatically validate our module. No outreach was sent.

## Verification, sources and preservation

The implementation is split across [local_assistant.py](../../scripts/local_assistant.py),
the [local HTTP adapter](../../scripts/run_editor.py), the
[command sheet](../../web/editor/assistant-panel.mjs) and the independent
[thermal prototype](../../scripts/thermal_prototype.py). Source and contract
ownership follow the [pre-implementation plan](PLAN.md).

Focused checks passed: **73 command-service tests**, **62 HTTP tests including
existing regressions**, **39 thermal tests**, and **27 combined JavaScript
presentation tests**. Counts overlap with the full regression suite rather than
being additive. The full regression suite passes **515 Python tests**.
The [combined Python receipt](pytest.xml) and
[JavaScript receipt](node_tests.txt) record the final suite results.

The [final browser check](browser_003/verification.json) exercises full runs,
command preview/manual apply, stale external revisions, cancellation during
inspector revalidation, late responses, explicit
comparison and unsupported optimization. No browser errors or external AI
calls occurred. Screenshots were reviewed at 1920, 1440, 1024 and 390 pixels.
Both comparison columns and their difference fit the sheet; exact evidence is
expandable. The first successful functional browser run is retained; its
comparison table required horizontal scrolling, which was improved before the
final screenshots. No project data was altered by that presentation change.

Four living files were preserved before editing in
[preservation_map.json](preservation_map.json). The new release verifier checks
all **88 artifacts** from the preceding release using those exact archived
versions for changed living files, then rechecks the earlier numerical and
provenance chain. Current source files and agent receipts are checked separately.
No old receipt or historical test failure was edited to make verification pass.

Frozen v1/v2 and published P45B models, nine unused LG cells, 48 unused P45B
members, the protected charge table/workbook, 13 unused FreeTwinEV records,
raw data and module assessment outcomes remain preserved. The unresolved
module-current discrepancy and P45B preparation/reference limitation remain.
The user's local Product Vision PDF and original downloaded archives are not
included in the Git update.

```powershell
$env:PYTHONPATH = 'src;scripts'
& C:\Users\DELL\anaconda3\python.exe -B -m pytest -q --junitxml=tmp/assistant_thermal_tests.xml
& 'C:\Program Files\nodejs\node.exe' --test tests/assistant_panel.test.mjs tests/evidence_state.test.mjs tests/editor_state.test.mjs
& C:\Users\DELL\anaconda3\python.exe -B scripts\check_assistant_browser.py --out tmp/assistant_browser_check
& C:\Users\DELL\anaconda3\python.exe -B scripts\verify_assistant_thermal.py --out tmp/assistant_thermal_verification.json
```

Use fresh output paths. Browser checks require installed Chrome and
websocket-client and use an isolated temporary profile. Full historical
verification requires the existing locked downloads locally. Local commands,
synthetic thermal checks and the reference demonstration require no API key or
new experimental downloads. [verification.json](verification.json) pins the
completed release's source/output hashes.

For a student: commands now help you use the electrical workspace and inspect
where its numbers came from. The thermal prototype shows how a simple object
responds to specified heat and cooling. We still need applicable battery data
before calling those temperatures predictions for this pack. Qualifying the
public M50T thermal archive is the next physical-model milestone.
