# Independent audit of V4

A fresh Claude session with no build context reviewed commit `089c649` on 30 and 31 Oct 2026. It is independent of the build work, but it is not a human reviewer or a different AI. Codex started the same review, then hit its usage limit until 4 Nov. The full report is in the session record.

**Its verdict:** the engine, the study recount and the frozen checks held up, and the 2-cell result is sound as a simulation. The slide and business case oversold the evidence.

**What it confirmed as sound:** energy accounting against an analytic case; every design in `cases.jsonl` on recount; all 33 required cases on rerun; the engineering checks on rerun; constant-power and entropy handling; 2-cell robustness in simulation.

| # | Severity | Finding | What we did |
| ---: | --- | --- | --- |
| 1 | Critical | PPTX, PDF and workbook were out of date | Rebuilt last, and checked against the PNG |
| 2 | Critical | Trust box hid that voltage also missed | Slide now says voltage and temperature missed all 12, and sharing missed too |
| 3 | Critical | Stage-one sum failed on the slide | Slide now names 130 labs and 31 teams, and the sum works by hand |
| 4 | High | Staged plan was circular and left out running costs | Stage one now serves labs and small teams, carries the lab, and says "before running costs" |
| 5 | High | Market panel sized people who pay nothing | SOM now shows paying labs. The team market is marked as not sized |
| 6 | High | "You can build it today" | Now "should fit a two-cell Pi UPS board, though we haven't built it yet" |
| 7 | High | "We use a range" was not what the app shows | App now marks temperature as a rough estimate. Claim removed from the slide |
| 8 | High | "9 tests sealed" oversold the exam | Now says 2 can test this cell, both at 40 °C |
| 9 | High | "Cells never share evenly" | Now "rarely", with the unsupported clauses removed |
| 10 | High | Energy balance offered as proof of a right model | Slide now says it catches solver errors, not a wrong model |
| 11 | High | Brief points missing | Slide now states scope, conditions and cutoffs. Bench safety is in the appendix |
| 12 | High | Desirability had no evidence and "buying parts and hoping" | Wording fixed. Trial kit ready. Still no user evidence |
| 13 | Medium | Find the smallest design tests normal conditions only | Slide says so. The product is unchanged and shows its scope |
| 14 | Medium | 2 cells have no spare | Added to the recommendation and appendix |
| 15 | Medium | Answer flips near 21.6 W | Slide says 25 W is the full supply rating. Appendix gives the threshold |
| 16 | Medium | Sharing check weaker than presented | Equal-share figure reported beside it. Gain sentence corrected in the reports |
| 17 | Medium | "54 experiments" read as validation | Now says 2 tests compared so far |
| 18 | Medium | Cost inputs and the AspenTech benchmark | AspenTech dropped from the slide and caveated in the appendix. Salary limits disclosed |
| 19 | Medium | Screenshots did not match the recommendation | Demo designs rebuilt from the study's own builder and retaken |
| 20 | Low | Low-charge figure | Corrected to the lowest across all 33 cases |
| 21 | Low | Millivolt CSV accepted | Refused, with a test |
| 22 | Low | Preflight checked the first step only | Later steps now warn, with a test |
| 23 | Low | Late load change on non-round times | Fixed, with a test |
| 24 | Low | Records had drifted | Study rerun on the final code, records updated |
| 25 | Low | Loose wording | Fixed on the slide |
| 26 | Low | 2.3 figure was not the best evidence | Replaced with the first-10-minutes result, labelled as added after the run |

**It could not check:** web sources, reserved records, real Pi draw, the X1205 on hardware, or real users. It did not run the live AI route, the browsers, Windows, export replay or PyBaMM. Those were read from the code or recorded results. The AI route and browsers were run separately by the builder.
