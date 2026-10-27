import {escapeHTML as h} from './state.mjs';
export const PALETTES = {temperature:['#fff5eb','#fdd0a2','#fd8d3c','#d94801','#7f2704'], current:['#f7fbff','#c6dbef','#6baed6','#2171b5','#08306b']};
export const NEUTRAL = '#d9e2eb';
const rgb = hex => [1,3,5].map(i => parseInt(hex.slice(i, i+2), 16));
const hex2 = v => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0');
export function colorFor(value, lo, hi, kind) {
  const stops = PALETTES[kind];
  if (!stops || !Number.isFinite(value) || !Number.isFinite(lo) || !Number.isFinite(hi)) return NEUTRAL;
  const t = hi > lo ? Math.max(0, Math.min(1, (value - lo) / (hi - lo))) : 0.5;
  const x = t * (stops.length - 1), i = Math.min(Math.floor(x), stops.length - 2), f = x - i;
  const a = rgb(stops[i]), b = rgb(stops[i+1]);
  return '#' + a.map((c, k) => hex2(c + (b[k] - c) * f)).join('');
}
export function textColorFor(hex) {
  const luminance = value => {
    const [r,g,b]=rgb(value).map(v=>v/255).map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4);
    return 0.2126*r+0.7152*g+0.0722*b;
  };
  const background=luminance(hex);
  if((background+0.05)/(luminance('#111111')+0.05)>=4.5) return '#111111';
  if(1.05/(background+0.05)>=4.5) return '#ffffff';
  return '#000000'; // The narrow middle range needs pure black to retain 4.5:1 contrast.
}

// Display only. Output is SVG for <svg id="canvas" viewBox="0 0 860 310">. The page CSP forbids
// inline styles and handlers, so only presentation attributes and class names are emitted.
export function assemblySVG({design, values = {}, overlay = 'none', unit = '', range = [0, 1], selected = '', time_s = null}) {
  const fmt = v => Number.isFinite(v) ? `${v.toFixed(2)} ${unit}`.trim() : '—';
  const colored = overlay === 'temperature' || overlay === 'current';
  const sel = id => selected === id ? ' selected' : '';

  const terminals = '<path d="M70 57 H220 M70 245 H220" stroke="#8a5a2b" stroke-width="4" fill="none"/>'
    + '<text class="asm-terminal" x="56" y="62">+</text><text class="asm-terminal" x="56" y="250">−</text>';

  let rails = '';
  for (const [prefix, y, name, labelY] of [['p', 52, 'Positive', 40], ['n', 240, 'Negative', 272]]) {
    for (let k = 1; k <= 3; k++) {
      const id = `rail_${prefix}_${k}`, x1 = 220 + (k - 1) * 165, x2 = x1 + 165;
      const mOhm = design.connections[id].resistance.value * 1000;
      const hitTop = Math.min(y - 5, labelY - 15), hitBottom = Math.max(y + 15, labelY + 5);
      rails += `<g class="asm-rail${sel(id)}" data-component="${id}" role="button" tabindex="0" aria-label="${h(`${name} rail ${k}, ${mOhm.toFixed(2)} milliohms`)}">`
        + `<rect class="asm-hit" x="${x1}" y="${hitTop}" width="165" height="${hitBottom-hitTop}" fill="transparent" pointer-events="all"/>`
        + `<rect class="asm-bar" x="${x1}" y="${y}" width="165" height="10" fill="#c58b54" stroke="#8a5a2b"/>`
        + `<text class="asm-label" x="${(x1 + x2) / 2}" y="${labelY}" text-anchor="middle">${h(mOhm.toFixed(2))} mΩ</text></g>`;
    }
  }

  let cells = '';
  for (let k = 1; k <= 4; k++) {
    const id = `cell_${k}`, cx = 220 + (k - 1) * 165, identity = design.cells[id].identity;
    const fill = colored ? colorFor(values[id], range[0], range[1], overlay) : '#ffffff', ink = textColorFor(fill);
    const reading = fmt(values[id]), spoken = Number.isFinite(values[id]) ? `${reading} simulated` : 'no value';
    cells += `<g class="asm-cell${sel(id)}" data-component="${id}" role="button" tabindex="0" aria-label="${h(`Cell ${k}, ${identity}, ${spoken}`)}">`
      + `<rect class="asm-body" x="${cx - 44}" y="78" width="88" height="150" fill="${fill}" stroke="#7a8a9a"/>`
      + `<ellipse cx="${cx}" cy="228" rx="44" ry="14" fill="${fill}" stroke="#7a8a9a"/>`
      + `<ellipse cx="${cx}" cy="78" rx="44" ry="14" fill="${fill}" stroke="#7a8a9a"/>`
      + `<ellipse cx="${cx}" cy="70" rx="14" ry="5" fill="#b8c2cc" stroke="#7a8a9a"/>`
      + `<text class="asm-id" x="${cx}" y="128" text-anchor="middle" fill="${ink}">${h(identity)}</text>`
      + `<text class="asm-pos" x="${cx}" y="148" text-anchor="middle" fill="${ink}">${h(`Cell ${k}`)}</text>`
      + `<text class="asm-val" x="${cx}" y="172" text-anchor="middle" fill="${ink}">${h(reading)}</text></g>`;
  }

  // Legend and time readout belong to a coloured overlay; overlay 'none' draws neither.
  let legend = '', time = '';
  if (colored) {
    legend = PALETTES[overlay].map((c, i) => `<rect class="asm-swatch" x="${640 + i * 28}" y="276" width="28" height="12" fill="${c}" stroke="#7a8a9a"/>`).join('')
      + `<text class="asm-legend-text" x="640" y="300">${h(fmt(range[0]))}</text>`
      + `<text class="asm-legend-text" x="780" y="300" text-anchor="end">${h(fmt(range[1]))}</text>`
      + `<text class="asm-legend-text" x="840" y="270" text-anchor="end">${h(overlay === 'temperature' ? 'Simulated · fixed run range' : 'Simulated · branch current')}</text>`;
    if (Number.isFinite(time_s)) time = `<text class="asm-label" x="16" y="24">${h(`t = ${time_s.toFixed(1)} s`)}</text>`;
  }
  return terminals + rails + cells + legend + time;
}
