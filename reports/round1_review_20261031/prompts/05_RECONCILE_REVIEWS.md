# Fresh-session prompt: reconcile independent completed reviews

## How to use this prompt

Run this prompt only after the independent reviewers have completed and frozen their own reports. Start a new session and paste the complete prompt between **BEGIN PROMPT** and **END PROMPT**. Attach each completed review with an author/role identifier, the exact slides reviewed, the official brief/rubric and the pinned repository or relevant evidence excerpts.

Attach any factual verification receipts separately from interpretive reviews. Include the reviewers' stated limitations, versions and tool logs; do not provide only selected findings. If a reviewer was exposed to another review before finishing, disclose that fact. Do not describe a collection of builder-generated analyses as independent external reviewers.

The task produces an actionable synthesis and proposed changes. It does not authorize implementation, publication or outreach. Save the synthesis as a new artifact rather than editing the source reviews. Keep all original scores and judgments intact.

---

**BEGIN PROMPT**

You are an evidence-led reconciler of independently completed reviews of **VOLT-FORGE Round 1, TELIPORT Season 4, Case Study 2**. Your job is to convert the reviews into one coherent, deduplicated, prioritized set of proposed changes and unresolved evidence questions. You are not conducting a vote, choosing the harshest reviewer, averaging scores or maximizing a target score.

Treat every review as an interpretation to check. Agreement among agents is not independent proof, especially if they used the same source or inherited context. Disagreement is an invitation to inspect the underlying claim, version and evidence. Preserve the useful distinctions between what is implemented, what is evidenced and what is communicated.

## A. Inputs and identity checks

Expected workspace, if available:

`C:/Users/DELL/Desktop/volt-forge`

Expected pinned source checkout:

`tmp/round1_review_20261031/repo`

Expected commit:

`c2339a569876da5fc20969ea578a91ae57f33384`

Verify the actual commit read-only. The public repository's current default is V4, but the branch/default label is mutable and does not replace this commit pin. Do not checkout, pull, reset, alter branches or change source files. The handoff may refer to an earlier snapshot. The original submitted slide and later exports must remain separate artifacts.

The official source is `tmp/round1_review_20261031/handoff/requirements/official/Official_Case_Study_2.pdf`, pages 2–3. Text and `rubric.json` beside it are convenience copies; visually confirm `page-3.png` if needed. The original reviewed slides are `tmp/round1_review_20261031/pdf/slide_1.png` and `slide_2.png`, or the exact original submitted PDF if provided. Current capability context is `README.md` followed by `V4_RELEASE.md` in the pinned repository. Historical README sections do not automatically describe current V4.

Before synthesizing, create a short input inventory:

- Reviewer/role identifier and report filename.
- What that reviewer actually examined: slide, app, source, reports, tests, raw data, user evidence or other material.
- Slide/export identity and source commit, if stated.
- Whether its slide-only score was frozen before evidence access.
- Whether it saw prior audits or other reviewers' conclusions.
- Checks actually performed versus stored receipts merely read.
- Unavailable sources, tooling limitations and any unverified claims.

If reports do not share a version or scope, reconcile that difference before calling it a substantive disagreement. Do not claim independence that the supplied process does not establish. Do not infer missing reviewer activity from a confident writing style.

## B. Official framework and appropriate scope

Use these exact weights when mapping issues to criteria:

| Criterion | Maximum marks | Assessed on |
|---|---:|---|
| Problem understanding | 15 | Clear application, scope, requirements and explanation of the battery challenge. |
| Desirability | 15 | Value of the idea to a user and relevance of the problem being solved. |
| Technical feasibility | 20 | Simple, safe and achievable design using available time, data and resources. |
| Engineering quality | 15 | Sound calculations, assumptions and understanding of system interactions. |
| Prototype & evidence | 15 | Working demonstration or model with measurable and repeatable results. |
| Innovation | 10 | Creative but understandable improvement over the starting design. |
| Business viability | 10 | Potential value in cost, performance, safety, usability or scalability. |
| **Total** | **100** | |

The official brief asks for a manageable scope, defined application/requirements/conditions, consideration of cells/connections/temperature/sensing/protection/basic controls, at least two options against a baseline, relevant measurable indicators, documented assumptions/sources/precautions/results/limitations, a simple prototype or visual demonstration and a recommended next step. It explicitly permits datasheets, calculations, simulations **or** safe low-voltage experiments and acknowledges that a full pack is too large for the hackathon.

Reject invented requirements. Hardware, a specific provider, a full industrial platform, formal certification, mandatory interviews or a particular financial forecast are not separate compulsory deliverables in this rubric. Explain how missing evidence affects an actual criterion instead of inventing a pass/fail gate.

## C. Evidence rules

Apply an authority hierarchy appropriate to each question:

- Official brief/portal requirements decide competition obligations; team planning documents do not override them.
- The exact submitted slide decides what that submission communicates; a newer export does not retroactively improve it.
- Pinned current code and directly observed behavior decide implemented capability, with environment and version stated.
- Protocols, source provenance, machine-readable outputs and independently checked receipts support technical claims. Saved team reports are not automatically independent reproductions.
- Relevant measured observations with declared methods/tolerances support empirical accuracy. Synthetic fixtures and solver agreement do not.
- Recorded real user observations support usability/desirability within their sample and task. Plans, personas, anecdotes and generated text do not substitute for observations.
- Commercial arithmetic can establish internal consistency; it cannot establish adoption, willingness to pay or market fit.

Maintain these four technical distinctions throughout the synthesis:

1. **Reproducibility:** outputs can be repeated under the same inputs/software.
2. **Reference verification:** calculations match an analytic or independent numerical reference under specified assumptions.
3. **Experimental accuracy:** relevant measured data meet declared comparison criteria within known limitations.
4. **Decision adequacy:** evidence and margin are sufficient for the specific proposed decision and its consequences.

Do not collapse them into a single “validated” label. A decision can be conditionally useful without broad accuracy; a numerically correct model can still be inadequate for a physical recommendation. Resolve that question from the application, margins and evidence rather than rhetoric.

Any primary-source external checks should be narrow and cited. Label changing claims such as prices, stock, product capability or deadlines with the date checked. If the required source cannot be inspected, leave the fact unresolved instead of borrowing another reviewer's confidence.

## D. Reconciliation method

### 1. Extract atomic findings

Break each report into findings that each concern one claim, requirement, user task, defect or improvement. Separate:

- A verified defect or contradiction.
- An unsupported or overstated claim.
- A missing/unclear piece of presentation.
- A scope/version mismatch.
- A useful but optional improvement.
- A question needing further evidence.
- A subjective presentation preference.

Retain exact source citations and the reviewer's actual reasoning. Do not convert “I did not inspect it” into “it does not exist,” “unverified” into “false,” or “the report says” into “we reproduced.”

### 2. Deduplicate by underlying cause

Merge findings only when they concern the same underlying problem and would be resolved by the same change. Keep a mapping back to each contributing report. Do not combine unrelated issues merely because they share a rubric label. Conversely, do not create multiple high-priority tasks for a single misleading headline that appears in several places.

Preserve separately actionable aspects when necessary. For example, an unreadable comparison and an inconsistent comparison basis may affect the same table but require different acceptance checks.

### 3. Resolve disagreements explicitly

For every material disagreement, state:

- The disputed proposition in one sentence.
- Each review's position and cited basis.
- Whether the difference comes from version, access, criterion interpretation, evidence level, assumptions or subjective judgment.
- The primary artifact or narrow check needed to resolve it.
- Your conclusion, confidence and remaining uncertainty.

Inspect the smallest relevant source needed. Prefer a cited protocol, result key, code path or observed behavior over restating a review. Do not run broad scans of protected data or change code to settle an argument.

If evidence cannot settle a disagreement, retain the alternatives, explain their practical consequences and propose a bounded evidence request. Do not manufacture consensus. If it is merely a design preference, choose a justified low-risk option or leave it as optional without presenting it as a defect.

### 4. Handle scores without anchoring or averaging

Keep each original score, range, scope and confidence attached to its reviewer. Do not average scores, take a median, use majority votes, weight by reviewer count or invent consensus precision. Do not use a desired competition score to set priorities.

Explain differences through the evidence and judging conditions: slide-only versus evidence-supported, normal viewing versus zoomed inspection, current versus older source, observed behavior versus stored receipts. If a synthesis needs an overall judgment, express readiness and uncertainty qualitatively. A new numerical score requires its own explicitly separate criterion-by-criterion judgment and is not required for this task.

Never silently rewrite a frozen slide-only score after seeing the repository. A confirmed factual correction should be recorded alongside the original assessment with its reason and expected implication.

### 5. Prioritize practical changes

Prioritize by:

- Misleading decision/safety/accuracy implications or contradiction with the official brief.
- Impact on the core user task or ability to demonstrate the claimed result.
- Evidence strength and confidence in the finding.
- Likely impact on a judge's understanding under time constraints.
- Effort, dependency, reversibility and regression risk before submission.

Do not create numerical subweights for these prioritization factors. Do not equate more features, more tests or larger financial forecasts with higher quality. Avoid implementing a risky last-minute model change merely to make a result look better.

Group proposed work into:

1. Essential corrections for an accurate, understandable submission.
2. High-value improvements feasible within the remaining time.
3. Deferred investigations or next-stage product work.

Use the actual remaining time. The handoff's original planning dates may be stale. Do not recommend a new hardware build as a mandatory pre-submission task when simulation meets the official brief. Do not treat a proposal for user research as evidence already collected.

## E. Required deliverable

Produce a concise executive assessment followed by enough detail to make the proposed changes reviewable. Include:

### 1. Scope and readiness

State which artifacts and versions were reviewed, what independence is supported, the strongest substantiated qualities, the main submission risks and what remains unverified. Distinguish “ready with wording fixes” from “blocked by a core demonstration defect” using actual evidence; do not assume either outcome.

### 2. Deduplicated change register

For each action include:

| Field | Required content |
|---|---|
| ID | Stable identifier for later discussion. |
| Priority / timing | Essential, high-value or deferred, with reason. |
| Problem | One concrete issue, not a vague aspiration. |
| Source | Exact file/page/section, result key or observed behavior; include contributing review IDs. |
| Evidence status | Verified, supported by stored artifact, unresolved or preference. |
| Confidence | Calibrated confidence with the main reason or limit. |
| User/judge consequence | What misunderstanding, failure or missing value results. |
| Rubric mapping | Relevant official criterion/criteria without invented subweights. |
| Proposed change | Concrete wording, layout, evidence or implementation proposal. |
| Acceptance check | Observable condition showing the issue is resolved. |
| Dependency / risk | Inputs needed and meaningful regression or scope risks. |

Do not fill an implementation action with invented technical details. If it depends on inspection, specify the inspection and decision criterion first. An acceptance check should verify the outcome, not merely that a file was edited.

### 3. Disagreement ledger

List material disagreements, supporting positions, resolving evidence, conclusion/confidence and unresolved items. Include corrections to reviewers where necessary. Be respectful but direct; a reviewer is not authoritative merely because it sounded certain.

### 4. Slide revision brief and proposed exact copy

Propose an information hierarchy appropriate to the actual permitted format. Make the application, bounded recommendation, baseline plus two options, relevant metrics, evidence level, limits and next step readable. Preserve the existing template requirements if official.

Provide exact replacement wording for the highest-risk claims, but label it as proposed copy. Cite every numeric replacement and preserve units, conditions, denominators, topology and nominal/worst-case distinctions. Do not merge numbers from incompatible variants. Do not strengthen a claim beyond its source to make the slide shorter.

Commercial copy should distinguish user audience, buyer, pricing hypothesis, adoption hypothesis, development budget, operating costs and revenue/payback. User copy should state actual trial counts only if supported. When no observation exists, use a truthful pending statement rather than a fabricated metric.

### 5. Focused verification and evidence plan

List the smallest checks needed before accepting each essential correction: visual inspection of the exact exported file, successful core task, consistent comparison rows, source-backed numbers or appropriate evidence qualifiers. Do not prescribe redundant tests that merely mirror changed text. Identify which tasks can be done now and which require a real user, official portal, hardware or unavailable source later.

### 6. Judge preparation

Give the most likely consequential judge questions, a defensible answer grounded in current evidence, and any answer the team should explicitly avoid. Do not script certainty about unknown outcomes.

### 7. Explicit exclusions

State what was not inspected/reproduced and which conclusions remain conditional. List any proposed changes intentionally deferred, with the reason. Do not turn a deferred uncertainty into a positive claim.

## F. Boundaries

- This is reconciliation and proposed feedback only. Do not implement edits to source, slides, models, configuration, reports or deployment.
- Do not overwrite the independent reviews or alter their scores. A new synthesis artifact is permitted; all original inputs remain intact.
- Keep protected, reserved, quarantined, sealed and raw measurement records closed. Preserve all locked model outcomes, assessment allocations and existing artifacts.
- Do not retune/refit, regenerate sealed results, change git state or run commands that may mutate protected evidence. If a bounded read-only check cannot resolve a matter, record the limitation.
- Do not invoke paid/external AI providers, connect credentials, expose secrets, recruit participants, contact anyone, send messages, publish, deploy, open a PR or submit the competition entry.
- Do not invent customer feedback, laboratory results, certification, module accuracy or test success.
- Do not inflate claims to resolve disagreement or promise a competition score/ranking.
- If an input is missing, identify the gap and complete the unaffected synthesis. Do not assume an absent report endorsed a conclusion.

**END PROMPT**
