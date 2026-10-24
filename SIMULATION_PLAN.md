# Four-cell simulation backend: predeclared scope

This sprint adds a versioned electrical coupling extension around frozen v2 C2.
The historical `models/coupling.py` is hash-protected and remains unchanged.
The extension reuses its ladder solver and reference interpretation, adds
explicit rail vectors, initial polarization, piecewise-constant loads, node
outputs, energy accounting and coverage reporting. No fitted parameter changes.

The application and four manual scenarios are in `configs/module_application_v1.json`
and `configs/module_scenarios_v1.json`. `configure` hashes these inputs and
materializes every scenario before simulation. Initial SOC, contact/rail values,
temperature and waveform transfer remain assumptions. Minimum load voltage and
allowed excursion duration are null. Missing requirements return **requirement
not configured**, and engineering decisions return **insufficient evidence**.

The main cases are equal SOC 0.70, the prior [0.72,0.70,0.68,0.70] imbalance,
hypothetical 0.5 mOhm segments on both rails, and a 12 A reduced-load case.
Each runs for 360 s. No feasibility, repair ranking or demonstrated performance
gain is implied. Compare delivered current, power and energy as well as losses.

Seven one-at-a-time sensitivities apply to all four main cases: relative SOC
alignment +/-0.02, capacity +/-1%, initial polarization +/-5 mV, and the already
investigated C/20-shape reference with the same rest anchors. These are sensitivity
scenarios, not uncertainty distributions. Separate paired SOC/reference-origin
shifts +/-0.02 on the baseline must leave the electrical result invariant.
Do not combine origin relabelling and relative alignment as independent errors.

Use exact one-RC state updates under interval-held branch current, coulomb
counting and the existing instantaneous Kirchhoff solution. Put load changes
on integration boundaries. Report instantaneous resistive losses and capacitor
storage separately. Integrate terminal power with endpoint voltages under the
same load on each interval, never trapezoid across a load discontinuity. Report
the finite-step energy-balance residual and its convergence; rested-voltage
source work is an electrical-model quantity, not proven chemical energy.
No losses are translated into temperature.

Stop before any state/reference evaluation outside its mathematical domain;
retain partial results and the failed time/state. Never clamp or extend reference
curves. Report waveform/dwell transfer as unsupported even if current lies inside
observed ranges. Track every cell's current direction, contiguous intervals,
SOC and recorded characterization-temperature evidence.

Verify analytical constant-current RC and rail cases, charging and circulation,
conservation, energy storage/loss identities, event handling, reference-domain
stops and time-step sensitivity (1, 0.5, 0.25 s). Test the measurement importer
with explicitly synthetic data, including malformed/misaligned/current-biased
records. Preserve bytes, source rows, polarity and calibration metadata; do not
rescale measured currents. Real comparison remains **awaiting suitable measurements**.

Deliver configure/simulate/compare/validate CLI commands, measurement specification,
numerical outputs, plots, tests and `SIMULATION_READINESS.md`. No frontend,
optimizer, outreach, repository publishing or protected assessment access.
