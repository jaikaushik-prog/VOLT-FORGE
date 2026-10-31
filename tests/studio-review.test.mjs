import test from 'node:test';
import assert from 'node:assert/strict';
import {numericDraft,flattenChanges,proposalRows,proposalPreview,contextModels,comparisonConditions,comparisonNotice,verdictContext,copilotAvailability,persistenceCopy,safeFileName,draftBackup,recoveryRequest} from '../web/editor/studio-review.mjs';
import {sampleLabel,sampleIndex,savedSampleTable} from '../web/editor/studio-charts.mjs';
import {actualTestName} from '../web/editor/studio-state.mjs';
import {renderCanvas,setCellLibrary} from '../web/editor/studio-canvas.mjs';
import {sizingDecisionRows,sizingDecision,cellCostLabel,verdictRows,partsPanel,missionRequest,newSetup,applicationLine} from '../web/editor/studio-mission.mjs';

test('Blank mandatory numbers and invalid unit text cannot become physical zero',()=>{
 for(const value of ['', '  ', 'abc','1 mΩ','NaN','Infinity','0x10'])assert.equal(numericDraft(value,{label:'Resistance',min:0}).ok,false,value);
 assert.deepEqual(numericDraft('0',{min:0}),{ok:true,value:0});
 assert.deepEqual(numericDraft(' 1.25e-3 ',{min:0}),{ok:true,value:.00125});
 assert.equal(numericDraft('-1',{min:0}).ok,false);
 assert.equal(numericDraft('0',{badInput:true,optional:true}).ok,false);
 assert.equal(numericDraft('201',{max:200}).ok,false);
});
test('Unknown optional targets remain null, distinct from an explicit zero',()=>{
 assert.deepEqual(numericDraft('',{optional:true,min:0}),{ok:true,value:null});
 assert.deepEqual(numericDraft('0',{optional:true,min:0}),{ok:true,value:0});
 assert.equal(numericDraft('no',{optional:true}).ok,false);
});
const graph={name:'Baseline',cells:[{id:'cell1',name:'Main cell',model:'old',charge_pct:70},{id:'cell2',name:'Far cell',model:'old',charge_pct:70}],connections:[{id:'wire1',a:'cell1:p',b:'cell2:p',resistance_mohm:1}],thermal:{contacts:[]}};
test('Full proposal preview expands added/removed dependent objects and interval arrays',()=>{
 const proposal={diff:[{path:'design.cells.cell2',before:{id:'cell2',name:'Far cell',model:'old',charge_pct:70},after:null},{path:'design.connections.wire1.resistance_mohm',before:1,after:0},{path:'settings.profile',before:[{start_s:0,end_s:600,current_A:8.4}],after:[{start_s:0,end_s:300,current_A:5},{start_s:300,end_s:600,current_A:0}]}],readiness:{ready:false,message:'Choose an output',warnings:[{message:'A link was removed'}]}};
 const rows=proposalRows(proposal,graph,[{key:'old',name:'Saved cell model'}]);
 assert.ok(rows.some(r=>r.path==='design.cells.cell2.charge_pct'&&r.beforeText==='70'&&r.afterText==='Absent'));
 assert.ok(rows.some(r=>r.label.includes('Main cell positive to Far cell positive')&&r.afterText==='0'));
 assert.ok(rows.some(r=>r.path==='settings.profile[1].end_s'&&r.afterText==='600'));
 assert.equal(rows.length,flattenChanges(proposal.diff).length);
 const html=proposalPreview(proposal,graph,[]);assert.ok(html.includes('Choose an output'));assert.ok(html.includes('A link was removed'));assert.ok(html.includes('historical'));
});
test('Proposal values are escaped and missing exact diff cannot masquerade as reviewable',()=>{
 const p={diff:[{path:'design.name',before:'A',after:'<script>x</script>'}]};
 assert.ok(!proposalPreview(p,graph,[]).includes('<script>'));
 assert.ok(proposalPreview({changes:['Change everything']},graph,[]).includes('complete change preview is unavailable'));
});
test('Historical model details never fall back to the current catalog',()=>{
 const current={cells:[{model:'new'}]},catalog=[{key:'new',name:'Current model'},{key:'old',name:'Changed library model'}];
 const saved={graph,model_cards:{old:{key:'old',name:'Captured model'}}};
 assert.deepEqual(contextModels(current,catalog,saved).map(m=>m.name),['Captured model']);
 assert.equal(contextModels(current,catalog,{graph}).every(m=>m.missing),true);
 assert.deepEqual(contextModels(current,catalog).map(m=>m.name),['Current model']);
});
test('Historical canvas labels use captured model cards and do not inherit a changed library',()=>{
 setCellLibrary([{key:'old',family:'Current library family'}]);
 const g={cells:[{id:'cell1',name:'One',model:'old',x:180,y:210,charge_pct:70}],connections:[],output:{positive:'cell1:p',negative:'cell1:n'}};
 const saved=renderCanvas(g,{models:{old:{family:'Captured family'}}});assert.ok(saved.includes('Captured family'));assert.ok(!saved.includes('Current library family'));
 assert.ok(!renderCanvas(g,{models:{}}).includes('Current library family'));
});
const completed=()=>({summary:{coverage:{complete:true},assessment:{requested_demand_met:true}},settings:{limits:{temperature_C:null,current_A:null,min_voltage_V:3.3,imbalance_pct:null}}});
test('Equal settings do not hide model, requirement, preparation or partial-run mismatches',()=>{
 const c={identical_test_conditions:true,comparable_duration:true,model_versions_match:false,solver_versions_match:true,requirements_match:false,design_changes:[{path:'cells.cell1.charge_pct'}],tests:[completed(),completed()]};
 let flags=comparisonConditions(c);assert.ok(flags.some(f=>f.label.startsWith('Model')&&!f.match));assert.ok(flags.some(f=>f.label.startsWith('Requirements')&&!f.match));assert.ok(flags.some(f=>f.label.startsWith('Cell preparation changed')&&!f.match));
 c.tests[1].summary.coverage.complete=false;flags=comparisonConditions(c);assert.equal(flags.at(-1).match,false);
 assert.ok(comparisonNotice(c).includes('more than one cause'));
});
test('Absent and incomplete operating-limit coverage stay explicit, even on a completed run',()=>{
 const t=completed();assert.ok(verdictContext(t).includes('not recorded'));assert.ok(verdictContext(t).includes('3 not set'));
 t.summary.operating_limit_coverage={complete:false};assert.ok(verdictContext(t).includes('unknown'));
 t.summary.operating_limit_coverage={complete:true};assert.ok(!verdictContext(t).includes('unknown'));
 assert.ok(verdictContext(t).includes('Hardware acceptance'));
});
test('AI configuration does not assert a verified connection',()=>{
 assert.equal(copilotAvailability({copilot:{available:false}}).available,false);
 const configured=copilotAvailability({copilot:{available:true,provider:'Example',connection_verified:false}});
 assert.ok(configured.label.includes('unverified'));
 assert.ok(copilotAvailability({copilot:{available:true,provider:'Example',connection_verified:true}}).label.includes('verified'));
});
test('Local, temporary and unreported persistence have different promises',()=>{
 assert.equal(persistenceCopy({persistence:'browser_session'}).temporary,true);
 assert.ok(persistenceCopy({persistence:'browser_session'}).description.includes('before closing'));
 assert.equal(persistenceCopy({persistence:'local_workspace'}).saved,'Saved');
 assert.ok(persistenceCopy().description.includes('not been reported'));
});
const rows=[{time_s:0,cell_current_A:[2,2]},{time_s:60,event_side:'before',event_kind:'load_change',cell_current_A:[2.123456789,2]},{time_s:60,event_side:'after',event_kind:'load_change',cell_current_A:[4.5,4]},{time_s:90,event_side:'before',event_kind:'protective_disconnect',cell_current_A:[4.5,4]},{time_s:90,event_side:'after',event_kind:'protective_disconnect',cell_current_A:[0,0]},{time_s:100,cell_current_A:[0,0]}];
test('Keyboard sample navigation reaches both saved event sides without interpolation',()=>{
 assert.equal(sampleIndex(rows,0,1,true),1);assert.equal(sampleIndex(rows,1,1),2);assert.equal(sampleIndex(rows,2,-1),1);
 assert.equal(sampleIndex(rows,4,1,true),4);assert.equal(sampleIndex(rows,0,-1),0);
 assert.notEqual(sampleLabel(rows[1]),sampleLabel(rows[2]));assert.ok(sampleLabel(rows[4]).includes('after protection disconnect'));
 const html=savedSampleTable({graph,rows},'current',1);assert.ok(html.includes('2.123456789'));assert.ok(html.includes('before load change'));assert.ok(html.includes('aria-live="polite"'));
});
test('Saved probe renders unavailable values as unavailable and escapes cell names',()=>{
 const html=savedSampleTable({graph:{cells:[{name:'<b>cell</b>'}]},rows:[{time_s:0,temperature_C:[null]}]},'temperature',0);
 assert.ok(html.includes('Not modeled'));assert.ok(!html.includes('<b>cell</b>'));
});
test('Run names disambiguate repeated runs and their historical state',()=>{
 const t={design_name:'Pi',name:'10 min',created_utc:'2026-10-31T10:00:00.123456+00:00',current:false};
 assert.notEqual(actualTestName(t),actualTestName({...t,created_utc:'2026-10-31T10:00:00.123457+00:00'}));assert.ok(actualTestName(t).includes('earlier version'));assert.ok(actualTestName(t).includes('UTC'));
});
test('Recovery export and import make a detached new design, never impersonating workspace lineage',()=>{
 const backup=draftBackup({id:'same-id',version:1},graph,{profile:[],limits:{}},[{value:'',label:'Resistance'}]);
 const request=recoveryRequest(backup);assert.equal(request.source_design_id,undefined);assert.equal(request.source_version,undefined);assert.equal(request.name,'Baseline recovered copy');
 request.graph.cells[0].charge_pct=50;assert.equal(graph.cells[0].charge_pct,70);assert.equal(backup.graph.cells[0].charge_pct,70);
 assert.equal(request.unfinished_fields,undefined);assert.throws(()=>recoveryRequest({rows:[]}),/design backup/);
 assert.ok(!safeFileName('../Pi: one/two').includes('/'));
 const long=draftBackup({id:'old',version:1},{...graph,name:'A'.repeat(100)},{profile:[],limits:{}});
 const recovered=recoveryRequest(long);assert.equal(recovered.name.length,100);assert.ok(recovered.name.endsWith(' recovered copy'));assert.equal(long.name.length,100);
});
test('Three-option summary keeps the existing case indices and does not fabricate missing runs or cell costs',()=>{
 const inv={graph:{cells:[1,2,3,4]},cases:[{cell_count:1,sizing:'refused'},{cell_count:2,sizing:'incomplete',summary:{metrics:{minimum_voltage_V:3.6}},parts:{cell_subtotals:{INR:20},cell_cost_complete:false}}]};
 assert.deepEqual(sizingDecisionRows(inv).map(x=>[x.count,x.index]),[[4,-1],[3,-1],[2,1]]);
 const html=sizingDecision(inv,false,index=>`Open case ${index}`);assert.ok(html.includes('Not calculated yet'));assert.ok(html.includes('Open case 1'));assert.ok(html.includes('unpriced cells'));assert.ok(html.includes('excludes boards'));
 assert.equal(cellCostLabel({subtotals:{INR:20}}),'Not recorded');
});
test('Charging quantity distinguishes current pack-terminal accounting from historical summed-cell Ah',()=>{
 const t={graph:{cells:[{id:'cell1',name:'One'}]},settings:{profile:[{current_A:-1}],limits:{}},summary:{coverage:{requested_duration_s:60,complete:true},assessment:{requested_demand_met:true},metrics:{busiest_cell:'cell1',peak_cell_current_A:1,imbalance_pct:null,warmest_cell:null},checks:[],charging:{version:'voltforge.pack-charge/2',net_charge_gained_Ah:.1,received_charge_Ah:.12,delivered_charge_Ah:.02,elapsed_s:60}}};
 assert.ok(verdictRows(t,String).includes('0.10 Ah net pack charge'));
 t.summary.charging={charge_gained_Ah:.4,elapsed_s:60};assert.ok(verdictRows(t,String).includes('historical'));assert.ok(verdictRows(t,String).includes('not pack-terminal'));
});
test('Part candidates expose incompatibility instead of suggesting a ready BOM',()=>{
 const html=partsPanel({subtotals:{USD:10},unpriced:[],lines:[{part:'Board',quantity:1,unit:'part',priced:false,note:'Candidate',selection:'candidate',compatibility:{status:'incompatible',reasons:['Wrong cell count'],conditions:['Verify charger']}}],scope:'Listed candidates'});
 assert.ok(html.includes('incompatible'));assert.ok(html.includes('Wrong cell count'));assert.ok(html.includes('Verify charger'));
 assert.deepEqual(missionRequest(newSetup()),{test_type:'discharge',preset:'pi5_gateway_backup'});
});
test('Edited current does not claim it still represents the original device power',()=>{
 const html=applicationLine({name:'Pi',purpose:'Backup',approximation:'Current is held constant.',requirements:[{key:'device_power_W',label:'Supply power',value:25,unit:'W',basis:'sourced',reason:'Supply envelope'},{key:'load_current_A',label:'Current',value:1,unit:'A',basis:'custom',reason:'Edited'},{key:'voltage_floor_V',label:'Floor',value:3.3,unit:'V',basis:'assumed',reason:'Study'}]});
 assert.ok(html.includes('does not automatically recalculate'));assert.ok(!html.includes('application approximated by'));assert.ok(html.includes('25.0 W'));
});
