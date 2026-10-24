# Four-cell editor implementation plan

The first screen is a working electrical schematic, with the existing frozen-v2
project API as the sole source of calculated outcomes. The supported assembly is
LG M50T P7/P17/P19/P13, same-side-terminal 1s4p. This work does not add physics.

## Design before implementation

Palette: paper `#f3f6f9`, surface `#ffffff`, ink `#122335`, line `#d9e2eb`,
action `#2762c6`, caution `#855016`. Branches use blue, orange, teal and violet,
with cell labels as well as colour. Bahnschrift headings recall instrument
lettering; Segoe UI provides legible controls and tabular numeric results.

Left-aligned controls frame an interactive circuit. The circuit, rather than a
decorative hero or a grid of summary cards, is the main visual identity.

```text
VOLT-FORGE / Four-cell workspace                Run / Export
Variants      | Four-cell circuit             | Inspector
Components    | explicit rails and terminals  | edit / preview
              | selected run at time t       | provenance
              | Current / voltage / evidence / compare
```

Review against the brief: remove generic dashboard tiles and decorative gradients.
Use actual resistor edges, node names and battery branches. Reserve amber for
outdated/unsupported evidence. Charts and numbers must refer to an explicit run;
an empty project shows instructions, not illustrative results. Narrow screens
stack the inspector and results; the circuit remains horizontally inspectable.

## Implementation and verification

- Add a loopback-only Python HTTP adapter in `scripts/` and native web assets in
  `web/editor/`. Leave electrical backend source unchanged so UI changes do not
  invalidate captured solver versions. No additional production dependencies.
- Use a separate ignored working project. Keep immutable snapshots, expected
  revisions, provenance, ownership and validation in the existing project API.
- Run/export jobs use a worker. Display execution status separately from freshness.
  Guard against delayed responses crossing variants. Display edits never revise
  physics; no geometry-to-resistance rule exists.
- Provide cell/connection/module inspectors, preview/apply, named variants,
  scenario selection, current/voltage plots, explicit evidence and comparison,
  and downloadable reproducible packages. Fitted parameters remain read-only.
- Test real HTTP lifecycle, rejection and export. Exercise the actual browser
  workflow, keyboard/mobile presentation, and preserve all prior release hashes.

Experimental module validation remains awaiting suitable measurements. Actual
device voltage requirements stay unset. Thermal simulation and AI optimization
remain unavailable.
