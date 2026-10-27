# Workspace simplification

27 October 2026. Implements the request to make the existing application clean, professional, explanatory and easier to use.

The previous screen kept a component tree, variant list, inspector, raw load JSON, source/classification controls, sensitivity choices, multiple plots and long limit tables visible together. Internal names and repeated caveats competed with the actual experiment.

The new workspace uses a larger assembly with an optional inspector, a designs/components menu and four dedicated views. Current/duration intervals use normal forms. The main result has four values, with whole-run versus selected-time behaviour explained. Advanced parameters, charts, detailed margins, model sources and accounting remain available through disclosure. Comparison leads with six meaningful metrics; investigation focuses on selected connections and gives a real case-count estimate.

Edits retain Preview → Save → Run. A pending visible edit disables Run so it cannot be mistaken for a saved input. Component switching retains a local draft; discarding it restores saved values. Earlier results retain outdated/partial and ownership labels. Case opening returns to the workspace. All component IDs, backend calculations, units, immutable source references, finite investigation and export/replay semantics remain in place.

Pre-redesign files and git state are preserved in `before_source/` and `baseline-git-status.txt`. This is UI implementation and executed software verification, not a user study or experimental battery validation. The GitHub design sources and visual decisions are recorded in the repository's DESIGN.md.

Final interaction checks widened the selectable busbar area to include its label and the gap above/below the thin conductor. Real coordinate clicks now select all six connections reliably. Preview checks verify four starting temperatures, per-cell heat capacities, neighbour pairs, the rail heat fraction, SOC percent/fraction, polarization mV/V and each connection’s mΩ/Ω mapping. Empty/unrun views no longer show a fabricated numeric overlay range. Overlay text uses WCAG contrast rather than a gamma-incorrect brightness approximation.

Executed checks: 257 Python tests passed with eight official-archive-dependent skips; 23 JavaScript tests passed; 14 full-browser workflow checkpoints passed, including a downloaded package and two electrical/thermal replays. Eight final render checks cover desktop/laptop/tablet/mobile, the mobile guide, actual overlay contrast, an unrun variant and browser errors. Twelve property-preview checks confirm ordered values and unit conversion. Source hashes in `final_render_checks.json` bind the final screenshots to the rendered UI. See `../v1_release/release_verification.json` for the combined evidence.
