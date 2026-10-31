# Round 1 improvements implemented in V4.1

31 October 2026. Base commit `5cfb62c5ed146bda4b84b30e634f5e9dfb3fb047`. The implementation follows the independent review while preserving the fitted models and frozen studies. It improves qualification, accounting, recovery and interpretation; it does not improve or validate physical battery performance.

## What changed

| Review issue | Implemented behavior | Verification |
|---|---|---|
| E1: missing custom-cell limits could qualify | Sizing requires applicable voltage/current/temperature limit coverage for each branch's actual current direction, including internal charging during module discharge | Synthetic missing/complete/exceeded limits, charging circulation, missing thermal support and saved-investigation cases |
| E2/E3: count-only board selection and incorrect source transfer | Listed boards are candidates screened against topology, holder/model compatibility and declared output demand. Unpublished battery-current, charge, efficiency and protection behavior stays unassessed | Series/mixed/custom/unsupported counts, excess output demand, charge-path caveats and malformed inputs |
| Stale power labels after editing a current profile | Modified current, voltage-floor or conversion assumptions cannot inherit the old preset's power-based board screening | Direct profile edits, scaled-load investigation and inconsistent power/efficiency/requirement records |
| Invalid mission data could fail after saving | Power/efficiency types, ranges and required records are validated before save/copy/import commits | Malformed mission fixtures leave documents/index unchanged |
| E4: series-count multiplication of charge Ah | Gross received/delivered and net pack-terminal Ah are explicit and versioned. Per-cell charge is separate | 1S, 2S, 2P, mixed topology, reversal and shortened/protected intervals |
| E5: unknown ideal-link current shown as zero | Current and density remain null with an explanation; zero resistive loss stays distinct | Ideal-link/finite-link cases and historical-export labelling |
| UX-01/05: numeric intent and recovery | Mandatory blank values remain unapplied drafts; zero must be deliberate. Drafts survive rerender, block save/run and can be reviewed/discarded or backed up. Save conflicts offer new-copy recovery and explicit reload | Numeric parser/backup tests; real store and loopback HTTP recovery tests. Browser focus/blur behavior still needs manual verification |
| UX-02: incomplete AI preview | Full structured before/after diff and readiness are visible, with Cancel and Apply | Deterministic proposal fixtures, added/removed nested objects and escaping; no provider inference |
| UX-03/07: historical provenance and unfair comparisons | Model explanations and assembly labels use saved model cards. Comparison exposes preparation, model, software, requirements, thermal and duration differences | Historical-model tests, missing-card handling and mismatch rendering |
| UX-04: hidden keyboard values | A persistent sample table and event navigation expose exact saved values and pre/post event sides for the same sample index | Pure sample/navigation tests; live keyboard/touch interaction remains untested |
| UX-06/08: demo and verdict comprehension | Guided entry uses the Pi mission. Result copy separates executed service, configured targets, missing limits and hardware acceptance. 4/3/2 summary uses cell-only cost and actual available cases | Mission, verdict, missing-case and cell-cost rendering checks |
| UX-09/10: provider/persistence/export clarity | Unavailable or configured-but-unverified AI is explicit. Local disk and temporary browser sessions have different copy. JSON design backups import as new designs; result ZIPs remain report/replay packages | Runtime/API metadata tests, no-provider request guard, backup isolation and historical charge semantics |

The optional public AI configuration request is bounded to two seconds and cannot indefinitely hold manual startup, including when a request or JSON body stalls. It sends no prompt and returns no credential. This work does not activate an AI account or make a provider call.

The frontend keeps the existing assembly/circuit, inspector and results views. It adds a compact context and recovery area, accessible tables and comparison notices. It does not replace the framework, add 3D CAD, or invent temperature contours. The actual UI still needs an interactive visual check: the browser automation host was unavailable, and no unrelated private browser window was accessed.

## Slide and evidence

The separate [revised one-page submission PDF](../slide_round1_review_v1/VOLT-FORGE_Round1_Reviewed_Draft.pdf) makes the 4/3/2 comparison legible, qualifies the two-cell candidate, separates 15/15 numerical checks from all 12 missed comparison cases, and reduces commercial claims to an explicit teaching-lab hypothesis. It uses frozen study data and an identified original V4 editor image. It does not imply that this software revision reran the full design study or produced fresh physical evidence.

The generator verifies all 13 input files against the pinned study source, records source selectors/hashes, renders the page and checks required text. [Visual QA](../slide_round1_review_v1/VISUAL_QA.md) records inspection at normal size. The original PDF, cover, slide source and study outputs are unchanged. The team must still confirm portal format/cover requirements; nothing has been submitted.

`PRESERVATION.json` records 649 pre-existing tracked reports, configurations and the runtime lock. `verify_review_improvements.py` checks their bytes against the baseline. The original audit package is included in that protected set. No raw measurement channel, unused characterization cell or protected assessment signal was reopened for model development. Constitutive equations and fitted model values were not tuned.

New simulations carry the new software hash in `verification.json`; old saved experiments retain their original source/model identities and quantities. Historical aggregate cell-Ah and ideal-wire-current semantics are explained on display/export without rewriting those records.

## Checks and their limits

The final machine-readable counts are in [verification.json](verification.json), with Python and JavaScript JUnit receipts beside it. Python checks include the full existing suite and new regressions, including real loopback HTTP/store recovery. JavaScript tests exercise numeric drafts, snapshot context, complete previews, sample navigation, comparisons, metadata and unavailable-provider behavior. They are not DOM/browser or real-user tests.

Final result: **515 Python checks and 71 JavaScript checks passed; 8 Python checks were skipped because this isolated checkout does not include the original official data archive.** All 649 protected artifact hashes matched. The public package matched 11 frontend assets and the current engine sources. The three manually declared 4-, 3- and 2-cell nominal examples completed their 600-second simulations.

Python was 3.12.3 with the same direct numerical versions used in the review; this Windows environment differs in transitive packages from the full recorded macOS lock. This is tested Windows software, not a claim of a newly sealed full-lock numerical replay. The suite still reports the existing NumPy scalar-conversion deprecation warnings in the synthetic first-law fixture. Some pre-existing optional evidence checks are skipped; no skip is counted as a pass. Detailed skip reasons are in the XML.

The generated public build is checked for current frontend assets, worker/status code and engine source bytes. This is a build/package check, not a live WebAssembly or deployment test. The public site has not been redeployed. The local editor and its new asset/API were reachable over loopback; no cloud provider was invoked.

On Windows, keep working projects and pytest temporary directories short. An initial test attempt exceeded Windows path length because the isolated checkout was nested deeply; the final tests use a short temporary directory. No system settings or snapshot hash lengths were changed to bypass it.

## Reproduce

From this V4.1 repository, with Python 3.12 and the documented dependencies:

```powershell
python -B scripts/run_editor.py --project workspace/my_project --port 8796
```

Open `http://127.0.0.1:8796`. The manual workflow works without an AI provider. Use the guided Pi example, inspect one connection, enter a deliberate resistance, run, inspect a saved sample, create an alternative and compare the recorded conditions. Use **Download design backup** for editable JSON and **Export** for a saved result/replay ZIP.

To create the three manually specified nominal examples in a fresh project:

```powershell
python -B scripts/demo_review_improvements.py --project workspace/review_demo --out tmp/review_demo.json
python -B scripts/run_editor.py --project workspace/review_demo --port 8796
```

Choose unused paths; the demonstration refuses to overwrite them. These are software examples, not new uncertainty studies or automatically ranked repairs. `demo_summary.json` records the demonstration generated during this implementation, including its actual settings and identities.

Run the checks, choosing an unused short test directory on Windows:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -B -m pytest -q -p no:cacheprovider --basetemp C:/path/to/short/new-test-dir --junitxml reports/round1_improvements_v1/python_tests.xml
node --test --test-reporter=junit --test-reporter-destination=reports/round1_improvements_v1/javascript_tests.xml (Get-ChildItem tests -Filter '*.mjs' | ForEach-Object {$_.FullName})
python -B scripts/verify_review_improvements.py
```

For the public package, first create a fresh demo project, then run `python -B scripts/build_public_site.py workspace/review_demo` and `python -B scripts/verify_review_improvements.py --public-build`. Building does not deploy. Recheck a generated slide after any rebuild using its own README instructions.

## Remaining work

1. Complete a live desktop/mobile and keyboard walkthrough: blank/zero input, reload conflict/copy, JSON import, old result inspection, event-side navigation and export/reopen. No browser-test pass is claimed here.
2. Have actual students/engineers perform the short observed task protocol before claiming usability or customer evidence. Generated personas cannot supply this evidence.
3. Obtain actual load/converter/board limits and suitable measurements before relying on the candidate for hardware design. Failed measured voltage/temperature checks, the current-reconciliation uncertainty and assembly-specific thermal assumptions remain limitations.

The next product step is that bounded live walkthrough and any resulting small fixes. Another model-fitting sprint, general CAD editor or new AI optimizer is not required to verify these interface corrections.
