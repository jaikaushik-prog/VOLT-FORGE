# Visual verification - revised submission draft

Reviewed 31 October 2026. This record applies to the generated one-page PDF with SHA-256:

`0f29a951d31f7aa48cee8404da1055440d4012a1573d58723828d06d8c763afa`

The sole PDF page was rendered with PDFium. The latest complete page was visually inspected at normal 1440 x 810 viewing size in `reviewed_slide_normal_view.png`; the larger render is also supplied. No clipping, overlaps, missing glyphs or out-of-page content were observed. The comparison numbers, conditions, caveats and core narrative are readable at normal viewing size. The original V4 screenshot illustrates the editor; its small UI labels are not required to read the comparison and its caption identifies its scope.

The table uses the same-end `baseline` option for 4, 3 and 2 cells, including required-case worst values. All 13 input files matched their SHA-256 bytes at source commit `c2339a569876da5fc20969ea578a91ae57f33384`. The current working-tree HEAD is recorded separately in `source_data.json` because application improvements are being made concurrently. No numerical study or model was rerun or edited.

The final evidence sentence says: "All 12 comparison cases missed the voltage and temperature bands." This does not call them independent experiments. The document presents 15/15 checks as numerical verification and explicitly states that measured accuracy is not established. No one-cell-loss guarantee, board certification, customer validation, current live-app fix or investment-return claim was added.

The automated checks confirmed one PDF page and required text, generated the two PNGs and extracted text, and wrote provenance and output hashes. They do not stand in for this visual review. The source-data JSON includes source selectors, unrounded values and hashes; links in the PDF point to the existing demo and appendix. The live endpoints were not tested by this artifact-building task.

The original cover, submitted slides, generators, frozen results and application code were not modified. This is a separate revised submission draft, not a published or submitted artifact. The team still needs to confirm the portal's accepted format and deadline.

Rebuild from the repository root:

```powershell
& C:/Users/DELL/anaconda3/python.exe scripts/build_reviewed_slide.py --pdfium-path C:/Users/DELL/Desktop/volt-forge/tmp/pdf_runtime
```

After a future rebuild, check the new output hash and re-inspect the rendered page before reusing this verification statement.
