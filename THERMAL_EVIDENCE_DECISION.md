# Public thermal-evidence decision

27 October 2026. **The bounded search is complete. Physical thermal fitting and
module temperature prediction remain unsupported.** We found more precise
documentation and a calorimetry-code lead, but no qualified replacement evidence
package in the inspected sources. This is a conclusion about this search, not a
claim that suitable public data does not exist.

The [author investigation](reports/thermal_public_evidence_v1/AUTHOR_SEARCH.md)
checked the current M50T release, a later thesis, related apparatus documentation
and public code/repository listings. The thesis repeats the published rod geometry
and generic protocol; it does not resolve test-103's clock relationship, offsets,
heat conversion or processing windows in the reviewed methods pages. A different
pouch-cell apparatus provides constants and averaging guidance, but importing
them into test-103 would be an unsupported change.

The [six-source comparison](reports/thermal_public_evidence_v1/ALTERNATIVES.md)
covers calorimetry, pulse-based thermal characterization, LG M50 material/property
data, LG M50 current/temperature records and two abuse-data sources. None was
adopted as an M50T module model or independent module validation.

The most concrete new lead is the
[1 Ah NMC811 calorimetry dataset](https://data.mendeley.com/datasets/98thdkgp8z/1).
Its example notebook defines its heat-sensor channels as **voltages**, then
converts them to millivolts for plotting. It does not supply the needed conversion
to watts or a documented cell/boundary temperature record. We inspected source
only, skipped saved outputs and left all ten numerical NPY members unopened.
The 16 MB archive was downloaded and hash-verified; the separate plots were not.
This distinction is recorded rather than claiming all raw bytes remained remote.

## Engineering decision

Keep frozen v2 and the synthetic-only thermal solver unchanged. Do not substitute
literature heat capacities, a different apparatus's conductance or sensor-voltage
amplitude for independently justified physical inputs. Do not fit away the
test-103 processing discrepancy or infer a module cooling coefficient from CCC.
No thermal control is enabled in the editor, and no temperature safety limit or
accuracy requirement becomes established by this search.

The electrical configure/edit/simulate/compare/export workflow remains the
implemented demonstration, with its existing coverage and validation limitations.
The local command assistant remains local. A real thermal demonstration would
require either resolving the M50T evidence or explicitly changing to a documented
single-cell calorimeter/fixture case; that would be a separate scope from the
four-cell application.

## Precise next evidence

For M50T, the required item is the **test-103 processing/calibration and acquisition
package**: clock relation, temperature offsets, SS_Q units, actual rod conductance,
steady-state window indices, fixture/setup mapping and uncertainty. The previous
engineering report already gives the questions; this search did not recover their
answers. The related author release is a documentation lead, not established heat
calibration.

For the calorimetry alternative, first obtain the methods/calibration material for
[DOI 10.1016/j.powera.2022.100097](https://doi.org/10.1016/j.powera.2022.100097),
specifically:

1. Sensor-voltage-to-heat conversion, sign, area convention, calibration runs,
   uncertainty and dynamic response.
2. Shared timestamps/start markers for heat sensors and the cycler.
3. Actual cell and calorimeter/boundary temperatures and thermal storage/path
   definitions if the aim is a temperature model, rather than entropy extraction.
4. Preparation/repetition/specimen identity sufficient to declare whole-sequence
   development and assessment allocations before numerical inspection.

The landing page/abstract and example code were accessible; the complete
calorimeter methods/calibration were not established in this pass. No outreach
was sent. If those documents lack the required measurements, this alternative
also cannot identify the intended temperature model. Additional downloads alone
will not remove that limitation.

## Reproduce and preservation checks

This release adds reports and documentation tooling only. All previously pinned
artifacts remain byte-identical. The verifier checks the prior release chain and
frozen software identity without reopening numerical measurement records. Its
optional local check hashes downloaded bytes; it does not deserialize arrays.

From the repository root:

```powershell
& C:/Users/DELL/anaconda3/python.exe -B -m pytest -q tests/test_thermal_evidence_documentation.py
& C:/Users/DELL/anaconda3/python.exe -B scripts/verify_thermal_public_evidence.py --verify
& C:/Users/DELL/anaconda3/python.exe -B scripts/verify_thermal_public_evidence.py --verify --local-sources
```

The last command requires the local downloads. To repeat the documentation-only
extraction from the pinned calorimetry archive, use a fresh directory:

```powershell
& C:/Users/DELL/anaconda3/python.exe -B reports/thermal_public_evidence_v1/inspect_calorimetry_documentation.py --out data/raw/thermal_public_evidence/notebook_replay
```

The fixed metadata downloader also accepts a fresh `--out` directory under
`data/raw/thermal_public_evidence`; its `--help` lists explicit document names.
New remote responses may differ and do not overwrite earlier evidence. Receipts
include failures and distinguish downloaded archives from inspected members.

For a student: the software can simulate the supported electrical case and check
its assumptions. We now know more exactly why these thermal files are insufficient
for a trustworthy temperature prediction. The next physical step is obtaining
calibrated heat and boundary information; the working electrical demonstration
can continue without claiming that thermal validation has been completed.
