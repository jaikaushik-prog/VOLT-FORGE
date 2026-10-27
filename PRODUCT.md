# VOLT-FORGE

A visual workspace that connects a battery design change to its electrical and thermal consequences.

The first audience is a competition judge using the application for the first time. The product must also let a technically informed user inspect inputs, evidence and calculations. The default experience must remain understandable without reading model documentation.

Current product direction, 27 October 2026:

- A quiet start with an example, a new design and a natural-language entry to the AI copilot.
- Build, Test and Results as the main task sequence. Contextual properties appear on selection.
- Editable cells, terminal connections and output placement. Series, parallel and mixed circuits use the graph actually drawn.
- A measured-data cell library, initially four LG M50T sample profiles. Additional instances reuse those profiles.
- Configurable current waveforms, duration, environment, starting states, requirements and explicit thermal contacts.
- Interactive sampled-data charts, linked assembly values, calculated insights, controlled comparisons and reproducible exports.
- A real locally authenticated AI provider. The AI explains supplied context and proposes typed edits; the engineer reviews and applies them.
- Calibration, physical validation and numerical verification remain separate scientific tasks. See SCIENCE_AND_VALIDATION_PLAN.md.

The present assembly is an editable illustrative physical view synchronized with an electrical graph. It is not a solid-model CAD kernel or a manufacturing geometry export. No feature should imply that visual placement automatically creates an electrical or thermal contact.

Preserve all previous project records and frozen scientific artifacts. New studio documents are stored additively beside them. Do not replace source data or reserved outcomes with a new fixture to make the demo appear successful.
