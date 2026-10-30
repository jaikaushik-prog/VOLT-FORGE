import test from 'node:test';
import assert from 'node:assert/strict';
import {newSetup,missionRequest,presetEdits,applicationLine,verdictRows,costLabel,partsPanel,warningList,sizingTable,tradeoffRows,loadBlockModel,setupLoadFields} from '../web/editor/studio-mission.mjs';
import {renderCanvas} from '../web/editor/studio-canvas.mjs';
import {timeLabel,deltaLabel} from '../web/editor/studio-state.mjs';

const parts=(inr,extra={})=>({lines:[],subtotals:{INR:inr,USD:52},unpriced:[],cell_mass_g:140,listed_mass_g:142,scope:'Listed parts only.',checked:'2026-10-30',...extra});
const result=(over={})=>({graph:{cells:[{id:'cell1',name:'Cell 1'},{id:'cell2',name:'Cell 2'}]},settings:{profile:[{start_s:0,end_s:600,current_A:8.42}],limits:{min_voltage_V:3.3}},parts:parts(2412),summary:{metrics:{duration_s:600,minimum_voltage_V:3.53,peak_cell_current_A:4.38,busiest_cell:'cell1',peak_temperature_C:27.5,warmest_cell:'cell1',imbalance_pct:8},checks:[{metric:'min_voltage_V',status:'within_target'}],coverage:{requested_duration_s:600,complete:true},assessment:{requested_demand_met:true}},...over});

test('A preset sends only its name; custom loads send their values',()=>{
 assert.deepEqual(missionRequest(newSetup()),{test_type:'discharge',preset:'pi5_gateway_backup'});
 const r=missionRequest({...newSetup(),preset:'custom_watts',power:10,efficiency:80,floor:3.2,minutes:2});
 assert.equal(r.power_W,10);assert.equal(r.efficiency,.8);assert.equal(r.duration_s,120);assert.equal(r.voltage_floor_V,3.2);
 assert.equal(missionRequest({...newSetup(),test_type:'charge',preset:'custom_amps',current:2}).voltage_floor_V,null);
});
test('A changed preset value is written to settings and an unchanged one is left alone',()=>{
 const settings={profile:[{end_s:600}],limits:{min_voltage_V:3.3},ambient_C:23};
 assert.equal(presetEdits(newSetup(),settings),false);
 assert.equal(presetEdits({...newSetup(),minutes:15},settings),true);assert.equal(settings.profile[0].end_s,900);assert.equal(settings.limits.min_voltage_V,3.3);
});
test('Charging setup does not ask for a voltage floor',()=>{
 assert.ok(!setupLoadFields({...newSetup(),test_type:'charge',preset:'custom_amps'}).includes('setup-floor'));
 assert.ok(setupLoadFields(newSetup()).includes('setup-floor'));
});
test('Requirements show their basis and escape text',()=>{
 const html=applicationLine({name:'<b>Pi</b>',purpose:'x',requirements:[{label:'Run time',value:600,unit:'s',basis:'assumed',reason:'r'},{label:'Load',value:null,unit:'A',basis:'custom',reason:'r'}],approximation:null});
 assert.ok(html.includes('&lt;b&gt;Pi'));assert.ok(html.includes('10 min'));assert.ok(html.includes('basis-chip assumed'));assert.ok(html.includes('Varies'));
 assert.equal(applicationLine(null),'');
});
test('The verdict passes a full run and fails a stopped one',()=>{
 const full=verdictRows(result(),timeLabel);assert.ok(full.includes('Full'));assert.ok(full.includes('Target 3.30 V'));assert.ok(full.includes('4% above an even share'));assert.ok(!full.includes('verdict-mark fail'));
 const stopped=result();stopped.summary.coverage.complete=false;stopped.summary.metrics.duration_s=300;
 assert.ok(verdictRows(stopped,timeLabel).includes('verdict-mark fail'));
});
test('Charging tests lead with charge gained, not backup time',()=>{
 const t=result();t.summary.charging={charge_gained_Ah:.5,elapsed_s:600,stop_message:'The requested test time ended.'};
 const html=verdictRows(t,timeLabel);assert.ok(html.includes('0.50 Ah gained'));assert.ok(!html.includes('Backup time'));
});
test('Cost keeps currencies apart and shows unpriced parts',()=>{
 assert.equal(costLabel(parts(2412)),'₹2,412 + US$52.00'.replace('52.00','52'));
 assert.ok(costLabel(parts(10,{unpriced:['Converter']})).endsWith('+ unpriced parts'));
 const panel=partsPanel(parts(1206,{lines:[{part:'Battery protection',quantity:1,unit:'part',priced:false,note:'Included in the UPS board'}]}));
 assert.ok(panel.includes('Included in the UPS board'));
});
test('No warnings means no warning box',()=>{assert.equal(warningList([]),'');assert.ok(warningList([{message:'<x>'}]).includes('&lt;x&gt;'));});
test('Sizing separates outcomes and uses the qualified claim',()=>{
 const inv={complete:true,sizing:{claim:'Smallest qualifying design among the parallel arrangements tested',scope:'Nominal',smallest_cell_count:2},cases:[{cell_count:1,sizing:'refused',parts:parts(1206)},{cell_count:2,sizing:'qualifies',parts:parts(2412),summary:{metrics:{minimum_voltage_V:3.5,peak_cell_current_A:4.4,peak_temperature_C:27}}}]};
 const html=sizingTable(inv,false,i=>`<b>${i}</b>`);
 assert.ok(html.includes('Refused: over a cell limit'));assert.ok(html.includes('2 cells'));assert.ok(html.includes('among the parallel arrangements tested'));
});
test('Trade-offs lead with cost, mass and margin',()=>{
 const html=tradeoffRows(result(),result({graph:{cells:[1,2,3,4].map(i=>({id:'c'+i,name:'c'}))},parts:parts(4824,{cell_mass_g:280})}),deltaLabel);
 assert.ok(html.indexOf('Listed cost')<html.indexOf('Cell mass'));assert.ok(html.includes('Margin above voltage target'));assert.ok(!html.includes('Energy'));
});
test('The load block draws from settings and stays out of the circuit graph',()=>{
 const graph={cells:[{id:'cell1',name:'Cell 1',x:180,y:210,charge_pct:70,temperature_C:23,model:'x'}],connections:[],output:{positive:'cell1:p',negative:'cell1:n'}};
 const load=loadBlockModel({name:'Raspberry Pi 5 gateway backup'},{profile:[{end_s:600,current_A:8.4175}]});
 assert.equal(load.detail,'8.42 A · 10 min');
 const before=JSON.stringify(graph),svg=renderCanvas(graph,{load});
 assert.ok(svg.includes('load-block'));assert.ok(svg.includes('data-act="view:test"'));assert.equal(JSON.stringify(graph),before);
 assert.ok(!renderCanvas({...graph,output:{positive:null,negative:null}},{load}).includes('load-block'));
 assert.equal(loadBlockModel(null,{profile:[]}),null);
});
