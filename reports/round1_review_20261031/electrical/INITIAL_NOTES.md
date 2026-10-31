# Independent initial electrical conclusions

Recorded before consulting any previous audit/re-audit or other reviewer notes. This review reads the isolated V4 checkout at c2339a569876da5fc20969ea578a91ae57f33384. No V4 source, frozen run, raw measurement, or reserved record was changed or rerun.

- The frozen two-cell result is a scoped simulation qualification, not blanket evidence of a complete Pi UPS. The load is 8.4175 A constant battery current, derived from 25 W / (0.90 * 3.3 V). Its conservatism is conditional on the voltage floor and efficiency assumption. The study and measured-comparison disclosures are materially better than a simple claim of validation.
- Candidate reproducible defects: missing operating limits can coexist with a sizing qualification; part selection is a cell-count lookup without electrical topology/voltage compatibility; charging Ah sums cell currents and may overstate pack charge in series; zero-ohm wire-current unknowns become zero in link checks.
- The measured comparison reports all 12 misses. First-law closure and timestep convergence establish numerical consistency, not measured accuracy. The transfer of voltage and temperature error bounds between fixtures and designs remains conditional.
- The board source's 95% value occurs under its 9–18 V power-input step-down converter. It does not establish backup boost efficiency. The board's up-to-3 A charger would be 1.5 A/cell for an equal two-cell parallel pack, slightly above the product's 1.455 A/cell charging rule at 23 C. This requires a charge-path compatibility check, separate from discharge qualification.

Runtime inspection: Python 3.12.3, NumPy 1.26.4, SciPy 1.13.1. Core numerical versions match; this is an exploratory Windows review, not the sealed macOS lock replay.
