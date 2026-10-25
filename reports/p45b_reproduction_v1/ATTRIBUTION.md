# Public source and derived comparison data

Source data: Edmund Dickinson, Ceren Zor, Darryl Doyle, Christian Pilling,
Katie Lukow, Kieran O'Regan and Gavin White, About:Energy (2026), Molicel P45B
ECM data release, [Zenodo DOI 10.5281/zenodo.19052626](https://zenodo.org/records/19052626).
The public record declares open access and
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
The preserved [metadata receipt](../p45b_intake_v1/public_release.json) records
the licence and original published checksums, matched to the local downloads.

This directory contains derived comparison CSVs and figures for only
`MOLICEL_P45B_025degC_1C_Dch.csv`, plus an audit of the published base parameter
table. Original experimental time/current/voltage/temperature values retain
their meanings and source line numbers. Added fields are simulated electrical
states, predicted voltages, errors, classification labels and coverage flags.
These additions are VOLT-FORGE calculations, not the source authors' predictions
or endorsements. Their simulation columns and validation workbook were not used.

The source archive MD5 is `0bd40f92dfabcea679900696cc2c0077` and the base parameter
table MD5 is `2b670bf683b99e59124f4b2454f17a75`. Exact SHA256 values and the selected
member hash are retained in the versioned configuration and completed summary.
Original downloads are unchanged and excluded from Git. The separate SSRN PDF
is not redistributed; this dataset licence is not assumed to cover that paper.

The derived results identify a substantial low-SOC voltage discrepancy. They do
not establish independent cell or module validation, battery improvement, or a
design recommendation. Assessment protection is a project evidence rule, not
a restriction on obtaining the original public dataset under its licence.
