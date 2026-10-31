# Exact notebook-source access boundary

The ZIP inventory contains one `example_code.ipynb`, one macOS sidecar and ten
NPY files (electrical/heat-sensor pairs labelled 4, 8, 10, 16 and 32 minute rest).
No member has been opened at this declaration.

Allow only `example_code.ipynb`, 343,779 uncompressed bytes. Decode its notebook
JSON and extract code/Markdown `source` fields only. Do not display saved cell
outputs, HTML/image attachments, tables or plots. Record skipped output counts.
Do not execute any code, import its dependencies or deserialize NPY/object data.
The compressed measurement members and macOS sidecar stay unopened.

Purpose: determine signal definitions, units, clock assumptions and calibration
requirements from the authors' usage example. Embedded source constants are
published-method evidence, not independent calibration or new model parameters.
