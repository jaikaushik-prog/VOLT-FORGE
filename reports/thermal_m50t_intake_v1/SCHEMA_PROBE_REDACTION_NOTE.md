# Development probe correction

The first successful schema receipt, development_schema.json, is retained as
attempt 002 together with schema_probe_attempt_002.py. Its thermal text prefix
contains leading NUL bytes. The row classifier treated the first numeric row
as a header because of that prefix, exposing one initial temperature row from
the already allocated test-103 development family. Therefore that receipt's
`numerical_outcomes_presented: false` field is incorrect for attempt 002.
No assessment or unused-reserve member was opened, and no fitting occurred.

Before attempt 003, strip leading NUL/space/tab only for classification and
header display; preserve raw bytes. Decode UTF-8 strictly, with an explicitly
recorded CP1252 fallback for this legacy text, instead of replacing degree
symbols. The header/line/byte limits and member allowlist stay unchanged.
Add a synthetic regression test for the leading-NUL case. Do not delete or
rewrite the earlier receipt. The first development family remains used evidence.

development_schema_003.json is the corrected schema output. It does not undo
the one-row exposure in attempt 002. This matters for provenance even though
the same family was deliberately reserved for development before either probe.
