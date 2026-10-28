# Round 1 feature freeze

User decision, 28 October 2026: retain the current V2 product workflow and prioritize the backend, scientific correctness and evidence for Round 1. Baseline snapshot: `8ba2037e5eb141ff3f831e1c36df16151480a3db` on the public `v2-studio` branch.

The current studio, modular wiring, Build / Test / Results workflow, AI copilot, charts, guided experiments, comparison and export form the Round 1 feature baseline. Interface work in this phase must serve correctness, the model catalogue or the interpretation of results. Preserve the clean professional design and contextual panels.

Two additional features were explicitly approved by the user on 28 October 2026:

- Custom cell creation and reuse, with a compact basic electrical-estimate flow and optional import of supported declarative model data. User-provided properties do not inherit built-in manufacturer limits or independent validation. Automatic model fitting from arbitrary data is outside this addition.
- A short interactive first-use walkthrough over the real example, Build / Test / Results, comparison, AI and export. It must be skippable, replayable from Help and protective of existing user work.

These additions are required Round 1 scope and remain planned until implemented and checked. They do not authorize a broader UI redesign, general CAD, manufacturing exports or an automatic scientific-model training platform.

The next authorized engineering work is to replace arbitrary global temperature restrictions with evidence-based model applicability, introduce temperature-dependent behaviour using traceable parameters, and add battery types with their own model data and geometry. These changes must retain earlier project records and scientific artifacts. New models require their own source versions, units, temperature/load/charge domains, fitting or import procedure, assessment allocation and independent evidence status.

Both baseline audits are complete. The fresh native `gpt-6-astra` review at `max` effort is in `../volt-forge-v2-astra-2026-10-28`; its assessment is 57/100. The earlier mixed/resumed-Sol review is in `../volt-forge-v2-redteam-2026-10-28`; its assessment is 63/100. These are reviewer judgments, not official competition scores or physical validation.

The reconciled execution plan is `../volt-forge-round1-roadmap-2026-10-28/START_HERE.md`. Its 27 work packages include custom cells (R25) and the walkthrough (R26), with original findings, dependencies, scientific/data gates, acceptance tests and evidence requirements. Product implementation status must be reported separately from plan completeness.

## Submission version decision, 29 October 2026

V3 Final is the Round 1 submission release. It must cover every concrete requirement of the official brief within the small-module scope, with supporting scientific and software evidence. Missing fundamentals remain V3 work. V4 is the Round 2 expansion line for greater fidelity and convenience. Final status and full marks are not inferred from passing software tests or a development preview. The product and one-slide pitch must reference the same frozen release and actual evidence.
