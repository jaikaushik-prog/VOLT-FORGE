# Uploading VOLT-FORGE to GitHub

The upload copy is `github-upload/volt-forge/`; its ZIP is
`github-upload/volt-forge-github-upload.zip`. Original project files stay in place.
The copy contains source, tests, configurations, reports and frozen evidence.
It excludes the raw dataset ZIP, processed-data cache, credentials, Git metadata
and downloaded TELIPORT briefing documents. Dataset attribution is retained in
`ATTRIBUTION.md`; no new software licence has been assigned on your behalf.

1. Sign in to GitHub and create an empty **public** repository named `volt-forge`.
2. Extract the upload ZIP, or open the prepared `github-upload/volt-forge` folder.
3. Upload that folder's **contents** at the repository root, preserving the
   `src`, `scripts`, `tests`, `configs` and `reports` folders. Upload in batches
   if the browser asks. Include `.gitignore` and `.gitattributes`.
4. Use a commit message such as `Add VOLT-FORGE electrical modelling research`.

Uploading only the ZIP would store an archive rather than a browsable project.
The large dataset must be downloaded separately using the README instructions.
Tests requiring that archive may skip or require it for reproduction.

Refresh the upload copy after further project work:

```powershell
cd C:\Users\DELL\Desktop\volt-forge
& C:\Users\DELL\anaconda3\python.exe scripts\prepare_github_upload.py
```

The companion `github-upload/upload_manifest.json` records each included file's
size and SHA-256. This preparation does not log in, create a remote or publish.
