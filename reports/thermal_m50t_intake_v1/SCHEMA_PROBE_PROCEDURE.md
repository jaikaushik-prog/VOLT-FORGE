# Bounded development schema probe

Declared after the metadata-only inventory and whole-family reservation, before
reading any measurement member. This is a separate follow-on to PROCEDURE.md;
the inventory command remains metadata-only. No model fitting is performed.

Only the three members of `cell_1_test_103` may be opened. The archive and
allocation must match their pinned hashes. Inspect at most 32 KiB/64 lines of
each text file for nonnumeric header lines and token types, without displaying
numeric sample values. Inspect the processed MAT variable names, dimensions and
MATLAB types using scipy.io.whosmat, without displaying array values. Do not
extract these files, scan other experiments or use these readings to select a
better-looking development case.

All three members are now designated used development material even though this
probe presents schema only. Do not later call them fresh assessment. A probe
must log the exact opened member names and preserve the allocation/procedure
hashes. Any other member, including all cell-2 members and unused cell-1 reserve,
is denied. No dynamic thermal parameter is identified by this operation.

Purpose: determine whether the development file schema offers explicit time,
units, heat-flow or calibration metadata for a subsequent ingestion procedure.
If it does not, report what remains unresolved instead of treating sample
amplitude, filename setpoints, cold-junction temperature or published CCC as
the missing physical input.
