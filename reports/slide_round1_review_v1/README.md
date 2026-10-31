# Revised Round 1 review draft

One content page, separate from the original cover and submission. Not published or submitted. The team must verify portal file/format rules and deadline before submission.

## Rebuild

From the pinned repository root in PowerShell:

```powershell
& C:/Users/DELL/anaconda3/python.exe scripts/build_reviewed_slide.py --pdfium-path C:/Users/DELL/Desktop/volt-forge/tmp/pdf_runtime
```

Pinned input commit: `c2339a569876da5fc20969ea578a91ae57f33384`. The generator reads frozen source reports; it does not rerun or modify a model. The source-data JSON includes selectors, original values and SHA-256 hashes for every input and font. The screenshot is the original V4 editor and is labelled as illustrative; its wiring is not the study table. No claim is made about subsequent live-app fixes.

`verification.json` records page/text/render checks. The generated PNGs require visual inspection after each rebuild. No hardware accuracy, protection certification, customer evidence or live deployment identity is inferred.
