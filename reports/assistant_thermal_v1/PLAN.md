# Local command assistant and thermal feasibility sprint

26 October 2026, starting from a185d5d. The user authorized three parallel
agents and explicitly selected local command mode: no external AI calls.
No language-model provider, API credential or model download is needed.

## Work allocation

- Assistant agent: new deterministic command parser/service, a predeclared
  evaluation set, exact contract and tests. It can explain saved evidence,
  preview a whitelisted explicit edit, or compare explicitly selected runs.
- Backend agent: guarded read-only HTTP route, HTTP checks and reproducible
  full workflow demonstration using distinct manual apply/run/export steps.
- Electrical agent: primary-source LG M50T thermal feasibility audit and a
  separately labelled synthetic prescribed-heat prototype with analytical tests.
- Root: frontend panel, cross-workstream review, browser integration,
  preservation-aware verification, final reports and GitHub update.

The four living files in preservation_map.json are copied byte-for-byte before
editing. No existing sealed report, numerical source, fitted model, dependency
lock, raw measurement or protected assessment outcome is changed. New thermal
work stays outside the frozen electrical source tree and does not affect its
solver fingerprint. No new measured outcomes are allocated or fitted here.

## Command boundary

Use scripts/local_assistant.py: handle_command(project_path, request).
Exact request: message; selection containing variant_id, revision_id,
component_id and run_id; comparison null or explicit first/second variant/run
selections. POST /api/assistant/request uses the existing session/origin gate.

The service returns the existing explanation, preview or comparison as payload
with explicit evidence, captured selection, warnings, applied=false and
simulation_started=false. A preview also returns its authoritative context for
revalidation. No text parser can apply an edit or run a simulation. Unmatched,
ambiguous, compound or unsupported commands are rejected without guessing.
Changing the selected component/variant/run/revision invalidates the displayed
response and any pending preview. Comparison selections are part of this state.

The only model in this interface is the existing backend electrical model.
The feature is labelled Local command assistant, with supported examples and
no external AI calls. It must not impersonate a general conversational model.

## Frontend plan

Keep the assembly and existing three-column editor. Add a dismissible Commands
sheet opened by a toolbar button, initially closed; no new global navigation.
The sheet is a compact command form, not a replacement for the workspace.

Palette: paper #FFFDFA, shell #F5F2EC, ink #202327, line #DDD8CF, selection
#245EA8 and caution #86540A. Segoe UI body 13-14 px; 19 px title; monospace
only for exact commands/provenance. Left alignment and 8/12/16/24 px spacing.
Use native form controls, clear keyboard focus and text states as well as color.

```
Existing assembly / inspector / results         Commands [toggle]
                                  +----------------------------+
                                  | Local command assistant [x]|
                                  | Selected cell/variant/run  |
                                  | Examples / command input   |
                                  | [Review request]           |
                                  | Cited result or preview    |
                                  | [Review in inspector]      |
                                  +----------------------------+
```

Review in inspector transfers the exact proposed edit to the existing explicit
Apply revision flow; it never applies or simulates. Source details remain
expandable. Failed, historical, missing-requirement and unsupported states stay
visible. Comparisons use actual backend metrics/units and require the existing
two explicit run pickers. Small screens retain a usable close control and
wrapped source fields. No thermal heatmap appears without supported outputs.

This fits the reference's optional assistance sheet while avoiding a full UI
redesign or new CAD framework. The PDF's illustrative temperatures and hardware
repair gains are not product evidence.

## Thermal boundary and completion criteria

Thermal output is a separate synthetic one-node energy-balance demonstration,
not an LG module prediction. Every C_th, conductance, temperature and signed
net-heat input is explicit, with units and assumption labels. Existing circuit
resistor losses are not silently promoted to complete electrochemical heat.
The source audit must distinguish exact M50T evidence from related cell types
and fixture-specific cooling measurements from ambient conductance.

Completion: constrained requests work end-to-end on the existing backend;
no-mutation, stale-selection, origin/token and citation checks pass; a real
browser demonstration reaches manual apply, run and comparison; thermal
analytical/energy checks and source-backed feasibility decision are recorded;
historical artifacts and frozen electrical fingerprints remain verifiable.
No experimental module accuracy or battery-performance improvement is claimed.
