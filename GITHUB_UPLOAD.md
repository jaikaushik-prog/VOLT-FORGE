# Uploading VOLT-FORGE to GitHub

Designated public repository: **https://github.com/jaikaushik-prog/VOLT-FORGE**.
Use this repository for future completed, tested project updates.

GitHub CLI authentication and repository push permission were verified on
2026-10-25. The local `origin` points to this repository. Fetch and inspect remote
changes before committing completed work; push as a normal descendant of the
remote history, never with a force-push. Keep the exclusions in `.gitignore`.
The existing root upload ZIP is a historical snapshot; the browsable source,
configuration files and reports describe the current project.

The upload-copy workflow below remains available as a manual fallback. It now
includes `SIMULATION_PLAN.md`, `SIMULATION_READINESS.md` and
`MEASUREMENT_IMPORT_SPEC.md` with the four-cell simulation backend. Preparing
that copy does not publish it.

The upload copy is `github-upload/volt-forge/`; its ZIP is
`github-upload/volt-forge-github-upload.zip`. Original project files stay in place.
The copy contains source, tests, configurations, reports and frozen evidence.
It excludes the raw dataset ZIP, processed-data cache, credentials, Git metadata
and downloaded TELIPORT briefing documents. Dataset attribution is retained in
`ATTRIBUTION.md`; no new software licence has been assigned on your behalf.
Large reproducible v2 per-sample prediction and synthetic coupling CSVs are also
excluded from the upload copy; sealed models, source hashes, numerical summaries
and plots remain included. The README commands regenerate those CSVs from the
original dataset without refitting. Preserved v1 files remain included because
the v2 lock verifies their exact bytes.

1. Sign in to GitHub and open **jaikaushik-prog/VOLT-FORGE**.
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
