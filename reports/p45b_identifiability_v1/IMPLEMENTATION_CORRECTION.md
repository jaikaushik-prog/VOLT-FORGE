# Export correction before the completed investigation

The procedure was committed in `4fb44ac`; the first implementation and 14
synthetic checks were committed in `4c1353e`. The first run stopped while
serializing C1's screening checks because a NumPy boolean was not JSON-native.
It had computed C1 but had not started C2. No candidate selection was completed.

`run_001` is retained as incomplete, with its failure description. Previous
implementation, tests and source lock are copied under `previous/`. The sole
calculation-path change converts screening booleans to Python `bool` for export.
A regression test exercises the real screening object and its JSON round trip.
The physical equations, allocation, weights, candidates, bounds and screening
criteria are unchanged. The corrected freeze precedes a complete new run in
`run_002`; no outputs are overwritten or omitted to improve reported accuracy.
