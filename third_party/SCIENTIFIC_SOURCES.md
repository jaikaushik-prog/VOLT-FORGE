# Scientific source attribution

The source-linked models and calculations are research-prototype inputs. Source
publication does not establish the accuracy of a new module or operating regime.

- **LG M50T published electrical tables:** Imperial College London, PyECN,
  commit `32540fe0819bfc4d099bcd601d1ab0625cb524a3`,
  `pyecn/Input_LUTs/Cylindrical_Cell1`.
  <https://github.com/ImperialCollegeLondon/PyECN>.
  BSD-3-Clause notice is retained in `PyECN-LICENSE.md`. The importer uses
  whole-cell resistance/capacitance tables and their stated rated charge,
  without unrelated cell-area scaling.
- **Samsung 30T electrical experiments:** Phillip Kollmeyer and Michael Skells,
  Samsung INR21700 30T 3 Ah Li-ion battery data, version 2,
  DOI [10.17632/9xyvy2njj3.2](https://data.mendeley.com/datasets/9xyvy2njj3/2),
  CC BY 4.0. The calibration model is a derived approximation; its methods,
  source files and assessment roles are recorded with the candidate.
- **Original LG M50T sample/module campaign:** G. Piombo, S. Fasolato,
  R. Heymer and colleagues, full-factorial parallel-cell dataset, version 2,
  DOI [10.17632/zh58byr53c.2](https://data.mendeley.com/datasets/zh58byr53c/2),
  CC BY 4.0. Historical fitted sample identities retain their original lineage.
- **Copper physical constants:** Copper Development Association,
  [Physical properties of massive fully dense copper, Table 3](https://copper.org/resource-library/characteristics-and-properties-of-copper-and-copper-alloy-p-m-materials/).
  The rectangular-link reference uses resistivity 1.71 microohm-cm and density
  8.94 g/cm3 at 20 C. Dimensions and joint/contact resistances are user or study
  assumptions. This calculation does not establish conductor ampacity or joint
  quality.
- **M50T thermal evidence:** M. Waseem Marzook, Cell Cooling Coefficient Data for
  Base Cooled LG M50T and Samsung 30Q,
  DOI [10.5281/zenodo.6421061](https://zenodo.org/records/6421061), CC BY 4.0.
  The linked paper is Marzook, Hales, Patel, Offer and Marinescu,
  [Thermal evaluation of lithium-ion batteries: Defining the cylindrical cell cooling coefficient](https://doi.org/10.1016/j.est.2022.105217),
  Journal of Energy Storage 54 (2022), 105217, CC BY 4.0. Follow-up qualification
  reads only allocated calibration observations. Its base-cooling conductance
  is distinct from cell heat capacity or room-air convection. No new thermal
  parameter from this experiment has been automatically promoted into the app.
- **M50T whole-cell heat capacity:** M. Steinhardt and colleagues,
  [Low-effort determination of heat capacity and thermal conductivity for cylindrical 18650 and 21700 lithium-ion cells](https://doi.org/10.1016/j.est.2021.103065),
  Journal of Energy Storage 42 (2021), 103065. The primary article is reproduced
  in the author's [TUM thesis](https://mediatum.ub.tum.de/doc/1651438/1651438.pdf).
  Table 1 identifies INR21700 M50T; Table A.14 supplies the whole-cell lumped
  heat capacities. The reference is 58.5 J/K at 298 K and about 71 percent charge.
  Its tabulated interval, systematic uncertainty and model limitations are
  distinct. It is used as a constant reference approximation, not a measured
  temperature-dependent law or new-specimen accuracy claim. Cooling is separately
  estimated from already-exposed Piombo rests with measured chamber temperature;
  transferring that fixture parameter to a new assembly remains an assumption.
  Source values and method are recorded in `configs/thermal_sources_v1.json`.

Manufacturer datasheet links, revisions and operating-policy interpretations
are attached to the individual model records. Geometry maxima, hardware limits,
model applicability, declared scenarios and measured accuracy have separate
meanings. Exact raw archives and local observation arrays are excluded from
this repository; reproduction requires the stated source revisions and access
allocations.

## V4 changes to the science

**Heat convention (`ecm_polarization_work/1`).** RC branches are fitted polarization terms, not physical capacitors. Their heat is the work `I*sum(v)` that Kirchhoff's voltage law assigns to them, which is PyBaMM's stated ECM convention. V3 used `v**2/R` with a held `v` and an `R` that changes with charge, which created heat with no electrical source and hid it in a compensating term. `tests/test_first_law.py` proves the new check fails on the V3 form.

**LG M50T low-charge table (`configs/cell_catalogue_v2.json`).** PyECN's branch 3 has `R = 1e-4` ohm and `C = 1e-4` F at or below 18% charge, then `tau = 350.1424873` s from 20%. V4 holds tau at that plateau in the 45 affected entries. The pattern looks like a switched-off branch, but no author statement confirms it, so this is an unvalidated low-charge modification, recorded with its parent hash in the catalogue's `revision` block. V1 stays unchanged.

**Measured comparison.** `configs/measured_comparison_v1.json` was committed before the first comparison ran. All 12 first cases missed their bands. `reports/measured_comparison_v1/post_hoc_diagnostic.json` is a labelled follow-up written after seeing that result. It changed no model value.
