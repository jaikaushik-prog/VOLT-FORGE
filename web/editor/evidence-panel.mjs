// Presentation and transport only; every physical value comes from the backend.
import {escapeHTML as h, failureMessage} from './state.mjs';
import {EvidenceRequestGuard, presentEvidence, presentPreview} from './evidence-state.mjs';

const labels = {maximum_branch_current_A:'Maximum branch current',minimum_branch_current_A:'Minimum branch current',
  minimum_cell_voltage_V:'Minimum cell voltage',minimum_terminal_voltage_V:'Minimum terminal voltage',
  delivered_net_Wh:'Delivered net energy',delivered_positive_Wh:'Delivered energy',received_Wh:'Received energy',
  mean_delivered_power_W:'Mean delivered power',delivered_charge_Ah:'Delivered charge',
  cell_R0_loss_Wh:'Cell ohmic loss',rail_loss_Wh:'Rail loss',R1_loss_Wh:'Polarization resistance loss',
  max_kcl_residual_A:'Current-conservation residual',max_charge_balance_As:'Charge-accounting residual',
  R0_ohm:'Ohmic resistance',R1_ohm:'Polarization resistance',tau_s:'Time constant',capacity_Ah:'Derived capacity'};

function sourceMarkup(claim) {
  return `<details class="evidence-source"><summary>Source details</summary>
    ${claim.unitProvenance?`<p>${h(claim.unitProvenance.explanation)}</p>`:''}
    <dl>${claim.citationFields.map(x=>`<dt>${h(x.label)}</dt><dd>${h(x.value)}</dd>`).join('')}</dl>
    <details><summary>Exact value and citation</summary><pre>${h(JSON.stringify({value:claim.value,unit:claim.unit,source:claim.source,...(claim.unitProvenance?{unitProvenance:claim.unitProvenance,sourceClaim:claim.sourceClaim}:{})},null,2))}</pre></details></details>`;
}
function claimMarkup(claim) {
  const complex = claim.value !== null && typeof claim.value === 'object';
  const label=labels[claim.label]||claim.label;
  const display=typeof claim.value==='number'?String(Number(claim.value.toPrecision(6))):claim.valueText;
  const component=claim.componentId?`<span class="evidence-component">${h(claim.componentId.replaceAll('_',' '))}</span>`:'';
  return `<li class="evidence-claim"><div class="evidence-claim-heading"><span>${h(label)}${component}</span>
    ${complex?'':`<strong title="Display uses up to six significant digits; source details retain the exact value.">${h(display)}${claim.unit?` <small>${h(claim.unit)}</small>`:''}</strong>`}</div>
    ${complex?`<details class="evidence-value"><summary>Inspect recorded values${claim.unit?` (${h(claim.unit)})`:''}</summary><pre>${h(claim.valueText)}</pre></details>`:''}
    ${sourceMarkup(claim)}</li>`;
}
export function previewMarkup(model) {
  if(!model.ok) return `<p class="error" role="alert">${h(model.title)} ${model.warnings.map(h).join(' ')}</p>`;
  const current=model.before.value;
  const currentValue=current&&typeof current==='object'&&Object.hasOwn(current,'value')?current.value:current;
  const currentUnit=model.before.unit||current?.unit;
  return `<section class="preview evidence-preview" aria-label="Review proposed change"><strong>Review before applying</strong>
    <p>${model.physicsChanged?'This creates a new design revision.':'This does not change the electrical inputs.'}
    ${model.invalidatedRunIds.length} owned run(s) will become outdated. Previous outputs are retained.</p>
    <div class="preview-values"><div><span>Current input${currentUnit?` (${h(currentUnit)})`:''}</span><pre>${h(JSON.stringify(currentValue,null,2))}</pre></div>
    <div><span>Proposed input (${h(model.proposed.unit)})</span><pre>${h(JSON.stringify(model.proposed.value,null,2))}</pre></div></div>
    <p class="evidence-classification">${h(model.proposed.classification.replaceAll('_',' '))} · ${h(model.proposed.source)}</p>
    <p>No change applied. The effect on current or voltage has not been calculated.</p>
    ${model.warnings.length?`<details><summary>Assumptions and review limits (${model.warnings.length})</summary><ul>${model.warnings.map(w=>`<li>${h(w)}</li>`).join('')}</ul></details>`:''}
    ${sourceMarkup(model.before)}
    <details><summary>Exact proposed input and review identity</summary><pre>${h(JSON.stringify({edit:model.proposed,binding:model.binding,preview_id:model.previewId},null,2))}</pre></details>
    <p>Choose <strong>Apply revision</strong> to save this input. Run a simulation separately to calculate its effect.</p></section>`;
}

export function createEvidencePanel({element,request,getSelection,isReady}) {
  const evidenceGuard=new EvidenceRequestGuard(), previewGuard=new EvidenceRequestGuard();
  const visible=()=>!element.hidden;
  function heading(selection) {
    return `<div class="evidence-heading"><div><h2>Evidence & assumptions</h2><p>${h(selection?.component_id?.replaceAll('_',' ')||'Selected component')}
      ${selection?` / ${h(selection.variant_id)}`:''}${selection?.run_id?` / ${h(selection.run_id)}`:' / configuration'}</p></div>
      <button id="refresh-evidence" class="small" ${!isReady()?'disabled':''}>Refresh evidence</button></div>`;
  }
  function empty(message='Inspect the assumptions behind this design, or select a saved run to inspect its evidence.') {
    element.innerHTML=heading(getSelection())+`<div class="evidence-empty"><h3>Follow the evidence</h3><p>${h(message)}</p>
      <p>This view reads saved calculations and their sources. It does not generate new predictions.</p></div>`;
  }
  function render(model) {
    if(!model.ok){element.innerHTML=heading(getSelection())+`<div class="evidence-message error" role="alert"><strong>${h(model.title)}</strong><p>${model.warnings.map(h).join(' ')}</p><p>Refresh evidence for the current selection.</p></div>`;return;}
    const warning=model.flags.failed||model.flags.outdated;
    const inputTitle=model.flags.outdated?'Current design assumptions':'Configured assumptions';
    element.innerHTML=heading(getSelection())+`<div class="evidence-status ${warning?'caution':''}" role="status"><strong>${h(model.title)}</strong>
      <span>${model.flags.configurationOnly?'No saved result selected':'Saved simulation evidence'}</span></div>
      ${model.runStatus?.error?`<p class="error evidence-failure" role="alert">${h(failureMessage(model.runStatus.error))}</p>`:''}
      ${model.runStatus?.outdated_reasons?.length?`<p class="evidence-outdated">Outdated: ${model.runStatus.outdated_reasons.map(h).join('; ')}</p>`:''}
      <div class="evidence-limit"><h3>${h(model.requirement.statusText)}</h3><p>${h(model.requirement.warning)}</p>
      <p><strong>Experimental module validation pending.</strong> ${h(model.decision)} for a validated module decision.</p></div>
      ${model.warnings.length?`<details class="evidence-warnings" ${warning?'open':''}><summary>${warning?'Result limitations':'Evidence limits'} (${model.warnings.length})</summary><ul>${model.warnings.map(x=>`<li>${h(x)}</li>`).join('')}</ul></details>`:''}
      <p class="evidence-explanation">${h(model.explanation)}</p>
      <div class="evidence-groups">${model.groups.filter(g=>g.claims.length).sort((a,b)=>['outputs','inputs','models','evidence'].indexOf(a.id)-['outputs','inputs','models','evidence'].indexOf(b.id)).map(g=>
        `<details class="evidence-group" ${g.id==='outputs'||(model.flags.configurationOnly&&g.id==='inputs')?'open':''}>
          <summary>${h(g.id==='inputs'?inputTitle:g.title)}<span>${g.claims.length} fields</span></summary>
          <ul>${g.claims.map(claimMarkup).join('')}</ul></details>`).join('')}</div>
      <details class="evidence-record"><summary>Full coverage and requirement record</summary><p>Fitting coverage, assessment coverage and unsupported transfer remain distinct. A current amplitude alone does not validate its duration or waveform.</p><pre>${h(JSON.stringify({run_status:model.runStatus,coverage:model.coverage,requirement:model.requirement.detail,pagination:model.pagination},null,2))}</pre></details>
      <details class="evidence-record"><summary>Evidence identity and available capabilities</summary><pre>${h(JSON.stringify({binding:model.binding,unavailable:model.unavailableCapabilities},null,2))}</pre></details>
      <p class="evidence-footnote">Displayed numbers use up to six significant digits; source details retain exact values. These explanations are assembled from backend evidence. Conversational AI, thermal prediction and optimization are unavailable.</p>`;
  }
  async function context(selection) {
    const data=await request('/api/evidence/context',{variant_id:selection.variant_id,run_id:selection.run_id,component_id:selection.component_id,limit:4});
    return {status:'ok',result:data};
  }
  async function refresh() {
    const selection=getSelection();
    if(!selection||!isReady()){empty('Wait for the current operation to finish, then refresh evidence.');return;}
    const ticket=evidenceGuard.begin(selection);
    element.innerHTML=heading(selection)+'<p class="evidence-loading" role="status">Reading the selected design and saved evidence…</p>';
    try {
      const ctx=await context(selection);
      if(!evidenceGuard.current(ticket,getSelection()))return;
      const response=await request('/api/evidence/request',{operation:'explain',context:ctx,arguments:{}});
      if(evidenceGuard.current(ticket,getSelection()))render(presentEvidence(response,selection));
    }catch(error){
      if(evidenceGuard.current(ticket,getSelection()))element.innerHTML=heading(selection)+`<div class="evidence-message error" role="alert"><strong>Evidence unavailable</strong><p>${h(error.message)}</p><p>Refresh evidence to retry. Saved results have not been changed.</p></div>`;
    }
  }
  function changed({reload=true}={}) {
    evidenceGuard.invalidate();previewGuard.invalidate();
    empty();if(reload&&visible())void refresh();
  }
  async function preview(edit) {
    const selection=getSelection(),ticket=previewGuard.begin(selection,edit);
    const ctx=await context(selection);
    if(!previewGuard.current(ticket,getSelection(),edit))throw new Error('The selection or input changed. Preview the change again.');
    const response=await request('/api/evidence/request',{operation:'preview_edit',context:ctx,arguments:{edit}});
    if(!previewGuard.current(ticket,getSelection(),edit))throw new Error('The selection or input changed. Preview the change again.');
    const model=presentPreview(response,selection,edit);
    if(!model.ok)throw new Error([model.title,...model.warnings].join(' '));
    return {context:ctx,response,model,selection};
  }
  async function revalidate(saved,edit) {
    const selection=getSelection(),ticket=previewGuard.begin(selection,edit);
    const response=await request('/api/evidence/request',{operation:'preview_edit',context:saved.context,arguments:{edit}});
    if(!previewGuard.current(ticket,getSelection(),edit))throw new Error('Selection changed. Preview again before applying.');
    const model=presentPreview(response,selection,edit);
    if(!model.ok)throw new Error([model.title,...model.warnings].join(' '));
    return model;
  }
  element.addEventListener('click',event=>{if(event.target.closest('#refresh-evidence'))void refresh();});
  empty();
  return {refresh,changed,preview,revalidate,invalidatePreview:()=>previewGuard.invalidate(),
    refreshIfVisible:()=>{if(visible())void refresh();}};
}
