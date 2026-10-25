# Evidence and edit-preview panel

User-authorized milestone after commit f0f4ebe, 25 October 2026. Extend the
existing 2D editor and local server. Preserve existing simulation/variant/export
flows, frozen electrical sources, models and reserved measurements.

## Design plan, reviewed against the product vision

Screens: the existing four-cell workspace's Evidence tab and inspector edit
preview. The assembly stays dominant; no chat box or new navigation framework.
Use the actual context/explanation/preview contract, not illustrative concept
outputs. The PDF's 3D/thermal/AI screens establish visual intent only.

Palette: ivory shell #F5F2EC, paper #FFFDFA, ink #202327, separator #DDD8CF,
selection blue #245EA8, caution #86540A. Retain existing surrounding editor
chrome in this bounded change. Use Segoe UI body text at 13-14px and the
existing heading family, tabular numerals and monospace only for source IDs.
No new font download. Left-aligned text, 8/12/16/24px spacing, calm separators.

```
Existing circuit and explicit selected component
Results | Evidence | Compare                 Saved run
Evidence for [component]                    Refresh evidence
[Completed / current OR failed / historical OR configuration only]
Requirements and evidence limits
Saved outputs / current assumptions / fitted values
  readable field + value + unit             expand source
Coverage and full provenance                expand details

Existing inspector: edit -> preview old/new -> Apply revision
Preview: assumptions, invalidation, sources; no predicted benefit
```

The subject-specific focus is traceable engineering evidence beside the selected
electrical component. Avoid generic chatbot messaging, inflated accuracy claims,
dashboard card grids or unsupported metrics. Historical output must stay visibly
separate from current design inputs. Empty/error/partial states offer a clear
refresh or selection action. Responsive controls wrap; keyboard focus remains
visible; status is text as well as color.

## Ownership

- Backend agent: scripts/run_editor.py, new HTTP tests and backend notes.
- AI agent: new pure evidence-state.mjs helpers and Node tests.
- Electrical agent: new bounded reference/origin study, frozen before analysis.
- Orchestrator: panel module/styles, app/index integration, browser verification,
  preservation-aware release checks, report, README and scoped Git updates.

Five living files are preserved in previous/; preservation_map.json pins their
bytes before editing. New historical verification must resolve those former
paths to their preserved versions and check current release files separately.
Never alter old receipts or numerical source hashes to make a check pass.

## Implemented API boundary to exercise

POST /api/evidence/context: {variant_id,run_id,component_id,limit}.
POST /api/evidence/request: {operation,context,arguments}, existing contract.
Both use the local session token/origin guard, read only, and refuse active jobs.
No new action executor or model API. Preview is approval-required; a deliberate
click on the existing Apply revision button still uses the existing backend
operation after revalidation. It never runs a simulation automatically.

Selection/edit epochs must prevent late evidence from the wrong variant, run,
revision or component appearing current. Visual moves do not invalidate physics.
Requirement-not-configured and insufficient-evidence states stay explicit.

## Verification

Meaningful HTTP and presentation tests, existing editor/backend regression tests,
real browser interactions on copied reference projects, screenshots at desktop,
tablet and phone widths, stale/failed/unset/empty/error states, preview then
manual apply, historical-run ownership and no automatic action. The electrical
work uses only previously opened data and has its own procedure and checks.
