# Bounded test-103 development import and electrothermal feasibility

Declared 26 October 2026, before the first full-record numerical reads in this
workstream. This is development analysis, not fresh assessment. The existing
test-103 schema probe, its one-row exposure and all published results are known.

## Source and access boundary

Only the following three members of the original M50.zip may be read:

- M50/M50_50SOC_20deg_cell1_test103.txt
- M50/M50_50SOC_20deg_cell1_test103.mat
- M50/Electrical/M50_50SOC_20deg_cell1_test103_CF8.txt

The ZIP SHA-256 is
`960ac78db8005d6b33072bbafdea95eb473057037ac5df85cbd99cf690a8cbb9`.
The allocation, prior inventory/schema and source-metadata hashes are recorded
in procedure_seal.json before numerical reads. All other numerical members
remain closed. No change is made to frozen models, old reports or dependencies.
Original raw files are never overwritten. Derived arrays stay in ignored local
data/processed or tmp; versioned reports contain diagnostics and provenance.

## Prospective analysis

1. Decode thermal text with exact 16-column order and explicit seconds/degC
   unit row. Record NUL removal and the legacy-encoding fallback. Require every
   numeric row to have the declared width; report nonfinite values and time
   monotonicity/gaps without silently dropping, sorting or filling samples.
2. Decode the complete electrical header using its declared line count. Retain
   column names and units, source timestamps and program steps; interpret current
   sign using recorded charge/discharge indicators/counters and explicit program
   settings. Never substitute the configured 1 Ah for actual cell capacity.
3. Decode only this development MAT file using HDF5 hard links. Read its labels
   and arrays with original storage shapes. Choose channel/time orientation
   from labels and array dimensions, corroborated by exact raw-series comparison.
   Never select a channel permutation or time shift to improve curve agreement.
4. Report raw time spans, interval distributions, duplicates/resets, current
   amplitude/direction and complete program pulse/rest blocks. Preserve both
   instruments' original clocks. Use a common time origin only if documented
   markers establish it; otherwise keep the axes separate and report alignment
   unresolved. No cross-correlation alignment is allowed.
5. Compare author-derived steady-state fields with explicitly defined raw channel
   differences and internal algebraic relationships. Report residuals and units
   only where evidenced. Do not search for windows or coefficients that reproduce
   the published CCC. An implied heat conversion, if algebraically observable,
   is processing evidence, not independent calibration.
6. Check electrical charge/energy conventions and integration sensitivity using
   left/right/trapezoid conventions where sample semantics are unresolved. These
   checks do not make electrical power into internal heat. Display complete
   development records and pertinent diagnostic plots, clearly labelled.
7. Test strict parsing, units, failed/denied reads, HDF5 references, channel
   orientation and simple analytical integration cases with synthetic fixtures.
   Replay the actual bounded import and hash reports/arrays/source artifacts.

## Model decision boundary

No parameter fitting is part of this procedure. First establish whether the
available definitions, heat scale, preparation, boundary conditions and clocks
support an identifiable physical thermal model. Separate internal heat
generation, fin heat rejection, fixture storage and other heat paths. CCC is
not node-to-ambient H. Cold-junction temperatures are not assumed ambient.
Neither constant nominal SOC nor an electrical I-squared-R heat source is
inferred from the paper or a visually plausible trace.

Any later fit needs its own frozen procedure and evidence-supported assumptions.
Do not open reserved experiments to resolve definitions or choose a better case.
If calibration/synchronization remains unresolved, finish the importer and
independent diagnostics, state exact missing evidence and make no module
temperature, repair-benefit or safety claim. No outreach or external AI calls.
