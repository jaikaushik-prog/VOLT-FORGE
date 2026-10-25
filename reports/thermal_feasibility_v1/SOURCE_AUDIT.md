# Thermal evidence audit: exact LG M50T versus a synthetic prototype

Research accessed 26 October 2026. These are primary literature/author-repository
sources. No new raw measurements were downloaded. This audit does not establish
that a missing property is absent from all literature; it states what the
reviewed evidence supports for this implementation.

| Source | Traceable evidence | Use and limit |
| --- | --- | --- |
| Marzook et al. (2022), [Thermal evaluation of lithium-ion batteries: Defining the cylindrical cell cooling coefficient](https://doi.org/10.1016/j.est.2022.105217) | Exact LG INR21700-M50T; two specimens, base-cooled insulated fixture. Reported combined base cooling coefficient 0.139 W/K, fit interval +/-2.8%. Its denominator is positive-cap-to-base temperature difference. | Evidence of a measured internal, fixture-specific cooling metric. It is **not** node-to-ambient H. No value is imported into the prototype. |
| Marzook, [author dataset v1](https://zenodo.org/records/6421061), DOI 10.5281/zenodo.6421061 | Metadata names M50T and Samsung 30Q thermal/electrical data. Lists M50.zip (90.0 MB, MD5 `6c447759755ea0d184050c49e4a2687a`), 30Q.zip and ReadMe.txt. | Concrete public-data lead; landing-page metadata only inspected. M50.zip's label must be reconciled with raw specimen metadata before use. Its suitability for transient identification and independent assessment remains unknown. |
| Li et al. (2021), [Optimal cell tab design and cooling strategy for cylindrical lithium-ion batteries, author manuscript](https://spiral.imperial.ac.uk/server/api/core/bitstreams/34e87deb-b30b-414b-8002-31cf6f4f839a/content), sections 2.2-2.3, 3.2 and Table I | Exact M50T distributed model includes internal geometry, core/surface temperatures and reversible heat. Component thermal properties are literature-derived; the entropy coefficient uses a similar NMC pouch cell. | Establishes why bulk/surface/core and cooling geometry must be distinguished. Component properties are not a directly measured whole-cell C_th. No borrowed entropy curve or aggregate heat capacity is adopted. |

The exact-part studies establish that relevant public work exists. They do not
calibrate a one-node model of our four-cell enclosure, connections or cooling
conditions. Their independent test outcomes were not extracted or used as
our assessment results. Nominal electrical Ah capacity is not thermal J/K.

## Local evidence already available

- `src/voltforge/models/coupling_v2.py`: computes cell R0 dissipation, R1
  resistor dissipation, rail dissipation and RC-state energy/work separately.
  Its closed electrical power balance is software evidence. The model's fitted
  resistance losses are not a measured complete electrochemical heat source.
  Rail losses occur outside the cell; their fraction entering it is unknown.
- Frozen LG electrical evidence uses nominal 23 degC characterization and
  lacks a validated temperature law, spatial temperature field and thermodynamic
  reference/entropy characterization. A circuit capacitor's fitted storage
  state is not an identified thermochemical energy store.
- `reports/p45b_reference_origin_v1/DECISION.md`: preparation/reference linkage
  remains unresolved; constant recorded 25 degC is protocol evidence. P45B
  quantities, including its separately documented heat capacity, do not become
  M50T inputs. No P45B data is used here.
- `VOLT_FORGE_Product_Vision.md` calls for evidence-backed capabilities. The
  current editor's thermal requests remain unavailable; this separate prototype
  does not create a thermal contact from visual position or an electrical edge.

## Parameter disposition

| Required quantity | Current disposition | Evidence required for real-cell use |
| --- | --- | --- |
| C_th, J/K | Unset for M50T; synthetic 100 only in the demonstration | Exact specimen/batch, mass, state, temperature range; calibrated calorimetry or identifiable known-heat transient, with uncertainty and repeatability. |
| H, W/K | Unset for the module; synthetic 0.5 only | Named lumped temperature and environment, contact/airflow/enclosure geometry, sensor placement, cooling boundary histories and suitable transients. |
| Prescribed signed heat, W | Synthetic piecewise input; no electrical mapping | Calibrated heat input/heat flow or an independently supported complete electrochemical heat model, including reversible contribution and allocation of external heat paths. |
| Initial and ambient temperature, degC | Synthetic; mandatory, no defaults | Calibrated synchronized measurements, equilibration/preparation history, ambient/coolant definition and spatial gradients. |
| One-node applicability | Mathematical assumption only | Evidence that the selected representative temperature and unmodelled internal gradients are adequate for the intended decision. |

No physical M50T thermal parameter is selected. A candidate public archive may
support a **different, specified laboratory cooling case** after prospective
allocation. It does not by itself establish our module's thermal behavior.
