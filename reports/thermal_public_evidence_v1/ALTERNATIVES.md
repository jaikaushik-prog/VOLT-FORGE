# Six alternative source families screened

27 October 2026. This is a bounded documentation screen. No candidate below
establishes thermal accuracy for the LG M50T 1s4p module. Published models,
different-cell measurements and a downloaded archive are distinguished from
qualified new experimental evidence.

| Candidate | Evidence inspected | Main limitation for our task | Disposition |
|---|---|---|---|
| [Ahmad/Thenaisie/Lee, 1 Ah NMC811 pouch](https://data.mendeley.com/datasets/98thdkgp8z/1) | Landing metadata, exact two-file inventory and notebook source only | Raw top/bottom sensor signals are volts; example supplies no watts conversion, calibration uncertainty or cell/boundary temperature channels | Best targeted calorimeter-documentation follow-up; no fitting yet |
| [Klink et al., Kokam 46 Ah](https://zenodo.org/records/13903526) | Metadata and author-uploaded paper methodology | Different cell and fixture; calibration excitation uses electrical pulses, with heat estimated from electrical overvoltage rather than independently established heat input | Conditional separate-fixture study only; not an M50T parameter source |
| [O'Regan et al., LG M50 properties](https://zenodo.org/records/5171874) | Parameter repository metadata and methods manuscript | Component-level thermal measurements and fitted boundary assumptions do not identify our specimen/fixture; M50-to-M50T equivalence unestablished | Useful property-method reference; no parameter adoption |
| [Chen et al., three LG M50 cells](https://zenodo.org/records/4032561) | Metadata and CSV filenames/checksums only | Current, voltage and cell/chamber temperature are advertised, without a separately calibrated heat-input channel | Potential later electrical/temperature transfer study; insufficient heat-scale evidence |
| [NIST mds2-4027](https://data.nist.gov/od/id/mds2-4027) | Primary experiment-description text | External-heater abuse experiments; electrical heater power is not necessarily heat entering the cell; post-venting events are outside normal-operation model scope | Exclude from present operating thermal identification |
| [NREL/NLR Battery Failure Databank](https://nrel.sitefinity.cloud/transportation/battery-failure) | Primary landing-page description | Heat output concerns thermal runaway/abuse and ejected contents | Exclude from present operating thermal identification |

## What the promising calorimetry example actually establishes

The Mendeley file API lists a 16,213,529-byte data/example archive and a separate
plot archive. The [declared extension](CALORIMETRY_ARCHIVE_DECLARATION.md)
permitted the former's download to inspect documentation. Its SHA-256 matched the
publisher's metadata. The directory has one notebook, a macOS sidecar, and ten
NPY records: heat-sensor/electrical pairs labelled 4, 8, 10, 16 and 32 minute rest.
Only the [explicitly allowed notebook source](NOTEBOOK_SOURCE_DECLARATION.md)
was inspected; two saved outputs were skipped. No NPY file was opened, no code
executed and no filtering applied. The plot archive was not downloaded.

The notebook documents time in seconds, top/bottom sensor voltages, and separate
current/voltage data. Its example converts volts to millivolts for plotting and
illustrates smoothing. Neither a physical heat calibration nor temperature
channels appear in that documented schema. This supports a precise next request:
the sensor-to-heat conversion with units and uncertainty, dynamic response and
clock relation, plus temperature/boundary records if identifying thermal storage.
This is a different cell; even a successful calorimeter replay would not validate
the M50T module. Source hashes and skipped-output accounting are retained.

## Methods findings that prevent inappropriate transfer

Klink's [author-uploaded paper](https://www.researchgate.net/publication/349076809_Thermal_fault_detection_by_changes_in_electrical_behaviour_in_lithium-ion_cells)
uses rectangular current excitation and an electrical overvoltage heat estimate.
Its discussion explicitly identifies fixture mass, effective area and parameter
ambiguity. An effective fit for that assembly is not independently calibrated
whole-cell heat capacity. Our interpretation is that it could support a carefully
declared study of that fixture, but changing the cell/application would be a
scope change. We did not download its measurement ZIPs.

O'Regan's [methods manuscript](https://wrap.warwick.ac.uk/id/eprint/196287/2/WRAP-Thermal-electrochemical-parameters-high-energy-22.pdf)
describes DSC on dried composite powders and separator and laser-flash analysis
on electrode samples. Its model discussion also describes tuning the heat-transfer
coefficient. Those are valuable material and model-development sources, not an
independent determination of the installed M50T module's cooling. The repository
labels the file an accepted manuscript, while internal cover/footer text identifies
a January 2022 preprint; record that version ambiguity rather than presenting it
as the verified version of record. No property curves or model parameters were
imported. Direct local PDF downloads failed; the web reader supplied methods text.

The Chen concept-record request resolves to version DOI 10.5281/zenodo.4032561.
The three cell CSV names/checksums are recorded, but the files remain undownloaded.
Nominally similar cells and measured temperature alone do not resolve heat-source
identifiability or fixture transfer.

The NIST description gives a heater electrical-power specification and sensor
placement, but the experiments deliberately continue through venting/ignition.
Selecting a convenient portion after viewing outcomes would require a separate
prospective protocol. No workbook was downloaded. The Failure Databank's
calorimetry likewise concerns abuse, so its files were not fetched.

## Exposure, access and reproducibility

Published search snippets included aggregate model-fit and abuse outcomes for
Klink, O'Regan and the NIST experiment descriptions. They are known literature,
not held-out validation. No numerical measurement member, assessment trace or
saved notebook plot was displayed. Ten new NPY members remain unopened inside
the downloaded archive; this is explicitly different from claiming no raw-data
archive was downloaded. Existing protected data and allocations are unchanged.

The first metadata download encountered the local socket restriction; the
authorized retry succeeded. The first Mendeley inventory URL returned 404;
the corrected public file endpoint succeeded. Institutional PDF retrieval had
TLS failures and the preprint endpoint returned 403. These are access limitations,
not evidence that a publication or calibration does not exist. Failure receipts
and successful response hashes are preserved in `alternative_sources.json`.

Re-run only metadata downloads with the fixed-list fetch script and a fresh
ignored directory. The source extractor independently pins the archive hash,
reads exactly one notebook and never executes its source. Exact commands are in
[the decision](../../THERMAL_EVIDENCE_DECISION.md). The original publication's
calorimeter calibration methodology remains the most focused follow-up; this
screen does not justify fitting or further indiscriminate dataset downloads.
