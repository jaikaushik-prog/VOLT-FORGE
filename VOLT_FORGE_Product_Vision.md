# VOLT-FORGE

> **Product Vision & Experience Blueprint**  
> Battery engineering / Tata Elxsi TELIPORT Case Study 2  
> **Concept brief — 24 October 2026**  
> **Status:** Product concept and proposed implementation, **not** a claim that a working, validated engineering product exists.

## The product in one sentence

**VOLT-FORGE is a visual engineering workspace that connects battery-design decisions to their physical consequences.**

**Design. Simulate. Understand. Improve.** The aim is to combine **AutoCAD's engineering capability**, **Figma's direct manipulation and simplicity**, and **Claude's visual restraint**. Engineers build configurations, test them, explore failure conditions, compare alternatives and defend decisions with reproducible evidence.

![VOLT-FORGE conceptual main workspace](assets/editor.png)

*Visual concept only. Screen content, part specifications, simulated performance figures and AI suggestions shown in the mockup are illustrative and have not been validated.*

---

## 1. Product premise

### Change one thing. See what that decision changes.

Battery design spans disciplines. A small change to wiring, a cell, contact resistance, sensor placement, cooling or load can change current distribution, temperatures, energy delivered, cost and safety margins. The underlying workflow is fragmented across component specification documents, circuit tools, mechanical/CAD systems, simulation tools and spreadsheets.

VOLT-FORGE aims to put **geometry, connections, operating conditions, component parameters, constraints and simulation results in one linked engineering model**. The user should be able to manipulate a design directly and understand *which physical consequences have changed*.

**Initial audience:** engineering students and engineers evaluating cell/module configurations, trade-offs and failure scenarios.  
**Initial scientific scope:** one measured **four-cell parallel research module (1s4p)**, **not** an industrially certified or production-ready battery pack.

Three pillars:

1. **Design** — assemble and configure cells, conductors, sensors and thermal interfaces through linked 3D and electrical/topology views.
2. **Simulate** — evaluate declared load and environmental conditions using explicit, physically grounded models.
3. **Decide** — identify violated requirements, explore design variants and compare outcomes using traceable evidence.

## 2. One continuous user journey

These are not nine disconnected tools; all screens operate on the **same versioned project state**.

| Step | User activity | Result |
| --- | --- | --- |
| 1. Start | Choose template, blank canvas or natural-language objective | Draft project with assumptions |
| 2. Assemble | Place cells, busbars, cooling, sensors and structures | Explicit geometry and connectivity |
| 3. Configure | Set component parameters, constraints and operating domain | Defined engineering problem |
| 4. Simulate | Run relevant electrical/thermal models | Predictions and validity metadata |
| 5. Investigate | Search for operating cases that violate limits | Reproducible failure scenarios |
| 6. Branch | Modify or duplicate the design | Alternatives A0/A1/A2 |
| 7. Compare | Run alternatives under identical conditions | Defensible engineering trade-offs |
| 8. Document | Export analysis with full assumptions | Reproducible evidence package |

**Invariant:** editing an input or component marks dependent simulation results **stale**. Old runs are preserved for comparison but must never appear current.

![Product screens and flow, illustrative atlas](assets/screen_atlas.png)

## 3. Project Hub

The user should enter a meaningful design in minutes rather than complete a long technical wizard.

**Three starting modes**

- **Template:** open a supported reference module with sourced starting parameters.
- **Blank canvas:** construct and connect components directly.
- **Describe a requirement:** AI proposes an editable configuration, lists missing constraints and asks for human approval.

Each project contains component identities and versions, geometry and electrical topology, thermal/control interfaces, scenarios and requirements, simulation histories, design branches, source evidence and reviewer decisions.

![Project Hub reference](assets/project_hub.png)

## 4. Design Studio: the canvas is the product

The central 3D assembly occupies most of the screen. The component library, contextual inspector, editing tools and AI copilot are supporting surfaces; they should collapse or move out of the way when the user needs focused design space.

**Main interactions**

- Place, select, drag, duplicate, group, measure, align and remove supported components.
- Orbit, pan and zoom; toggle **2D / 3D / exploded / section** where implemented.
- Snap and connect cells, busbars and parts using explicit engineering rules.
- Select an object to inspect only its relevant parameters, interfaces, datasheet, model fidelity and source.
- Edit a parameter, preview invalidated analyses, then rerun the required physics.
- Undo/redo and create named design variants rather than overwriting a useful configuration.

**Important modelling rule:** a 3D shape touching another shape does *not* automatically imply a valid electrical or thermal connection. The solver must use explicit graph-based connections.

### One component, several linked representations

| Representation | What is stored |
| --- | --- |
| **Geometry** | Shape, position, dimensions, clearances, fasteners and physical assembly |
| **Electrical topology** | Cells, terminals, graph nodes/edges, contact resistance, protection and branch connections |
| **Thermal/control topology** | Contact surfaces, cooling boundaries, temperature sensing, control and operating policies |
| **Evidence** | Datasheets, experimental parameters, validity domain, versions and uncertainty |

This is the architectural core: multiple views over one coherent engineering object.

## 5. Component Library

Not a collection of pretty thumbnails. Every selectable part must have a typed and versioned **component contract**.

**Example classes:** cells, modules, busbars/connections, structural frames and enclosures, thermal interfaces and cooling, sensors, BMS/control and protective devices.

**Typical metadata:** identifier and type; manufacturer/part number; chemistry; physical geometry; electrical and thermal parameters with units; interfaces and connection points; applicable load and temperature ranges; documentation; source; revision; uncertainties; supported model fidelity.

Users can browse/compare parts, import documented parameters, view evidence, insert into a project and inspect which analyses are enabled or disabled by the available information.

![Component library visual reference](assets/component_library.png)

**Do not invent component specifications or treat model parameters derived from unrelated cell types as measured facts.**

## 6. Simulation Studio

Every run is a versioned experiment, not just a “Run AI” button.

| Input | Examples |
| --- | --- |
| **Load** | Constant-current discharge, scheduled variable load, charging profile, imported profile |
| **Environment** | Ambient temperature, selected cooling assumptions, boundary conditions |
| **Starting state** | State of charge (SOC), initial temperatures, justified cell variations |
| **Physics scope** | Available electrical/thermal models and fidelity; other domains only when implemented |
| **Numerics** | Run duration, solver settings, tolerances, random seed where relevant |
| **Constraints** | Allowed voltage, current and temperature ranges, as defined for the experiment |

Changing geometry should update the visual object immediately. Calculating new coupled temperatures or branch currents may require a full rerun. Do not fake instant results to make the UI feel magical.

![Simulation setup visual reference](assets/simulation_setup.png)

## 7. Results Explorer

**Show the physics on the assembly, not only in charts.**

- Toggle supported data overlays: per-cell temperature, current, voltage and other quantities actually produced by implemented models.
- Scrub the simulation timeline and see corresponding model states.
- Select Cell 3 or a busbar to view its series, parameter assumptions and relevant connections.
- Click an apparent hotspot to inspect its generating load case, model and limits.
- Keep synchronized plots and quantitative tooltips alongside the spatial view.

**Every output receives an evidence label:**

1. **Measured** — present in a published or independently acquired experiment.
2. **Model validated in range** — prediction with measured agreement inside a stated parameter domain.
3. **Simulated** — physics-based prediction not yet independently validated for that case.
4. **Extrapolated** — prediction outside the established measurement/validation range.

A decorative thermal, mechanical stress or current-density image must never be presented as a solver result without the corresponding model and boundary conditions.

![Simulation results visual reference](assets/simulation_results.png)

## 8. Failure Investigator: VOLT-FORGE's signature capability

This incorporates Jai's **counterexample-guided battery module redesign** research within the broader visual product.

The premise: a module that behaves acceptably at its nominal operating point may violate requirements if a contact degrades, temperature changes, load shifts or cell properties differ.

**Proposed workflow**

1. Engineer declares a measurable requirement and a valid operating domain.
2. An experiment runner evaluates permitted conditions and parameter variation.
3. The system finds a **counterexample**: a reproducible input scenario that violates the requirement.
4. It surfaces relevant model assumptions and a finite catalogue of *physically representable* repairs.
5. The engineer explores and approves one or more changes, then reruns the simulation.
6. Competing variants are compared honestly with common test conditions and costs.

**Examples of permitted intervention classes:** modify allowed interconnections or busbar parameters, change model-supported cell placement, adjust sensing, or derate permitted operating limits. An intervention that changes cooling geometry without a supporting thermal model must not inherit old predictions.

**AI optimisation is optional.** For small discrete candidate sets, evaluate all valid options or use transparent engineering heuristics. Introduce search/optimisation only where it demonstrates value over a fair baseline.

## 9. Design Versions and Comparison

VOLT-FORGE should encourage controlled experimentation rather than losing work each time the user tries something new.

| Variant | Meaning |
| --- | --- |
| **A0** | Original measured/reconstructed research-module baseline |
| **A1** | Sensible heuristic modification chosen by an engineer |
| **A2** | Alternative selected through search or manual exploration |

Compare all options using the **same declared conditions**, with outputs limited to quantities the model can support: delivered energy, branch-current imbalance, cell temperature, size/mass where available, estimated cost where sourced, constraint margins, runtime and uncertainty.

The tool should make trade-offs obvious, **not declare a winner without a fair comparison**. No fabricated improvement percentages or safety certifications.

![Design comparison visual reference](assets/design_comparison.png)

## 10. AI Engineering Copilot

**A creative interface, not a physics oracle.** AI maps natural language to *proposed engineering actions* and explains verified solver data; specialist mathematical solvers produce numerical outcomes.

| Mode | Example request |
| --- | --- |
| **Create** | “Draft a four-cell parallel module.” |
| **Modify** | “Try a more symmetrical busbar connection.” |
| **Explain** | “Why is Cell 3 warmer than the others?” |
| **Investigate** | “What requirement did this operating case violate?” |
| **Compare** | “What do I gain and sacrifice in Variant B?” |
| **Learn** | “Teach me why contact resistance affects current sharing.” |

**Preview before apply:** enumerate proposed changes, verify model support and constraints, state invalidated runs, request approval, apply changes, then rerun the engineering model.

The copilot should be dismissible, resizable and context-aware rather than permanently occupying half the canvas. It should cite exact run IDs, component sources and assumptions when explaining findings.

![AI copilot visual reference](assets/ai_copilot.png)

## 11. Reports and Handoff

Engineering results matter when they can be reproduced and independently reviewed.

**Proposed report/export package**

- **Design:** component IDs and versions, geometry, electrical connections, cooling arrangements and requirements.
- **Run:** environmental/load settings, initial conditions, solver settings, seed, model/software version.
- **Results:** supported metrics, time series, overlays, design-comparison tables and constraint violations.
- **Evidence:** input datasets/datasheets, parameter-fitting and holdout methodology, model errors and applicability limits.
- **Exports:** PDF report, structured simulation tables and configuration files. Manufacturing-grade CAD exports are later scope until properly supported.

![Report UI visual reference](assets/report.png)

## 12. Science and Validation

### Starting evidence anchor: Piombo v2

**Reference:** Piombo parallel-module experimental dataset, DOI: [10.17632/zh58byr53c.2](https://doi.org/10.17632/zh58byr53c.2).

Start with the **1s4p all-NMC LG M50T subset**, including measured branch currents and cell surface temperatures. Inspect original raw experiment files, parameter documentation, cell identity, units, current sign conventions, sampling/timestamps and which conditions are actually present.

**Validation proposal**

1. Reconstruct one real measured experimental run using a declared model and calibration process.
2. Preserve **whole experimental runs** for held-out testing; adjacent time samples in one experiment are not independent trials.
3. Compare predicted and observed per-cell currents and temperatures, not merely overall voltage.
4. Compare baseline and at least two valid alternatives under shared conditions, separating published measurement from new simulation.
5. Log data provenance, model code/parameters, uncertainties, model applicability and every assumption.

**What is not currently proved:** accuracy of this team's own solver, a quantified improvement from any repair, successful battery safety certification, or end-to-end pack-scale model validity. Available research makes such tests feasible; it does not substitute for completing them.

## 13. Proposed Technical Architecture

```text
Interactive design editor (2D / 3D)
         |                  |
Typed component library    Engineering constraints
         |                  |
         +-------+----------+
                 |
         Versioned model graph
      (geometry + electrical + thermal + control)
                 |
       +---------+----------+
       |         |          |
  Electrical   Thermal   Controls / checks
    solver      solver       engine
       |         |          |
       +---------+----------+
                 |
       Experiment runner + validity metadata
                 |
     Failure-case search + scenario replay
                 |
       Variant comparison + engineering report
                 |
        AI copilot (proposes/explains,
               never fakes solver output)
```

**Initial engineering models:** explicit cell/branch electrical network, source-backed per-cell equivalent-circuit parameters, state-of-charge evolution, suitable low-order thermal dynamics and modelled sensing/control assumptions.

**Optional future extensions:** higher-fidelity electrochemistry, computational fluid dynamics (CFD), structural finite-element analysis (FEA), automated search, larger packs and advanced CAD exchange. Their inclusion depends on adequate models, geometry, numerical validation and data.

## 14. Build Strategy: Don't shrink the vision; prove it

### Stage 1 — Credible working demonstrator

- Editable four-cell parallel module and explicit electrical topology.
- Sourced/declared cell and contact parameters, supported thermal assumptions.
- A numerical electrical + thermal solver and reproducible experiment setup.
- Actual current/temperature outputs rendered as time series and on the assembly.
- Basic failure/constraint checks and saved variants.

### Stage 2 — Scientific proof

- Load one raw Piombo experiment, verify cell identities and channel conventions.
- Fit allowable parameters without leaking held-out experiment data.
- Quantify errors on untouched runs; characterize validity limitations.
- Compare A0 against two feasible modifications using consistent conditions.

### Stage 3 — Product proof

- Professional 3D selection and manipulation, contextual properties, component library and scenario editor.
- Searchable/replayable failure display, branch history, side-by-side comparison and sourced report generation.
- User testing: can an engineering student/engineer understand and reproduce a meaningful design decision?

### Long-term scope

More chemistries and topologies; parametric assembly; configurable cooling; importable datasets; higher-fidelity simulation; complex fault scenarios; optional intelligent search; pack-scale modelling; collaborative engineering review; CAD interoperability and validated exports.

**Scope discipline:** a spectacular 3D editor cannot compensate for invented physical outputs. Conversely, a validated four-cell simulation can serve as the seed of a much larger editor architecture.

## 15. Decisions for the team

1. **User and use case:** Is the initial buyer/user an engineering student, university lab, or module-design engineer? What decision is difficult or expensive today?
2. **Exact module scope:** Which 1s4p geometry, interconnections, cooling conditions and component modifications can the model represent honestly?
3. **Raw data status:** Has the team downloaded the original Piombo experiment and verified signal names, units and identities?
4. **Proof:** What are the A0/A1/A2 alternatives, model accuracy targets and fair comparison procedure?
5. **Division of work:** Who owns electrical model/validation, thermal model/validation, design experience/frontend, integration and evidence/slide quality? Assign based on demonstrated technical skills.
6. **Competition brief:** Align the big product vision with the official battery Case Study 2, without claiming the future platform is already built.

### Competition context

The registered-portal screenshot supplied to the team lists the **Round 1 submission deadline as 1 November 2026, 23:59 IST** (revised from earlier third-party listings). Confirm portal instructions on slide count and template details before submission.

## 16. Visual Reference Atlas

The included images are **concept mockups only**. They communicate visual language, layout, interaction patterns and potential workflows. **All displayed values, labels, part numbers, performance improvements and pseudo-physics graphics must be checked against actual sources or replaced with working solver outputs.**

- [Full editor and exploded assembly](assets/editor.png)
- [Multi-screen application atlas](assets/screen_atlas.png)
- [Project Hub](assets/project_hub.png)
- [Component Library](assets/component_library.png)
- [Simulation Setup](assets/simulation_setup.png)
- [Simulation Results](assets/simulation_results.png)
- [AI Copilot](assets/ai_copilot.png)
- [Design Comparison](assets/design_comparison.png)
- [Reports](assets/report.png)

---

## Final positioning

> **VOLT-FORGE — A visual engineering workspace that connects battery design decisions to their physical consequences.**  
> Build configurations. Understand interactions. Discover what breaks. Compare alternatives. Defend the result with evidence.

The immediate commitment is a **measured four-cell research module**, **physically grounded, reproducible simulations**, **counterexample-guided review**, and **clear, source-backed design comparisons**. The modular CAD-like platform is the direction of travel, not a claim about today's implementation.
