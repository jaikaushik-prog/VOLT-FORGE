# Local command mode: predeclared software evaluation

This procedure and [evaluation cases](../../configs/local_assistant_eval_v1.json)
are written before implementing or running this sprint's command parser.
The implementation will match a small complete-string grammar. It will use no
language model, provider, API key, network request or automatic executor.

The only service operations are help, existing evidence explanation, existing
read-only edit preview and comparison of two explicitly selected saved runs.
The current variant/revision/component/run selection is authoritative. Explicit
rail names must agree with the selected rail. A timestep edit requires module
selection; cell edits require a selected cell. No target or run is guessed.

The parser may convert explicit input units (mOhm/mΩ to ohm, percent to fraction,
and mV to V). Those conversions are input interpretation, not a physical model.
Accepted numeric input uses ordinary decimal notation. Scientific notation,
ambiguous units, unit case changes, missing units, compound instructions and
unrecognized requests fail visibly. All proposed inputs remain assumptions with
the original command as provenance and require separate human review.

The bounded evaluation uses the frozen LG reference assets in temporary projects,
complete saved simulation outputs, and clearly synthetic load/failure cases.
It does not inspect new characterization or protected assessment outcomes.
Tests will check the predeclared accepted/rejected command list, exact delegated
payloads/citations, state and freshness preservation, unchanged project bytes,
same-condition comparison rejection and concurrent-change handling.

Success means the permitted commands are reproducible and preserve backend
evidence and permissions. It does not establish broad language understanding,
model accuracy, safe repairs or an experimental battery-performance gain.
No frozen script, source solver, dependency or previous report will be edited.
