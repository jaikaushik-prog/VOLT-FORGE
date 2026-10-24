import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chooseRun, RequestEpoch, escapeHTML, finiteInput, bounds, viewLabel, failureMessage} from '../web/editor/state.mjs';

test('inherited and sensitivity runs cannot be selected as current nominal results',()=>{
  const info={runs:[{run_id:'old'},{run_id:'sensitivity'}],current_runs_by_scenario:{soc_plus_2pp:['sensitivity']}};
  assert.equal(chooseRun(info),'');
  assert.equal(chooseRun(info,'soc_plus_2pp'),'sensitivity');
  assert.equal(chooseRun(info,'nominal','foreign'),'');
  assert.equal(chooseRun(info,'nominal','old'),'old'); // explicit historical selection only
});
test('late results fail the selection epoch after a variant change',()=>{
  const epoch=new RequestEpoch(),old=epoch.begin(),fresh=epoch.begin();
  assert.equal(epoch.current(old),false);assert.equal(epoch.current(fresh),true);
});
test('user content escapes markup and numeric edits reject empty or nonfinite input',()=>{
  assert.equal(escapeHTML('<img src="x">'), '&lt;img src=&quot;x&quot;&gt;');
  for(const value of ['', ' ', 'Infinity','NaN'])assert.throws(()=>finiteInput(value));
  assert.equal(finiteInput('-2.5'),-2.5);
});
test('chart bounds show negative charge and flat data without undefined scales',()=>{
  assert.ok(bounds([-2,0,4])[0]<-2);assert.ok(bounds([-2,0,4])[1]>4);
  const [lo,hi]=bounds([3.7,3.7]);assert.ok(lo<3.7&&hi>3.7);
  assert.match(viewLabel({run_id:'r',owner_variant_id:'A0',scenario_id:'nominal',execution_status:'failed',freshness:'outdated'}),/failed · outdated/);
  assert.equal(failureMessage({last_valid_time_s:36,reason:'Reference support exceeded',attempted_SOC:[.09]}),'Stopped at 36.00 s. Reference support exceeded');
});
