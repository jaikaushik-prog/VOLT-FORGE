# Prospective P45B investigation: scope and evidence allocation

This plan follows the complete six-file intake, before reading any experimental,
author-simulation, numerical parameter-table or validation-workbook rows. It is a
**proposed allocation**, not a claim that a model or assessment has been completed.
The accompanying machine-readable allocation keeps every outcome protected. The
next implementation must commit its precise procedure and allowed calibration
steps before releasing development records, and freeze that procedure before
opening any assessment voltage. These are engineering evidence controls, not
requests for further user permission.

## First operating case

Characterized Molicel INR21700-P45B **single cell**, nominal 25 degC under the
authors' controlled surface-temperature protocol, with current as measured input.
Start with the complete 1C discharge and charge profiles, nominal 4.5 A according
to the supplied format guide. These are development records, not fresh tests.
Actual durations, sample intervals and temperature variation remain uninspected.
Outputs: predicted terminal voltage, declared SOC proxy, polarization states,
coverage flags, source references and voltage residuals. Do not predict temperature.

Keep source current negative on discharge; expose a separately named positive-
discharge quantity for our solver. Use `I_exp_A` as input, `V_exp_V` as measured
target, and `T_exp_degC` as controlled-temperature evidence. Do not substitute
`I_sim_A`, source `SOC_sim`, `E_OCV_V` or the author's predicted voltage/temperature.
The format guide defines `Q_sim_W` as signed cell power, not measured heat loss.

The earlier application remains proposed 14.55 A for 360 s in a four-cell module.
It has not been reduced or transferred to these cells by this plan. Equal sharing
would mean 3.6375 A per cell; uneven sharing could exceed the nominal 4.5 A
development profile. A cell test is not a four-branch waveform/duration validation.
The module's connections, preparation, calibration and branch measurements remain
separate issues. Neither 3.50 V nor 25 mV becomes an application requirement.
Device minimum voltage/excursion duration remain **requirement not configured**.

## Whole-family allocation proposal

Each family groups files with identical condition stems, including `-charge.csv`
versions. The format guide says those versions contain outputs from the alternate
author parameter set. Their experimental-channel equality has not yet been tested.
They must never be split between development and assessment, even if their
experimental channels later prove to differ. Filename families are not cell IDs.

| Intended role | Complete families | Files |
|---|---|---:|
| Development candidates at 25 degC | C/30 charge/discharge, GITT charge/discharge, 1C charge/discharge | 7 in 6 families |
| Future assessment candidates at 25 degC | 3C charge/discharge, 10C discharge, WLTP, eVTOL | 6 in 5 families |
| Reserved temperature-transfer evidence | All 10, 40 and 60 degC families | 38 in 32 families |
| Author validation workbook | Entire workbook | 1, unopened |

All 51 CSV outcomes remain unopened in this intake. Proposed roles use only
filename/protocol metadata. Preserve complete profiles, pulse/rest sequences and
paired simulation variants. No random timestamp splits. The nine unused LG cells,
protected LG module records and 13 unused FreeTwinEV module tests stay protected.
FreeTwinEV ID01 is already used development evidence; it cannot become a fresh test.

## Two distinct modelling routes

**Independent measured-data route:** begin with a rested/low-rate reference and
the simplest useful electrical model. C/30 voltage is loaded voltage, not proof
of equilibrium OCV. GITT can support rest and relaxation diagnosis only after its
actual timing is checked. Introduce one RC state only if development residuals
and identifiable time constants justify it. No automatic adoption of two RC pairs
because the published parameter tables contain them. State nominal-capacity and
initial-state assumptions explicitly, and keep reference/SOC-origin uncertainty
coupled. This route can progress without adopting the authors' full model.

**Published-model reproduction route:** the base and charge-optimized lookup
tables require the authors' exact equations, hysteresis/initial-state conventions,
parameter interpolation and extrapolation rules. The two-page format guide is
not a complete implementation specification. The linked detailed documentation
redirects to a login handoff, and the SSRN abstract/PDF requests returned HTTP 403
during this intake. Do not invent gamma units/evolution, a capacity origin or a
thermal law to make the tables run. An accessible specification or publication is
needed for a defensible claim of reproducing that model. The public overview and
table headers alone do not establish mathematical compatibility with frozen LG v2.

Do not choose between published base/charge variants by examining the protected
validation workbook or future assessment errors. Any comparison of those variants
must be predeclared as a reproduction study; the authors' own validation cases are
not fresh independent evidence for their already-published parameters.

## Procedure to freeze before outcome access

For the selected route, version: measured-channel mapping, integration convention,
complete calibration intervals, initial SOC/capacity/reference origin, permitted
initial polarization estimation, temperature treatment, parameter bounds, solver
step and stopping rules. Stop on undefined SOC/reference support; flag any explicitly
allowed exploratory extrapolation. Do not repair data or align against assessment
voltage. Calibration choices must use development evidence only.

Report sample-weighted and time-weighted RMSE, bias, maximum absolute error and
errors by complete sequence/current direction/amplitude/transition interval and
declared SOC proxy. For a strictly increasing time base, time-weighted statistics
use trapezoidal endpoint/interior weights; do not assume uniform sampling or bridge
unexplained acquisition gaps. Preserve measured-versus-predicted and residual plots
with original row references. Identify slow dynamics unsupported by sample timing
and distinguish parameter uncertainty conditional on the reference from absolute
SOC uncertainty. State any correlations instead of combining them as independent.

Primary assessment stays within the measured/reference-supported 25 degC domain
established during development. Higher currents and other temperatures are transfer
questions; mathematical interpolation is not experimental proof. No voltage-limit
pass/fail or design recommendation is possible without a sourced application
requirement and an error budget tied to that decision. All model comparisons must
be called cell-model development/assessment or published-model reproduction, not
independent experimental validation of the four-cell module.
