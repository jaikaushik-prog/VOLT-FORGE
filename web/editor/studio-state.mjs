export const clone = x => structuredClone(x);
export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const fmt = (n, digits=1) => Number.isFinite(n) ? new Intl.NumberFormat('en',{maximumFractionDigits:digits,minimumFractionDigits:digits}).format(n) : '—';
export function timeLabel(seconds) {
  if (seconds < 60) return `${fmt(seconds,seconds%1 ? 1 : 0)} s`;
  const minutes = Math.floor(seconds/60), rest = seconds%60;
  return rest ? `${minutes}:${String(Math.floor(rest)).padStart(2,'0')}` : `${minutes} min`;
}
export function nextId(items,prefix) { let i=1; while(items.some(x=>x.id===prefix+i)) i++;return prefix+i; }
export function addCell(graph,model='P7') {
  const id=nextId(graph.cells,'cell'), i=graph.cells.length;
  graph.cells.push({id,name:`Cell ${id.replace('cell','')}`,model,x:180+(i%4)*210,y:210+Math.floor(i/4)*260,charge_pct:70,temperature_C:23,polarization_V:0});
  if(graph.cells.length===1)graph.output={positive:id+':p',negative:id+':n'};
  return id;
}
export function removePart(graph,id) {
  if(graph.cells.some(c=>c.id===id)) {
    graph.cells=graph.cells.filter(c=>c.id!==id);
    graph.connections=graph.connections.filter(w=>![w.a.split(':')[0],w.b.split(':')[0]].includes(id));
    graph.thermal.contacts=graph.thermal.contacts.filter(c=>![c.a,c.b].includes(id));
    if(graph.thermal.cell_parameters)delete graph.thermal.cell_parameters[id];
    for(const pole of Object.keys(graph.output)) if(graph.output[pole]?.split(':')[0]===id)graph.output[pole]=null;
  } else graph.connections=graph.connections.filter(w=>w.id!==id);
}
export function connect(graph,a,b,resistance=1) {
  if(a===b) throw new Error('Choose a different terminal to finish the connection.');
  if(graph.connections.some(w=>[w.a,w.b].includes(a)&&[w.a,w.b].includes(b)))throw new Error('Those terminals are already connected.');
  const id=nextId(graph.connections,'wire');
  graph.connections.push({id,a,b,resistance_mohm:resistance,source:'User design assumption'});return id;
}
export function describeConnection(graph,wire) {
  const terminal=t=>{const [id,p]=t.split(':');return `${graph.cells.find(c=>c.id===id)?.name||'Cell'} ${p==='p'?'positive':'negative'}`;};
  return `${terminal(wire.a)} to ${terminal(wire.b)}`;
}
export function actualTestName(test) { return `${test.design_name} · ${test.name}`; }
export function samePhysics(a,b) {
  const clean=g=>{g=clone(g);delete g.name;g.cells.forEach(c=>{delete c.x;delete c.y;delete c.name;});return g;};
  return JSON.stringify(clean(a))===JSON.stringify(clean(b));
}
export class History {
  constructor(){this.undo=[];this.redo=[];}
  push(value){this.undo.push(clone(value));if(this.undo.length>60)this.undo.shift();this.redo=[];}
  back(value){if(!this.undo.length)return null;this.redo.push(clone(value));return this.undo.pop();}
  forward(value){if(!this.redo.length)return null;this.undo.push(clone(value));return this.redo.pop();}
}
