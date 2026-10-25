// Local command presentation only. Physical values come from saved backend runs.
import {escapeHTML as h, failureMessage} from './state.mjs';
import {EvidenceRequestGuard, selectionKey, presentEvidence, presentPreview} from './evidence-state.mjs';
import {previewMarkup} from './evidence-panel.mjs';

const metrics={maximum_branch_current_A:['Peak branch current','A'],minimum_cell_voltage_V:['Minimum cell voltage','V'],
  minimum_terminal_voltage_V:['Minimum terminal voltage','V'],mean_delivered_power_W:['Mean delivered power','W'],
  delivered_net_Wh:['Delivered net energy','Wh'],delivered_charge_Ah:['Delivered charge','Ah'],
  cell_R0_loss_Wh:['Cell ohmic loss','Wh'],rail_loss_Wh:['Rail loss','Wh'],R1_loss_Wh:['Polarization resistor loss','Wh'],
  above_4_9A_cell_seconds:['Time above 4.9 A','cell s']};
const require=(condition,message)=>{if(!condition)throw new Error(message);};
const display=value=>typeof value==='number'?String(Number(value.toPrecision(6))):String(value);
const compact=value=>value!==0&&Math.abs(value)<0.0001?value.toExponential(2):String(Number(value.toPrecision(4)));
const exact=value=>`<pre>${h(JSON.stringify(value,null,2))}</pre>`;
const warningList=warnings=>warnings?.length?`<details class="command-sources"><summary>Assumptions and limits (${warnings.length})</summary><ul>${warnings.map(x=>`<li>${h(x)}</li>`).join('')}</ul></details>`:'';

export function validateCommandResponse(result,selection,comparison) {
  require(result?.schema==='voltforge.local_assistant/1'&&result.mode==='local_commands','Unsupported assistant response.');
  require(result.applied===false&&result.simulation_started===false,'A command response must not execute an action.');
  require(selectionKey(result.selection)===selectionKey(selection),'Selection changed. Review the command again.');
  require(Array.isArray(result.warnings)&&result.warnings.every(x=>typeof x==='string'),'Missing command limitations.');
  if(result.action==='help')return {result,model:null};
  if(result.action==='explain') {
    const model=presentEvidence(result.payload,selection);require(model.ok,model.title+': '+model.warnings.join(' '));return {result,model};
  }
  if(result.action==='preview_edit') {
    require(result.context?.status==='ok','Preview has no authoritative context.');
    const model=presentPreview(result.payload,selection,result.payload.proposed_edit);
    require(model.ok,model.title+': '+model.warnings.join(' '));return {result,model};
  }
  require(result.action==='compare','Unsupported local command action.');
  const payload=result.payload, rows=payload?.ordered_results, delta=payload?.deltas_vs_first;
  require(comparison?.first&&comparison?.second,'Select two explicit runs in Compare.');
  require(Array.isArray(rows)&&rows.length===2&&Array.isArray(delta)&&delta.length===1,'Incomplete comparison.');
  const expected=[comparison.first,comparison.second];
  require(expected[0].run_id!==expected[1].run_id||expected[0].variant_id!==expected[1].variant_id,'Select two different run entries.');
  rows.forEach((row,i)=>{
    require(row.run_id===expected[i].run_id&&row.variant_id===expected[i].variant_id&&typeof row.snapshot_id==='string','Comparison belongs to different selected runs.');
    require(['current','outdated'].includes(row.freshness)&&typeof row.requirement==='string'&&row.decision==='insufficient evidence','Comparison is missing evidence status.');
    for(const key of Object.keys(metrics))require(Number.isFinite(row[key]),'Missing numerical comparison field: '+key);
  });
  require(delta[0].run_id===rows[1].run_id&&Object.keys(metrics).every(key=>Number.isFinite(delta[0][key])),'Incomplete comparison differences.');
  require(payload.kind==='simulation comparison'&&payload.conditions==='identical operating conditions'&&typeof payload.condition_sha256==='string','Comparison conditions are not declared.');
  const evidence=result.evidence?.comparison;
  require(Array.isArray(evidence?.source_references)&&evidence.source_references.length>0&&Array.isArray(evidence.runs)&&evidence.runs.length===2,'Comparison source references are missing.');
  for(const [key,[,unit]] of Object.entries(metrics))require(evidence.units?.[key]===unit,'Comparison units are missing or inconsistent.');
  rows.forEach((row,i)=>{
    const run=evidence.runs[i];
    require(run.run_id===row.run_id&&run.snapshot_id===row.snapshot_id&&run.viewed_variant_id===row.variant_id
      &&typeof run.owner_variant_id==='string'&&run.execution_status==='completed'&&run.freshness===row.freshness,'Comparison run metadata is inconsistent.');
    require(evidence.source_references.some(ref=>ref.operation==='compare'&&ref.payload_pointer===`/ordered_results/${i}`
      &&ref.run_id===row.run_id&&ref.snapshot_id===row.snapshot_id),'Comparison row citation is missing.');
  });
  return {result,model:null};
}

export function commandMarkup({result,model}) {
  const sources=`<details class="command-sources"><summary>Exact response and sources</summary>${exact(result)}</details>`;
  if(result.action==='help')return `<h3>Supported local commands</h3><p>${h(result.payload.description)}</p><ul class="command-help">${result.payload.commands.map(command=>`<li><code>${h(command)}</code></li>`).join('')}</ul>${warningList(result.payload.notes)}${warningList(result.warnings)}`;
  if(result.action==='preview_edit')return previewMarkup(model)+`<button id="assistant-review" class="primary">Review in inspector</button><p class="command-note">Reviewing does not apply this edit or start a simulation.</p>${sources}`;
  if(result.action==='explain') {
    const outputs=model.claims.filter(c=>c.kind==='simulated_output'&&typeof c.value==='number').slice(0,6);
    return `<h3>${h(model.title)}</h3>${model.runStatus?.error?`<p class="error">${h(failureMessage(model.runStatus.error))}</p>`:''}
      ${model.runStatus?.outdated_reasons?.length?`<p class="command-caution">Historical output: ${model.runStatus.outdated_reasons.map(h).join('; ')}</p>`:''}
      <p>${h(model.explanation)}</p><p class="command-caution">${h(model.requirement.statusText)}. Experimental module validation remains pending.</p>
      ${outputs.length?`<h4>Saved module summary</h4><dl class="command-metrics">${outputs.map(c=>`<dt>${h(metrics[c.label]?.[0]||c.label)}</dt><dd>${h(display(c.value))} ${h(c.unit)}</dd>`).join('')}</dl>`:'<p>No saved output selected. The evidence describes the current configuration.</p>'}
      <button id="assistant-evidence">Open full evidence</button>${warningList(model.warnings)}${sources}`;
  }
  const p=result.payload,[a,b]=p.ordered_results,d=p.deltas_vs_first[0];
  return `<h3>Simulation comparison</h3><p>${h(p.conditions)}. ${h(p.evidence)}</p>
    ${p.historical_results?'<p class="command-caution">Includes historical results. Each row retains its run and snapshot identity.</p>':''}
    <div class="command-table"><table><thead><tr><th>Metric</th><th>${h(a.variant_id)} / ${h(a.run_id)}</th><th>${h(b.variant_id)} / ${h(b.run_id)}</th><th>Second minus first</th></tr></thead><tbody>
    ${Object.entries(metrics).map(([k,[label,unit]])=>`<tr><th>${h(label)} (${h(unit)})</th><td>${h(compact(a[k]))}</td><td>${h(compact(b[k]))}</td><td>${h(compact(d[k]))}</td></tr>`).join('')}
    <tr><th>Requirements</th><td>${h(a.requirement)}</td><td>${h(b.requirement)}</td><td>—</td></tr>
    <tr><th>Freshness</th><td>${h(a.freshness)}</td><td>${h(b.freshness)}</td><td>—</td></tr></tbody></table></div>
    <p class="command-caution">Insufficient evidence for a validated module decision. No repair ranking or demonstrated battery-performance gain.</p>${warningList(result.warnings)}${sources}`;
}

export function createAssistantPanel({element,toggle,request,getSelection,getComparison,isReady,onPreview,onEvidence,onChooseComparison}) {
  const guard=new EvidenceRequestGuard();let saved=null,pending=false;
  element.innerHTML=`<div class="command-heading"><div><h2 id="assistant-title">Local command assistant</h2><p>Supported commands. No external AI calls.</p></div><button id="assistant-close" aria-label="Close commands">×</button></div>
    <p id="assistant-context" class="command-context"></p><div class="command-examples" aria-label="Command examples">
    <button data-command="explain this result">Explain selection</button><button data-command="compare selected runs">Compare selected runs</button><button data-command="help">Help</button></div>
    <form id="assistant-form"><label for="assistant-message">Command</label><textarea id="assistant-message" rows="3" maxlength="400" placeholder="Select a rail, then: preview change selected rail to 0.5 mOhm"></textarea>
    <div class="command-actions"><button id="assistant-send" type="submit" class="primary">Review request</button><button id="assistant-choose-runs" type="button">Choose comparison runs</button></div></form>
    <div id="assistant-response" aria-live="polite"><p>Explain saved evidence or preview one supported change. Apply and simulation remain separate actions.</p></div>
    <p class="command-note">Values come from the backend. Display rounding is for readability; exact values and citations are expandable.</p>`;
  const input=element.querySelector('#assistant-message'),output=element.querySelector('#assistant-response');
  const data=()=>({message:input.value.trim(),comparison:getComparison()});
  function sync(){const s=getSelection();element.querySelector('#assistant-context').textContent=s?`${s.variant_id} / ${s.component_id} / ${s.run_id||'configuration only'}`:'Open a project first.';element.querySelector('#assistant-send').disabled=pending||!isReady();}
  function changed(){guard.invalidate();saved=null;pending=false;output.innerHTML='<p>Selection or inputs changed. Review a command for the current context.</p>';sync();}
  function close(){element.hidden=true;toggle.setAttribute('aria-expanded','false');toggle.focus();}
  function open(){element.hidden=false;toggle.setAttribute('aria-expanded','true');sync();input.focus();}
  async function submit(){
    if(!isReady()||pending)return;
    const selection=getSelection(),fields=data();if(!fields.message){input.focus();return;}
    const ticket=guard.begin(selection,fields);saved=null;pending=true;sync();output.innerHTML='<p role="status">Reading the selected project evidence…</p>';
    try{
      const response=await request('/api/assistant/request',{message:fields.message,selection,comparison:fields.comparison});
      if(!guard.current(ticket,getSelection(),data()))return;
      const view=validateCommandResponse(response,selection,fields.comparison);saved={view,ticket,fields};output.innerHTML=commandMarkup(view);
    }catch(error){if(guard.current(ticket,getSelection(),data()))output.innerHTML=`<p class="error" role="alert">${h(error.message)}</p><p>Use Help for the supported command forms. No project change was applied.</p>`;}
    finally{if(guard.current(ticket,getSelection(),data())){pending=false;sync();}}
  }
  element.querySelector('#assistant-form').addEventListener('submit',event=>{event.preventDefault();void submit();});
  input.addEventListener('input',changed);
  element.addEventListener('click',event=>{
    const example=event.target.closest('[data-command]');if(example){input.value=example.dataset.command;changed();input.focus();}
    if(event.target.closest('#assistant-close'))close();
    if(event.target.closest('#assistant-choose-runs')){close();onChooseComparison();}
    if(event.target.closest('#assistant-evidence')){close();onEvidence();}
    if(event.target.closest('#assistant-review')&&saved){
      if(!guard.current(saved.ticket,getSelection(),data())){changed();return;}
      const snapshot=saved;event.target.disabled=true;
      const current=()=>guard.current(snapshot.ticket,getSelection(),data());
      Promise.resolve(onPreview(snapshot.view.result,current)).then(()=>{if(current())close();}).catch(error=>{
        if(current()){output.innerHTML=`<p class="error" role="alert">${h(error.message)}</p><p>Review the command again for the current selection.</p>`;saved=null;}
      });
    }
  });
  element.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();close();}});
  toggle.addEventListener('click',()=>element.hidden?open():close());sync();
  return {changed,sync,close,open};
}
