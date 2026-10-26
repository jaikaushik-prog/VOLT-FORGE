# MATLAB 7.3 metadata reader

The first test-103 probe read the electrical text prefix and processed MAT
container, then stopped: scipy.io.whosmat reported MATLAB 7.3/HDF5. It produced
no result receipt and displayed no measurement values. The attempted source is
preserved in schema_probe_attempt_001.py. The raw thermal prefix had not yet
been read. The entire family remains used development material.

Before retrying, permit an HDF5 metadata-only path for this same MAT member:
list group/dataset names, shapes, dtypes and MATLAB_class attributes. Never
index datasets, follow soft/external links, read virtual datasets or decode
numeric array contents. No other family or numerical analysis is added.
Use existing h5py; do not modify the frozen application's dependencies.

This change concerns file format handling, not a fitting/assessment rule or
model choice. The original reservation and no-fitting boundary remain intact.
