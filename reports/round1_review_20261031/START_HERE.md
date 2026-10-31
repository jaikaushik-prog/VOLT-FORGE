# VOLT-FORGE Round 1 review package

**The submission has a credible working simulation story. Make that story legible and conditional; fix misleading qualification and component-selection paths before strengthening the hardware recommendation.** A visual redesign alone will not resolve those issues.

31 October 2026. Prepared for the team to review and apply. This package contains audits, synthetic reproducers, a frontend brief and fresh-session prompts. It does **not** implement the proposed fixes, revise the slide, establish experimental accuracy or represent real customer feedback.

## Read and send

1. Read this file and the priority table below.
2. Use [JUDGE_REVIEW.md](JUDGE_REVIEW.md) for scores, exact replacement slide copy, the 4/3/2 table and likely judge questions.
3. Use [ELECTRICAL_REVIEW.md](ELECTRICAL_REVIEW.md) for reproduced engineering defects, board-source corrections and acceptance checks.
4. Use [USER_EXPERIENCE_REVIEW.md](USER_EXPERIENCE_REVIEW.md) for student/engineer task reviews, recovery/accessibility issues and a real-user trial script.
5. Use [FRONTEND_IMPROVEMENT_BRIEF.md](FRONTEND_IMPROVEMENT_BRIEF.md) to turn the existing design skill and product vision into a focused UI revision. The old guide is included unchanged under [design_reference](design_reference/README.md) because it was absent from the friend's V4 tree.
6. Send this package to your teammate yourself. No message or lab request was sent on your behalf.

## Independent judge estimate

The judge agent received the slide and official rubric before repository evidence, and was not given the friend's 68/95 scorecard or other reviewers' findings. It froze the slide-only score first. The other two agents independently inspected electrical behavior and simulated user tasks. Their reports are preserved as separate judgments, not averaged into a new score.

| Official criterion | Maximum | Slide only | With supporting artifacts |
|---|---:|---:|---:|
| Problem understanding | 15 | 12 | 13 |
| Desirability | 15 | 9 | 9 |
| Technical feasibility | 20 | 16 | 17 |
| Engineering quality | 15 | 10 | 12 |
| Prototype and evidence | 15 | 11 | 12 |
| Innovation | 10 | 6 | 7 |
| Business viability | 10 | 5 | 5 |
| **Total** | **100** | **69** | **75** |

The judge's ranges are 61–76 and 68–82 respectively: subjective judgment ranges, not statistical intervals. These are **not official scores or a promise of selection**. The evidence-supported estimate assumes a judge reads the linked artifacts; it is not earned by a link alone. It was formed before the parallel electrical/UX findings and does not certify those product paths. The friend's 95 target is an aspiration, not an established attainable score. The screenshot's category targets must not replace the official maxima above.

The supplied official brief permits calculations and simulation; lack of laboratory access does not by itself disqualify this Round 1 approach. It asks for a manageable application, interactions and precautions, baseline plus at least two alternatives, relevant indicators, sources/assumptions/limits and a prototype/next step. Actual portal deadline, cover-page and file rules still need the team's check. The handoff states 1 November 2026 at 23:59 IST; this review did not verify the portal.

## Priority changes for the teammate

P0 means fix a misleading claim or qualification before relying on it in a recommendation. It does not mean a physical fault was observed. P1 protects the demonstrated workflow. P2 improves comprehension and polish. The time to implement depends on the code/test findings; no point gain is guaranteed.

| Priority / owner | Change | Evidence | Acceptance |
|---|---|---|---|
| P0 · slide | Call two cells the smallest qualifying **simulated candidate in the declared set**, with starting SOC, temperature, converter/floor assumptions and no spare | Judge replacement copy; electrical decision limits | A reader cannot infer measured hardware approval, a global optimum or universal two-cell suitability |
| P0 · backend | Missing relevant custom-cell limits must not produce unqualified sizing eligibility | E1, synthetic receipt | Missing limits → incomplete; explicit applicable limits → assess them; do not erase otherwise valid simulated outputs |
| P0 · backend/content | Check board electrical compatibility instead of selecting by cell count; separate backup, charger and protection paths | E2/E3; manufacturer source locators | Series/custom/unsupported cases do not imply X1205/X1206 fit; unknown current/cutoff settings remain unknown |
| P0 · slide | Separate numerical verification, measured accuracy and sensitivity | Judge evidence table; E review | State all 12 declared voltage/temperature comparison cases missed; no “34%/34% proves accuracy” or “within 13% thermal accuracy” |
| P1 · slide | One legible 4/3/2 table, one useful editor screenshot, concise business hypothesis | Judge replacement table/copy | Third option visible at normal size; same-end/opposite-end and nominal/worst-case values not mixed; cells-only cost labelled |
| P1 · frontend | Bind historical model explanations and comparison mismatch notices to saved runs | UX-03/07, source-derived | Old-result evidence stays old; model/solver/requirements/preparation changes shown before deltas |
| P1 · frontend | Prevent blank numeric values from becoming zero; show full proposal diff; enable conflict recovery | UX-01/02/05, source-derived | Draft intent preserved; all physical changes previewed; concurrent save failure offers usable copy/reload/export |
| P1 · backend | Correct pack charging-Ah semantics and unknown ideal-link-current summaries | E4/E5, synthetic receipts | Series count does not multiply terminal Ah; unknown current is null/reason or uniquely recovered, never fabricated zero |
| P1 · demo | Guided Pi route, truthful AI availability, accessible chart probe, persistence explanation | UX-04/06/09/10, source-derived | Manual no-provider flow completes; keyboard values visible; guided mission matches pitch; local and public persistence separately explained |
| P2 · design | Apply the canvas-led hierarchy and linked result/comparison states | Frontend brief; product vision pp. 5/9/11 | Actual screenshots at supported sizes; no invented output or contour; all state meanings remain distinct |
| P2 · research | Conduct a short observed task trial if participants are available | UX trial script | Actual denominators, assistance and comprehension recorded; pending otherwise; no generated persona counts as a participant |

Before submission, prioritize truthful slide wording, legible alternatives and verified demo paths. Avoid a last-minute framework change, new fitting campaign or rushed physical battery build to chase marks.

## Where the reviews agree, and where to be more precise

- The strongest story is a repeatable educational/early-design comparison with explicit assumptions. It is not a measured prediction service for arbitrary packs.
- The numerical and first-law tests are meaningful. All 12 published-data voltage/temperature comparison cases nevertheless missed their declared bands. Both facts belong together.
- The judge repeats the report's three-cell spare-cell argument. The electrical review narrows it correctly: **three cells are a candidate for a declared single-cell-loss case, not demonstrated tolerance of every contact/link/cell fault**. Test the actual fault topology before claiming N−1 survival.
- The original recommendation associates “up to 95%” with the board. The electrical review checked its source location: that figure belongs to the input step-down path, not an established battery-to-Pi backup curve. Keep backup efficiencies labelled assumptions/scenarios.
- Local-server storage exists. The handoff says the public browser session is volatile; its runtime was not exercised here. Do not generalize one mode's save behavior to the other.
- Current V4 capabilities supersede the older design skill's capability list. Keep its visual language; inspect current contracts before enabling or removing a feature.

## How to use the fresh-session prompts

Run **01, 02 and 03 in separate fresh sessions**, giving each the original inputs and pinned source but not this package's findings, scores or the other sessions' answers until it has frozen its own first pass. Then give the completed reviews to **05**. Use **04** for implementation after selecting the changes. This preserves useful independence rather than asking several sessions to agree with the same conclusions.

- [01 · Judge](prompts/01_JUDGE_FRESH_SESSION.md)
- [02 · Electrical engineer](prompts/02_ELECTRICAL_ENGINEER_FRESH_SESSION.md)
- [03 · Student/engineer user experience](prompts/03_USER_EXPERIENCE_FRESH_SESSION.md)
- [04 · Frontend implementer](prompts/04_FRONTEND_IMPLEMENTER.md)
- [05 · Reconcile independent reviews](prompts/05_RECONCILE_REVIEWS.md)

Attachment checklist: the exact submission PDF, official case-study PDF/rubric extracted from the supplied handoff, pinned V4 repository, product vision PDF and existing design skill. Do not attach private chat logs, credentials, raw measurement archives or unused assessment records. If an attachment is unavailable, the new reviewer must say what it cannot assess. Each prompt provides scope and output requirements without embedding the current scores as desired answers.

## Source/version record and performed checks

- Supplied slide: `VOLT-FORGE_Round1_Slide.pdf`, SHA-256 `7d4f9e49796b784cf951bd82dfc69dfc6cc7de0996063cc4e3cc0f82a0acc3f8`.
- Supplied handoff: `VOLT-FORGE_Handoff_Package.zip`, SHA-256 `fe6587748f78980e6c933b4505f3b97fdb43d9faed91e016560b10c55943acf0`.
- Product vision: `VOLT_FORGE_Product_Vision.pdf`, SHA-256 `d158a3801e2eecac66eda41ea84df6e35270134683ef95551afc1a1fa88cc8eb`.
- Handoff bundle source: `bba3eb5f3c33b7f06e4a5e0fc53f21d2b328a8e6`.
- Reviewed friend source: `c2339a569876da5fc20969ea578a91ae57f33384`. The later commit changes slide PDF/PPTX/export script only. The supplied PDF remains the scored artifact; no automatic readability credit was given to the later export.
- V4 reports name software ID `97ca199f2fd21aac`. The review did not alter its physics, fitted models, frozen studies or measurement files.
- Six synthetic probes, including a cell-order invariance control, were recorded. Eight selected first-law/protection tests passed. Runtime differences from the full lock are documented; this is exploratory Windows reproduction, not a complete locked replay.
- The judge counted saved cases and inspected result/verification summaries; it did not rerun all 4,006 cases or reopen raw/protected measurements.
- Browser host unavailable; automatic approval review rejected binding to the existing private Chrome session. No live app walkthrough was completed. UX findings are source-derived hypotheses about interaction, not invented observations or real-user feedback.

The reports use local locators `R/` or `tmp/.../repo` for the pinned source and `H/` or `tmp/.../handoff` for the supplied attachments. These folders are not redistributed in this package. Resolve code references against [the pinned source](https://github.com/jaikaushik-prog/VOLT-FORGE/tree/c2339a569876da5fc20969ea578a91ae57f33384); provide the original brief/slide separately to fresh sessions.

## Reproduce the synthetic review

From a clone containing this package and the reviewed V4 code, using an environment with its documented numerical dependencies:

```powershell
python -B reports/round1_review_20261031/electrical/reproduce_electrical.py --repo . --out tmp/round1-review-repeat.json
python -B reports/round1_review_20261031/verify_package.py
```

Choose a new receipt filename for each repeat; the probe refuses to overwrite. The first command records current behavior and inputs; it is a diagnostic, not a passing-regression suite for the proposed fixes. The exact selected test names are in the electrical report. Package verification checks bytes, not physical accuracy. The standalone ZIP can also be verified with `python -B verify_package.py` from its extracted review directory.

## Repository handoff

`v4` was copied to **jaikaushik-prog/VOLT-FORGE** and set as its default branch, as requested. `main` remains available; the previously staged thermal-evidence search was independently verified and preserved in commit `70e31e6`. This review is delivered as an additive documentation/diagnostic commit on V4. It does not change the application implementation, deploy a site or send feedback to your friend automatically.

**Next action:** your teammate can take the P0/P1 items as a small change list, render the revised slide, and verify the declared manual demo. Use fresh reviews to challenge the result; use real users and suitable measurements for claims that generated personas and numerical tests cannot establish.
