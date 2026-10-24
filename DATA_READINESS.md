# VOLT-FORGE: data readiness decision

**Subsequent sprint:** see [MODELLING_DECISION.md](MODELLING_DECISION.md) for the
completed provisional cell identification, independent reconciliation and
software-verified ladder solver. The original inspection decision below is
retained as a historical record; its statements about work not yet implemented
describe the earlier stage. Original provenance, audits and module splits remain
unchanged. Experimental module validation is still pending.

**24 October 2026 — GO for a scoped 23 C single-cell identification task; NO-GO
for validating module current sharing, coupled thermal behaviour, or ranking
repairs until the current-channel inconsistencies are reconciled.**

The real-data inspection pipeline runs successfully. This is not a validated
battery model. Software checks establish parser behaviour, not physical validity.
The dataset remains useful; the findings below do not invalidate the entire
campaign.

## Acquired and actually inspected

The user downloaded the full official dataset ZIP after this session's socket
permissions blocked direct retrieval. It is **758,227,888 bytes**, SHA-256:

```text
1a2b578859bc83bf71a32f5ad0df8841001ec8cb5c2b2c810818cbe746c20fa1
```

The archive has **194 data files**: 54 raw module Excel exports, 54 processed
module MATLAB files, 78 characterization files for 39 cells, and eight Hall
calibration files. All members were read for CRC integrity and SHA-256 hashing;
all passed. The archive expands to 762,469,662 bytes. It is read in place without
rewriting original bytes. No measured data were fabricated or substituted.

Actual filenames and decoded cell metadata establish **54 distinct module
conditions, 18 all-NMC**. Factor labels form the complete 3 chemistry x 2 ageing x
3 resistance x 3 temperature grid, with the ageing contradiction below. The 19
fresh NMC identities are **P2 through P20**, not an assumed P1-P19 numbering.
The other characterization identities are F1-F18, GS3 and Y1.

The inspected numerical subset is:

| Experiment / article test | Nominal conditions | Cells in positions 1-4 | Raw rows | Role |
|---|---|---|---:|---|
| `M1_NMC_Unaged_R0_T25` / 53 | All-NMC, unaged, 0 mOhm, 25 C | P7, P17, P19, P13 | 33,079 | Calibration baseline |
| `M1_NMC_Unaged_R3_T25` / 28 | All-NMC, unaged, 3 mOhm, 25 C | P17, P4, P10, P16 | 41,689 | Development validation |

Both raw and processed records were fully parsed. For **P4, P7, P10, P13, P16,
P17 and P19**, both pseudo-OCV and HPPC/MS records were fully parsed: 14 files.
H1-H4 were parsed as the relevant M1 sensor calibrations. Cell identities were
decoded for all 54 module records, but other module signals were not audited.
For row 32, cell metadata and the raw workbook header/first four rows were
inspected solely to investigate the contradiction. Final-assessment traces were
not plotted, scored or used for tuning.

The official [v2 dataset record](https://data.mendeley.com/datasets/zh58byr53c/2)
specifies **CC BY 4.0**. Source URL, DOI/version, access date, member names, sizes
and hashes are in [provenance](reports/provenance.json) and
[file inventory](reports/file_inventory.json); attribution and changes are in
[ATTRIBUTION.md](ATTRIBUTION.md). There is no publisher checksum or embedded
version manifest in the downloaded archive. Its association with v2 relies on
the requested official download and user handoff; hashes freeze this exact copy.
The article itself references v1, which is kept distinct from the requested v2.

## Data quality and contradictions

### Parsing and timing

The inspected raw `Data` sheets contain 23 columns; processed tables contain 15
numeric channels plus cell identities. Raw Excel and decoded MATLAB values match
**exactly at every sample** for elapsed/step time, step/cycle indices, module
voltage/current, all four surface temperatures and ambient temperature. This is
an independent cross-format check of the table decoder and channel assignment.

Both runs have zero backward timestamps, zero repeated timestamps, zero duplicate
rows and no missing primary current/voltage/temperature/Hall channels. The
`Internal Resistance(Ohm)` export column is entirely blank in both runs. It must
not be treated as a resistance measurement.

Median interval is 1.000 s. Event-boundary intervals can be as short as 0.0008 s;
maxima are 1.175488 s (test 53) and 1.176300 s (test 28). No interval exceeds the
**provisional** 1.5 s missing-interval screening threshold. This threshold is not
an accuracy requirement. Plots break lines and shade longer gaps if present;
none are present in this subset. No interpolation, smoothing or row deletion
was applied.

Absolute Excel dates have no declared time zone. Their elapsed differences agree
with `Test_Time(s)` to within 1.592 ms and 2.492 ms respectively, descriptive
comparisons rather than clock specifications. Test 53's `Global_Info` start
07:57:58 differs from the first `Data` timestamp 07:54:22.441 on 21 December
2022. The pipeline preserves both and uses elapsed test time as its clock.

### Current conservation prevents module validation

Source currents are positive on charge and negative on discharge. Internally
all currents are multiplied by -1. Branch currents below are the authors'
calibrated measurements from the processed MAT tables; raw Excel contains Hall
**voltage**, not direct branch amperes.

Define residual = sum of four discharge-positive branch currents minus the raw
discharge-positive module current. During the recorded constant-current
discharge (step 5):

| Quantity | Test 53: R0/25 C | Test 28: R3/25 C |
|---|---:|---:|
| Mean measured module current | 14.5544 A | 14.5610 A |
| Mean current-conservation residual | **-1.6833 A** | **+1.5479 A** |
| Residual RMS | 1.6859 A | 1.5511 A |
| Maximum absolute residual | 2.0884 A | 1.9570 A |
| Mean discrepancy / mean module current | -11.57% | +10.63% |
| Full-cycle residual RMS | 0.6925 A | 0.5042 A |

At rest, the mean sums are much smaller: approximately -0.013 to -0.019 A for
test 53 and +0.020 to +0.032 A for test 28. Thus one constant offset correction
cannot explain the full discharge discrepancy. Shifting the branch sum by +/-1
or +/-2 samples increases full-cycle RMS in both runs. This limited sensitivity
check does not rule out all timing effects, but it does not support a simple
one/two-sample alignment fix. A phase-dependent scale/calibration issue, current
reference issue, or undocumented processing remains possible; its cause is not
established.

Simple OLS reconstructions from H1-H4 were tried with Hall voltage, Hall/supply
ratio and Hall-minus-half-supply features. These are derived diagnostics only.
The raw-Hall calibration-fit RMS values are 0.0374, 0.0541, 0.0317 and 0.0317 A
for H1-H4. Applying those raw-Hall fits to test 53 differs from its published
branch currents by RMS 0.8743, 0.6343, 0.0773 and 0.6076 A. The alternative
supply-aware fits also fail to reproduce the supplied currents. This does not
prove the authors used OLS or that their measurements are wrong. The archive
contains no processing scripts/coefficient provenance to explain the difference.

No branch traces were rescaled to force conservation, and no calibration
diagnostic was substituted for the published currents. The article's +/-1%
shunt-resistor tolerance is a **component tolerance**, not a Hall or cycler
current accuracy. No end-to-end measurement uncertainty budget was found, so
the pipeline deliberately has no fabricated ampere pass/fail tolerance.

An additional charge-throughput check reinforces the need for reconciliation:

| Step-5 integrated quantity | Test 53 | Test 28 |
|---|---:|---:|
| Raw module current integral | 21.9681 Ah | 17.0802 Ah |
| Sum of author branch integrals | 19.4274 Ah | 18.8959 Ah |
| Sum of separate cells' C/20 characterization integrals | 19.3951 Ah | 19.4132 Ah |

These are trapezoidal integrals over the observed discharge samples, excluding
unobserved transition edges. The characterization and module protocols/rates
and nominal temperatures differ, so their integrals are not expected to be
identical. Nevertheless, the baseline module integral exceeding its four-cell
C/20 total warrants investigation, not an invented capacity or time correction.

### Recorded protocol differs from the article

[Data in Brief Table 4 and section 3](https://pangea.stanford.edu/ERE/pdf/OnoriPDF/Journals/91.pdf)
describe a 90 min initial rest, a 60 min post-discharge rest, and module CV
termination below 0.2 A. The actual recorded steps show:

- Initial rest: approximately **30 min** in test 53 and **240 min** in test 28.
- Post-discharge rest: approximately **45 min** in both runs.
- Both CV phases end at approximately **1 A**, not 0.2 A, in both runs.
- Charging plateaus are approximately 6.47 A; discharge approximately 14.55 A;
  voltage approaches 4.2 V and ends discharge near 2.5 V.

Use the recorded current and step flags as inputs. Do not assume these records
begin at an exactly known SOC, meet a common equilibration protocol, or represent
the paper's nominal recipe verbatim. The source schedule file is named in
`Global_Info` but is not included in this archive. The paper also has a duplicated
step label in Table 4; actual raw step indices are 1-8.

### Row 32 is isolated, not silently relabelled

The article's test 32 and the actual processed
`M2_NMC_Unaged_R1_T25.mat` both assign **P20, P11, P17, Y1**. Y1 is the aged NMC
cell per the article and the actual `Aged_cells` characterization folder.
The raw workbook test label contains `TEST_32_NMC_R1_T25_NEW_DOE2` and has no
independent cell-ID field. Thus raw metadata does **not resolve** the ageing
contradiction; it corroborates the conflicting label rather than providing a
replacement identity. The run is quarantined. All other all-NMC article cell
allocations match their processed metadata. Neither selected run contains Y1.

## Topology and thermal observability

The physical object is a **1s4p LG INR21700-M50T NMC module**, at cell-level
voltage, not a complete 12 V/48 V backup battery. The terminals are on the same
side of a ladder. Position 1 is nearest them; position 4 is furthest. M1 maps
positions 1-4 to sensors H1-H4; M2 uses H5-H8 for its local positions 1-4.

Proposed electrical topology: four cell branches between two rails, with
interconnect segments between neighbouring positions on **both** positive and
negative rails. For the idealized equal-segment resistance `R_int`, the related
model's equation (1) gives, with positive discharge:

```text
I_module = I1 + I2 + I3 + I4
V_cell(k+1) - V_cell(k) = 2 R_int * sum(I_j for j > k),  k = 1,2,3
```

The factor 2 accounts for both rails. Shared downstream currents flow through
these segments, so four independent per-cell series resistors are not an
equivalent topology. See [Fasolato et al., section 2.2 / equation (1)](https://pangea.stanford.edu/ERE/pdf/OnoriPDF/Journals/109.pdf).
R0/R1/R3 are nominal 0/1/3 mOhm settings. Residual lead/contact resistance and
actual component values are not identified independently. R0 is not proof of
zero physical resistance. No network solver has been implemented in this task.

Observed thermal states are the four cell-centre **surface** temperatures and
measured ambient. Surface ranges are 24.65-28.73 C in test 53 and 24.26-30.24 C
in test 28. The ambient trace varies (24.65-27.76 C and 24.48-28.94 C), including
brief excursions. Use the measured ambient trace and investigate its sensor
location before interpreting it as a spatially uniform boundary condition.
Core temperature is unmeasured. A surface-equivalent lumped network is the
appropriate first hypothesis; core/surface separation, thermal contact and
convection parameters need independent evidence/identifiability analysis.

## What the characterization can support

Both the article and related modelling methods specify **23 C** chamber
characterization. All seven relevant cells have usable pseudo-OCV and HPPC/MS
records. Actual surface temperature is retained, not set to 23 C. Pseudo-OCV
surface temperatures across this subset span about 22.06-23.93 C; HPPC/MS surfaces
reach about 27.93 C, so even these tests are not perfectly isothermal cells.

| Cell | Observed C/20 discharge integral [Ah] | Present in initial subset |
|---|---:|---|
| P7 | 4.8486 | Test 53 |
| P17 | 4.8444 | Tests 53 and 28 |
| P19 | 4.9040 | Test 53 |
| P13 | 4.7981 | Test 53 |
| P4 | 4.8346 | Test 28 |
| P10 | 4.8320 | Test 28 |
| P16 | 4.9022 | Test 28 |

No backwards/duplicate timestamps or screening gaps were found in these 14
characterization records. Pseudo-OCV sample counts range from 7,124 to 7,281;
median interval is 10 s. All seven HPPC/MS files have 71,309 samples, include
cycle indices 1-9, and have mixed ~1 s/~0.1 s intervals plus event samples.
Source step indices are 9-15 and 17-22, not a literal copy of the paper's
conceptual step numbers. For example, P7 has ~4.85 A discharge in step 10,
~2.66 A discharge pulses in step 12 and ~2 A charge pulses in step 14. Rest and
multisine segments are available; actual signals must guide segmentation.

| Parameter or state | Evidence and next-task limit |
|---|---|
| Discharge capacity at this protocol | Integrate complete C/20 record; values above are derived from observations, not fitted model parameters. |
| Pseudo-OCV versus passed charge/SOC proxy | C/20 loaded voltage supports a low-rate curve. Equilibrium OCV, hysteresis and exact SOC require explicit assumptions. |
| Effective instantaneous resistance | HPPC steps support finite-sampling pulse estimates after alignment; 0.1 s logging cannot distinguish all faster processes. |
| One-RC polarization parameters | Pulse/rest/MS data can support a candidate fit, followed by identifiability and independent protocol checks; no parameters have been fitted yet. |
| Temperature-dependent parameters over 10-40 C | Not identified by 23 C characterization alone. Temperature-labelled module runs exist, but their signals outside 25 C remain unaudited and current reconciliation is open. |
| Initial SOC, parasitic/contact resistance | Require explicit assumptions or additional identification; do not absorb current inconsistencies into these parameters. |
| Thermal capacity/conductances/heat coefficients | Surface transients alone do not uniquely establish these. Sourced priors or new experiments are needed, plus consistent electrical heat accounting. |

## Frozen experiment splits and leakage limits

[Split manifest](configs/splits.json) and [hash binding](configs/splits.lock.json)
were fixed before any battery model fitting. Whole experiments, never random
timestamps, are allocated as follows:

| Role | Exact runs |
|---|---|
| Calibration | `M1_NMC_Unaged_R0_T25`, `M1_NMC_Unaged_R0_T10`, `M1_NMC_Unaged_R0_T40` |
| Development validation | `M1_NMC_Unaged_R3_T25`, `M2_NMC_Unaged_R1_T10` |
| Final assessment | `M1_NMC_Unaged_R3_T10`, `M2_NMC_Unaged_R1_T40`, `M1_NMC_Unaged_R3_T40` |
| Quarantine | `M2_NMC_Unaged_R1_T25` |
| Deferred scope | All aged and non-NMC runs |

The initial inspection is restricted to the two 25 C calibration/development
runs. The wider manifest reserves a possible temperature-extension assessment;
it does not certify readiness over that temperature range. There is **no clean
25 C final-assessment unaged run** left after quarantining row 32. A future
independent 25 C test is needed for such a claim.

This is **known-cell reconstruction conditional on characterization**, not
unseen-cell generalization. Calibration and final sets reuse P3, P6, P7, P12,
P13 and P14. Development and final sets reuse P3, P7, P12 and P16. Tests 53/28
reuse P17. Reused cells, sensor rigs and experimental history create dependence;
rows and even whole runs are not independent draws of new batteries.

Pre-module characterization may inform each named cell's parameters, including
cells later used for assessment, provided that policy is declared. Final module
signals must remain closed until the model, sensor corrections and engineering
acceptance criteria are fixed. Revision requires a new manifest version and a
contamination assessment. The CLI refuses to audit final/quarantined signals.

## Repair comparisons and next-task gate

Near the measured domain, future validated work could investigate current
sharing under the recorded 0/1/3 mOhm shared-rail settings and characterized cell
heterogeneity. A cell-placement or interconnect change remains a **prospective
comparison**, not a demonstrated improvement. Tests 53 and 28 have different
cell populations and equilibration histories, so their difference is not a
controlled same-module repair experiment.

The current evidence cannot support ranked cooling redesigns, different geometry,
unmeasured contact arrangements, mixed-chemistry repairs, life extension, cost or
runtime improvement claims, high-voltage backup operation, or certification.
There is no optimizer or autonomous redesign in this deliverable.

**Next task permitted:** identify capacity/pseudo-OCV and a provisional low-order
single-cell electrical model for the seven inspected cells, at the documented
23 C protocol, with parameter provenance and identifiability checks. This is
permission to investigate those records, not a claim of validated performance.

**Module gate remains closed** until an authoritative calibration/processing
explanation or independent measurement reconciles the branch and module
currents, the actual schedules and initial-state assumptions are understood,
and an engineering uncertainty/acceptance budget is agreed before fitting.

Do not select whichever current source makes a prospective model look best.

## Reproduction and delivered evidence

In PowerShell, from the project root:

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe -m voltforge.data.cli all
& C:\Users\DELL\anaconda3\python.exe -m pytest -q
```

The tested environment is CPython 3.12.3, NumPy 1.26.4, SciPy 1.13.1, pandas
2.2.2, Matplotlib 3.9.2, OpenPyXL 3.1.5 and pytest 7.4.4. Versions and portable
installation commands are in [README.md](README.md) and `requirements.txt`.

Numerical evidence: [module audit](reports/module_audit.json),
[characterization audit](reports/characterization_audit.json),
[Hall calibration audit](reports/hall_calibration_audit.json),
[actual dictionary](reports/DATA_DICTIONARY.md), and
[parser notes](reports/PARSER_NOTES.md). See [verification](reports/VERIFICATION.md)
for completed checks and their limits.

Measured figures (no model predictions):

- [Test 53 full cycle](reports/plots/M1_NMC_Unaged_R0_T25_full.png),
  [discharge](reports/plots/M1_NMC_Unaged_R0_T25_discharge.png),
  [current-conservation residual](reports/plots/M1_NMC_Unaged_R0_T25_kcl.png).
- [Test 28 full cycle](reports/plots/M1_NMC_Unaged_R3_T25_full.png),
  [discharge](reports/plots/M1_NMC_Unaged_R3_T25_discharge.png),
  [current-conservation residual](reports/plots/M1_NMC_Unaged_R3_T25_kcl.png).

## Three questions for the human team

1. **Can the data authors provide the exact Hall-to-current processing code,
   per-sensor/per-run coefficients, current-reference calibration and actual
   schedules for tests 53 and 28?** Ask specifically about the opposite-sign
   discharge residuals, test 53 throughput, and the recorded 1 A CV endpoints.
   No outreach has been sent by this agent.
2. **For test 32, was position 4 actually Y1, or is the Unaged label/cell table
   wrong?** Until clarified, keep it excluded. Can the team obtain an independent
   25 C all-NMC run to preserve a meaningful final assessment at the pilot temperature?
3. **Which engineering decision should the first validated model distinguish,
   and what measurement uncertainty and acceptable error would make that decision
   credible?** Confirm scope at 23-25 C first, agree a tolerance budget before
   fitting, and assign electrical topology/sensing and thermal interpretation reviewers.
