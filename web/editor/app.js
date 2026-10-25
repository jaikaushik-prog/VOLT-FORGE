import {escapeHTML as h, chooseRun, viewLabel, bounds, RequestEpoch, number as n, finiteInput, failureMessage} from './state.mjs';
import {createEvidencePanel, previewMarkup} from './evidence-panel.mjs';
import {createAssistantPanel} from './assistant-panel.mjs';
import {presentPreview, selectionKey} from './evidence-state.mjs';

const $ = id => document.getElementById(id);
const ids = ['cell_1','cell_2','cell_3','cell_4'];
const scenarios = {nominal:'Nominal design', soc_minus_2pp:'Sensitivity: SOC −2 points', soc_plus_2pp:'Sensitivity: SOC +2 points',
  capacity_minus_1pct:'Sensitivity: capacity −1%', capacity_plus_1pct:'Sensitivity: capacity +1%',
  polarization_minus_5mV:'Sensitivity: polarization −5 mV', polarization_plus_5mV:'Sensitivity: polarization +5 mV',
  loaded_reference_shape:'Sensitivity: loaded reference shape'};
const state = {token:'', info:null, variant:'A0', selected:'module', scenario:'nominal', run:null, series:null,
  index:0, offset:0, busy:false, action:false, preview:null, catalog:[], display:null};
const designEpoch = new RequestEpoch(), seriesEpoch = new RequestEpoch();
state.loading=false;state.previewEvidence=null;
const evidence=createEvidencePanel({element:$('panel-evidence'),request,
  getSelection:()=>state.info?{variant_id:state.variant,revision_id:state.info.revision_id,component_id:state.selected,run_id:state.run?.run_id||null}:null,
  isReady:()=>Boolean(state.info)&&!state.busy&&!state.loading});
const assistant=createAssistantPanel({element:$('assistant-panel'),toggle:$('assistant-toggle'),request,
  getSelection:commandSelection,getComparison:commandComparison,
  isReady:()=>Boolean(state.info)&&!state.busy&&!state.action&&!state.loading,
  onPreview:reviewAssistantProposal,onEvidence:()=>$('tab-evidence').click(),
  onChooseComparison:()=>{$('tab-compare').click();$('compare-first').focus();}});

function commandSelection(){return state.info?{variant_id:state.variant,revision_id:state.info.revision_id,component_id:state.selected,run_id:state.run?.run_id||null}:null;}
function commandComparison(){
  const rows=[$('compare-first').value,$('compare-second').value].map(id=>state.catalog.find(r=>r.run_id===id));
  return rows.every(Boolean)?{first:{variant_id:rows[0].variant_id,run_id:rows[0].run_id},second:{variant_id:rows[1].variant_id,run_id:rows[1].run_id}}:null;
}

function notice(message, kind='') { $('notice').textContent=message; $('notice').className='notice '+kind; $('notice').setAttribute('role',kind==='error'?'alert':'status'); }
async function request(path, body) {
  const response = await fetch(path, body ? {method:'POST',headers:{'Content-Type':'application/json','X-Voltforge-Token':state.token},body:JSON.stringify(body)} : {});
  let data;
  try { data=await response.json(); } catch { throw new Error('The local server stopped responding. Restart it, then reload this page.'); }
  if (data.status !== 'ok') throw new Error(`${data.error?.code || 'request_failed'}: ${data.error?.message || response.statusText}`);
  return data.result;
}
const api = (operation, arguments_={}) => request('/api/request',{operation,arguments:arguments_});
function buttons() {
  const locked=state.busy||state.action||!state.info;
  for(const id of ['run','new-variant','reset-layout','preview-edit','apply-edit']) if($(id)) $(id).disabled=locked||(id==='apply-edit'&&!state.preview);
  $('export').disabled=locked||!state.catalog.length;
  $('run-select').disabled=locked;
  $('run').textContent=state.busy?'Working…':'▷ Run simulation';
  $('make-export').disabled=locked;
  assistant.sync();
}
async function action(fn) {
  if(state.action||state.busy) return;
  state.action=true; buttons();
  try { await fn(); } catch(e) { notice(e.message,'error'); }
  finally { state.action=false; state.loading=false; buttons(); }
}

async function refresh(variant=state.variant, preferred='') {
  const epoch=designEpoch.begin(); seriesEpoch.begin();
  state.loading=true;evidence.changed({reload:false});assistant.changed();invalidatePreview();
  state.run=null;state.series=null;state.preview=null; renderResults(); drawCanvas();
  $('comparison').textContent='';
  const info=await api('inspect',{variant_id:variant});
  if(!designEpoch.current(epoch)) return;
  state.info=info;state.variant=variant;state.display=structuredClone(info.display);
  state.loading=false;
  $('variant-title').textContent=`${variant} / ${info.name}`;
  $('revision').textContent=`Revision ${info.revision_id.slice(4,12)} · 4 cells / 6 rail segments`;
  renderNavigation(); renderInspector(); renderRunPicker(); drawCanvas(); buttons();
  const picked=chooseRun(info,state.scenario,preferred);
  $('run-select').value=picked;
  if(picked) await loadRun(picked);
  if(!designEpoch.current(epoch)) return;
  await catalogRuns(epoch);
  evidence.refreshIfVisible();assistant.changed();
}
async function catalogRuns(epoch=designEpoch.value) {
  const infos=await Promise.all(Object.keys(state.info.variants).map(variant_id=>api('inspect',{variant_id})));
  if(!designEpoch.current(epoch)) return;
  state.catalog=infos.flatMap(i=>i.runs.filter(r=>r.owner_variant_id===i.variant_id).map(r=>({...r,variant_id:i.variant_id})));
  const completed=state.catalog.filter(r=>r.execution_status==='completed');
  for(const id of ['compare-first','compare-second']) {
    const old=$(id).value; $(id).innerHTML=completed.map(r=>`<option value="${h(r.run_id)}">${h(viewLabel(r))}</option>`).join('');
    if(completed.some(r=>r.run_id===old)) $(id).value=old;
  }
  if(state.run?.execution_status==='completed') $('compare-second').value=state.run.run_id;
  $('compare').disabled=completed.length<2;
  buttons();
}
function renderNavigation() {
  $('variants').innerHTML=Object.entries(state.info.variants).map(([id,v])=>`<button class="nav-item ${id===state.variant?'active':''}" data-variant="${h(id)}" aria-current="${id===state.variant?'true':'false'}"><strong>${h(id)}</strong><small>${h(v.name)}</small></button>`).join('');
  const items=[['module','Module / operating case',0],...ids.map((id,i)=>[id,`Cell ${i+1} / ${state.info.design.cells[id].identity}`,i+1]),...Object.keys(state.info.design.connections).map(id=>[id,`${id.includes('_p_')?'Positive':'Negative'} rail ${id.at(-1)}`,0])];
  $('components').innerHTML=items.map(([id,label,c])=>`<button class="nav-item component ${id===state.selected?'active':''}" data-component="${h(id)}"><i class="dot c${c}"></i>${h(label)}</button>`).join('');
  $('mobile-component').innerHTML=items.map(([id,label])=>`<option value="${h(id)}" ${id===state.selected?'selected':''}>${h(label)}</option>`).join('');
}
function selectComponent(id) { state.selected=id;state.preview=null;renderNavigation();renderInspector();drawCanvas();evidence.changed();assistant.changed(); }

function position(i) { return state.display?.positions[ids[i]] || [190+i*180,155]; }
function drawCanvas() {
  if(!state.info) return;
  const d=state.info.design, points=ids.map((_,i)=>position(i));
  const edge=(rail,i)=>{
    const id=`rail_${rail}_${i+1}`,a=points[i],b=points[i+1],dy=rail==='p'?-99:99;
    const ay=a[1]+dy,by=b[1]+dy,mx=(a[0]+b[0])/2,my=(ay+by)/2;
    // The path is purely visual: each group is exactly one backend rail segment.
    const path=`M${a[0]} ${ay} L${mx-22} ${my} l5 -6 7 12 7 -12 7 12 7 -12 7 6 L${b[0]} ${by}`;
    return `<g class="edge ${state.selected===id?'selected':''}" data-component="${id}" role="button" tabindex="0" aria-label="${rail==='p'?'Positive':'Negative'} rail ${i+1}, ${n(d.connections[id].resistance.value*1000,3)} milliohms"><title>${id}: ${d.connections[id].node_a} to ${d.connections[id].node_b}</title><path class="edge-hit" d="${path}"/><path class="wire" d="${path}"/><text class="edge-label" text-anchor="middle" x="${mx}" y="${my+(rail==='p'?-14:23)}">${n(d.connections[id].resistance.value*1000,2)} mΩ</text></g>`;
  };
  const terminal=points[0];
  let svg=`<path class="wire" d="M30 ${terminal[1]-99} H${terminal[0]} M30 ${terminal[1]+99} H${terminal[0]}"/><circle class="node" cx="30" cy="${terminal[1]-99}" r="5"/><circle class="node" cx="30" cy="${terminal[1]+99}" r="5"/><text class="terminal" x="25" y="${terminal[1]-114}">+ Module</text><text class="terminal" x="25" y="${terminal[1]+121}">− Reference</text>`;
  for(const rail of ['p','n']) for(let i=0;i<3;i++) svg+=edge(rail,i);
  svg+=ids.map((id,i)=>{
    const [x,y]=points[i],c=d.cells[id],row=state.series?.[id]?.rows[state.index], overlay=$('overlay').value;
    const val=overlay==='none'?'':row?(overlay==='voltage'?`${n(row.voltage_V)} V`:`${n(row.current_A)} A`):'—';
    return `<g class="cell-group c${i+1} ${state.selected===id?'selected':''}" data-component="${id}" role="button" tabindex="0" aria-label="Cell ${i+1}, ${c.identity}. Select to inspect. Arrow keys move display when selected."><path class="wire" d="M${x} ${y-99} V${y-62} M${x} ${y+62} V${y+99}"/><circle class="node" cx="${x}" cy="${y-99}" r="4"/><circle class="node" cx="${x}" cy="${y+99}" r="4"/><text class="node-label" x="${x+9}" y="${y-90}">p${i+1}</text><text class="node-label" x="${x+9}" y="${y+92}">n${i+1}</text><rect class="cell-body" x="${x-61}" y="${y-62}" width="122" height="124" rx="9"/><rect class="cell-accent" x="${x-60}" y="${y-48}" width="4" height="29" rx="2"/><text class="cell-title" x="${x-44}" y="${y-29}">${h(c.identity)}</text><text class="cell-sub" x="${x-44}" y="${y-10}">Cell ${i+1} · LG M50T</text><path class="cell-symbol" d="M${x+35} ${y-48} v18 m-5 -9 h10"/><text class="cell-value" x="${x-44}" y="${y+21}">${h(val)}</text><text class="cell-sub" x="${x-44}" y="${y+43}">${row?`${n(row.soc*100,1)}% SOC`:`Start ${n(c.initial_soc.value*100,1)}% SOC`}</text></g>`;
  }).join('');
  $('canvas').innerHTML=svg;
  $('overlay-state').textContent=state.run?`${state.run.freshness==='outdated'?'Historical / ':''}${state.run.execution_status==='failed'?'Failed / partial / ':''}${state.run.owner_variant_id} ${state.run.run_id} at ${n(state.series?.module?.rows[state.index]?.time_s,2)} s`:'No simulation selected';
}

function field(label,id,value,type='number',extra='') { return `<label>${label}<input id="${id}" type="${type}" value="${h(value)}" ${extra}></label>`; }
function renderInspector() {
  if(!state.info) return;
  const d=state.info.design,id=state.selected,c=d.cells[id],edge=d.connections[id];
  let content='', options='';
  if(c) {
    const p=state.info.fitted_parameters[id];
    content=`<div class="inspector-title">${h(c.identity)} <span class="muted">/ ${h(id)}</span></div><p>LG M50T NMC · ${h(c.positive_node)} to ${h(c.negative_node)}</p><span class="tag">Frozen v2 · fitted parameters</span><dl><dt>R₀</dt><dd>${n(p.R0_ohm*1000)} mΩ</dd><dt>R₁</dt><dd>${n(p.R1_ohm*1000)} mΩ</dd><dt>Time constant</dt><dd>${n(p.tau_s,2)} s</dd><dt>Capacity</dt><dd>${n(p.capacity_Ah)} Ah</dd></dl><p>Model and capacity are read-only. Initial states below are assumptions relative to this cell’s voltage reference.</p>`;
    options='<option value="soc">Initial SOC (%)</option><option value="polarization">Initial polarization (mV)</option>';
  } else if(edge) {
    content=`<div class="inspector-title">${edge.rail==='positive'?'Positive':'Negative'} rail ${id.at(-1)}</div><p>${h(edge.node_a)} to ${h(edge.node_b)} · ${h(id)}</p><span class="tag">${h(edge.resistance.classification)} resistance</span><p>${h(edge.resistance.source)}</p><p>Effective segment resistance. A change is hypothetical until its physical connection and resistance are established.</p>`;
    options='<option value="resistance">Segment resistance (mΩ)</option>';
  } else {
    content=`<div class="inspector-title">Module</div><p>Four LG M50T cells in parallel. Same-side terminals at p1 and n1.</p><span class="tag">Proposed operating case</span><dl><dt>Load intervals</dt><dd>${d.scenario.load_profile.length}</dd><dt>Duration</dt><dd>${n(d.scenario.load_profile.at(-1).end_s,1)} s</dd><dt>Ambient assumption</dt><dd>${n(d.scenario.temperature.assumed_ambient_C,1)} °C</dd></dl><p>Discharge current is positive. Temperature is an evidence assumption; no thermal model or temperature scaling is available.</p>`;
    options='<option value="load">Load profile (A, s)</option><option value="temperature">Temperature assumptions (°C)</option><option value="step">Numerical time step (s)</option><option value="requirements">Voltage requirement (V, s)</option>';
  }
  $('inspector-content').innerHTML=content+`<hr><label>Edit property<select id="edit-property">${options}</select></label><div id="edit-fields"></div><label>Input classification<select id="classification"><option value="assumed">Assumed</option><option value="proposed_requirement">Proposed requirement</option><option value="user_declared_measurement">User-declared measurement</option></select></label><label>Source / reason<input id="edit-source" value="Manual exploratory edit in 2D workspace" maxlength="500"></label><div class="form-actions"><button id="preview-edit">Preview change</button><button id="apply-edit" class="primary" disabled>Apply revision</button></div><div id="edit-feedback" aria-live="polite"></div><div class="selection-readout" id="selection-readout"></div><div class="scenario-box"><label>Next simulation<select id="scenario">${Object.entries(scenarios).map(([id,label])=>`<option value="${id}" ${id===state.scenario?'selected':''}>${label}</option>`).join('')}</select></label><p>Sensitivity scenarios are assumption checks, not confidence intervals. They do not replace the design or fitted models.</p></div>`;
  renderEditFields(); updateReadout(); buttons();
}
function renderEditFields() {
  const d=state.info.design,c=d.cells[state.selected],prop=$('edit-property').value;
  let html='';
  if(prop==='resistance') html=field('Resistance (mΩ)','edit-value',d.connections[state.selected].resistance.value*1000,'number','min="0" step="any"');
  if(prop==='soc') html=field('Initial SOC (%)','edit-value',c.initial_soc.value*100,'number','min="0" max="100" step="any"');
  if(prop==='polarization') html=field('Initial polarization (mV)','edit-value',c.initial_polarization.value*1000,'number','step="any"');
  if(prop==='step') html=field('Maximum step (s)','edit-value',d.simulation.dt_s,'number','min="0.000001" step="any"');
  if(prop==='load') html=`<label>Contiguous intervals from 0 s<textarea id="edit-json" rows="6" spellcheck="false">${h(JSON.stringify(d.scenario.load_profile,null,2))}</textarea></label><p>Each interval uses start_s, end_s and current_A. Rest uses 0 A; charging uses a negative current.</p>`;
  if(prop==='temperature') html=field('Assumed ambient (°C)','edit-value',d.scenario.temperature.assumed_ambient_C,'number','step="any"')+`<label>Assumed cell surfaces, cells 1–4 (°C)<input id="surface-values" value="${h(d.scenario.temperature.assumed_surface_C.join(', '))}"></label>`;
  if(prop==='requirements') html=field('Device minimum voltage (V), blank if unknown','minimum-voltage',d.requirements.minimum_terminal_voltage_V??'','number','step="any"')+field('Permitted excursion (s), blank if unknown','excursion',d.requirements.maximum_contiguous_excursion_s??'','number','min="0" step="any"')+field('Documented requirement source','requirement-source',d.requirements.documented_source??'','text')+'<p>Missing requirements produce “requirement not configured”. No project alarm is an authoritative device limit.</p>';
  $('edit-fields').innerHTML=html;invalidatePreview();
}
function invalidatePreview(){state.preview=null;state.previewEvidence=null;evidence.invalidatePreview();if($('edit-feedback')) $('edit-feedback').textContent='';buttons();}
function collectEdit() {
  const prop=$('edit-property').value,id=state.selected,d=state.info.design;
  const source=$('edit-source').value.trim(); if(!source) throw new Error('Add a source or reason for this input.');
  const edit={target:'cell',id,property:'initial_soc',value:null,unit:'fraction',source,classification:$('classification').value};
  if(prop==='resistance') Object.assign(edit,{target:'connection',property:'resistance',unit:'ohm',value:finiteInput($('edit-value').value)/1000});
  if(prop==='soc') edit.value=finiteInput($('edit-value').value)/100;
  if(prop==='polarization') Object.assign(edit,{property:'initial_polarization',unit:'V',value:finiteInput($('edit-value').value)/1000});
  if(prop==='load') Object.assign(edit,{target:'scenario',property:'load_profile',unit:'A,s',value:JSON.parse($('edit-json').value)});
  if(prop==='temperature') Object.assign(edit,{target:'scenario',property:'temperature',unit:'degC',value:{...d.scenario.temperature,assumed_ambient_C:finiteInput($('edit-value').value),assumed_surface_C:$('surface-values').value.split(',').map(finiteInput)}});
  if(prop==='step') Object.assign(edit,{target:'simulation',property:'dt_s',unit:'s',value:finiteInput($('edit-value').value)});
  if(prop==='requirements') Object.assign(edit,{target:'requirements',property:'voltage_requirement',unit:'V,s',value:{minimum_terminal_voltage_V:$('minimum-voltage').value.trim()?finiteInput($('minimum-voltage').value):null,maximum_contiguous_excursion_s:$('excursion').value.trim()?finiteInput($('excursion').value):null,documented_source:$('requirement-source').value.trim()||null}});
  return edit;
}
async function previewEdit() {
  const args={variant_id:state.variant,edit:collectEdit(),expected_revision:state.info.revision_id};
  const saved=await evidence.preview(args.edit);
  if(args.variant_id!==state.variant || args.expected_revision!==state.info.revision_id || JSON.stringify(args.edit)!==JSON.stringify(collectEdit())) {
    notice('The input changed while validation was running. Preview it again.'); return;
  }
  state.preview=args;
  state.previewEvidence=saved;
  $('edit-feedback').innerHTML=previewMarkup(saved.model);
}
async function applyEdit() {
  if(!state.preview||!state.previewEvidence) return;
  const args=state.preview, preferred=state.run?.run_id||'';
  try{await evidence.revalidate(state.previewEvidence,args.edit);}catch(error){invalidatePreview();throw error;}
  if(state.preview!==args)throw new Error('The input changed. Preview again before applying.');
  await api('apply_edit',args); await refresh(args.variant_id,preferred);
  notice('Revision saved. Previous runs are retained; outdated results must be rerun for this design.');
}

async function reviewAssistantProposal(result,isCurrent) {
  if(state.busy||state.action||state.loading)throw new Error('Wait for the current operation to finish.');
  const selection=commandSelection(),edit=result.payload.proposed_edit;
  if(selectionKey(selection)!==selectionKey(result.selection))throw new Error('Selection changed. Review the command again.');
  const model=presentPreview(result.payload,selection,edit);
  if(!model.ok)throw new Error(model.warnings.join(' '));
  const saved={context:result.context,response:result.payload,model,selection};
  const fields=()=>JSON.stringify([...$('inspector-content').querySelectorAll('input,select,textarea')].map(e=>[e.id,e.value]));
  const priorFields=fields();state.action=true;buttons();
  try {
    await evidence.revalidate(saved,edit);
    if(!isCurrent()||selectionKey(selection)!==selectionKey(commandSelection())||priorFields!==fields())throw new Error('Command, selection or inspector changed. Review the command again.');
    const property={resistance:'resistance',initial_soc:'soc',initial_polarization:'polarization',dt_s:'step'}[edit.property];
    if(!property)throw new Error('This command is not supported by the inspector.');
    $('edit-property').value=property;renderEditFields();
    const factor={resistance:1000,initial_soc:100,initial_polarization:1000,dt_s:1}[edit.property];
    $('edit-value').value=String(edit.value*factor);$('classification').value=edit.classification;$('edit-source').value=edit.source;
    state.preview={variant_id:selection.variant_id,edit,expected_revision:selection.revision_id};state.previewEvidence=saved;
    $('edit-feedback').innerHTML=previewMarkup(model);
    notice('Command preview reviewed. Choose Apply revision to save it; run the simulation separately.');
    $('edit-feedback').scrollIntoView({block:'center'});
  }finally{state.action=false;buttons();}
}

function renderRunPicker() {
  $('run-select').innerHTML='<option value="">Select a saved run</option>'+state.info.runs.map(r=>`<option value="${h(r.run_id)}">${h(viewLabel(r))}</option>`).join('');
}
async function loadRun(run_id,offset=0) {
  const epoch=seriesEpoch.begin(),variant=state.variant;
  state.loading=true;invalidatePreview();evidence.changed({reload:false});assistant.changed();
  state.run=null;state.series=null;state.index=0;renderResults();drawCanvas();
  if(!run_id){state.loading=false;evidence.refreshIfVisible();return;}
  $('run-state').textContent='Loading this run’s saved outputs…';
  const [run,...series]=await Promise.all([api('get_run',{variant_id:variant,run_id}),...state.info.output_components.map(component_id=>api('series',{variant_id:variant,run_id,component_id,offset,limit:5000}))]);
  if(!seriesEpoch.current(epoch)||variant!==state.variant) return;
  state.run=run;state.series=Object.fromEntries(series.map(s=>[s.component_id,s]));state.offset=offset;
  state.loading=false;evidence.changed();
  renderResults();drawCanvas();updateReadout();
}
function metric(label,value,unit,digits=3){return `<div class="metric"><span>${label}</span><strong>${n(value,digits)}</strong><small>${unit}</small></div>`;}
function renderResults() {
  const r=state.run,summary=r?.summary;
  $('run-state').className='run-state';
  $('metrics').innerHTML='';$('timeline').hidden=true;
  if(!r) {
    $('run-state').textContent=state.info?.runs.length?'Select an explicit saved run. Inherited runs are historical, not current for this variant.':'Run the reference module to inspect its electrical behaviour.';
    $('plots').className='plots empty';$('plots').innerHTML='<div><h3>No run selected</h3><p>Run this design or select a saved run above.<br>Charts always use the selected run’s saved outputs.</p></div>';
    return;
  }
  $('run-state').classList.add(r.freshness==='outdated'?'outdated':r.execution_status);
  $('run-state').textContent=`${r.execution_status==='failed'?'Failed simulation — partial outputs only': 'Completed simulation'} / ${r.freshness==='outdated'?'Outdated for this design':'Current for this design'} · ${r.scenario_id} · ${r.run_id}${r.outdated_reasons.length?' · '+r.outdated_reasons.join(', '):''}${r.error?' · '+failureMessage(r.error):''}`;
  $('metrics').innerHTML=metric('Peak branch current',summary.maximum_branch_current_A,'A')+metric('Minimum terminal voltage',summary.minimum_terminal_voltage_V,'V')+metric('Delivered net energy',summary.delivered_net_Wh,'Wh')+metric('Mean delivered power',summary.mean_delivered_power_W,'W',2);
  const rows=state.series.module.rows;
  if(rows.length){
    $('plots').className='plots';renderCharts();$('timeline').hidden=false;$('time').max=rows.length-1;$('time').value=0;
    $('sample-window').textContent=`Samples ${state.offset+1}–${state.offset+rows.length} of ${state.series.module.total_samples} · saved solver samples`;
    $('previous-page').disabled=state.offset===0;$('next-page').disabled=state.series.module.next_offset===null;
    setTime(0);
  } else { $('plots').className='plots empty';$('plots').innerHTML='<div><h3>No valid simulation samples</h3><p>Inspect the failure and assumptions before rerunning.</p></div>'; }

}
function chart(key,unit,terminal=false) {
  const rows=state.series.module.rows,t0=rows[0].time_s,t1=rows.at(-1).time_s;
  const channels=ids.map((id,i)=>({rows:state.series[id].rows,key,css:`chart-line c${i+1}`}));
  if(terminal) channels.push({rows,key:'terminal_V',css:'chart-module'});
  const [lo,hi]=bounds(channels.flatMap(c=>c.rows.map(r=>r[c.key]))),x=t=>40+(t-t0)/(t1-t0||1)*340,y=v=>154-(v-lo)/(hi-lo)*127;
  let svg='';
  for(let i=0;i<4;i++){const val=lo+(hi-lo)*i/3,yy=y(val);svg+=`<path class="chart-grid" d="M40 ${yy} H380"/><text class="chart-label" x="34" y="${yy+3}" text-anchor="end">${n(val,2)}</text>`;}
  for(let i=0;i<4;i++){const t=t0+(t1-t0)*i/3;svg+=`<text class="chart-label" x="${x(t)}" y="174" text-anchor="middle">${n(t,0)}</text>`;}
  for(const c of channels) svg+=`<path class="${c.css}" d="${c.rows.map((r,i)=>`${i?'L':'M'}${x(r.time_s).toFixed(2)},${y(r[c.key]).toFixed(2)}`).join(' ')}"/>`;
  svg+='<path class="chart-cursor" d="M40 22 V155"/><text class="chart-label" x="380" y="191" text-anchor="end">Time (s)</text>';
  return `<div class="plot"><div class="plot-title"><h3>${terminal?'Cell & terminal voltage':'Current sharing'}</h3><span>${unit} · ${terminal?'pk − nk':'discharge positive'}</span></div><svg viewBox="0 0 400 198" role="img" aria-label="${terminal?'Voltage':'Branch current'} versus time, saved simulated outputs">${svg}</svg><div class="legend">${ids.map((id,i)=>`<span><i class="dot c${i+1}"></i>${h(state.info.design.cells[id].identity)}</span>`).join('')}${terminal?'<span>┄ Module p1 − n1</span>':''}</div></div>`;
}
function renderCharts(){ $('plots').innerHTML=chart('current_A','A')+chart('voltage_V','V',true); }
function setTime(index) {
  const rows=state.series?.module.rows;if(!rows?.length)return;
  state.index=Math.max(0,Math.min(index,rows.length-1));$('time').value=state.index;
  const t=rows[state.index].time_s;$('time-label').textContent=`${n(t,2)} s`;
  const x=40+(t-rows[0].time_s)/(rows.at(-1).time_s-rows[0].time_s||1)*340;
  document.querySelectorAll('.chart-cursor').forEach(e=>e.setAttribute('d',`M${x} 22 V155`));drawCanvas();updateReadout();
}
function updateReadout() {
  const el=$('selection-readout');if(!el)return;
  const row=state.series?.[state.selected]?.rows[state.index];
  if(!state.run||!row){el.innerHTML='<strong>Saved simulation readout</strong><p>Select a run and time to inspect cell or module values. Rail channels are included in exported results.</p>';return;}
  const module=state.selected==='module';
  if(state.selected.startsWith('rail_')){el.innerHTML=`<strong>${h(state.run.run_id)} / ${h(state.run.freshness)} / ${n(row.time_s,2)} s</strong><p>${n(row.current_A)} A · ${n(row.voltage_drop_V*1000)} mV drop</p><p>${n(row.loss_W,4)} W electrical loss</p><p>${state.selected.includes('_p_')?'Current toward p1; drop toward p1.':'Current outward from n1; drop outward from n1.'}</p>`;return;}
  el.innerHTML=`<strong>${h(state.run.run_id)} / ${h(state.run.freshness)} / ${n(row.time_s,2)} s</strong><p>${n(row.current_A)} A · ${n(module?row.terminal_V:row.voltage_V)} V</p>${module?`<p>${n(row.power_W,2)} W · ${n(row.delivered_net_Wh)} Wh</p>`:`<p>${n(row.soc*100,2)}% SOC · ${n(row.polarization_V*1000,2)} mV polarization</p>`}`;
}

async function waitJob(id) {
  for(;;){const job=await request('/api/jobs/'+id);if(job.state==='completed'||job.state==='failed'){
    if(job.response.status!=='ok')throw new Error(job.response.error.message);return job.response.result;
  }notice(`${job.operation==='run'?'Simulating electrical behaviour':'Preparing reproducible export'}… ${Math.max(0,Math.round(Date.now()/1000-job.started_at))} s elapsed.`, 'busy');await new Promise(resolve=>setTimeout(resolve,600));}
}
async function runSimulation() {
  state.busy=true;assistant.changed();buttons();const variant=state.variant;
  try{const {job_id}=await request('/api/jobs',{operation:'run',arguments:{variant_id:variant,expected_revision:state.info.revision_id,scenario_id:state.scenario}});
    const result=await waitJob(job_id);
    if(state.variant===variant) await refresh(variant,result.run_id);else await catalogRuns();
    notice(result.execution_status==='failed'?`Simulation stopped. ${result.run_id} preserves the failure and any valid partial outputs.`:`Saved ${variant} / ${result.run_id}. Experimental module validation remains pending.`,result.execution_status==='failed'?'error':'');
  }finally{state.busy=false;buttons();evidence.refreshIfVisible();}
}
async function compareRuns() {
  const selections=[$('compare-first').value,$('compare-second').value].map(id=>state.catalog.find(r=>r.run_id===id)).map(r=>({variant_id:r.variant_id,run_id:r.run_id}));
  if(selections[0].run_id===selections[1].run_id)throw new Error('Select two different runs.');
  const result=await api('compare',{selections});
  const labels={maximum_branch_current_A:['Peak branch current','A'],minimum_cell_voltage_V:['Minimum cell voltage','V'],minimum_terminal_voltage_V:['Minimum terminal voltage','V'],mean_delivered_power_W:['Mean delivered power','W'],delivered_net_Wh:['Delivered net energy','Wh'],delivered_charge_Ah:['Delivered charge','Ah'],cell_R0_loss_Wh:['Cell R₀ loss','Wh'],rail_loss_Wh:['Rail loss','Wh'],R1_loss_Wh:['Polarization R₁ loss','Wh'],above_4_9A_cell_seconds:['Time above 4.9 A','cell·s']};
  const [a,b]=result.ordered_results,delta=result.deltas_vs_first[0];
  $('comparison').innerHTML=`<div class="evidence-banner"><strong>Simulation comparison · ${h(result.conditions)}</strong><p>${h(result.evidence)}${result.historical_results?' Includes outdated results.':''}</p></div><div class="table-wrap"><table><thead><tr><th>Metric</th><th>${h(a.variant_id)} / ${h(a.run_id)}</th><th>${h(b.variant_id)} / ${h(b.run_id)}</th><th>Second − first</th></tr></thead><tbody>${Object.entries(labels).map(([k,[name,unit]])=>`<tr><td>${name} (${unit})</td><td>${n(a[k],4)}</td><td>${n(b[k],4)}</td><td>${n(delta[k],4)}</td></tr>`).join('')}<tr><td>Requirements</td><td>${h(a.requirement)}</td><td>${h(b.requirement)}</td><td>—</td></tr><tr><td>Result status</td><td>${h(a.freshness)}</td><td>${h(b.freshness)}</td><td>—</td></tr></tbody></table></div><p class="evidence-note">No repair ranking or demonstrated battery-performance gain. Reduced load changes delivered service and cannot use this like-for-like comparison.</p>`;
}
function exportDialog() {
  $('export-choices').innerHTML=state.catalog.map(r=>`<label><input type="checkbox" value="${h(r.run_id)}" ${r.run_id===state.run?.run_id?'checked':''}>${h(viewLabel(r))}</label>`).join('');
  $('export-error').textContent='';$('download').textContent='';$('export-dialog').showModal();
}
async function exportRuns() {
  const checked=[...$('export-choices').querySelectorAll('input:checked')].map(el=>el.value);
  if(!checked.length)throw new Error('Select at least one saved run.');
  const selections=checked.map(id=>state.catalog.find(r=>r.run_id===id)).map(r=>({variant_id:r.variant_id,run_id:r.run_id}));
  state.busy=true;assistant.changed();buttons();
  try{const {job_id}=await request('/api/jobs',{operation:'export',arguments:{selections}});const result=await waitJob(job_id);
    $('download').innerHTML=`<a href="${h(result.download_url)}" download>Download result package (.zip)</a><p>Includes replay.py and manifest hashes. No original raw archive.</p>`;notice('Reproducible package ready. Use the download link to save it.');
  }finally{state.busy=false;buttons();}
}

async function saveDisplay() {
  const display={...state.display,selection:[state.selected]};
  await api('update_display',{display});state.display=display;
  notice('Layout saved. Electrical parameters, design revision and run freshness are unchanged.');
}
let drag=null;
$('canvas').addEventListener('pointerdown',e=>{
  const group=e.target.closest('[data-component]');if(!group)return;
  const id=group.dataset.component;
  if(!id.startsWith('cell_')||state.busy||state.action)return;
  const point=new DOMPoint(e.clientX,e.clientY).matrixTransform($('canvas').getScreenCTM().inverse());
  drag={id,start:point,origin:position(ids.indexOf(id)),moved:false};$('canvas').setPointerCapture(e.pointerId);
});
$('canvas').addEventListener('pointermove',e=>{
  if(!drag)return;
  const point=new DOMPoint(e.clientX,e.clientY).matrixTransform($('canvas').getScreenCTM().inverse());
  if(Math.abs(point.x-drag.start.x)+Math.abs(point.y-drag.start.y)<4&&!drag.moved)return;
  drag.moved=true;state.display.positions[drag.id]=[Math.max(110,Math.min(780,drag.origin[0]+point.x-drag.start.x)),Math.max(132,Math.min(176,drag.origin[1]+point.y-drag.start.y))];drawCanvas();
});
function finishDrag(){if(!drag)return;const old=drag;drag=null;selectComponent(old.id);if(old.moved)action(saveDisplay);}
$('canvas').addEventListener('pointerup',finishDrag);$('canvas').addEventListener('pointercancel',finishDrag);
$('canvas').addEventListener('click',e=>{const el=e.target.closest('[data-component]');if(el&&!drag)selectComponent(el.dataset.component);});
$('canvas').addEventListener('keydown',e=>{
  const id=e.target.closest('[data-component]')?.dataset.component;if(!id)return;
  if(e.key==='Enter'||e.key===' '){e.preventDefault();selectComponent(id);$('canvas').querySelector(`[data-component="${id}"]`)?.focus();}
  if(id.startsWith('cell_')&&e.key.startsWith('Arrow')&&!state.busy&&!state.action){e.preventDefault();const [x,y]=position(ids.indexOf(id));if(state.selected!==id)selectComponent(id);state.display.positions[id]=[Math.max(110,Math.min(780,x+(e.key==='ArrowRight'?10:e.key==='ArrowLeft'?-10:0))),Math.max(132,Math.min(176,y+(e.key==='ArrowDown'?5:e.key==='ArrowUp'?-5:0)))];drawCanvas();$('canvas').querySelector(`[data-component="${id}"]`)?.focus();action(saveDisplay);}
});
$('variants').addEventListener('click',e=>{const el=e.target.closest('[data-variant]');if(el)action(async()=>{await refresh(el.dataset.variant);notice(`Opened ${el.dataset.variant}. Only this variant’s current runs are selected automatically.`);});});
$('components').addEventListener('click',e=>{const el=e.target.closest('[data-component]');if(el)selectComponent(el.dataset.component);});
$('mobile-component').addEventListener('change',()=>selectComponent($('mobile-component').value));
$('inspector-content').addEventListener('change',e=>{if(e.target.id==='edit-property')renderEditFields();else if(e.target.id==='scenario'){state.scenario=e.target.value;notice(`Next run: ${scenarios[state.scenario]}. The displayed run has not changed.`);}else invalidatePreview();});
$('inspector-content').addEventListener('input',e=>{if(e.target.id!=='scenario')invalidatePreview();});
$('inspector-content').addEventListener('click',e=>{if(e.target.id==='preview-edit')action(async()=>{try{await previewEdit();}catch(err){$('edit-feedback').innerHTML=`<p class="error" role="alert">${h(err.message)}</p>`;throw err;}});if(e.target.id==='apply-edit')action(applyEdit);});
$('run').addEventListener('click',()=>action(runSimulation));
$('run-select').addEventListener('change',()=>action(()=>loadRun($('run-select').value)));
$('overlay').addEventListener('change',drawCanvas);
$('time').addEventListener('input',()=>setTime(Number($('time').value)));
$('previous-page').addEventListener('click',()=>action(()=>loadRun(state.run.run_id,Math.max(0,state.offset-5000))));
$('next-page').addEventListener('click',()=>action(()=>loadRun(state.run.run_id,state.series.module.next_offset)));
$('reset-layout').addEventListener('click',()=>action(async()=>{state.display.positions={};drawCanvas();await saveDisplay();}));
for(const name of ['results','evidence','compare']) $('tab-'+name).addEventListener('click',()=>{
  for(const n of ['results','evidence','compare']){$('tab-'+n).setAttribute('aria-selected',n===name?'true':'false');$('panel-'+n).hidden=n!==name;}
  if(name==='evidence')void evidence.refresh();
});
document.querySelector('.tabs').addEventListener('keydown',e=>{const tabs=[...document.querySelectorAll('[role=tab]')];let i=tabs.indexOf(document.activeElement);if(i<0)return;if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();i=e.key==='Home'?0:e.key==='End'?2:(i+(e.key==='ArrowRight'?1:2))%3;tabs[i].focus();tabs[i].click();}});
$('compare').addEventListener('click',()=>action(async()=>{ $('comparison').textContent='';await compareRuns(); }));
for(const id of ['compare-first','compare-second'])$(id).addEventListener('change',()=>{$('comparison').textContent='';assistant.changed();});
$('new-variant').addEventListener('click',()=>{let i=1;while(state.info.variants['A'+i])i++;$('variant-id').value='A'+i;$('variant-name').value='Connection study';$('variant-error').textContent='';$('variant-dialog').showModal();$('variant-id').focus();});
$('cancel-variant').addEventListener('click',()=>$('variant-dialog').close());
$('variant-form').addEventListener('submit',e=>{e.preventDefault();action(async()=>{try{const id=$('variant-id').value;await api('create_variant',{source_variant:state.variant,variant_id:id,name:$('variant-name').value,expected_revision:state.info.revision_id});$('variant-dialog').close();await refresh(id);notice(`Created ${id}. Inherited results are outdated for this variant; run it to obtain owned results.`);}catch(err){$('variant-error').textContent=err.message;}});});
$('export').addEventListener('click',exportDialog);$('close-export').addEventListener('click',()=>$('export-dialog').close());
$('make-export').addEventListener('click',()=>action(async()=>{try{$('export-error').textContent='';await exportRuns();}catch(err){$('export-error').textContent=err.message;}}));

try {
  const session=await request('/api/session');state.token=session.token;$('project-location').textContent=session.project;
  await refresh();notice('Reference project ready. Select a component to inspect it, or run the proposed operating case.');
  if(session.active_job){state.busy=true;assistant.changed();buttons();try{await waitJob(session.active_job);await refresh();notice('Previous job finished. Saved runs are available.');}finally{state.busy=false;buttons();}}
} catch(e) {notice(e.message,'error');}
