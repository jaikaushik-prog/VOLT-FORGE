import test from 'node:test';
import assert from 'node:assert/strict';
import {validateCommandResponse,commandMarkup} from '../web/editor/assistant-panel.mjs';

// Explicitly synthetic response fixtures; no measured outcomes or solver claim.
const selection={variant_id:'A1',revision_id:'rev_test',component_id:'module',run_id:'run_2'};
const comparison={first:{variant_id:'A0',run_id:'run_1'},second:{variant_id:'A1',run_id:'run_2'}};
const units={maximum_branch_current_A:'A',minimum_cell_voltage_V:'V',minimum_terminal_voltage_V:'V',mean_delivered_power_W:'W',
  delivered_net_Wh:'Wh',delivered_charge_Ah:'Ah',cell_R0_loss_Wh:'Wh',rail_loss_Wh:'Wh',R1_loss_Wh:'Wh',above_4_9A_cell_seconds:'cell s'};
function fixture(){
  const rows=Object.values(comparison).map((item,i)=>({...item,snapshot_id:'snapshot_'+i,freshness:i?'current':'outdated',
    requirement:'requirement not configured',decision:'insufficient evidence',...Object.fromEntries(Object.keys(units).map(k=>[k,1+i]))}));
  return {schema:'voltforge.local_assistant/1',mode:'local_commands',selection,action:'compare',applied:false,simulation_started:false,warnings:['Synthetic fixture'],
    payload:{kind:'simulation comparison',conditions:'identical operating conditions',condition_sha256:'fixture',ordered_results:rows,
      deltas_vs_first:[{run_id:'run_2',...Object.fromEntries(Object.keys(units).map(k=>[k,1]))}],historical_results:true,evidence:'Synthetic only'},
    evidence:{comparison:{units,runs:rows.map(r=>({...r,viewed_variant_id:r.variant_id,owner_variant_id:r.variant_id,execution_status:'completed'})),
      source_references:rows.map((r,i)=>({operation:'compare',payload_pointer:'/ordered_results/'+i,run_id:r.run_id,snapshot_id:r.snapshot_id}))}}};
}
test('comparison preserves exact values, supplied deltas and explicit historical/unconfigured evidence',()=>{
  const raw=fixture(),before=JSON.stringify(raw),view=validateCommandResponse(raw,selection,comparison),html=commandMarkup(view);
  assert.equal(JSON.stringify(raw),before);assert.match(html,/Includes historical results/);assert.match(html,/requirement not configured/);
  assert.match(html,/Insufficient evidence/);assert.match(html,/No repair ranking/);assert.match(html,/run_1/);assert.match(html,/run_2/);
});
test('wrong selected variant, swapped comparison or changed snapshot rejects display',()=>{
  assert.throws(()=>validateCommandResponse(fixture(),{...selection,variant_id:'A0'},comparison),/Selection changed/);
  assert.throws(()=>validateCommandResponse(fixture(),selection,{first:comparison.second,second:comparison.first}),/different selected/);
  const raw=fixture();raw.payload.ordered_results[0].snapshot_id='different';assert.throws(()=>validateCommandResponse(raw,selection,comparison),/metadata/);
});
test('missing units, missing row citations, failed or nonfinite comparisons reject display',()=>{
  for(const mutate of [r=>{r.evidence.comparison.units={...units,rail_loss_Wh:'W'};},r=>{r.evidence.comparison.source_references=[];},
    r=>{r.evidence.comparison.runs[0].execution_status='failed';},r=>{r.payload.ordered_results[0].minimum_cell_voltage_V=NaN;}]){
    const raw=fixture();mutate(raw);assert.throws(()=>validateCommandResponse(raw,selection,comparison));
  }
});
test('action-execution claims and unknown assistant modes are rejected',()=>{
  for(const update of [{applied:true},{simulation_started:true},{mode:'llm'},{action:'run'}])assert.throws(()=>validateCommandResponse({...fixture(),...update},selection,comparison));
});
test('untrusted command/provenance text is escaped rather than rendered as markup',()=>{
  const raw=fixture();raw.warnings=['<img src=x onerror="injected()">'];raw.payload.evidence='<script>injected()</script>';
  const html=commandMarkup(validateCommandResponse(raw,selection,comparison));assert.ok(!html.includes('<img'));assert.ok(!html.includes('<script>'));assert.match(html,/&lt;script&gt;/);
});
