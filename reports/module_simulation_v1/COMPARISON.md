# Predeclared electrical simulation comparison

**Synthetic simulation, not experimental validation. No automatic ranking.** All voltage requirements are unconfigured in the supplied case. All engineering decisions remain insufficient evidence.

| Manual scenario | Max branch [A] | Min cell / terminal [V] | Mean delivered power [W] | Delivered [Wh] | R0 / rail / R1 loss [Wh] | >4.9 A [cell s] |
|---|---:|---:|---:|---:|---:|---:|
| equal_soc | 4.6669 | 3.6332 / 3.6332 | 53.689 | 5.3689 | 0.1318 / 0.0338 / 0.1000 | 0.00 |
| soc_imbalance | 5.3528 | 3.6337 / 3.6337 | 53.697 | 5.3697 | 0.1336 / 0.0315 / 0.1016 | 19.25 |
| lower_rail_resistance | 4.2345 | 3.6454 / 3.6454 | 53.862 | 5.3862 | 0.1313 / 0.0177 / 0.0993 | 0.00 |
| reduced_load | 3.8599 | 3.6841 / 3.6841 | 44.765 | 4.4765 | 0.0897 / 0.0229 / 0.0680 | 0.00 |

Cell seconds sum duration across cells; they are descriptive coverage flags, not safety limits.
Every cell waveform remains an unsupported module transfer even where all amplitudes fall inside fitting or assessment ranges.
Reduced load requests less service. Its voltage/loss differences must be read together with delivered current, power and energy.
Reference source work and equivalent-RC storage are model bookkeeping, not measured chemical energy or efficiency.

[Sensitivity plot](sensitivity_scenarios.png), [matched sensitivity contrasts](sensitivity_contrasts.json), [time-step checks](software_verification.json).

- equal_soc: [electrical](runs/equal_soc/electrical.png), [nodes/power](runs/equal_soc/nodes_and_power.png), [coverage and status](runs/equal_soc/summary.json).
- soc_imbalance: [electrical](runs/soc_imbalance/electrical.png), [nodes/power](runs/soc_imbalance/nodes_and_power.png), [coverage and status](runs/soc_imbalance/summary.json).
- lower_rail_resistance: [electrical](runs/lower_rail_resistance/electrical.png), [nodes/power](runs/lower_rail_resistance/nodes_and_power.png), [coverage and status](runs/lower_rail_resistance/summary.json).
- reduced_load: [electrical](runs/reduced_load/electrical.png), [nodes/power](runs/reduced_load/nodes_and_power.png), [coverage and status](runs/reduced_load/summary.json).
