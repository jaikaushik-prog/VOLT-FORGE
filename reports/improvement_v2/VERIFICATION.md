# V2 verification record

24 October 2026. The complete repository suite passed: **46 tests, 0 failures**
in 46.69 s using Python 3.12.3 in the existing Anaconda environment. The
[JUnit record](pytest.xml) contains test names and timings.

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe -m pytest -q --junitxml=reports/improvement_v2/pytest.xml
& C:\Users\DELL\anaconda3\python.exe -m voltforge.models.improvement verify
```

The preservation check passed after the suite: the original archive and all
51 protected original/v1 artifacts retain their recorded hashes. The v2
procedure and fresh-model seals also remain intact. No final module signal
outcomes were scored. The metadata-only archive review is separate from
model assessment.

Tests cover analytical RC responses on irregular timestamps, constrained
parameter recovery, source-row and voltage-masking guards, monotone reference
support, sample/time error aggregation without bridging excluded intervals,
contiguous current-coverage spans, static ladder analytical cases, dynamic
current conservation, coulomb accounting and a closed-form single-cell RC
coupling response. They verify implementation, not experimental module accuracy.

The completed diagnostic commands in the [README](../../README.md) reproduced
sealed v1 predictions within 1e-11 V, regenerated v2 scores/plots from sealed
models, and checked per-branch current, SOC balance and time-step sensitivity.
Detailed results and unsupported conditions are in the
[decision report](../../MODEL_IMPROVEMENT_DECISION.md). Fresh v2 assessment has
now been opened and must be treated as used evidence for future development.

The public-repository upload copy is generated separately by
`scripts/prepare_github_upload.py`. Its manifest records included file hashes;
raw downloads and large reproducible v2 per-sample CSVs are excluded. Preparing
that copy does not publish or push changes.
