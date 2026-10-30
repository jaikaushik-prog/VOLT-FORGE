import {esc,fmt,describeConnection} from './studio-state.mjs';

export const palette=['#3467b8','#ad7440','#3c8877','#8976ad'];
let cellLibrary={};
export function setCellLibrary(library){cellLibrary=Object.fromEntries(library.map(m=>[m.key,m]));}
export function terminalPoint(cell,pole,mode='assembly') {
  return {x:cell.x,y:cell.y+(pole==='p'?-99:99)};
}
export function wireGeometry(graph,wire){
  const point=t=>{const [id,pole]=t.split(':');return terminalPoint(graph.cells.find(c=>c.id===id),pole);};
  const a=point(wire.a),b=point(wire.b),same=wire.a.split(':')[1]===wire.b.split(':')[1];
  const y=(a.y+b.y)/2+(same?(wire.a.endsWith(':p')?-20:20):0);
  return {path:`M ${a.x} ${a.y} L ${a.x} ${y} L ${b.x} ${y} L ${b.x} ${b.y}`,x:(a.x+b.x)/2,y};
}
function gradientDefs(prefix) {
  return `<defs><linearGradient id="${prefix}-wrap" x1="0" x2="1"><stop offset="0" stop-color="#1a4a94"/><stop offset=".18" stop-color="#2d67a2"/><stop offset=".47" stop-color="#3c79b3"/><stop offset=".7" stop-color="#326bb4"/><stop offset="1" stop-color="#174789"/></linearGradient><linearGradient id="${prefix}-metal"><stop stop-color="#98a7b7"/><stop offset=".4" stop-color="#f1f5f8"/><stop offset=".7" stop-color="#bdc7d1"/><stop offset="1" stop-color="#8291a3"/></linearGradient><linearGradient id="${prefix}-copper" x2="0" y2="1"><stop stop-color="#e5ba83"/><stop offset=".5" stop-color="#bc874e"/><stop offset="1" stop-color="#9d6b39"/></linearGradient></defs>`;
}
export function cellImage({id='preview',selected=false,attention=false,name='',value=null,color=null,small=false,label='LG M50T'}={}) {
  const p=id.replace(/[^a-zA-Z0-9_-]/g,'');
  const wrapper=color||`url(#${p}-wrap)`;
  return `${gradientDefs(p)}<g class="battery-cylinder">
    <ellipse cx="0" cy="112" rx="62" ry="13" fill="#c9d3df" opacity=".28"/>
    ${selected||attention?`<rect x="-62" y="-119" width="124" height="239" rx="21" fill="${attention?'#fff1e9':'#e8f0ff'}" stroke="${attention?'#a74c2b':'#265ccc'}" stroke-width="2.2" stroke-dasharray="5 5"/>`:''}
    <path d="M-47 -85 L-47 82 C-47 103 47 103 47 82 L47 -85 Z" fill="${wrapper}" stroke="#214a80" stroke-width="1"/>
    <path d="M-36 -78 V78" stroke="#b4d9ff" stroke-width="3" opacity=".28"/>
    <ellipse cy="82" rx="47" ry="15" fill="${wrapper}" stroke="#2e537e"/>
    <ellipse cy="-85" rx="47" ry="16" fill="url(#${p}-metal)" stroke="#8896a7"/>
    <ellipse cy="-88" rx="34" ry="10" fill="#354659"/>
    <ellipse cy="-94" rx="25" ry="8" fill="url(#${p}-metal)" stroke="#8593a3"/>
    <path d="M-47 72 C-22 87 22 87 47 72" fill="none" stroke="#bfd8ef" opacity=".4"/>
    ${name?`<text x="0" y="-20" text-anchor="middle" fill="#fff" font-size="16" font-weight="650">${esc(name)}</text><text x="0" y="3" text-anchor="middle" fill="#fff" font-size="10" letter-spacing="1">${esc(label)}</text>`:''}
    ${value!==null?`<text x="0" y="38" text-anchor="middle" fill="#fff" font-size="17" font-weight="650">${esc(value)}</text>`:''}
    ${!small?'<text x="0" y="-109" text-anchor="middle" fill="#5b6a7d" font-size="14">+</text><text x="0" y="117" text-anchor="middle" fill="#5b6a7d" font-size="14">−</text>':''}
  </g>`;
}
export function thumbnail(cell) {
  return `<svg class="cell-thumbnail" viewBox="-70 -125 140 255" aria-label="${esc(cell.name)} selected">${cellImage({id:'thumbnail',name:'',small:true})}</svg>`;
}
export function renderCanvas(graph,{mode='assembly',selected=null,layer='none',row=null,tool='select',pending=null,prefix='main',alertCells=[],alertConnections=[],interactive=true,load=null}={}) {
  const loadX=Math.max(0,...graph.cells.map(c=>c.x))+215;
  const width=Math.max(1020,...graph.cells.map(c=>c.x+140),load?loadX+130:0),height=Math.max(500,...graph.cells.map(c=>c.y+180));
  const cells=Object.fromEntries(graph.cells.map(c=>[c.id,c]));
  const point=t=>{const [id,pole]=t.split(':');return terminalPoint(cells[id],pole,mode);};
  const wires=graph.connections.map(w=>{
    const a=point(w.a),b=point(w.b),same=w.a.split(':')[1]===w.b.split(':')[1];
    const y=same?(a.y+b.y)/2+(w.a.endsWith(':p')?-20:20):((a.y+b.y)/2);
    const path=`M ${a.x} ${a.y} L ${a.x} ${y} L ${b.x} ${y} L ${b.x} ${b.y}`;
    const chosen=selected===w.id;
    return `<g class="wire ${chosen?'selected':''} ${alertConnections.includes(w.id)?'limit-hit':''}" data-wire="${esc(w.id)}" role="${interactive?'button':'img'}" tabindex="${interactive?'0':'-1'}" aria-label="${esc(describeConnection(graph,w))}"><title>${esc(describeConnection(graph,w))}</title><path d="${path}" class="wire-hit"/><path d="${path}" class="${mode==='assembly'?'copper-link':'circuit-link'}" ${chosen?'stroke="#2458c5"':''}/>${mode==='circuit'?`<g transform="translate(${(a.x+b.x)/2} ${y})"><rect x="-29" y="-10" width="58" height="20" rx="4" fill="#f7f9fc" stroke="${chosen?'#2458c5':'#aab8c8'}"/><text text-anchor="middle" y="4" font-size="11" fill="#536379">${fmt(w.resistance_mohm,1)} mΩ</text></g>`:''}</g>`;
  }).join('');
  const bodies=graph.cells.map((c,i)=>{
    let val=null;
    if(row)val=layer==='temperature'?(row.temperature_C[i]===null?'Not modeled':`${fmt(row.temperature_C[i])} °C`):layer==='current'?`${fmt(row.cell_current_A[i],2)} A`:layer==='charge'?`${fmt(row.charge_pct[i],0)}%`:layer==='voltage'?`${fmt(row.cell_voltage_V[i],3)} V`:null;
    const selectedCell=selected===c.id;
    const body=mode==='assembly'?cellImage({id:prefix+'-'+c.id,selected:selectedCell,attention:alertCells.includes(c.id),name:c.name,value:val,label:cellLibrary[c.model]?.family||'Cell model'}):
      `<rect x="-66" y="-80" width="132" height="160" rx="12" fill="${selectedCell?'#eef4ff':'#fff'}" stroke="${selectedCell?'#2458c5':'#b9c8d9'}" stroke-width="${selectedCell?2.5:1.5}"/><path d="M0 -99 V-80 M0 80 V99" stroke="#788ca5" stroke-width="2"/><text x="0" y="-42" text-anchor="middle" font-weight="650" font-size="16" fill="#23364e">${esc(c.name)}</text><path d="M-16 -6 H16 M-8 6 H8" stroke="${palette[i%4]}" stroke-width="3"/><text x="0" y="47" text-anchor="middle" fill="#536379" font-size="12">${val||`${fmt(c.charge_pct,0)}% to start`}</text>`;
    return `<g data-cell="${esc(c.id)}" class="canvas-cell ${selectedCell?'is-selected':''}" transform="translate(${c.x} ${c.y})" tabindex="${interactive?'0':'-1'}" role="${interactive?'button':'img'}" aria-label="${esc(c.name)}, ${fmt(c.charge_pct,0)} percent starting charge. ${alertCells.includes(c.id)?'Limit highlighted. ':''}${interactive?'Select to edit.':''}">${body}</g>`;
  }).join('');
  const handles=graph.cells.map(c=>['p','n'].map(p=>{
    const t=c.id+':'+p,{x,y}=point(t),output=Object.entries(graph.output).find(([k,v])=>v===t)?.[0];
    return `<g data-terminal="${t}" class="terminal ${pending===t?'pending':''}" tabindex="${interactive?'0':'-1'}" role="${interactive?'button':'img'}" aria-label="${esc(c.name)} ${p==='p'?'positive':'negative'} terminal${output?', battery '+output+' output':''}"><circle cx="${x}" cy="${y}" r="14" class="terminal-hit"/><circle cx="${x}" cy="${y}" r="${tool==='connect'||pending===t?7:5}" fill="${output?'#2458c5':'#fff'}" stroke="${output?'#2458c5':'#7489a3'}" stroke-width="2"/>${output?`<g transform="translate(${x+12} ${y-4})"><rect x="0" y="-10" width="29" height="18" rx="5" fill="#e8f0ff"/><text x="14" y="3" text-anchor="middle" font-size="10" fill="#2458c5" font-weight="650">${output==='positive'?'OUT+':'OUT−'}</text></g>`:''}</g>`;
  }).join('')).join('');
  const loadBlock=()=>{
    if(!load||!graph.output?.positive||!graph.output?.negative)return '';
    const a=point(graph.output.positive),b=point(graph.output.negative),mid=(a.y+b.y)/2,top=mid-46,bottom=mid+46;
    const wire=(p,edge,rail)=>`<path d="M ${p.x} ${p.y} V ${rail} H ${loadX} V ${edge}" class="load-wire"/>`;
    return `<g class="load-block" data-act="view:test" role="button" tabindex="${interactive?'0':'-1'}" aria-label="Load: ${esc(load.name)}, ${esc(load.detail)}. Open the test settings."><title>The load this design is tested against. It is not part of the circuit you wire.</title>${wire(a,top,a.y-34)}${wire(b,bottom,b.y+34)}<rect x="${loadX-122}" y="${top}" width="244" height="92" rx="12"/><text x="${loadX}" y="${mid-20}" text-anchor="middle" class="load-kind">${load.charging?'CHARGER':'LOAD'}</text><text x="${loadX}" y="${mid+2}" text-anchor="middle" class="load-name">${esc(load.name.length>32?load.name.slice(0,31)+'…':load.name)}</text><text x="${loadX}" y="${mid+24}" text-anchor="middle" class="load-detail">${esc(load.detail)}</text></g>`;
  };
  return `<svg id="battery-canvas" viewBox="0 0 ${width} ${height}" class="battery-canvas ${tool==='connect'?'connecting':''}" aria-label="Editable battery ${mode}" data-width="${width}" data-height="${height}">${wires}${bodies}${handles}${loadBlock()}</svg>`;
}
export function heroBattery() {
  const graph={cells:[0,1,2,3].map(i=>({id:'hero'+i,name:'',x:150+i*155,y:205,charge_pct:70,temperature_C:23})),connections:[],output:{}};
  return `<svg viewBox="0 0 800 400" role="img" aria-label="Four battery cells with copper connections" class="hero-battery"><ellipse cx="390" cy="325" rx="325" ry="22" fill="#dce5f0" opacity=".5"/>${graph.cells.map((c,i)=>`<g transform="translate(${c.x} ${c.y})">${cellImage({id:c.id,small:true})}</g>`).join('')}<path d="M150 106 H615" stroke="#8f6138" stroke-width="12"/><path d="M150 102 H615" stroke="#d1a26b" stroke-width="8"/><g fill="#f2d7b1" stroke="#9d754c">${graph.cells.map(c=>`<circle cx="${c.x}" cy="102" r="5"/>`).join('')}</g><path d="M150 298 H615" stroke="#ab7b47" stroke-width="9"/></svg>`;
}
