# M50T thermal data intake complete; physical fitting remains gated

26 October 2026. The public archive is authentic, documented enough to inventory
and begin a bounded importer, and relevant to LG M50T thermal research. It is
**not yet a calibrated input package for our dynamic thermal model**. No thermal
parameter was fitted or adopted, and no module temperature prediction was added.
The frozen LG/P45B electrical models and synthetic thermal prototype are unchanged.

## What was completed

The original M50.zip and ReadMe.txt match the published checksums. The archive
contains **11 experiment families, 33 measurement members, one internal README
and one directory entry**. Each family has raw thermal text, processed MATLAB
data and raw electrical text. Those three files are not independent experiments.
The [inventory](inventory.json) records original names, sizes, CRCs, source hash,
nominal conditions and family-level reservations. It never extracts measurements.

We obtained the open-access main paper from Imperial College and the publisher's
Word supplement. The sensor diagram and color-coded protocol table were visually
inspected; the supplement text and all embedded figures were inspected. The
original files remain local under data/raw/thermal_m50t/documentation. Their
URLs and hashes are retained in [sources.json](sources.json).

The metadata-only procedure was followed by a separately declared schema probe
of **cell 1, test 103 only**. Its three members are now used development material.
Thirty numerical members remain unopened: 12 in the unused development reserve
and 18 in the assessment reserve. No assessment outcome was viewed or selected.

## Prospective allocation

| Whole family | Filename SOC (%) | Filename temperature (degC) | Allocation / current access |
| --- | ---: | ---: | --- |
| cell 1 / test 103 | 50 | 20 | First development candidate; bounded schema probe completed |
| cell 1 / test 100 | 75 | 20* | Unused development reserve |
| cell 1 / test 102 | 25 | 20 | Unused development reserve |
| cell 1 / test 104 | 50 | 10 | Unused development reserve |
| cell 1 / test 105 | 50 | 30 | Unused development reserve |
| cell 2 / test 106 | 50 | 20 | Unopened assessment reserve |
| cell 2 / tests 107, 108 | 50 | 10 | Both reserved; setup/fault relationship unresolved |
| cell 2 / test 109 | 50 | 30 | Unopened assessment reserve |
| cell 2 / test 110 | 75 | 20 | Unopened assessment reserve |
| cell 2 / test 111 | 25 | 20 | Unopened assessment reserve |

*Test 100's electrical filename omits temperature. Its thermal filenames say
20 degC; the electrical member's own temperature remains null in the inventory.
All listed conditions are labels, not verified measured histories. Test 103 was
chosen as the central nominal condition before its payload was opened.

[thermal_m50t_allocation_v1.json](../../configs/thermal_m50t_allocation_v1.json)
keeps representations together and reserves the second specimen. Assessment
requires a later frozen modelling/calibration procedure and complete sequences;
no timestamp-level random split is allowed. The paper and supplement's published
aggregate outcomes are known. These raw records are unused by VOLT-FORGE, not
blind to all published results. A future check on cell 2 would assess another
characterized specimen in the same laboratory fixture, not an unknown-cell
population or the four-cell application.

## Confirmed documentation and scope

The primary paper defines a base-cooled, insulated fixture with nickel electrical
tabs, a brass cooling rod and Peltier control. It uses 1 Hz alternating current,
nominal zero mean, six-hour pulse sets and 90-minute rests. Table 1 uses amplitudes
3.75, 5, 6.25, 7.5, 8.75 and 10 A at 50% SOC and nominal 10/20/30 degC. Its blue
cells restrict 25/75% SOC tests to 20 degC and the first four amplitudes. These
are published protocol descriptions, not verified per-file coverage.
[Paper, sections 3.2-3.3, Figure 3 and Table 1](https://spiral.imperial.ac.uk/server/api/core/bitstreams/7390acd4-1bea-47d3-8ecd-33adb1897777/content).

The paper's CCC relates base heat rejection to cap-to-base temperature difference
at steady state. It does not identify whole-cell heat capacity or the module's
node-to-ambient conductance. The application remains LG M50T 1s4p with its proposed
14.55 A, 360 s load. Any first thermal demonstrator must explicitly use this
different, single-cell laboratory case. Application temperature limits and
acceptable prediction errors remain **requirement not configured**.

## Schema findings and unresolved definitions

The [corrected development schema](development_schema_003.json) records the
following observations. These are file-format findings, not thermal accuracy.

| Observation | Consequence |
| --- | --- |
| Raw thermal header has 16 columns; internal README lists 15. The final raw column is a second instrument's cold-junction channel. | Do not silently discard or relabel it. The [channel map](channel_map.json) preserves raw order and separates the README mapping from unresolved interpretation. Neither cold-junction channel is established ambient. |
| Raw text declares seconds and degC. Prefix includes NUL bytes and legacy degree-symbol encoding. | Preserve raw bytes; record decoding and normalization. Time zero and cross-instrument alignment remain unverified. |
| Processed MAT is MATLAB 7.3/HDF5. It includes SS_Q, Qnet, Qgain, Qloss, AltQ, SS_T, SS_CCC and uncertainty-related names. | Heat-related outputs exist. Their names alone do not establish units, sign, calibration, formulas, steady-state windows or whether they are independently measured. No dataset values were read. |
| HDF5 storage shapes include SS_Q 1x6, SS_T 15x6, celltemps 5x258986 and templabels 1x14. | These are container dimensions, not verified MATLAB presentation order or channel mapping. Do not transpose or align them by assumption. |
| Electrical file declares a 97-line header; this bounded probe inspected only the first 64 lines / 32 KiB. | Electrical data columns, time/current units, actual waveform and polarity have not been decoded. The complete header is a concrete next importer task. |
| Header names a SOC-reset settings file and declares instrument capacity 1 Ah. | The settings file is absent from the archive inventory. Instrument configuration is not a measured M50T capacity, nor proof of achieved initial SOC. Do not overwrite the frozen electrical capacity. |

The supplement adds a documented setup fault: a cooling-fin/negative-tab contact
introduced electrical noise into voltage and thermocouple readings, later fixed
in another setup. Its body describes a 10 degC comparison while the Figure 9
caption says 20 degC. It does not identify raw test numbers for those setups.
The two 10 degC cell-2 files **might** relate to that repeat, but this remains a
hypothesis. Neither is excluded or designated the good run based on its outcome.
[Publisher supplement, Setup & Cell Variation / Figure 9](https://ars.els-cdn.com/content/image/1-s2.0-S2352152X22012166-mmc1.docx).

## Why no physical thermal fit was made

The reviewed package has no standalone processing script or calibration file
in its directory inventory. The README, main paper and supplement do not provide
an explicit calibrated rod-temperature-to-heat conversion and its uncertainty
for these raw records. The metadata probe found processed heat fields, so it
would be wrong to claim that heat information is absent. Their numerical content
and processing lineage remain unverified.

In our proposed balance, C*dT/dt = Qgen - Qout, the outgoing heat through the
fin is not the heat generated inside the cell during a transient: energy can
accumulate in the cell, contacts and fin. Using Qout as Qgen would remove the
storage term we want to identify. Multiplying an unknown heat scale, C and H
by one factor also leaves the simple one-node temperature response unchanged.
Thus fitting all of them to temperature cannot establish their physical scale.
An electrical loss estimate does not independently resolve that ambiguity.

A steady-state CCC reproduction may become possible with traceable processed
heat definitions or a calibrated fin conversion. A cooling-only study might
identify an effective relaxation rate under stated boundary assumptions; that
would not by itself determine C and H separately. Neither result automatically
supports temperature prediction for the proposed module.

## Exact next engineering work and external dependencies

Continue locally with a bounded importer for test 103: decode its complete
electrical header and thermal channels, retain original timestamps, establish
sign/units and a justified alignment, decode MATLAB label references without
assuming orientation, and compare processed/raw representations. Mark resulting
observations as development evidence. Do not open cell 2 to resolve this schema.

Before fitting a physically scaled dynamic model, establish:

1. The formulas, constants, units and sign of SS_Q, Qnet, Qgain, Qloss and AltQ;
   calibrated brass-rod conductivity/conductance, sensor offsets/uncertainty and
   loss corrections; the steady-state averaging windows and uncertainty method.
2. The thermal/electrical synchronization convention and any resampling, discarded
   channels/rows or clock-offset corrections. Explain the extra cold-junction
   channel and all processed temperature-label dimensions.
3. The mapping from setup 1/2/3 to raw test numbers, which records contain the
   reported fault, and whether the supplement comparison is at 10 or 20 degC.
4. The original preparation/settings file, actual SOC/capacity definition and
   any ambient/Peltier-control trace. Filename values alone are insufficient.
5. For dynamic C/H identification, an independently supported heat source and
   boundary/storage model, or appropriate known-heat transient/calorimetry data.

The archive/schema work can continue without author contact. If the necessary
calibration/procedure cannot be recovered from the development files or public
documentation, authors' processing/calibration files or another suitable public
dataset are required. Controlled measurements are an alternative, not the only
route. The questions above are prepared for later use; no outreach was sent.

## Verification and provenance

**65 tests pass:** 26 new synthetic intake/probe checks plus the 39 existing
synthetic thermal checks. Tests check complete-family reservation, duplicate and
unsafe paths, hash changes, denied assessment reads, HDF5 link restrictions,
no numerical dataset indexing, legacy text handling and the NUL-row regression.
These are software checks; no measured-model error or independent module
validation result was produced.

Attempt 001 stopped at the MATLAB-version mismatch. Attempt 002 inadvertently
displayed one NUL-prefixed initial row from the already allocated development
family. Both attempted implementations and the first receipt remain preserved;
[the correction note](SCHEMA_PROBE_REDACTION_NOTE.md) explicitly identifies its
incorrect no-values-presented field. Attempt 003 fixes the classifier. No
assessment exposure occurred, and the whole development family is treated as
used evidence throughout. The numerical row is not used for a fitted result.

The [verification receipt](verification.json) pins this intake and checks every
artifact of the preceding assistant/thermal release. Source models, raw archives,
unused electrical records and frozen module outcomes remain unchanged.

```powershell
& C:\Users\DELL\anaconda3\python.exe -B scripts\intake_thermal_m50t.py --verify reports/thermal_m50t_intake_v1/inventory.json
& C:\Users\DELL\anaconda3\python.exe -B scripts\probe_thermal_m50t_schema.py --out tmp/m50t_schema_replay.json
& C:\Users\DELL\anaconda3\python.exe -B -m pytest -q tests/test_thermal_m50t_intake.py tests/test_thermal_prototype.py
& C:\Users\DELL\anaconda3\python.exe -B scripts\verify_thermal_m50t_intake.py --out tmp/m50t_intake_verification.json
```

Use fresh output paths and the downloaded archive. The metadata-only inventory
uses the Python standard library. The bounded schema probe uses installed SciPy
and h5py; frozen application dependency files were not modified. PDF-reading
tools were installed only under ignored tmp/pdf_runtime for document review.

For a student: we have useful real thermal data and a protected test plan. We
first need to know exactly what the recorded heat and temperatures mean. A
curve that looks convincing would not yet give us trustworthy pack temperatures.
