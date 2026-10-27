import {test} from 'node:test';
import assert from 'node:assert/strict';
import {PALETTES, NEUTRAL, colorFor, textColorFor, assemblySVG} from '../web/editor/assembly.mjs';

// Every expected colour below is written out from the specification's hex stops and worked by hand.
// None of them is produced by calling colorFor or textColorFor.
const TEMPERATURE = ['#fff5eb', '#fdd0a2', '#fd8d3c', '#d94801', '#7f2704'];
const CURRENT = ['#f7fbff', '#c6dbef', '#6baed6', '#2171b5', '#08306b'];

function fakeDesign(identities = ['P7', 'P17', 'P19', 'P13']) {
  const cells = {}, connections = {};
  identities.forEach((identity, i) => { cells[`cell_${i + 1}`] = {identity}; });
  for (const rail of ['p', 'n']) for (let k = 1; k <= 3; k++) connections[`rail_${rail}_${k}`] = {resistance: {value: 0.001}};
  return {cells, connections};
}
const VALUES = {cell_1: 24, cell_2: 25, cell_3: 26, cell_4: 27};
const render = (extra = {}) => assemblySVG({design: fakeDesign(), values: VALUES, overlay: 'temperature', unit: '°C', range: [23, 27], selected: 'cell_3', time_s: 12.5, ...extra});
const count = (text, needle) => text.split(needle).length - 1;

// One entry per component <g>: classes, id, aria-label and the markup inside it.
function components(svg) {
  const found = [...svg.matchAll(/<g class="([^"]*)" data-component="([^"]+)" role="button" tabindex="0" aria-label="([^"]*)">(.*?)<\/g>/g)];
  return Object.fromEntries(found.map(([, classes, id, label, inner]) => [id, {classes: classes.split(' '), label, inner}]));
}
const bodyFill = inner => inner.match(/<rect class="asm-body"[^>]* fill="([^"]+)"/)[1];
const capFills = inner => [...inner.matchAll(/<ellipse [^>]*rx="44"[^>]* fill="([^"]+)"/g)].map(m => m[1]);
const inkOf = inner => inner.match(/<text class="asm-id"[^>]* fill="([^"]+)"/)[1];

test('colorFor hits the palette stops, blends channels as worked by hand, and falls back to neutral', () => {
  assert.deepEqual(PALETTES, {temperature: TEMPERATURE, current: CURRENT});
  assert.equal(NEUTRAL, '#d9e2eb');

  // Endpoints are the first and last stop of each palette.
  assert.equal(colorFor(23, 23, 27, 'temperature'), '#fff5eb');
  assert.equal(colorFor(27, 23, 27, 'temperature'), '#7f2704');
  assert.equal(colorFor(0, 0, 10, 'current'), '#f7fbff');
  assert.equal(colorFor(10, 0, 10, 'current'), '#08306b');
  // Values outside the range clamp to the end stops.
  assert.equal(colorFor(-100, 23, 27, 'temperature'), '#fff5eb');
  assert.equal(colorFor(1e9, 23, 27, 'temperature'), '#7f2704');
  // Midpoint (t = 0.5) is exactly the middle stop; t = 0.25 and 0.75 are exactly stops 1 and 3.
  assert.equal(colorFor(25, 23, 27, 'temperature'), '#fd8d3c');
  assert.equal(colorFor(5, 0, 10, 'current'), '#6baed6');
  assert.equal(colorFor(24, 23, 27, 'temperature'), '#fdd0a2');
  assert.equal(colorFor(26, 23, 27, 'temperature'), '#d94801');

  // t = 0.125 is halfway between stop 0 (#fff5eb) and stop 1 (#fdd0a2). Work each channel out here:
  const red = (0xff + 0xfd) / 2;            // (255 + 253) / 2 = 254
  const green = (0xf5 + 0xd0) / 2;          // (245 + 208) / 2 = 226.5, rounds half up to 227
  const blue = (0xeb + 0xa2) / 2;           // (235 + 162) / 2 = 198.5, rounds half up to 199
  assert.deepEqual([red, Math.round(green), Math.round(blue)], [254, 227, 199]);
  const byHand = '#' + [red, Math.round(green), Math.round(blue)].map(c => c.toString(16).padStart(2, '0')).join('');
  assert.equal(byHand, '#fee3c7');
  assert.equal(colorFor(0.125, 0, 1, 'temperature'), byHand);
  // Same halfway rule on the current palette: stop 1 #c6dbef (198,219,239) and stop 2 #6baed6 (107,174,214)
  // average to (152.5, 196.5, 226.5), which rounds half up to (153, 197, 227) = #99c5e3.
  assert.equal(colorFor(3, 0, 8, 'current'), '#99c5e3');
  // A non-half fraction: t = 0.4 is 60% of the way from stop 1 (253,208,162) to stop 2 (253,141,60).
  // Red stays 253; green is 208 - 0.6 * 67 = 167.8 -> 168 (0xa8); blue is 162 - 0.6 * 102 = 100.8 -> 101 (0x65).
  assert.equal(colorFor(0.4, 0, 1, 'temperature'), '#fda865');
  // Output is always lowercase #rrggbb.
  for (const kind of ['temperature', 'current']) for (let i = 0; i <= 40; i++) assert.match(colorFor(i, 0, 40, kind), /^#[0-9a-f]{6}$/);

  // Anything that is not a finite number, or an unknown palette, is the neutral colour.
  for (const value of [NaN, undefined, null, Infinity, -Infinity, '25']) assert.equal(colorFor(value, 23, 27, 'temperature'), '#d9e2eb');
  assert.equal(colorFor(25, NaN, 27, 'temperature'), '#d9e2eb');
  assert.equal(colorFor(25, 23, Infinity, 'temperature'), '#d9e2eb');
  assert.equal(colorFor(25, undefined, 27, 'temperature'), '#d9e2eb');
  assert.equal(colorFor(25, 23, 27, 'voltage'), '#d9e2eb');

  // A degenerate range (hi <= lo) uses the t = 0.5 colour.
  assert.equal(colorFor(5, 5, 5, 'temperature'), '#fd8d3c');
  assert.equal(colorFor(9, 10, 2, 'temperature'), '#fd8d3c');
  assert.equal(colorFor(5, 5, 5, 'current'), '#6baed6');
});

test('textColorFor picks dark ink on light fills and white ink on dark fills', () => {
  assert.equal(textColorFor('#ffffff'), '#111111');
  assert.equal(textColorFor('#08306b'), '#ffffff');
  // WCAG relative luminance uses linearized sRGB channels; white/near-black can both miss 4.5:1 in the middle range.
  assert.equal(textColorFor('#000000'), '#ffffff');       // 0
  assert.equal(textColorFor('#fd8d3c'), '#111111');       // 0.2126*0.992 + 0.7152*0.553 + 0.0722*0.235 = 0.623
  assert.equal(textColorFor('#d94801'), '#000000');       // relative luminance about 0.194; black contrast about 4.89:1
  assert.equal(textColorFor('#d9e2eb'), '#111111');       // the neutral fill is light: 0.88
});

test('assemblySVG draws four selectable cells and six rail segments with hand-derived colours and legend', () => {
  const svg = render();
  assert.equal(count(svg, 'class="asm-cell'), 4);
  assert.equal(count(svg, 'class="asm-rail'), 6);

  const parts = components(svg);
  assert.deepEqual(Object.keys(parts), ['rail_p_1', 'rail_p_2', 'rail_p_3', 'rail_n_1', 'rail_n_2', 'rail_n_3', 'cell_1', 'cell_2', 'cell_3', 'cell_4']);
  // Only cell_3 is selected.
  assert.ok(parts.cell_3.classes.includes('selected'));
  assert.deepEqual(Object.keys(parts).filter(id => parts[id].classes.includes('selected')), ['cell_3']);
  assert.ok(Object.keys(parts).filter(id => id.startsWith('cell_')).every(id => parts[id].classes[0] === 'asm-cell'));
  assert.ok(Object.keys(parts).filter(id => id.startsWith('rail_')).every(id => parts[id].classes[0] === 'asm-rail'));
  // Selecting a rail selects only that rail.
  const railSelected = components(render({selected: 'rail_n_2'}));
  assert.deepEqual(Object.keys(railSelected).filter(id => railSelected[id].classes.includes('selected')), ['rail_n_2']);

  // 24, 25, 26 and 27 over the range 23..27 land exactly on palette stops 1..4 (t = 0.25, 0.5, 0.75, 1).
  const fills = ['cell_1', 'cell_2', 'cell_3', 'cell_4'].map(id => bodyFill(parts[id].inner));
  assert.deepEqual(fills, ['#fdd0a2', '#fd8d3c', '#d94801', '#7f2704']);
  for (const [i, id] of ['cell_1', 'cell_2', 'cell_3', 'cell_4'].entries()) assert.deepEqual(capFills(parts[id].inner), [fills[i], fills[i]]);
  // The orange #d94801 needs pure black: white and near-black both fall short of 4.5:1.
  assert.deepEqual(['cell_1', 'cell_2', 'cell_3', 'cell_4'].map(id => inkOf(parts[id].inner)), ['#111111', '#111111', '#000000', '#ffffff']);

  // Text, labels and accessible names.
  assert.ok(svg.includes('26.00 °C'));
  assert.ok(svg.includes('1.00 mΩ'));
  assert.ok(svg.includes('t = 12.5 s'));
  assert.ok(svg.includes('Simulated'));
  assert.equal(parts.cell_3.label, 'Cell 3, P19, 26.00 °C simulated');
  assert.equal(parts.rail_p_1.label, 'Positive rail 1, 1.00 milliohms');
  assert.equal(parts.rail_n_3.label, 'Negative rail 3, 1.00 milliohms');
  assert.ok(parts.cell_1.inner.includes('>P7</text>') && parts.cell_1.inner.includes('>Cell 1</text>') && parts.cell_1.inner.includes('>24.00 °C</text>'));
  // Rail labels sit centred on each segment: above the positive bar (y 40) and below the negative bar (y 272).
  assert.deepEqual([...svg.matchAll(/<text class="asm-label" x="([\d.]+)" y="(\d+)"[^>]*>1\.00 mΩ<\/text>/g)].map(m => [+m[1], +m[2]]),
    [[302.5, 40], [467.5, 40], [632.5, 40], [302.5, 272], [467.5, 272], [632.5, 272]]);
  assert.match(svg, /<text class="asm-label" x="16" y="24">t = 12\.5 s<\/text>/);

  // Legend: five swatches in palette order, the two range ends with the unit, and the caption.
  const swatches = [...svg.matchAll(/<rect class="asm-swatch" x="(\d+)" y="276" width="28" height="12" fill="(#[0-9a-f]{6})"/g)].map(m => [+m[1], m[2]]);
  assert.deepEqual(swatches, [[640, '#fff5eb'], [668, '#fdd0a2'], [696, '#fd8d3c'], [724, '#d94801'], [752, '#7f2704']]);
  assert.deepEqual([...svg.matchAll(/<text class="asm-legend-text"[^>]*>([^<]*)<\/text>/g)].map(m => m[1]), ['23.00 °C', '27.00 °C', 'Simulated · fixed run range']);
  // The caption is right-aligned at x 840 (inside the legend box). Left-aligned at x 790 it would run past the 860 edge.
  assert.ok(svg.includes('<text class="asm-legend-text" x="840" y="270" text-anchor="end">Simulated · fixed run range</text>'));

  // Current overlay: current palette, branch-current caption, unit A.
  const current = assemblySVG({design: fakeDesign(), values: {cell_1: 0, cell_2: 5}, overlay: 'current', unit: 'A', range: [0, 5]});
  assert.ok(current.includes('Simulated · branch current'));
  assert.ok(!current.includes('fixed run range'));
  assert.deepEqual([...current.matchAll(/<rect class="asm-swatch"[^>]* fill="(#[0-9a-f]{6})"/g)].map(m => m[1]), CURRENT);
  const currentParts = components(current);
  assert.equal(bodyFill(currentParts.cell_1.inner), '#f7fbff');
  assert.equal(bodyFill(currentParts.cell_2.inner), '#08306b');
  assert.ok(!current.includes('t = '));                      // no time_s supplied, so no time text

  // A missing value under a coloured overlay is neutral grey, shown as an em dash, and announced as "no value".
  const missing = components(assemblySVG({design: fakeDesign(), values: {cell_1: 24}, overlay: 'temperature', unit: '°C', range: [23, 27]}));
  assert.equal(bodyFill(missing.cell_2.inner), '#d9e2eb');
  assert.ok(missing.cell_2.inner.includes('>—</text>'));
  assert.equal(missing.cell_2.label, 'Cell 2, P17, no value');
  assert.equal(inkOf(missing.cell_2.inner), '#111111');

  // Nothing is drawn outside the 860 x 310 viewBox.
  for (const m of svg.matchAll(/<rect [^>]*x="([\d.]+)" y="(\d+)" width="(\d+)" height="(\d+)"/g)) {
    const [x, y, w, h] = m.slice(1).map(Number);
    assert.ok(x >= 0 && x + w <= 860 && y >= 0 && y + h <= 310, m[0]);
  }
  for (const m of svg.matchAll(/<ellipse cx="(\d+)" cy="(\d+)" rx="(\d+)" ry="(\d+)"/g)) {
    const [cx, cy, rx, ry] = m.slice(1).map(Number);
    assert.ok(cx - rx >= 0 && cx + rx <= 860 && cy - ry >= 0 && cy + ry <= 310, m[0]);
  }
});

test('markup in identities and units is escaped and can never appear raw', () => {
  const design = fakeDesign(['<script>alert(1)</script>', 'P"17\'', 'P19', 'P13']);
  const svg = assemblySVG({design, values: VALUES, overlay: 'temperature', unit: '<b>°C</b>', range: [23, 27], selected: 'cell_1'});
  assert.ok(svg.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
  assert.ok(!svg.includes('<script'));
  assert.ok(!svg.includes('</script>'));
  assert.ok(svg.includes('&lt;b&gt;'));
  assert.ok(!svg.includes('<b>'));
  assert.ok(!svg.includes('</b>'));
  // Quotes in an identity cannot end the aria-label attribute early.
  const label = svg.match(/data-component="cell_2" role="button" tabindex="0" aria-label="([^"]*)"/)[1];
  assert.equal(label, 'Cell 2, P&quot;17&#39;, 25.00 &lt;b&gt;°C&lt;/b&gt; simulated');
  assert.ok(components(svg).cell_1.label.startsWith('Cell 1, &lt;script&gt;'));
  // Every tag still parses as balanced angle brackets: no tag was opened by data.
  assert.equal(count(svg, '<'), count(svg, '>'));
});

test('output has no style attribute and no inline event handler attribute', () => {
  const outputs = [
    render(),
    render({selected: 'rail_p_2', overlay: 'current', unit: 'A', range: [0, 5]}),
    render({overlay: 'none'}),
    assemblySVG({design: fakeDesign()}),
  ];
  for (const svg of outputs) {
    assert.doesNotMatch(svg, /\sstyle\s*=/i);
    assert.doesNotMatch(svg, /\son[a-z]+\s*=/i);
    assert.doesNotMatch(svg, /<script|javascript:/i);
  }
  // Structural check on hostile data: after escaping, no tag carries a style or on* attribute name.
  const hostile = assemblySVG({design: fakeDesign(['x" onfocus="alert(1)', '<img src=x onerror=alert(1)>', 'P19', 'P13']), values: VALUES, overlay: 'temperature', unit: '" style="x', range: [23, 27]});
  for (const tag of hostile.match(/<[a-zA-Z][^>]*>/g)) {
    const names = [...tag.replace(/="[^"]*"/g, '=""').matchAll(/\s([^\s=\/>]+)=/g)].map(m => m[1].toLowerCase());
    assert.ok(names.every(name => name !== 'style' && !name.startsWith('on')), tag);
  }
});

test("overlay 'none' draws no legend, no time text and plain white cells", () => {
  const svg = render({overlay: 'none', unit: ''});          // values and time_s are supplied on purpose
  assert.ok(!svg.includes('Simulated'));
  assert.ok(!svg.includes('fixed run range'));
  assert.ok(!svg.includes('branch current'));
  assert.ok(!svg.includes('asm-legend-text'));
  assert.ok(!svg.includes('asm-swatch'));
  assert.ok(!svg.includes('t = '));
  assert.equal(count(svg, '<text class="asm-label"'), 6);   // the six rail labels only, no time readout
  const parts = components(svg);
  for (const id of ['cell_1', 'cell_2', 'cell_3', 'cell_4']) {
    assert.equal(bodyFill(parts[id].inner), '#ffffff');
    assert.deepEqual(capFills(parts[id].inner), ['#ffffff', '#ffffff']);
    assert.equal(inkOf(parts[id].inner), '#111111');          // white fill gets dark ink
    assert.ok(parts[id].inner.includes('stroke="#7a8a9a"'));  // grey outline so a white cell is visible
  }
  // With no unit the reading carries no trailing space; with no values it is an em dash.
  assert.ok(parts.cell_1.inner.includes('>24.00</text>'));
  assert.equal(parts.cell_3.label, 'Cell 3, P19, 26.00 simulated');
  const bare = components(assemblySVG({design: fakeDesign()}));
  assert.ok(bare.cell_1.inner.includes('>—</text>'));
  assert.equal(bare.cell_1.label, 'Cell 1, P7, no value');
  assert.equal(count(assemblySVG({design: fakeDesign()}), 'asm-legend-text'), 0);
});

// Independent WCAG contrast calculation covers interpolated colours, not only palette stops.
test('cell value text retains at least 4.5:1 contrast throughout both overlay scales',()=>{
  const relative=hex=>{
    const linear=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(c=>c<=.04045?c/12.92:((c+.055)/1.055)**2.4);
    return linear[0]*.2126+linear[1]*.7152+linear[2]*.0722;
  };
  for(const kind of ['current','temperature']) for(let value=0;value<=1000;value++){
    const bg=colorFor(value,0,1000,kind),fg=textColorFor(bg),a=relative(bg),b=relative(fg);
    assert.ok((Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=4.5,`${kind} ${bg} ${fg}`);
  }
});
