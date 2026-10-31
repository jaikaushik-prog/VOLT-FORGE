# Editable Round 1 slide

One 16:9 content slide, created from the V4 teammate handoff. The PowerPoint contains editable text and one native comparison table; the original V4 screenshot and logos remain raster images. The PDF is exported from that same PowerPoint. Source references and scope qualifications are in the speaker notes.

- `VOLT-FORGE_Round1_Editable.pptx`: editable presentation.
- `VOLT-FORGE_Round1_Editable.pdf`: shareable one-page export.
- `VOLT-FORGE_Round1_Editable.png`: native PowerPoint render.
- `source_data.json`: copied frozen-study provenance, including the source commit and exact selectors.
- `verification.json`, `package_checks.json`, `layout_checks.json`: generation, text-fit, PDF and package checks.

The table is from the frozen V4 study, not a new run or a claim that the revised implementation has experimental validation. The screenshot is explicitly identified as the original V4 editor. The earlier reviewed PDF, original submission files, model artifacts and study results are preserved. All 649 protected artifacts retained their hashes.

## Rebuild

Requires Windows, installed Microsoft PowerPoint, Python 3.12, pywin32 and Pillow. This environment did not provide the local Artifact Tool runtime, so the generator uses native PowerPoint automation. It closes only its own presentation and does not quit an existing PowerPoint session.

```powershell
python -B scripts/build_submission_slide_native.py --out tmp/new_slide_build
```

Choose a fresh output directory. The generator refuses to overwrite existing final artifacts. Recheck every rebuilt slide visually. Native PowerPoint font metrics and package/layout validators passed; an Artifact Tool import check was unavailable.

## Visual review

The final PowerPoint render was inspected at 1920 x 1080 and the PDF was independently rendered with PDFium and inspected at 1440 x 810. A table-caption overlap in an earlier private draft was corrected before delivery. Final titles, table, caveats and footer fit without clipping or unintended overlap. The screenshot is illustrative: its tiny controls are not the evidence table. The PDF contains one page; required values and caveats were checked by text extraction. Neither file has been submitted to the competition.

The team still needs to confirm portal rules, including whether a separate cover is required. No cover was added to this one-slide deliverable. No public application deployment or outreach was performed.
