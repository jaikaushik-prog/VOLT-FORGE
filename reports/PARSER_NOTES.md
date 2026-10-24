# Reader scope and verification

The archive contains MATLAB Level-5 files. Simple characterization arrays load
with `scipy.io.loadmat`. Module and Hall-calibration tables instead serialize as
MCOS objects. A normal `loadmat` call returns opaque references rather than a
numeric table; treating the reference vector as a measurement would be incorrect.

`src/voltforge/data/matlab.py` reads the nested subsystem with the pinned SciPy
1.13.1 MAT5 reader. The subsystem has an 8-byte little-endian header. Its first
struct contains an MCOS FileWrapper with a property pool. The observed calibration
layout has 11 slots; module files have 22 slots, including four scalar UTF-16
cell identities. This adapter checks wrapper type, table labels and ordering,
dimensions, equal vector lengths, scalar-string headers, cell-name syntax, and
the four cell-name reference vectors. Unsupported layouts raise errors.

This is a dataset-specific adapter using a private SciPy API. It is not claimed
to parse arbitrary MAT files or future serializations. It reads data only and
does not execute MATLAB code. All 54 module metadata records decode with this
layout. All 18 NMC cell allocations agree with the independently transcribed
article Table 5, including the inconsistent row 32.

For the two audited runs, a separate OpenPyXL reader loads the original Excel
exports. Every elapsed-time sample, step/cycle flag, module voltage/current,
four surface temperatures and ambient temperature matches the decoded processed
table exactly. Row counts match too. This independently checks the numeric
table mapping; equality of branch currents to raw currents is not asserted,
because the raw channels are Hall voltages. Their calibration remains an open
scientific issue.

Excel temperature headers literally contain replacement characters in the unit
label (`Aux_Temperature(��)_1` through `_5`). The parser matches the complete
channel structure and requires exactly one header per number. Celsius and the
surface/ambient mapping are corroborated by the processed table's explicit
labels and the article. It does not pretend the raw header encoding is intact.

No sorting, resampling, smoothing, filling, zero-current offset subtraction or
renormalization is performed. Raw and processed rows are joined only after exact
elapsed-time equality. Elapsed time is the analysis clock; absolute Excel dates
are retained without inventing a time zone. Raw `Global_Info` start time for run
53 disagrees with its first `Data` timestamp, so it is not used to reconstruct
the series clock.

Inventory reads/decompresses every file for CRC/SHA verification. Decoding cell
metadata necessarily materializes the containing MATLAB object, including its
numeric arrays, but final-assessment signal values are not examined, scored,
plotted or used for decisions. Only the declared initial subset is audited.

Tests include independently inspected original Excel values, raw-versus-MAT
equality, article cell identities, the row-32 contradiction, a small synthetic
MAT fixture, sign/units, missing-branch propagation, gap/duplicate/backward-time
handling and split disjointness. Numeric equality tolerances in parser tests
describe serialization agreement, not sensor accuracy.
