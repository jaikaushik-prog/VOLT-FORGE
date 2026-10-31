# Bounded public author-documentation search

27 October 2026 (India time). **No new evidence found in the checked sources
establishes test-103 clock alignment, temperature-offset calibration or its heat
conversion. The physical-fitting gate remains closed.** The search did find a
later author thesis, explicit processing guidance for a different pouch-cell
apparatus, and a related author dataset with settings/channel documentation.
Those are useful leads, not substitutes for the missing test-103 definitions.

This work read public repository metadata and selected documentation only. It
did not reopen any measurement member, rerun full-record diagnostics, inspect
reserved outcomes, fit parameters, send outreach or change frozen artifacts.
Downloads and selected-page extracts remain ignored under
`data/raw/thermal_public_evidence/author_search/`. `author_sources.json` records
URLs, retrieval times, hashes, access boundaries and unsuccessful requests.

## Sources checked and concrete findings

1. **Existing Zenodo release and version API.** The [record](https://zenodo.org/records/6421061)
   and its [version listing](https://zenodo.org/api/records/6421061/versions)
   report one version, 6421061, marked latest. The listed files remain M50.zip,
   30Q.zip and ReadMe.txt. No new archive was downloaded. This establishes what
   this record currently exposes; it does not establish that the authors have no
   processing code elsewhere. The [paper's Imperial original-file listing](https://spiral.imperial.ac.uk/server/api/core/bundles/46e97995-6f29-4703-833f-fc8a5229245d/bitstreams)
   exposes the already known published PDF. Current Crossref metadata has an empty
   relation field and no `update-to` entry; that is not proof that no correction exists.

2. **Later thesis, new methods evidence.** Marzook's [2024 doctoral thesis](https://doi.org/10.25560/122074)
   was located through the Imperial repository API. Its contents/bookmarks were
   inspected before selecting methods pages. Printed pages 42–45 (PDF 65–68)
   repeat the 6 mm rod diameter, 60 mm thermocouple separation and generic six-hour
   protocol. They provide no numerical rod-conductivity calibration or test-103
   processing timestamps. Printed page 74 (PDF 97) recommends controlling losses
   and realistic connections, and explicitly limits transferring CCC across changed
   thermal/electrical boundaries. Appendix A.2 (PDF 201) concerns theoretical 3D
   heat-transfer equations, not raw measurement processing. Thus the reviewed
   thesis material neither explains the conditional 500.085 W/(m K) inference
   nor changes the no-transfer/no-fit decision. No chapter results pages were opened.

3. **Different apparatus: useful method, not interchangeable calibration.**
   Russell, Hales, White and Patel's [HardwareX methods paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC9058592/)
   describes a pouch-cell apparatus. Its Fins section uses 12 mm bars, 100 mm
   sensor separation and a design conductivity of 127 W/(m K). Its Data processing
   section averages the last 600 seconds of each pulse-current set, then calculates
   fin heat from the temperature gradient and geometry. These values belong to
   that design; they do not establish M50T test-103's constants or averaging windows.
   Its [OSF project](https://osf.io/zywvf/) currently lists license.txt, CCC-CAD.zip
   and CCC-BOM.xlsx in the inspected storage provider. No standalone measurement
   processing script appears in that listing. The CAD archive and spreadsheet were
   not downloaded. No claim is made about their uninspected contents.

4. **Related author release: a future documentation lead.** The Zenodo author
   query returned eight records, including two battery releases. The [related
   benchmarking release](https://zenodo.org/records/7385979) lists Thermal.zip,
   Electrical.zip and ReadMe.txt. Its [README](https://zenodo.org/records/7385979/files/ReadMe.txt?download=1)
   says the base-cooled/natural-convection electrical folders include BioLogic
   settings, and thermal channel labels are defined by ThermConfig files. Only
   metadata and that README were downloaded. This suggests better preparation and
   mapping documentation may be available there. It does not establish a heat
   calibration, independent heat source, test-103 correspondence or a suitable
   validation allocation. Both numerical ZIPs remain unopened and undownloaded.

5. **Bounded script search.** GitHub repository search returned zero repositories
   for the exact phrase `cell cooling coefficient`, and zero for `Waseem Marzook`.
   The broader `Marzook` query returned 47; only its first 30 titles/descriptions
   were reviewed, without finding an attributable battery-processing repository.
   Repository search does not search all code. Exact-filename and `SS_Q` web
   searches did not surface a relevant public processing script in their returned
   results. No exhaustive internet-absence claim is justified.

## What remains unresolved

| Question | What this search adds | Evidence still needed |
|---|---|---|
| Electrical/thermal clocks | No start marker, offset or synchronization procedure in the selected M50T methods material | Test-103 acquisition log or explicit synchronization rule, including drift and sample semantics |
| Raw-to-MAT offsets and removed first row | No calibration origin for the already observed offsets in the reviewed pages | Author processing script, calibration record, and uncertainty/offset convention |
| Heat conversion | Thesis repeats the published geometry; another apparatus has explicitly different dimensions/constants | Test-103 SS_Q units, actual rod geometry and calibrated conductance, equations and uncertainty |
| Steady-state windows | A different pouch apparatus uses a 600 s terminal window | Test-103's own window indices/times and whether ratios are averaged before or after division |
| Fixture fault and 10/20 degC discrepancy | No new raw-ID mapping from the reviewed methods pages | Setup-to-test-ID log and clarification of the original supplement |
| Dynamic cell storage | No independently justified transient heat source or fixture-storage separation recovered | Known-heat/heat-flux calibration, boundary history and a defensible fixture/contact model |

The 500.085 W/(m K) quantity remains a **conditional processing inference** from
already used development evidence. The separate apparatus's 127 W/(m K) is not a
replacement constant. Neither similar magnitudes nor geometry-based speculation
would establish an author error or justify rescaling SS_Q. The 600 s example must
not be searched against test-103 until it matches an expected CCC; that would be
circular window selection. No such calculation was performed.

## Access and exposure accounting

The thesis was downloaded as documentation after notifying the orchestrator.
Only its bookmarks and PDF pages 65–68, 97, 200–201 were extracted. Pages 67–68
were also rendered and visually checked. PDF page 68 contains the previously
published protocol matrix, not fresh assessment outcomes. Page 97 contains author
usage limitations. The Setup & Cell Variation subsection at PDF page 70 lies in
Results & Discussion and was deliberately not opened; consequently this search
does not claim that the entire thesis lacks a setup-ID statement.

The HardwareX search response incidentally included a published Kokam example
caption and a qualitative repeatability statement. They were not used as validation
evidence. The local review extracted only CCC calculation, Fins and Data processing,
removing example-figure/table containers; the Validation and characterisation
section was not opened. The previously known main paper's published aggregate
outcomes also appeared in web search results. All published material is treated as
known background; nothing here is a new independent assessment.

The first direct metadata fetch was blocked by the local socket sandbox; a
permitted read-only retry succeeded. A Zenodo query requesting 100 results received
HTTP 400 because unauthenticated requests permit 25; the corrected query returned
all eight hits. Both failure receipts remain preserved. No credentials were used
or exposed, and no numerical data download was attempted.

## Next bounded action

Keep the frozen model and reserves unchanged. The precise outstanding request is
for test-103 processing/calibration and acquisition metadata, or a public source
with independently documented heat input and boundary conditions. The related
benchmarking README is a lead for later metadata-first screening, not permission
to treat its temperature traces as calibrated heat measurements. The orchestrator
is screening alternative public datasets separately; this report makes no dataset
selection or parameter recommendation.
