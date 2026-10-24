# Model-improvement plan — frozen before v2 fitting

The intended application case remains a 14.55 A, 360 s discharge from a 1s4p
LG M50T NMC ladder (P7/P17/P19/P13), nominal 1 mOhm per segment on each rail,
starting SOC proxies 0.3-0.8 at nominal 23 C ambient after rest. Desired outputs
are terminal/cell voltage, branch current, SOC and proximity to a proposed
3.50 V operational alarm. This alarm is a research decision example, not a
manufacturer cutoff or an established application requirement.

Equal sharing needs 3.6375 A/cell, already above v1 fitting's 2.66 A discharge.
Unequal sharing must be checked branch by branch. Open cell records contain
4.85 A discharges lasting about 360 s, plus shorter higher-current multisines.
These allow a relevant fitting extension; current amplitude alone does not
validate an unmeasured 3.64 A waveform or arbitrary dwell time. The module
current discrepancy independently blocks experimental module validation.

The executable demonstrator is explicitly **single-cell voltage prediction on
the recorded discharge/pulse/rest protocol**, with primary domain SOC proxy
0.2-0.8, discharge/rest current 0-4.9 A, measured surface 22-28 C under nominal
23 C chamber conditions. It is narrower than the module application; application
requirements are not being relaxed. Temperature excursions here are correlated
with load; they do not identify a general temperature law. Rails, contacts and
initial SOC remain uncertain application inputs.

Propose sample- and time-weighted RMSE <=10 mV, |bias| <=5 mV and maximum error
<=25 mV in that primary domain. A provisional 50 mV decision guard allocates
25 mV to model error, 10 mV to instrumentation/reference, 10 mV to initial
conditions and 5 mV to temperature transfer. The latter allocations lack an
uncertainty budget and are not established tolerances. Predictions within
3.50 +/-0.05 V are undecided; false clearances outside that band are reported,
without claiming a certified decision rule.

Diagnosis before fitting: v1 P7 late-rest bias is about +24/+27 mV at SOC
0.30/0.20, between sparse reference anchors. During 4.85 A discharges, residual
increases with time under load (late-load mean about +90 mV across cycles).
Left/right versus trapezoid counting changes SOC by at most 0.000268, too small
to explain these patterns alone. These observations motivate reference and
polarization changes; they do not uniquely establish physical causes.

Evaluate only three revisions: C1 replaces the loaded-curve correction with
a monotone calibration-rest PCHIP reference and refits constant resistance over
the expanded load coverage; C2 adds one positive RC; C3 lets R0/R1 vary linearly
over three SOC knots with one shared tau. No extra RC, hysteresis state or
temperature law will be added. Compare against a protocol-matched v1 method
calibrated with the same permitted cycles, while preserving the actual sealed
v1 results for diagnosis. Differences in permitted calibration are disclosed.

All seven opened cells are development evidence, including their old v1 held
cycles. Inventory metadata identifies 12 unused unaged NMC cells. Reserve
P2/P5/P8 as additional characterized assessment cells based on identifiers,
before viewing their voltage outcomes. For every cell, calibrate on complete
cycles 1/3/5/7/9; evaluate complete cycles 2/4/6/8. Fresh cells may use their own
C/20 record, initial cycle-1 rest and permitted calibration cycles. This is
not zero-shot generalization. The other nine unused cells remain unopened.

The [machine-readable plan](configs/model_improvement_v2.json) fixes equations,
bounds, weighting, selection, diagnostics and sensitivity checks. Freeze it and
source hashes before fitting. Freeze executable procedure and selection before
fresh-cell calibration; seal those fitted parameters before fresh assessment.
Selection requires improvement on development voltage errors, not training
error, and an identifiability screen. Assessment cannot trigger tuning.

Review archive metadata for embedded processing/calibration evidence without
repeating completed numerical checks. Keep both module-current sources intact.
Any ladder coupling/current/SOC/time-step checks are software verification only.
No app, dashboard, optimizer, repairs, outreach or publishing is part of this
modelling sprint.
