# V4 re-audit against the 20 V3 findings

Checked 30 October 2026 at commit `6fea142` plus the release notes. Software identity `dd8746b0898bcae0`.

**This is not an independent audit.** The same reviewer audited V3 and built V4. Treat it as a self-check and have Codex or a fresh reviewer repeat it.

| ID | V3 finding | V4 status | Evidence |
| --- | --- | --- | --- |
| VF3-01 | Heat created energy | Fixed | `tests/test_first_law.py`; Samsung 6 A stops at 1,001.9 s at its charge limit, peak 27.94 °C; check fails on the V3 form |
| VF3-02 | LG table step | Fixed, unvalidated | `configs/cell_catalogue_v2.json`; no step at fixed current and temperature; modification recorded as unvalidated |
| VF3-03 | AI creation failed | Fixed on Claude | 4 of 4 audit prompts opened drafts through the Claude route. Codex route untested because the account reached its limit |
| VF3-04 | Recommendation did not generalise | Addressed | 4,006-case study; conditional recommendation; no link option wins every case |
| VF3-05 | Application, mass, cost, charging hidden | Mostly fixed | Application, requirements, cost, mass and charging result on screen. Cell dimensions are not shown |
| VF3-06 | Checks could not see heat | Fixed for numerics | First-law check closed in every calculated study case. Measured accuracy is still not established |
| VF3-07 | Cooling weakly identified | Partly addressed | Relabelled, range shown, low-cooling assumption added. The value stays rig-specific, and the measured comparison shows this matters |
| VF3-08 | OCV slope contradicts entropy | Open | Not changed. Needs a sensitivity check before any claim |
| VF3-09 | Interface conflicts unflagged | Fixed | `studio/design_rules.py`, in the shared simulation path |
| VF3-10 | No over-voltage threshold | Fixed | Voltage ceiling and charge window tested in the browser |
| VF3-11 | Seeded design blocked | Fixed | Unchanged 14.55 A seed ran from a clean install |
| VF3-12 | Keyboard focus lost | Fixed | Focus kept after a re-render with real key input |
| VF3-13 | Stale session token | Fixed | Same page ran a test after a server restart |
| VF3-14 | Compare hid settings differences | Fixed | Settings changes listed in Compare |
| VF3-15 | AI saw little context | Fixed | Current settings and a bounded trace added |
| VF3-16 | Sent draft not cleared | Fixed | Render no longer restores the old draft |
| VF3-17 | Restart traceback | Fixed | Clean message tested. The port can stay busy briefly after closing |
| VF3-18 | Chart and naming polish | Fixed | Axis units, changing-load names, outputs in the guide |
| VF3-19 | Identity source locators | Open, minor | Paper names M50T. Locator not added to the model record |
| VF3-20 | Stop messages | Fixed | Messages name the range and next actions |

Summary: 15 fixed, 3 partly fixed or limited, 2 open.

## New limits V4 introduced or exposed

- All 12 pre-declared measured comparison cases missed their bands. Single-cell runs fit the low end of the cooling range; the module rig ran cooler than the whole range.
- The Geekworm X1206 V2.0 is not confirmed to run with fewer than four cells, and it publishes no battery cutoff or efficiency.
- Only one exact-part listing was found for that board, so its price is not an average.
- 8.42 A is a constant-current approximation, not a constant-power load.

## Verification record

| Check | Result |
| --- | --- |
| Clean install, Python | 437 passed, 8 known skips |
| Clean install, JavaScript | 50 passed |
| PyBaMM on frozen code | 15 of 15, voltage and heat |
| Export replay | 5 of 5, tampered results and models refused |
| Study | 4,006 cases, 42 refused, first law closed in every calculated case |
| Browser, clean copy | Setup, load block, warnings, live cost, verdict, seeded design, protection, restart recovery, 1024 px, 390 px |

Not tested: Windows, browsers other than Chrome, hardware, real users, and the Codex AI route.
