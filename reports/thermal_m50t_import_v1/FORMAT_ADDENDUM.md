# Electrical header/data mismatch found by the first importer

The first sealed implementation stopped on a row-width mismatch. The declared
97th header line contains `time/s`, `Ecell/V`, `I/mA` and two trailing empty
labels. Every numeric-data row instead has four nonempty fields: a calendar
timestamp, voltage, current and an unlabelled numeric value. No rows were dropped.
The first implementation and failure receipt are preserved.

Before attempt 002, permit only this exact observed source layout. Preserve
calendar timestamp strings, parse their explicit month/day/year and fractional
second representation, and derive seconds since the first recorded electrical
timestamp solely for within-record arithmetic. Keep timezone unknown. Preserve
the fourth column as unlabelled/units unknown. Do not infer a shared thermal
time zero or a meaning for the extra field. No new experiment or fitting is added.

All numerical members belong to the previously allocated development family.
This format correction does not turn any of them into fresh assessment evidence.
