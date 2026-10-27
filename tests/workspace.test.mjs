import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadProfile, durationLabel, componentLabel, resultLabel, limitLabel} from '../web/editor/workspace.mjs';

test('the load editor preserves discharge, rest and charging as exact contiguous intervals',()=>{
  assert.deepEqual(loadProfile([{duration:'120',current:'14.55'},{duration:'30',current:'0'},{duration:'60',current:'-3.2'}]),[
    {start_s:0,end_s:120,current_A:14.55},{start_s:120,end_s:150,current_A:0},{start_s:150,end_s:210,current_A:-3.2},
  ]);
  assert.deepEqual(loadProfile([{duration:'.125',current:'2'},{duration:'.25',current:'4'}]),[
    {start_s:0,end_s:.125,current_A:2},{start_s:.125,end_s:.375,current_A:4},
  ]);
});
test('empty, negative, nonfinite and subprecision durations cannot become solver inputs',()=>{
  for(const rows of [[],[{duration:'',current:'1'}],[{duration:'0',current:'1'}],[{duration:'-2',current:'1'}],[{duration:'Infinity',current:'1'}],[{duration:'1',current:''}],[{duration:'1',current:'NaN'}],[{duration:'1e100',current:'1'},{duration:'1',current:'1'}]]) assert.throws(()=>loadProfile(rows));
});
test('result labels preserve ownership, historical freshness and incomplete execution',()=>{
  assert.equal(resultLabel({run_id:'run_0005',owner_variant_id:'A0',freshness:'current',execution_status:'completed',scenario_id:'nominal'}),'run_0005 · A0 · Current · Nominal');
  assert.match(resultLabel({run_id:'old',owner_variant_id:'A0',freshness:'outdated',execution_status:'completed',scenario_id:'nominal'}),/Outdated/);
  assert.match(resultLabel({run_id:'partial',owner_variant_id:'C1',freshness:'current',execution_status:'failed',scenario_id:'soc_minus_2pp'}),/Partial · Sensitivity/);
  assert.equal(limitLabel('no sampled exceedance; insufficient evidence for a pass'),'No sampled exceedance');
  assert.equal(limitLabel('requirement not configured'),'Not configured');
});
test('display names explain components and retain unknown names without inventing a component',()=>{
  assert.equal(componentLabel('rail_p_2'),'Positive connection 2');
  assert.equal(componentLabel('cell_3'),'Cell 3');
  assert.equal(componentLabel('unknown'),'unknown');
  assert.equal(durationLabel(360),'6 min');
  assert.equal(durationLabel(37.5),'37.50 s');
});
