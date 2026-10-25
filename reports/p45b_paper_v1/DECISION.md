# P45B paper review and isolated equation checks

The user-supplied full paper resolves the missing **core electrical specification**.
The inaccessible second documentation link is no longer needed for this step.
This stage adds a page-referenced method map and a synthetic-tested electrical
kernel. It does not fit a model, consume reserved measurements, replace frozen
LG v2, or make the editor capable of simulating P45B modules.

The original [intake decision](../p45b_intake_v1/DECISION.md) remains preserved as
the record of what was known before the paper arrived. Its specification-access
blocker is superseded here. The original prospective allocation is unchanged.

## Source and access record

Source: Dickinson et al., *An Industry-Standard Parameterisation of a Lithium-Ion
Battery Equivalent Circuit Model for a High-Power Cylindrical Cell: Molicel P45B*,
[SSRN 6861858](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6861858).
The supplied PDF has 56 pages, including supporting information. Page references
below use the PDF's one-based page order. The file hash and methods inspected
are recorded in [source.json](source.json). This identifies the local copy, not
an independently verified publisher version. The original PDF stays local;
the Zenodo data licence is not assumed to license this separate PDF.

Methods were extracted and equation pages 7, 8 and 53 visually checked against
renderings. Locating methods also exposed some published validation captions.
The paper's published results are prior information, not blinded assessment.
**No numerical rows from either parameter CSV, any of the 51 experimental CSVs,
or the validation workbook were opened.** All 43 filename families remain
protected. All nine unused LG characterization cells, protected module outcomes,
13 unused FreeTwinEV records and existing frozen artifacts remain preserved.

## Equations and implementation conventions

| Paper location | Confirmed specification | Implementation consequence |
|---|---|---|
| p.7, Eqs.1-2 | Two reference branches mixed by hysteresis h; gamma controls its current-dependent evolution | Use both branches and preserve h through rests; do not treat gamma as another RC time constant |
| p.8, Eqs.3-6 | Two RC states, series resistance and **charge-positive** current | Source discharge current is negative; convert explicitly at any future interface with the discharge-positive LG solver |
| p.8 footnote | Equations assume coherent units | Capacity in Ah needs a factor of 3600 with current in A and time in s |
| pp.8,17 | Linear SOC/temperature interpolation and nearest-neighbour extension | Future table adapter must declare the interpolation construction; stop outside support by default, permit flagged boundary extension only explicitly |
| p.9, Eqs.7-10 | Nominal-capacity SOC; equilibrium initial RC voltages zero | Capacity is nominal 4.5 Ah; SOC=1 is the fresh cell's charge-direction 4.2 V equilibrium at 25 degC; SOC below zero is not automatically a coding error |
| pp.16-17 | Reference curves derived from loaded C/30 pOCV; positive fit bounds, R2 can approach zero | Do not call the reference a directly measured long-rest equilibrium curve; handle a degenerate zero-R pair explicitly |
| p.53, validation conditions | Constant nominal setpoint temperature; input is recorded experimental current even for power-controlled tests | First reproduction is isothermal and open loop in current, not a closed-loop power or thermal simulation |
| p.53 | Discharge/drive-cycle SOC0=1; h0=-1. Charge h0=+1, SOC0 from preceding charge counting | These are the authors' reproduction assumptions, not measured starting states or permission to tune against assessment voltage |
| p.53 | Compare shared pre-termination interval; omit charge CV hold in author RMSE | Declare any future truncation/CV exclusions and also report the available full comparison interval |

For clarity, the electrical equations in our notation are:

```text
E = (1+h)/2 * E_charge + (1-h)/2 * E_discharge
dSOC/dt = I / (3600 * Q_nom_Ah)
dh/dt = gamma * abs(I) / (3600 * Q_nom_Ah) * (sign(I) - h)
dVn/dt = (I * Rn - Vn) / (Rn * Cn), n=1,2
V_terminal = E + I * R0 + V1 + V2
```

Zero current freezes h and SOC while the RC voltages relax. R0 acts immediately
at a current transition, including a nonzero first current sample. Equilibrium
initialization does not justify suppressing the first ohmic drop. A zero-R pair
has zero algebraic voltage; an active pair needs positive capacitance.

The authors order RC pairs by time constant (p.8). The kernel preserves the
supplied labels rather than dynamically swapping stored states; a future table
audit must report any crossing/degeneracy. The initial hysteresis direction in
p.53 is explicitly justified by the loaded reference construction. Reversing it
to match the preceding physical charge direction would change this reproduction.

**Printed metric discrepancy:** p.53 Eq.S7 appears to omit the square on the
voltage residual inside the sum, although its accompanying prose says
root-mean-square error. Future comparison will use the conventional
`sqrt(mean((predicted - measured)**2))`, with V units and separately declared
time weighting. It will not implement the dimensionally inconsistent printed
expression or silently redefine a reported author number.

## What is implemented and checked

[`scripts/ae_p45b_equations.py`](../../scripts/ae_p45b_equations.py) is an isolated
equation kernel, kept outside the frozen LG implementation. It accepts explicit
parameters and initial states. Under constant current and parameters, exponential
RC/hysteresis updates and coulomb counting are exact apart from floating-point
roundoff. It rejects invalid/nonfinite parameters. There is no automatic SOC
clipping. A separate reference-support guard stops by default; an explicit nearest
query returns a warning without changing integrated SOC.

The CLI generates only an **invented** discharge/rest/charge example. It reads
neither real measurements nor fitted tables. It is not an end-to-end published
model reproduction: the actual CSV loader, two-dimensional table interpolation,
variable-parameter integration and record comparison are still to be completed.
The reference guard is not a claim that lookup support has been established.
No temperature state, thermal loss prediction, module coupling or optimizer is
added. Constant-parameter step invariance does not prove adequate step size for
SOC-dependent parameters.

The tests check analytical charge accounting, both current signs, reference
mixing, immediate ohmic steps, two exponential pulse responses, rest recovery,
current reversal, bounded hysteresis, gamma=0, a degenerate RC pair, explicit
support failures, invalid inputs, and complete synthetic sequence invariance
under a four-times smaller time step. The test receipt records the actual count.
These checks establish software consistency, not measured voltage accuracy.

## Next bounded work and remaining dependencies

1. Freeze the precise published-parameter reproduction procedure and allowed data
   access before opening outcomes. Start with the **base parameter table** and
   the complete **25 degC 1C discharge development family** already identified in
   the allocation proposal. Do not choose a table by looking at protected errors.
2. Audit the table grid, units, positivity, RC time constants and supported SOC
   bounds. Implement declared interpolation, substep convergence, measured-current
   sampling convention and stop/extension handling. The paper supplies the rule
   class but not all numerical details of the authors' proprietary simulator.
3. Use nominal 4.5 Ah, SOC0=1, h0=-1, V1=V2=0 and constant 25 degC as **declared
   author assumptions** for that discharge reproduction. No voltage-based initial
   state adjustment. Diagnose actual sampling, temperature and termination from
   the development record; record discrepancies rather than quietly correcting.
4. Only after freezing the procedure, assess further declared whole sequences.
   The authors' validation profiles are not fresh independent tests of their own
   already-published parameters. Keep our unused families protected until needed.

No further document is required to begin that discharge route. Charge reproduction
still needs its charge-counted starting state/preparation history. The paper points
to the initial disclosed simulated SOC; using that value would be a declared author
initial condition, not independent measured SOC, and is not authorized by the
current measured-only adapter. Exact refitting of the authors' parameters would
also require their proprietary identification procedure and calibration protocols;
using the published tables is a different, feasible task.

For actual four-cell validation, calibration uncertainties, preparation/history,
sensor timing/mapping, voltage sense locations, interconnect/contact resistance
and individual branch-current evidence remain missing. This single-cell paper
does not supply those measurements for the FreeTwinEV module or resolve the LG
current discrepancy. Device minimum voltage and permitted excursion duration
remain **requirement not configured**. No outreach was sent.

## Reproduce this stage

From the repository root, use fresh output paths:

```powershell
& C:\Users\DELL\anaconda3\python.exe -m pytest tests\test_ae_p45b_equations.py tests\test_ae_p45b_intake.py -q
& C:\Users\DELL\anaconda3\python.exe scripts\ae_p45b_equations.py --out tmp\p45b_synthetic_equations.json
& C:\Users\DELL\anaconda3\python.exe scripts\verify_p45b_paper.py --out tmp\p45b_paper_verification.json
```

In student terms: we now know the mathematical rules needed to use the new cell
dataset, and the basic implementation behaves correctly on problems with known
answers. We have not yet shown that it predicts these real cells accurately.
The next step is a declared single-cell comparison, before any four-cell claim.
