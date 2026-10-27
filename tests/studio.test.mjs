import test from 'node:test';
import assert from 'node:assert/strict';
import {addCell,connect,removePart,History,samePhysics,esc} from '../web/editor/studio-state.mjs';
import {chartSvg,nearestIndex,pointValues,probeSvg} from '../web/editor/studio-charts.mjs';
const blank=()=>({name:'My design',cells:[],connections:[],output:{positive:null,negative:null},thermal:{contacts:[]}});
test('Cell insertion, real terminal edges, removal and undo preserve graph meaning',()=>{
 const g=blank(),h=new History();addCell(g);addCell(g,'P17');h.push(g);
 connect(g,'cell1:p','cell2:p');connect(g,'cell1:n','cell2:n');assert.equal(g.connections.length,2);
 assert.throws(()=>connect(g,'cell2:p','cell1:p'),/already/);
 assert.throws(()=>connect(g,'cell1:p','cell1:p'),/different/);
 removePart(g,'cell1');assert.equal(g.connections.length,0);assert.equal(g.output.positive,null);
 const old=h.back(g);assert.equal(old.cells.length,2);assert.equal(old.output.positive,'cell1:p');
});
test('Geometry and names are separate from electrical changes',()=>{
 const a=blank();addCell(a);const b=structuredClone(a);b.cells[0].x=800;b.cells[0].name='Main cell';b.name='Renamed';assert.ok(samePhysics(a,b));b.cells[0].charge_pct=60;assert.ok(!samePhysics(a,b));
});
test('Probe chooses nearest saved sample, including ends and unequal spacing',()=>{
 const rows=[0,.5,1.3,2.1,5].map(time_s=>({time_s}));assert.equal(nearestIndex(rows,-4),0);assert.equal(nearestIndex(rows,1.2),2);assert.equal(nearestIndex(rows,4.9),4);
});
test('Long 16-cell trajectories render without spreading an array into function arguments',()=>{
 const test={graph:{cells:Array.from({length:16},(_,i)=>({name:'Cell '+i}))},rows:Array.from({length:12000},(_,j)=>({time_s:j*.5,cell_current_A:Array.from({length:16},(_,i)=>i===4&&j===6017?120:3+i*.1)}))};
 const html=chartSvg(test,'current',6017);assert.match(html,/data-max="/);assert.match(html,/result-chart/);assert.ok(html.length<2_000_000);assert.ok(!html.includes('NaN'));
 assert.match(probeSvg(test,'current',6017,new Set(),0,150,6000),/circle/);
});
test('Tooltips escape cell names and display the real chosen data point',()=>{
 const test={graph:{cells:[{name:'<img onerror=alert(1)>'}]},rows:[{time_s:10,cell_current_A:[2.123]}]};const html=pointValues(test,'current',0);assert.ok(!html.includes('<img'));assert.match(html,/2.12/);assert.equal(esc('A&B'),'A&amp;B');
});
