# VOLT-FORGE interface system

Direction approved through Shubhra's detailed critique and the supplied product vision: clean, professional, canvas-first and understandable to a new judge. Surface mode: Operate.

## Composition

The first screen has two explicit design actions and an AI entry. No settings, historical result or technical evidence table is open by default. A project has Build, Test and Results navigation. The canvas dominates Build. A single contextual panel shows either selection properties or the copilot. The physical drawing and electrical view share the same component/terminal graph.

The test form begins with direction, current, duration in minutes and room temperature. Changing-load intervals, targets, solver options and heat-transfer parameters are progressively disclosed. Results show three useful quantities, one interactive chart and short calculated findings. What-if and comparison are deliberate next actions.

## Tokens

- Ground: `#f6f8fa`; paper: `#ffffff`.
- Foreground: `#213247`; secondary: `#596b80`.
- Border: `#dfe6ee`; secondary surface: `#edf2f7`.
- Action blue: `#2458c5`; pressed blue: `#1948a8`; blue surface: `#edf3ff`.
- Copper: `#b57a42`; positive status: `#267260`.
- Series colors: blue `#3467b8`, copper `#ad7440`, green `#3c8877`, violet `#8976ad`.
- System UI sans for operating controls and explanatory text. Normal text 14 px, contextual text 12–13 px, page headings 22–32 px. Numeric displays use tabular numerals.
- Input/button radius 8 px; panel/content radius 12 px. Borders establish hierarchy. Shadows appear only on temporary surfaces and the copilot proposal composer.
- Header 66 px on desktop, 59 px on small screens. Properties/copilot width 340 px, 310 px at narrower laptop sizes. On phones it becomes a dismissible side sheet.

## Rules

- Use Cell 1, a user-assigned design name and readable experiment descriptions. Internal IDs never serve as ordinary labels.
- A visible number comes from a saved input, a traceable model value or a solver result. Do not place decorative engineering metrics.
- Explain the purpose of a property directly beneath its control. Give the selected cell a thumbnail and a clear canvas highlight.
- Show edits and their consequence through the object, not a dropdown of backend property names.
- Keep provenance and scientific detail accessible through meaningful text, definitions and downloads. Do not dump JSON into the product.
- AI edits are previewed and validated before application. A template alternative preserves the source design.
- Chart probes display saved samples. Keyboard time control and legend toggles provide alternatives to pointing.
- Preserve a quiet default state. Do not solve a confusing form by placing a large permanent instructions banner above it.
- Respect reduced motion, visible focus, accessible names, adequate contrast and page overflow at small sizes.

## References and skills

The product vision PDF and Markdown supplied by Shubhra are the product authority. The existing screenshots are an anti-reference for information overload and backend terminology. The installed Impeccable and frontend-design skills informed restraint, progressive disclosure, copy, focus states and visual inspection. The build is code-led and verified in a real browser; no unimplemented generated mockup is represented as the app.
