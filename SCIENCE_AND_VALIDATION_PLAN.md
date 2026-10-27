# VOLT-FORGE: data, mathematics and physical validation

Revision: 27 October 2026. Intended use: an editable battery engineering demonstrator that can grow into a defensible engineering tool. This is an implementation and experimental specification, not a certificate of physical accuracy.

The product must connect a design change to a physical consequence. A feature is complete only when the design input, mathematical model, numerical solution, physical evidence and displayed conclusion agree. A clean interface cannot compensate for missing calibration. A large test suite cannot establish agreement with hardware.

## 1. Work to execute first

The present data supports a bounded nominal-temperature electrical model. Replace the missing temperature dependence through a separate calibration campaign and model version, rather than fitting unrelated parameters to make module plots look convincing.

| Priority | Concrete job | Output required before the next job |
| --- | --- | --- |
| 1 | Reconcile the current measurement chain | Sensor-to-cell map, calibration functions, instrument uncertainty, residual plots, and charge-throughput reconciliation for development records |
| 2 | Identify nominal-temperature cell parameters independently of module outcomes | Per-cell reference curve, capacity, resistance and relaxation parameters, fit residuals, covariance/profile likelihood, and calibration record hashes |
| 3 | Obtain and identify electrical temperature dependence | Same cell family measured at multiple equilibrated temperatures; temperature/SOC parameter surfaces with held-out temperature checks |
| 4 | Separate heat capacity, heat generation and fixture cooling | Independent heat-capacity evidence, cooling/contact identification, and measured heating records not reused as assessment |
| 5 | Implement and verify two-way electrothermal coupling | Temperature changes electrical parameters; electrical losses change temperature; converged time stepping and a consistent energy ledger |
| 6 | Validate the assembled module | Untuned predictions of module voltage, branch currents and mapped surface sensors on reserved experiments |
| 7 | Quantify uncertainty and decision margins | Output intervals, sensitivity ranking, uncertainty budget, and a requirement-specific acceptance decision |
| 8 | Expand topology and cell libraries | A separate evidence envelope for each new chemistry, model family, interconnection arrangement and cooling configuration |

The new studio implements an arbitrary editable electrical graph, not a four-cell picture over the old fixed ladder. It does not silently inherit the old ladder's empirical scope. Its default temperature policy prevents nominal-temperature fits from generating unsupported hot-room predictions. That policy is an interim operating boundary. It is not the requested temperature calibration itself.

## 2. Current implementation and evidence inventory

The numerical implementation is in `src/voltforge/studio/network.py`. Persistence and replay are in `store.py`. The frozen earlier solver remains unchanged and is used as an independent parity target for the corresponding four-cell ladder.

| Item | Current basis | Required improvement |
| --- | --- | --- |
| Cell reference voltage | Frozen, fitted calibration-rest PCHIP curve for each of four LG M50T samples | Establish preparation and equilibrium assumptions; assess hysteresis and temperature effects |
| Capacity | Charge integrated from separate low-rate characterization | Resolve instrument uncertainty, endpoint definitions, usable SOC origin and capacity dependence on rate/temperature/age |
| R0, R1, relaxation time | Frozen constant one-RC fits | Identify dependence on SOC, temperature, direction and ageing only where data resolves it |
| Electrical connectivity | User-drawn terminal graph, modified nodal analysis | Validate model applicability for each hardware arrangement; add explicit non-cell components when supported |
| Connection resistance | User assumption, including an editable source | Four-wire measurements or geometry/material/contact evidence; temperature coefficient where supported |
| Heat capacity | 69.25 J/K from nominal mass multiplied by an assumed specific heat | Independently determine heat capacity and uncertainty |
| Cooling to ambient | Approximately 0.148629 W/K derived from one previously opened cooling record | New fixture-specific identification and independent assessment |
| Cell-to-cell thermal contacts | Explicit graph; no heat contact inferred from a drawing | Measure contact resistance and mounting pressure; characterize busbar/fixture paths |
| Connection heat partition | Declared fraction, initially 0.5 | Identify through fixture energy balance or a resolved conductor model |
| Surface temperature | One thermal state per cell | Add core/surface states only with identified parameters and mapped measurements |
| Temperature feedback | Not calibrated in the current frozen electrical fits | Complete the temperature campaign and coupled model described below |
| Independent module accuracy | Not established | Measurement-chain repair and reserved module experiments |

The numerical values above describe existing implementation inputs, not manufacturer ratings. Preserve their provenance. Do not turn a model fit into a directly measured physical resistance or equilibrium open-circuit voltage by changing a label.

Local evidence to inspect before refitting:

- `DATA_READINESS.md`, `MODELLING_DECISION.md`, `MODEL_IMPROVEMENT_DECISION.md`.
- `REFERENCE_INITIAL_STATE_DECISION.md`, `SIMULATION_READINESS.md`.
- `reports/hall_calibration_audit.json` and `reports/reconciliation/cycle_balance/CYCLE_BALANCE.md`.
- `reports/thermal_v1/cooling_derivation.json` and `configs/thermal_v1.json`.
- Development-only characterization outputs. Reserved/fresh outcome files stay outside calibration inputs.

## 3. Scientific questions and quantities to predict

Write a prediction contract before collecting or fitting data. The first useful contracts are:

1. Given measured starting states, a specified connection network, a current waveform and a fixture environment, predict each cell current and module terminal voltage over a stated interval.
2. Given the same experiment plus identified heat-transfer parameters, predict the temperature at each explicitly mapped sensor location.
3. Given a requirement with a numerical threshold, time-duration rule and source, detect violations within the simulated interval and applicable evidence domain.
4. Given two designs under controlled common conditions, estimate the difference in a metric and whether that difference is larger than the uncertainty in the difference.

Do not use a single word such as “accurate” for all four. Current-sharing accuracy, voltage accuracy and thermal accuracy have different measurement chains and error budgets. Define the required resolution and tolerance for each intended decision before looking at assessment results.

## 4. Data architecture

Use immutable scientific artifacts and a small transactional catalog. The first implementation uses atomic JSON documents and immutable result/model/software bundles. The next data layer should use SQLite for indexes and transactions and columnar files for long numeric series. Keep the scientific identity independent of the storage engine.

The dependency chain is:

`source bytes -> parsed record -> calibrated channels -> authorized split -> model fit -> design revision -> experiment specification -> solver trajectory -> derived metrics -> decision -> report`

Every arrow records the transformation version and input hashes. Re-running a parser must not rewrite raw bytes. Updating a name or drawing position must not alter a physical experiment's identity.

### 4.1 Entity contracts

| Entity | Identity and required fields |
| --- | --- |
| Source artifact | SHA-256, byte size, immutable storage key, retrieval UTC, original filename, publisher URL, DOI/version, licence and attribution |
| Acquisition record | Instrument identifier, serial number where available, configuration/firmware, calibration certificate, physical setup, operator, timestamp/time zone, channel map and protocol |
| Parsed dataset | Source hash, parser version, sheet/table/channel selection, units, original timebase, sign convention, row count, validity flags, missing-data policy and parser diagnostics |
| Calibrated dataset | Parsed hash, calibration function and coefficients, coefficient covariance, channel uncertainty, supply compensation, sensor temperature, calibration range and residuals |
| Experiment | Physical module/cell identities, interconnection map, sensor-to-location map, fixture geometry, cooling boundary conditions, protocol and initial-state preparation |
| Split assignment | Dataset/group identifiers, role, rationale, access permissions, assignment timestamp and immutable split hash |
| Parameter set | Model equations/version, parameter values and units, source/calibration records, optimizer settings, residual definition, fit diagnostics, uncertainty and validity domain |
| Component definition | Part identity, physical dimensions and source, interface terminals, allowed model families, material parameters, evidence and version |
| Component instance | Definition version, unique instance, physical cell identity when known, state initialization, orientation/position and user name |
| Electrical graph | Typed components, terminals, net/connection endpoints, resistance or richer conductor model, output terminals and physical provenance |
| Thermal graph | Thermal states, capacities, explicit contacts/conductances, ambient/coolant boundaries and heat-source mappings |
| Design revision | Canonical physical graph hash, parent, change description, component/model versions, user action UTC; drawing layout kept separately |
| Experiment specification | Design hash, initial states, load/environment time functions, solver configuration, requested channels and target definitions |
| Numerical execution | Specification, exact model bundle, source/dependency hashes, platform/runtime, start/end/status, termination reason, series checksum and verification diagnostics |
| Validation assessment | Locked model version, reserved measured experiment, alignment rule, comparison metrics, uncertainty, applicability findings and decision |
| Report | References to all upstream identities, human explanations, units, charts, limitations and a reproducibility manifest |

A “measured” label attaches to the appropriate channel/parameter and experiment, not to the entire application. A single independently measured parameter cannot make all downstream simulated outputs “validated”.

### 4.2 Transaction and invalidation rules

- Save a design with an expected version. Reject a stale writer; do not silently replace another window's design.
- Capture a test's entire design and settings before computing. Later edits cannot change that test.
- Verify the result payload against the indexed payload hash before reading, comparing or exporting it.
- Capture model inputs and solver source. Replay verifies both before calculating.
- Write result files before publishing their catalog entries. Use a transaction or a durable journal to recover an interrupted publication.
- Rename/layout changes preserve physical freshness. Topology, parameters, initial states, environment, load, model or solver changes require a new analysis identity.
- Retain old analyses with their original inputs. Mark them as earlier versions in the UI without presenting them as current calculations.
- An analysis failure must not publish a successful empty result. A domain stop is a partial trajectory with a recorded stopping reason.
- Use an OS/process lock plus thread locking for the local file implementation. Migrate to database transactions before multi-user editing.
- Back up the catalog and immutable artifact store together. Test restoration and detect orphaned files/catalog pointers.

### 4.3 Units and channels

Use SI internally: seconds, amperes, volts, ohms, joules, watts and kelvin for thermodynamic equations. Store Celsius as a display/measurement convention with an explicit conversion. Use fractions for SOC internally and percentage only at the interface. Export units in column metadata and CSV headers.

Current convention: positive battery output current discharges. Positive cell current leaves the positive cell terminal. A negative cell current can occur during charging or circulation, even when the external battery current is zero.

Keep the original current sign in raw records. Normalization is an explicit multiplication with provenance. Do not “correct” current direction separately in the graph, chart and report.

Store true timestamps and event markers. The integration grid includes each load discontinuity. Do not assume all experiments are exactly sampled every second. Never integrate missing intervals as if their values were observed.

## 5. Source audit and measurement reconciliation

The primary existing source is the [Piombo experimental campaign, version 2](https://data.mendeley.com/datasets/zh58byr53c/2), which includes cell characterization and 54 parallel-module conditions. The associated [authors' data article](https://pangea.stanford.edu/ERE/pdf/OnoriPDF/Journals/91.pdf) describes the instruments and experiment. Those records are source evidence, not a guarantee that every processed channel is ready to calibrate this product.

The existing local audit reports disagreement between the sum of branch currents and the module current. Repair that measurement problem before judging module current-sharing accuracy.

### 5.1 Sensor reconciliation procedure

1. Verify original archive/member hashes and parser row/column mapping. Retain raw Excel and author-processed MAT channels separately.
2. Recover which Hall sensor, supply measurement and calibration table corresponds to each physical branch and cell. Do not infer the map from which permutation makes model residuals smallest.
3. Recover the actual calibration equation. Candidate forms include `I = a V_H + b`, `I = a (V_H/V_supply) + b`, and a supply-referenced differential form. Compare them on calibration records, not on the module trajectory used for validation.
4. Estimate zero offset from declared zero-current records, accounting for drift and temperature. Check direction dependence and hysteresis. Do not fit a different arbitrary scale for each phase to force conservation.
5. Fit with errors in both axes where reference-current uncertainty is material. Retain residuals, covariance, calibration range and extrapolation flags.
6. Propagate calibration uncertainty and covariance to branch current and branch-current sum. Shared supply/reference errors are correlated.
7. Compute `r_I(t) = sum_i I_i(t) - I_module(t)` and integrate the residual. Compare to its combined uncertainty over current, temperature, direction and time.
8. Check time alignment using independent event timestamps and instrument bandwidth. Do not pick an arbitrary lag by minimizing final model error. If estimated from calibration events, freeze it before assessment.
9. Reconcile charge throughput with instrument current integration and protocol endpoints. Check Ah/mAh, seconds/hours, timebase drift, truncated cycles, state resets and export conventions.
10. If a residual remains unexplained, keep separate hypotheses with source-specific predictions. Obtain independent current instrumentation for a new experiment. Do not silently choose whichever instrument makes a model appear correct.

### 5.2 Measurement uncertainty inventory

For current: reference accuracy, resolution, shunt tolerance and temperature coefficient, amplifier gain/offset, Hall sensitivity and drift, supply variation, quantization, alignment and bandwidth.

For voltage: sense-lead placement, four-wire configuration, common-mode limits, instrument gain/offset, resolution, synchronization and contact drops included/excluded by the measurement.

For temperature: sensor calibration, cold-junction compensation, attachment/contact resistance, sensor position, adhesive, thermal mass, ambient representativeness, radiation and response lag.

For time and geometry: oscillator accuracy, timestamp resolution, unit conversion, sample gaps, dimension tolerances, contact pressure, actual conductor path and fixture repeatability.

Unknown uncertainty remains unknown until measured or supported. A tolerance on one resistor is not an end-to-end sensor accuracy.

## 6. Electrical graph and governing equations

The graph contains cell elements and conductive connections. A visual overlap is not a connection. Physical wires, thermal contacts and visual grouping are independent typed relations.

Let `v` be non-ground node potentials, `i` the vector of cell currents, `B` the node-to-cell incidence matrix with +1 at a positive terminal, and `G` the passive conductor Laplacian. For a link with resistance `R_ab`, its conductance contributes `g (e_a-e_b)(e_a-e_b)^T` to `G`, where `g=1/R_ab`.

For each cell, use a rest-reference one-RC equivalent circuit:

```
e_i = U_i(z_i) - v_p,i
v_pos,i - v_neg,i + R0_i i_i = e_i
```

The coupled algebraic system is:

```
[ G     -B ] [ v ] = [ b ]
[ B^T   R0 ] [ i ]   [ e ]
```

`b` withdraws the load current at the positive output and injects it at the negative output. Ground the chosen negative output. This formulation supports series, parallel and mixed arrangements without hard-coding four branches.

For an ideal zero-resistance link, merge equivalent nodes. Do not approximate it by an enormous conductance. Individual currents through redundant ideal links are not uniquely identifiable; report that quantity as unavailable rather than zero. Their resistive heat is zero.

Validate endpoint existence, unique identities, duplicate links, finite values, signs, output connectivity, isolated subgraphs, shorted cell terminals and output shorts before solving. A physically invalid graph must not acquire plausible-looking results through numerical regularization.

After solving, check node-current residuals, cell voltage equations and network power balance. Detect singular/ill-conditioned systems. If an intentionally open-circuit element is supported later, define its constitutive equation explicitly; do not add a tiny numerical leak and hide it.

## 7. Cell state equations and integration

The nominal-temperature cell model is:

```
dz_i/dt = -i_i / (3600 Q_i)
dv_p,i/dt = i_i/C1_i - v_p,i/(R1_i C1_i)
tau_i = R1_i C1_i
V_i = U_i(z_i) - R0_i i_i - v_p,i
```

`Q_i` is Ah. Do not mix module current with an individual cell's current, especially after changing topology.

For a held current during a step `h`:

```
a = exp(-h/tau)
b = R1 i
d = v_p,0 - b
v_p(h) = b + d a
z(h) = z(0) - i h/(3600 Q)
```

The current studio holds cell currents within a finite step and re-solves the graph at the next step. This is a numerical approximation, even though the RC update within that held interval is exact. Assess state/voltage/current convergence independently of the energy residual, since residual terms can cancel.

All load transition times are grid points. A state cannot be advanced past the support of its reference curve and then clipped back into range. Stop before leaving the domain or localize the boundary crossing with a bracketed root solve in the next integrator version.

Use `expm1` for stable small-step exponential differences. Reject nonpositive capacities/resistances/time constants. Preserve initial polarization energy. Test charging, rest, circulating currents, sign changes and unbalanced initial charge, not only one positive constant load.

### 7.1 Higher-accuracy integrator to implement next

Represent states as conserved charge, polarization state and thermal energy/temperature. At each ODE/DAE evaluation, reconstruct references and temperature-dependent coefficients, solve the electrical graph, then evaluate all electrical and thermal derivatives.

Use adaptive integration with explicit load-event restarts. Compare an explicit method and an implicit stiff method on representative fast/slow time scales. A quasi-steady electrical network with slow electrochemical/thermal states can still become stiff when added RC branches or controls introduce short time constants.

Record solver tolerances, accepted/rejected steps and domain events. Dense output is a numerical interpolation, not another measured or independently solved state. Chart probes should identify whether they use saved samples or dense solver output.

## 8. Electrical energy and charge accounting

For fixed nominal-temperature RC parameters:

```
E_pol = sum_i 0.5 C1_i v_p,i^2
dE_pol/dt = sum_i [v_p,i i_i - v_p,i^2/R1_i]
P_R0 = sum_i R0_i i_i^2
P_R1 = sum_i v_p,i^2/R1_i
P_wires = sum_links R_link I_link^2
P_load = V_output I_load
P_source = sum_i U_i(z_i) i_i
P_source = P_load + P_R0 + P_R1 + P_wires + dE_pol/dt
```

An RC branch stores energy as well as dissipating heat. Do not heat the cell with `i v_p` and also add capacitor storage; that double counts energy. The heat generated in its resistor is `v_p^2/R1`.

For an interval with held current, the exact RC resistor energy is:

```
E_R1 = [b^2 h + 2 b d tau (1-a) + d^2 tau (1-a^2)/2] / R1
```

Integrate rest-reference source work using the curve's antiderivative along the SOC path. Keep terminal work, resistive loss and polarization storage separate. Report finite-step energy residuals and demonstrate convergence; do not define one term as the remaining balance and call the ledger a validation check.

Per-cell charge accounting is `3600 Q_i [z_i(0)-z_i(t)] = integral i_i dt`. For a parallel module, the sum of branch charge equals output charge. For a series module, each cell carries output charge; summing all cell charges multiplies it by the series count. A generic solver must never reuse a parallel-only aggregate identity.

Separate delivered energy, received energy and net energy for bidirectional tests. The studio records signed net output work and separate positive delivered/received integrals. The main result shows received energy for a charging-only test. Assess integration convergence before using a cycle to claim efficiency.

## 9. Thermal network and exact heat integration

For a lumped surface-equivalent state per cell:

```
C_i dT_i/dt = q_i - G_i,a (T_i-T_a) - sum_j G_i,j (T_i-T_j)
q_i = R0_i i_i^2 + v_p,i^2/R1_i + allocated_connection_heat_i
```

`C_i = m_i c_p,i` has units J/K. `G` has units W/K. The contact matrix is a passive symmetric graph Laplacian. With nonnegative conductances, internal cell-to-cell transfer cancels in the whole-module energy balance.

A connection loss can heat a conductor, a cell, a fixture or the environment. A fixed partition is an assumption, not a consequence of drawing endpoints. For a higher-fidelity conductor model, add its own heat capacity and contacts, instead of forcing all connection loss directly into cells.

With a held electrical current, `v_p(t)=b+d exp(-t/tau)`, so RC resistor heat contains constant, exponential and double-exponential modes. Propagate that forcing with the thermal matrix exponential. Replacing it by average heat before applying cooling preserves total generated heat but changes the temperature trajectory.

The thermal ledger is:

```
Delta E_thermal = sum_i C_i [T_i(t)-T_i(0)]
Delta E_thermal = integral heat_into_cells dt - integral heat_from_cells_to_ambient dt
```

Track conductor heat sent directly to ambient separately. Negative ambient exchange is physically possible when the room is warmer than the cell. Do not force cooling to be positive.

### 9.1 When one thermal state is insufficient

Check the Biot number using the appropriate cell geometry, surface boundary condition and effective anisotropic conductivity. A small external Biot number alone does not establish that a jelly roll has no internal gradient.

Add core/surface nodes only when experiments can identify their capacities and conductances. A two-node structure is:

```
C_core dT_core/dt = q_core - G_cs (T_core-T_surface)
C_surface dT_surface/dt = q_surface + G_cs (T_core-T_surface) - q_boundary
```

Use radial/axial anisotropy when escalating to a spatial model. Validate the observable sensor temperature before claiming internal core temperature. A smooth color map over a cylinder cannot establish a resolved temperature field.

## 10. Fixing temperature dependence through calibration

This is the main missing physical capability. It requires temperature-resolved data for the correct cell family and an identified model, not a generic temperature coefficient pasted into the solver.

### 10.1 Minimum experimental matrix

Proposed planning grid, not existing measurements: 10%, 30%, 50%, 70% and 90% nominal SOC at 10, 20, 25, 35 and 45 °C, within manufacturer-approved testing conditions. Use at least three independent cells and repeat selected points to estimate repeatability. Treat this as a starting design-of-experiments proposal; reduce or expand it using identifiability and decision sensitivity, not convenience alone.

At each point, record equilibrated surface/environment temperatures and preparation time. Apply multiple current magnitudes and both permitted directions with pulse/rest sequences that resolve immediate resistance and slower relaxation. Record voltage/current at a rate that resolves the fastest model time constant and instrument response. Keep the exact cell identities and cumulative ageing/throughput.

Reserve complete temperatures, cells and waveforms for assessment. Do not split neighboring time samples from the same pulse between training and validation.

### 10.2 Parameter estimation

Fit `U(z,T)`, `R0(z,T,direction)`, one or more polarization branches and capacity/usable-state definitions only as far as the measurements identify them. Prefer the simplest model that meets the intended-use error budget on reserved conditions.

Use positive parameterizations, such as fitting `log R`, `log C` or bounded transforms. Preserve covariance and correlation. For a temperature law, compare interpolation of measured parameter surfaces against a fitted Arrhenius-type relation:

```
R(T) = R(T_ref) exp[(E_a/R_g)(1/T - 1/T_ref)]
```

Here temperature is kelvin. Estimate `E_a` for the relevant process from data. Do not assume the activation energy of another chemistry or a different fitted resistance is transferable. Do not extrapolate an exponential temperature law far beyond its calibration range because it has a plausible physical name.

Use residual whitening or a justified noise model. A fit should not gain apparent quality simply because it is dominated by a long rest segment. Weight events and operating regimes according to measurement uncertainty and intended use, freeze that weighting, and then assess.

### 10.3 Two-way coupling and thermodynamics

At every integration evaluation, evaluate electrical coefficients from the current cell temperature. Solve for current, calculate irreversible heat, integrate thermal states, and feed temperature back into the next electrical evaluation. Verify convergence of a monolithic or iterated partitioned coupling scheme.

Temperature-dependent equilibrium voltage contributes reversible heat. Under discharge-positive current, a common reduced balance contains `-I T (partial U_eq/partial T)_z`. Establish the sign from the actual charge convention and derive the implemented balance. A fitted short-rest voltage reference is not automatically an equilibrium potential suitable for an entropy derivative.

If RC capacitance varies with temperature/SOC, differentiating `0.5 C v_p^2` adds a `0.5 v_p^2 dC/dt` term. Do not retain the constant-capacitance energy ledger unchanged. Either use a thermodynamically consistent state representation, keep identified constant capacitances within their domain, or derive and assess the additional terms explicitly.

For temperature-dependent capacity, distinguish reference charge inventory from temperature-dependent usable capacity and voltage endpoints. Simply replacing `Q` in `dz/dt` with a varying number can violate conservation or create artificial SOC jumps.

### 10.4 Release gate for wider temperatures

Enable the wider range only after the registered model has temperature-resolved source records, independent assessment, uncertainty, an applicability envelope and passing coupled-solver checks. The UI reads allowed ranges from that registered model. It must not have its own inconsistent hard-coded range after this upgrade.

A software-only synthetic temperature map can verify interpolation and feedback code. It cannot satisfy this empirical gate.

## 11. Identifying thermal parameters

A cooling time constant identifies `C/G`; it does not separately identify heat capacity and conductance. Determine one independently, or fit multiple experiments that identify both with acceptable uncertainty.

Use separate low-power cooling, controlled heating and mounting/contact experiments. Fit individual sensor trajectories and common ambient conditions, not only a module average. Include sensor lag and mounting differences if their effect is significant relative to the target error.

Estimate neighbour conductance from experiments with deliberately asymmetric heating and mapped contact paths. Symmetric heating barely excites that parameter. Identify conductor heat partition with conductor/fixture measurements or a justified resolved model.

The public [LG M50T base-cooling dataset](https://zenodo.org/records/6421061) is a useful additional candidate source for thermal model development. Its cooling arrangement must be checked against the proposed assembly before transferring any coefficient. It is not a replacement for fixture-specific validation.

Evaluate whether convection, radiation, enclosure conduction and coolant transport materially affect the decision. Add only the terms that can be parameterized and tested:

```
q_conv = h A (T_surface-T_air)
q_rad = epsilon sigma A (T_surface^4-T_surroundings^4)
q_contact = (T_a-T_b)/R_thermal_contact
q_coolant = m_dot c_p (T_out-T_in)
```

Radiation uses kelvin. Convective coefficients depend on geometry, orientation, flow, spacing and temperature; a decorative fan icon does not define `h`.

For a liquid circuit, track inlet temperature, flow, pressure drop, heat exchanger behavior and transient coolant storage where needed. Conservation through the coolant network must be verified independently of cell temperatures.

## 12. Additional real-world factors and when to add them

| Factor | Effect to represent | Evidence needed |
| --- | --- | --- |
| Contact resistance | Unequal current paths and local conductor heat | Four-wire/contact measurements under representative torque/pressure and temperature |
| Busbar geometry/material | Distributed resistance, thermal conduction and mass | Dimensions, alloy/resistivity, temperature coefficient, manufacturing tolerance and contact separation |
| Unequal starting charge | Circulating/unequal currents and different usable energy | Measured initialization protocol with charge/voltage uncertainty |
| Age and state of health | Capacity loss and resistance growth | Longitudinal cell data; distinguish capacity fade from resistance growth |
| Hysteresis | Charge/discharge voltage differences | Bidirectional rest/pulse experiments across SOC and temperature |
| High current and fast transients | Nonlinear resistance, diffusion, limits and inductive effects | Bandwidth-resolved experiments; model-order selection and regime-specific validation |
| Sensor/control behavior | Sampling, lag, quantization, balancing and protection | Sensor/controller transfer functions, software policy and hardware-in-loop checks |
| Cell-to-cell variation | Differences in capacity, resistance, reference and cooling | Independent cells with uncertainty; correlated parameter distribution |
| Mechanical mounting | Contact pressure, heat paths and dimensional fit | Geometry, fixture data, contact identification and structural model when needed |
| Ageing/lifetime | Path-dependent degradation | Dedicated cycling/calendar data and out-of-sample life trajectories |
| Abuse/runaway | Reaction heat, venting, propagation and protection | Specialized models, abuse data and qualified experimental work |

The present simulator must not claim that its ordinary equivalent circuit predicts abuse, short-circuit fault transients, thermal runaway, certification, manufacturing tolerance compliance or lifetime. Those are separate intended uses with separate evidence.

## 13. Calibration, validation and final-assessment separation

Assign roles by entire physical groups: source experiment, cell, module, fixture, temperature, protocol and acquisition session. Maintain a manifest of who has accessed each role. Existing protected artifacts remain frozen.

Use development data for parser diagnosis, model selection and parameter fitting. Use development validation for choosing model order and tuning only within the declared procedure. Reserve a final assessment that is opened once after the model, procedure, thresholds and uncertainty method are frozen.

If final outcomes influence a repair or threshold, that set becomes development data. Create a new independent final set. Relabeling the same traces “fresh” is not independence.

Separate initial-state estimation from prediction. If early test voltage/current is used to infer SOC or polarization, state the assimilation window and exclude it from forward-prediction scoring. Do not infer initial states from the full measured future trajectory and then call the simulation predictive.

For each assessment, preserve the exact untuned prediction before opening measured outcomes. Store time alignment, sensor mapping, event windows and exclusion rules in the locked assessment specification.

## 14. Verification matrix

### 14.1 Electrical analytical cases

- One cell with a resistor and current load; rest, discharge and charging signs.
- Identical parallel cells with ideal links: equal currents and correct terminal voltage.
- Series cells: equal current, summed voltage and per-cell charge conservation.
- Series-parallel groups: group KCL and string KVL.
- Unequal source voltages at zero external load: circulation, heat and charge transfer.
- Asymmetric conductor resistances: expected branch ordering and connection losses.
- Zero-resistance node equivalence, redundant ideal links and unidentifiable ideal-link currents.
- Disconnected nodes, invalid endpoints, shorted terminals, duplicate links, nonfinite and negative inputs.
- Permuting component storage order does not change node/cell physical results.
- Editable four-cell ladder reproduces the frozen solver for its identical inputs.

### 14.2 Dynamic and thermal cases

- Exact one-RC response to a current step, including nonzero initial storage.
- Piecewise load transitions occur at exact event boundaries.
- No extrapolation or SOC clipping.
- Time-step refinement of independent trajectory outputs.
- Adiabatic cell: thermal rise equals integrated resistor heat divided by heat capacity.
- Passive cooling: the exponential limiting case.
- Symmetric heat exchange: no energy gained by internal contacts.
- Zero cooling, zero contacts and very strong contacts as limiting cases.
- RC heat integration agrees with constant/exponential/double-exponential analytical forcing.
- Core/surface and temperature-feedback checks once those model families exist.

### 14.3 Persistence and user-result binding

- Layout/name edits preserve physical freshness; a connection or load edit invalidates it.
- An immutable test renders its own captured geometry/parameters, even after the current design changes.
- Concurrent writers cannot overwrite each other.
- A failed/stopped execution is distinguishable from a completed execution.
- Altering a result, model bundle or solver source is detected before export/replay.
- Export reproduces all numeric channels with the included source/model inputs.
- UI probes, legend selection, time controls and reports show the same saved samples.
- AI numeric statements are grounded in supplied solver outputs; AI actions are typed, bounded, previewed and checked for stale versions.

Software tolerances in unit tests derive from floating-point conditioning and numerical method expectations. They are not battery acceptance tolerances.

## 15. Experimental assessment metrics

Compute metrics in physical units, by experiment and operating regime before pooling. Include mean bias, RMSE, MAE, maximum absolute error, event-aligned transient error, drift, integrated charge/energy error and threshold-crossing timing error.

For a channel with measured values `y_k` and predictions `yhat_k`:

```
r_k = yhat_k - y_k
bias = mean(r_k)
RMSE = sqrt(mean(r_k^2))
MAE = mean(abs(r_k))
max_error = max(abs(r_k))
```

Do not use percentage voltage error to hide an absolute error that matters near a cutoff. Do not divide by a near-zero current or temperature rise. For imbalance, publish the exact denominator and applicability to the topology.

Assess peak cell identity and peak time, not just the numeric maximum. For current sharing, score mapped branch trajectories and total current conservation with measurement uncertainty. For temperature, score the actual sensor-equivalent state and its lag, not a visually attractive internal heatmap.

For thermal transients, include temperature rise above the measured local boundary and absolute temperature. A model can fit a rise while using the wrong ambient offset.

Report error by SOC, current, temperature, direction, cell, fixture and waveform. A global average can hide a failure precisely where a requirement is tight.

## 16. Uncertainty and sensitivity

Use the [BIPM/JCGM uncertainty guides](https://www.bipm.org/en/committees/jc/jcgm/publications) as the methodological reference for measurement-model uncertainty, correlated inputs and propagation. This plan does not claim conformity to a certification standard.

For a local smooth measurement model `y=f(x)`, a first-order propagation is `Sigma_y ≈ J Sigma_x J^T`. Retain off-diagonal terms. Shared calibration error does not disappear by averaging four branches.

Separate instrument uncertainty, parameter uncertainty, initial-state uncertainty, numerical error, model discrepancy and natural cell variation. Do not roll them into an arbitrary percentage on a chart.

For nonlinear or event-based outputs, propagate input distributions through the model using Monte Carlo or a justified alternative. Preserve correlations. Check sample convergence of quantiles and event probabilities; report sampling error. A small Monte Carlo sample is not a reliable rare-event probability estimate.

Use local sensitivities to find influential quantities, then use global sensitivity where interactions matter. Important candidates are contact resistance, initial charge, reference offset, capacity, R0/R1/time constant, heat capacity, cooling/contact conductance, ambient and current measurement calibration.

Compare designs using paired uncertainty draws for shared uncertain inputs. Compute uncertainty in the difference, not just two unrelated error bars. A small apparent improvement is inconclusive if its difference interval spans zero or a decision-relevant margin.

## 17. Requirements, investigation and comparison

A target record contains the quantity, units, direction, threshold, time-duration rule, source, applicability, uncertainty decision rule and owner. “No target configured” is not a pass.

A finite scenario screen evaluates exactly the cases listed. It does not establish a global worst case. Store evaluated/skipped/failed/stopped cases, search bounds, budget and model applicability in the evidence package, with simple outcomes in the interface.

Investigate interactions deliberately: load versus contact resistance, temperature versus resistance, charge imbalance versus connection layout, cooling versus heat generation, and cell variation versus output placement. A one-factor-at-a-time trial is useful for explanation but cannot identify all interactions.

For a discovered violation, save its exact design, operating conditions, target and first crossing. Reproduce it using the ordinary solver. Open it as an editable design so a proposed repair can be tested under the same conditions.

Comparisons require controlled common external conditions and explicit identification of what changed. If durations differ because one test stopped, do not rank delivered energy totals as though both covered the same experiment. Avoid a single winner when objectives trade off. Add Pareto analysis only when metrics, uncertainties and constraints are defined consistently.

## 18. Release gates and evidence products

Use a credibility lifecycle inspired by the [NASA model-and-simulation standard](https://standards.nasa.gov/node/263): intended use, conceptual model, verification, empirical assessment, uncertainty and controlled release. This is a development structure, not a NASA endorsement or compliance claim.

| Gate | Required evidence | Allowed claim |
| --- | --- | --- |
| Graph/software gate | Analytical topologies, numerical convergence, energy/charge/heat accounting, replay and UI/result binding | The implementation solves its declared equations for these software cases |
| Cell calibration gate | Traceable calibration records, identifiable parameters, residual/uncertainty diagnostics and frozen fits | Parameters fitted for the declared cell/protocol domain |
| Cell assessment gate | Reserved cells/waveforms/temperatures, locked predictions and requirement-specific errors | Assessed cell predictions within the tested domain |
| Module gate | Reconciled instrumentation, mapped branches/sensors, reserved physical assemblies and uncertainty | Assessed module predictions for the stated configurations and conditions |
| Temperature/cooling gate | Independent temperature-resolved electrical data and fixture-specific thermal tests | Two-way electrothermal prediction over the stated evidence envelope |
| Design decision gate | Error/uncertainty smaller than the required decision margin, controlled comparison and engineering review | A supported conclusion about the stated requirement or trade-off |

Before competition submission, include the exact input/model/software versions, an ordinary baseline, a reproducible difficult case, one justified design revision, controlled comparison, measured versus predicted plots, uncertainty and the limits of the conclusion. If empirical gates are incomplete, the submission's engineering claim must remain narrower than a validated predictive tool.

## 19. Implementation sequence and audit ownership

1. Freeze the current mathematical/model artifacts and snapshot the local measurement audit.
2. Create the source/calibration/split/parameter registry with immutable identifiers and import diagnostics.
3. Resolve current-channel calibration and mapping before module fitting.
4. Acquire temperature-resolved development data for the correct part; keep independent cells/temperatures/waveforms reserved.
5. Implement positive, bounded parameter surfaces and their uncertainty; verify interpolation and domain behavior on synthetic tests separately.
6. Replace the one-way fixed-parameter integrator with a consistent two-way state system. Derive the temperature-dependent storage and reversible-heat terms for the chosen model.
7. Identify thermal properties and fixture contacts through experiments that excite those parameters independently.
8. Lock predictions and assess reserved cell/module records. Compare residuals against the predeclared measurement and decision budgets.
9. Repair model deficiencies using development data only. Reserve new final experiments if previous assessment outcomes inform changes.
10. Review the product claims against the achieved gates and attach a reproducibility package to every shown result.

The technical audit should try to falsify the model, measurement chain, code and conclusion independently. A reviewer must be able to locate a claim, reproduce its calculation, identify its empirical evidence and state the smallest counterexample that breaks it.

## 20. Source and assumption discipline

Primary sources consulted on 27 October 2026:

- [Piombo campaign v2, DOI 10.17632/zh58byr53c.2](https://data.mendeley.com/datasets/zh58byr53c/2): source scope, version and licence.
- [Piombo and colleagues, Data in Brief 53 (2024), 110227](https://pangea.stanford.edu/ERE/pdf/OnoriPDF/Journals/91.pdf): characterization and experimental instrumentation.
- [BIPM/JCGM publications](https://www.bipm.org/en/committees/jc/jcgm/publications): uncertainty references, including JCGM 100, 101 and 106 and current amendments.
- [NASA-STD-7009B record](https://standards.nasa.gov/node/263): model/simulation credibility lifecycle reference.
- [Marzook, base-cooled LG M50T and Samsung 30Q dataset](https://zenodo.org/records/6421061): additional candidate thermal data; no coefficients transferred in the present implementation.
- [Bernardi, Pawlikowski and Newman, general battery energy balance](https://doi.org/10.1149/1.2113792): background reference for deriving a complete thermal balance. The current implementation's constant-parameter resistor/storage equations are derived explicitly above; they are not a claim to implement every term of that general model.

All proposed experimental grid values and release tasks in this document are plans. Existing fitted/default parameter values are identified as such. No protected assessment outcomes were opened or refitted to produce this plan.
