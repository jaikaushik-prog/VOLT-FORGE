# Bounded thermal feasibility procedure

Declared 26 October 2026, before the synthetic demonstration. No parameter fitting
or new experimental record analysis is authorized by this procedure.

1. Read the frozen electrical loss accounting, current readiness/product vision,
   latest P45B reference/origin decision and protected source allocation. Audit
   exact LG INR21700-M50T primary literature and public dataset metadata. Do not
   download or inspect numerical outcomes from a new thermal dataset.
2. Separate whole-body heat capacity C_th (J/K), body-to-environment conductance
   H (W/K), internal heat input (W), initial temperature and ambient boundary.
   An internal base-to-cap cooling coefficient cannot substitute for H. Do not
   transfer M50, M50LT or P45B properties to M50T.
3. Implement only the standalone one-node balance
   `C_th*dT/dt = prescribed_heat_W - H*(T - ambient_degC)`. The prescribed heat
   is signed, positive into the node, and excludes the H exchange already
   represented. Require every parameter explicitly; accept synthetic-labelled
   configurations only. Reject electrical model references, automatic coupling,
   unknown fields, missing parameters, nonfinite values and unsupported domains.
4. Use an exact constant-input solution on every contiguous profile interval.
   Retain all changes in ambient/heat and continuous temperature. Compute signed
   source energy, signed outward boundary energy and stored energy independently
   from their analytic expressions. H=0 is an exact supported limit. Output dt
   controls reporting density, not the integration accuracy of this model.
5. Before the demonstration, test analytic heating/cooling, zero input, H=0,
   small-H limit, exact transition continuity, energy conservation, independent
   numerical quadrature, invalid inputs and output-grid invariance. Demonstrate
   that scaling unknown C_th, H and heat by the same factor leaves temperature
   unchanged: temperature alone cannot identify all three.
6. Run the single predeclared synthetic profile with output intervals of 10 and
   2.5 seconds. Include every event boundary. Publish a temperature/heat/energy
   plot, machine-readable series, summary and SHA-256 manifest. Inspect the
   plot. Preserve the input/procedure/source/test hashes in that manifest.
7. Report the feasible mathematics separately from physical applicability.
   Name the minimum exact-part, preparation, heat-input, sensor and cooling
   evidence needed to identify parameters. Stop at an explicit evidence gap;
   do not compensate with arbitrary LG defaults or another fitting search.

The numbers in the synthetic configuration (including C_th=100 J/K and
H=0.5 W/K) are chosen arithmetic examples, not literature estimates, priors,
calibration or specifications for any battery. No module temperatures, hottest
points, thermal runaway, safety margins or battery-performance gains are claimed.
The prototype neither reads module output nor changes the LG editor/backend.

All nine unused LG cells, 48 P45B members / 40 families, 13 FreeTwinEV records,
frozen module outcomes and previous artifacts remain unopened/unchanged. Public
M50T thermal archive metadata is a lead for a future prospective allocation;
its numerical files remain unopened in this sprint.
