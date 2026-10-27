import {escapeHTML as h, chooseRun, bounds, RequestEpoch, number as n, finiteInput, failureMessage} from './state.mjs';
import {assemblySVG} from './assembly.mjs';
import {requirementsHTML, rangeOf, investigationFormHTML, parsePlan, investigationHTML} from './panels.mjs';
import {loadProfile, durationLabel, componentLabel, resultLabel, limitLabel} from './workspace.mjs';

const $ = id => document.getElementById(id);
const ids = ['cell_1','cell_2','cell_3','cell_4'];
const scenarios = {nominal:'Nominal design', soc_minus_2pp:'Sensitivity: SOC −2 points', soc_plus_2pp:'Sensitivity: SOC +2 points',
  capacity_minus_1pct:'Sensitivity: capacity −1%', capacity_plus_1pct:'Sensitivity: capacity +1%',
  polarization_minus_5mV:'Sensitivity: polarization −5 mV', polarization_plus_5mV:'Sensitivity: polarization +5 mV',
  loaded_reference_shape:'Sensitivity: loaded reference shape'};
const THERMAL = {heat_capacity:{label:'Heat capacity, 4 cells (J/K)',key:'heat_capacity_J_per_K',unit:'J/K',count:4,input:'Cells 1–4 (J/K), comma-separated'},
  ambient_conductance:{label:'Cell-to-ambient conductance, 4 cells (W/K)',key:'ambient_conductance_W_per_K',unit:'W/K',count:4,input:'Cells 1–4 (W/K), comma-separated'},
  neighbour_conductance:{label:'Neighbour conductance, 3 pairs (W/K)',key:'neighbour_conductance_W_per_K',unit:'W/K',count:3,input:'Pairs 1–2, 2–3, 3–4 (W/K), comma-separated'},
  rail_heat_to_cells_fraction:{label:'Rail heat to cells (fraction)',key:'rail_heat_to_cells_fraction',unit:'fraction',count:0,input:'Fraction from 0 to 1'}};
const LIMITS = {peak_branch_current:{name:'Peak branch current',label:'Peak branch current (A)',key:'peak_branch_current_A',unit:'A',show:'A'},
  current_imbalance:{name:'Current imbalance',label:'Current imbalance (%)',key:'current_imbalance_pct',unit:'%',show:'%'},
  peak_cell_temperature:{name:'Peak cell temperature',label:'Peak cell temperature (°C)',key:'peak_cell_temperature_C',unit:'degC',show:'°C'}};
const subOptions = (table,sub) => Object.entries(table).map(([key,t])=>`<option value="${key}"${key===sub?' selected':''}>${t.label}</option>`).join('');
const state = {token:'', info:null, variant:'A0', selected:'module', scenario:'nominal', run:null, series:null,
  index:0, offset:0, busy:false, action:false, preview:null, catalog:[], display:null, view:'assembly', subProperty:'', investigation:null, chart:'current', dirty:false};
const designEpoch = new RequestEpoch(), seriesEpoch = new RequestEpoch();
const editorDrafts = new Map();
const editorKey = () => `${state.variant}/${state.selected}`;
function rememberEditor() {
  if(!state.info||!state.dirty||!$('edit-property'))return;
  editorDrafts.set(editorKey(),{html:$('inspector-content').innerHTML,sub:state.subProperty,
    fields:[...$('inspector-content').querySelectorAll('input,select,textarea')].map(e=>({key:e.id||e.name,value:e.value}))});
}

let noticeTimer;
function notice(message, kind='') {
  clearTimeout(noticeTimer);$('notice').textContent=message;$('notice').className='notice '+kind;
  $('notice').setAttribute('role',kind==='error'?'alert':'status');
  if(message&&kind!=='busy'&&kind!=='error') noticeTimer=setTimeout(()=>{$('notice').textContent='';},6000);
}
async function request(path, body) {
  const response = await fetch(path, body ? {method:'POST',headers:{'Content-Type':'application/json','X-Voltforge-Token':state.token},body:JSON.stringify(body)} : {});
  let data;
  try { data=await response.json(); } catch { throw new Error('The local server stopped responding. Restart it, then reload this page.'); }
  if (data.status !== 'ok') throw new Error(data.error?.message || `Request failed: ${response.statusText}. Try again.`);
  return data.result;
}
const api = (operation, arguments_={}) => request('/api/request',{operation,arguments:arguments_});
function buttons() {
  const locked=state.busy||state.action||!state.info;
  for(const id of ['run','new-variant','reset-layout','preview-edit','apply-edit','inv-run']) if($(id)) $(id).disabled=locked||(id==='apply-edit'&&!state.preview);
  $('export').disabled=locked||!state.catalog.length;
  $('run-select').disabled=locked;
  $('run').disabled=locked||state.dirty;
  $('run').title=state.dirty?'Preview and save the pending change before running.':'';
  if($('discard-edit')) $('discard-edit').hidden=!state.dirty;
  $('run').innerHTML=state.busy?'Working…':'<svg viewBox="0 0 20 20" aria-hidden="true"><path d="m7 4 9 6-9 6Z"/></svg><span>Run simulation</span>';
  $('make-export').disabled=locked;
}
async function action(fn) {
  if(state.action||state.busy) return;
  state.action=true; buttons();
  try { await fn(); } catch(e) { notice(e.message,'error'); }
  finally { state.action=false; buttons(); }
}

async function refresh(variant=state.variant, preferred='') {
  const epoch=designEpoch.begin(); seriesEpoch.begin();
  state.run=null;state.series=null;state.preview=null; renderResults(); drawCanvas();
  $('comparison').textContent='';state.investigation=null;$('investigation-results').innerHTML='';
  const info=await api('inspect',{variant_id:variant});
  if(!designEpoch.current(epoch)) return;
  state.info=info;state.variant=variant;state.display=structuredClone(info.display);state.dirty=false;
  $('variant-title').textContent=info.name==='Reference A0'?'Reference module':info.name;
  $('variant-id').textContent=variant;
  $('physics-mode').textContent=info.capabilities.thermal?'Electrical + thermal':'Electrical only';
  $('revision').textContent='4 × LG M50T · Parallel module (1s4p)';
  $('revision').title=`Design revision ${info.revision_id}`;
  const load=info.design.scenario.load_profile;
  $('operating-summary').textContent=`${load.length===1?`${n(load[0].current_A,2)} A load`:`${load.length} load intervals`} · ${durationLabel(load.at(-1).end_s)} · ${n(info.design.scenario.temperature.assumed_ambient_C,1)} °C ambient`;
  renderNavigation(); renderInspector(); renderInvestigationForm(); renderRunPicker(); setView(state.view); buttons();
  const picked=chooseRun(info,state.scenario,preferred);
  $('run-select').value=picked;
  if(picked) await loadRun(picked);
  if(!designEpoch.current(epoch)) return;
  await catalogRuns(epoch);
  await showLatestInvestigation(epoch);
}
async function catalogRuns(epoch=designEpoch.value) {
  const infos=await Promise.all(Object.keys(state.info.variants).map(variant_id=>api('inspect',{variant_id})));
  if(!designEpoch.current(epoch)) return;
  state.catalog=infos.flatMap(i=>i.runs.filter(r=>r.owner_variant_id===i.variant_id).map(r=>({...r,variant_id:i.variant_id})));
  const completed=state.catalog.filter(r=>r.execution_status==='completed');
  for(const id of ['compare-first','compare-second']) {
    const old=$(id).value;
    $(id).innerHTML=['current','outdated'].map(freshness=>`<optgroup label="${freshness==='current'?'Current results':'Earlier results'}">${completed.filter(r=>r.freshness===freshness).toReversed().map(r=>`<option value="${h(r.run_id)}">${h(resultLabel(r))}</option>`).join('')}</optgroup>`).join('');
    if(completed.some(r=>r.run_id===old)) $(id).value=old;
    else {
      const preferred=completed.filter(r=>r.owner_variant_id===(id==='compare-first'?'A0':state.variant)&&r.freshness==='current').at(-1);
      if(preferred) $(id).value=preferred.run_id;
    }
  }
  if(state.run?.execution_status==='completed') $('compare-second').value=state.run.run_id;
  $('compare').disabled=completed.length<2;
  buttons();
}
function renderNavigation() {
  $('variants').innerHTML=Object.entries(state.info.variants).map(([id,v])=>`<button class="nav-item ${id===state.variant?'active':''}" data-variant="${h(id)}" aria-current="${id===state.variant?'true':'false'}"><strong>${h(id)}</strong><small>${h(v.name)}</small></button>`).join('');
  const items=[['module','Module & operating conditions',0],...ids.map((id,i)=>[id,`Cell ${i+1} · ${state.info.design.cells[id].identity}`,i+1]),...Object.keys(state.info.design.connections).map(id=>[id,componentLabel(id),0])];
  $('components').innerHTML=items.map(([id,label,c])=>`<button class="nav-item component ${id===state.selected?'active':''}" data-component="${h(id)}"><i class="dot c${c}"></i>${h(label)}</button>`).join('');
}
function inspectorOpen(open=true, scroll=false) {
  document.querySelector('.workbench').dataset.inspector=open?'open':'closed';
  $('toggle-inspector').setAttribute('aria-expanded',String(open));
  if(open&&scroll&&innerWidth<=1000) $('inspector').scrollIntoView({block:'start'});
}
function selectComponent(id) { rememberEditor();state.selected=id;state.preview=null;state.subProperty='';renderNavigation();renderInspector();drawCanvas();inspectorOpen(true,true);$('project-panel').hidePopover(); }
function setView(v){state.view=v;$('view-assembly').setAttribute('aria-pressed',String(v==='assembly'));$('view-circuit').setAttribute('aria-pressed',String(v==='circuit'));$('reset-layout').hidden=v!=='circuit';const voltage=$('overlay').querySelector('option[value="voltage"]');if(voltage)voltage.disabled=v==='assembly';if(v==='assembly'&&$('overlay').value==='voltage')$('overlay').value='current';drawCanvas();}

function position(i) { return state.display?.positions[ids[i]] || [190+i*180,155]; }
function drawCanvas() {
  if(!state.info) return;
  if(state.view==='assembly'){
    const overlay=$('overlay').value,key={temperature:'temperature_C',current:'current_A'}[overlay]||null;
    const unit={temperature:'°C',current:'A'}[overlay]||'',values={};
    if(key)for(const id of ids){const row=state.series?.[id]?.rows[state.index];values[id]=row&&Number.isFinite(row[key])?row[key]:null;}
    const kind=key&&ids.some(id=>Number.isFinite(values[id]))?overlay:'none';
    $('canvas').innerHTML=assemblySVG({design:state.info.design,values,overlay:kind,unit,range:key&&state.series?rangeOf(state.series,key):[0,1],selected:state.selected,time_s:state.series?.module?.rows[state.index]?.time_s??null});
    caption();return;
  }
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
    const val=overlay==='none'?'':row?(overlay==='temperature'?(Number.isFinite(row.temperature_C)?`${n(row.temperature_C,2)} °C`:'—'):overlay==='voltage'?`${n(row.voltage_V)} V`:`${n(row.current_A)} A`):'—';
    return `<g class="cell-group c${i+1} ${state.selected===id?'selected':''}" data-component="${id}" role="button" tabindex="0" aria-label="Cell ${i+1}, ${c.identity}. Select to inspect. Arrow keys move display when selected."><path class="wire" d="M${x} ${y-99} V${y-62} M${x} ${y+62} V${y+99}"/><circle class="node" cx="${x}" cy="${y-99}" r="4"/><circle class="node" cx="${x}" cy="${y+99}" r="4"/><text class="node-label" x="${x+9}" y="${y-90}">p${i+1}</text><text class="node-label" x="${x+9}" y="${y+92}">n${i+1}</text><rect class="cell-body" x="${x-61}" y="${y-62}" width="122" height="124" rx="9"/><rect class="cell-accent" x="${x-60}" y="${y-48}" width="4" height="29" rx="2"/><text class="cell-title" x="${x-44}" y="${y-29}">${h(c.identity)}</text><text class="cell-sub" x="${x-44}" y="${y-10}">Cell ${i+1} · LG M50T</text><path class="cell-symbol" d="M${x+35} ${y-48} v18 m-5 -9 h10"/><text class="cell-value" x="${x-44}" y="${y+21}">${h(val)}</text><text class="cell-sub" x="${x-44}" y="${y+43}">${row?`${n(row.soc*100,1)}% SOC`:`Start ${n(c.initial_soc.value*100,1)}% SOC`}</text></g>`;
  }).join('');
  $('canvas').innerHTML=svg;caption();
}
function caption() {
  for(const component of $('canvas').querySelectorAll('[data-component]'))component.setAttribute('aria-pressed',String(component.dataset.component===state.selected));
  $('canvas').setAttribute('aria-label',state.view==='assembly'?'Four-cell isometric assembly':'Four-cell electrical circuit');
  $('canvas-help').textContent=state.view==='assembly'?'Select a cell or connection to inspect it. Geometry is illustrative.':'Select a cell or connection. Dragging changes the drawing only.';
  $('overlay-state').textContent=state.run?`${state.run.freshness==='outdated'?'Historical / ':''}${state.run.execution_status==='failed'?'Failed / partial / ':''}${state.run.owner_variant_id} ${state.run.run_id} at ${n(state.series?.module?.rows[state.index]?.time_s,2)} s`:'No simulation selected';
}

function field(label,id,value,type='number',extra='') { return `<label>${label}<input id="${id}" name="${id}" type="${type}" value="${h(value)}" autocomplete="off" ${extra}></label>`; }
function renderInspector() {
  if(!state.info) return;
  state.dirty=false;
  const d=state.info.design,id=state.selected,c=d.cells[id],edge=d.connections[id];
  let content='', options='';
  $('inspector-heading').textContent=c?'Cell properties':edge?'Connection properties':'Operating conditions';
  const draft=editorDrafts.get(editorKey());
  if(draft){
    $('inspector-content').innerHTML=draft.html;state.subProperty=draft.sub;
    const controls=[...$('inspector-content').querySelectorAll('input,select,textarea')];
    for(const field of draft.fields){const e=controls.find(e=>(e.id||e.name)===field.key);if(e)e.value=field.value;}
    state.dirty=true;invalidatePreview();updateReadout();return;
  }
  if(c) {
    const p=state.info.fitted_parameters[id];
    content=`<div class="inspector-title">Cell ${id.at(-1)} <span class="muted">· ${h(c.identity)}</span></div><p class="property-description">LG M50T. Change its starting state to explore how the cells share the load.</p><details class="model-details"><summary>Fitted cell model</summary><dl><dt>Ohmic resistance R₀</dt><dd>${n(p.R0_ohm*1000)} mΩ</dd><dt>Polarization R₁</dt><dd>${n(p.R1_ohm*1000)} mΩ</dd><dt>Time constant</dt><dd>${n(p.tau_s,2)} s</dd><dt>Measured capacity</dt><dd>${n(p.capacity_Ah)} Ah</dd></dl><p>Frozen v2 fitted parameters. These values are read-only. Initial charge is relative to the cell’s recorded voltage reference.</p><p>${h(c.positive_node)} to ${h(c.negative_node)} · ${h(c.identity)}</p></details>`;
    options='<option value="soc">Initial state of charge</option><option value="polarization">Initial polarization</option>';
  } else if(edge) {
    content=`<div class="inspector-title">${h(componentLabel(id))}</div><p class="property-description">Resistance affects current sharing and electrical losses. This is an effective connection resistance, including represented contacts.</p><details class="model-details"><summary>Connection source & nodes</summary><p>${h(edge.node_a)} to ${h(edge.node_b)} · ${h(id)}</p><p>${h(edge.resistance.classification)} · ${h(edge.resistance.source)}</p><p>Changing the value is a design assumption. Moving a component does not change this resistance.</p></details>`;
    options='<option value="resistance">Connection resistance</option>';
  } else {
    content='<p class="property-description">Set the load, starting temperatures and limits for this four-cell module.</p>';
    options='<option value="load">Load & duration</option><option value="temperature">Starting temperatures</option>';
    if(d.engineering_requirements) options+='<option value="limits">Engineering limits</option>';
    options+='<optgroup label="Advanced"><option value="requirements">Minimum voltage requirement</option>';
    if(d.thermal) options+='<option value="thermal">Thermal model parameters</option>';
    options+='<option value="step">Solver time step</option></optgroup>';
  }
  $('inspector-content').innerHTML=content+`<label class="property-picker">${c||edge?'Edit property':'Configure'}<select id="edit-property" name="edit-property">${options}</select></label><div id="edit-fields"></div><details class="provenance-fields"><summary>Assumptions & source</summary><label>Input classification<select id="classification" name="classification"><option value="assumed">Assumed</option><option value="proposed_requirement">Proposed requirement</option><option value="user_declared_measurement">User-declared measurement</option></select></label><label>Source or reason<input id="edit-source" name="edit-source" value="Exploratory design change" maxlength="500" autocomplete="off"></label><p>Saved with this change so its assumptions can be reviewed.</p></details><div class="form-actions"><button id="preview-edit">Preview change</button><button id="apply-edit" class="primary" disabled>Save change</button></div><button id="discard-edit" class="text-button" type="button" hidden>Discard unsaved change</button><div id="edit-feedback" aria-live="polite" tabindex="-1"></div><section class="selection-section"><h3>At the selected time</h3><div class="selection-readout" id="selection-readout"></div></section><details class="scenario-box"><summary>Sensitivity experiments</summary><label>Next simulation<select id="scenario" name="scenario">${Object.entries(scenarios).map(([id,label])=>`<option value="${id}" ${id===state.scenario?'selected':''}>${label}</option>`).join('')}</select></label><p>These test a declared assumption without changing the design. They are not confidence intervals.</p></details>`;
  renderEditFields();updateReadout();buttons();
}
function loadDraft() {
  return [...$('edit-fields').querySelectorAll('.load-interval')].map(row=>({duration:row.querySelector('[data-load-duration]').value,current:row.querySelector('[data-load-current]').value}));
}
function renderLoadFields(profile) {
  $('load-rows').innerHTML=profile.map((row,i)=>`<fieldset class="load-interval"><legend>${profile.length>1?`Interval ${i+1}`:'Constant current'}</legend><div class="load-fields"><label>Current (A)<input data-load-current name="load-current-${i}" type="number" value="${h(row.current_A)}" step="any" autocomplete="off"></label><label>Duration (s)<input data-load-duration name="load-duration-${i}" type="number" value="${h(row.end_s-row.start_s)}" min="0.000001" step="any" autocomplete="off"></label></div>${profile.length>1?`<button class="text-button remove-interval" data-interval="${i}" type="button">Remove interval</button>`:''}</fieldset>`).join('');
}
function renderEditFields() {
  state.dirty=false;
  const d=state.info.design,c=d.cells[state.selected],prop=$('edit-property').value;
  let html='';
  if(prop==='resistance') html=field('Resistance (mΩ)','edit-value',d.connections[state.selected].resistance.value*1000,'number','min="0" step="any"')+'<p class="field-hint">1 mΩ = 0.001 Ω. This changes the effective resistance of the selected connection.</p>';
  if(prop==='soc') html=field('Initial state of charge (%)','edit-value',c.initial_soc.value*100,'number','min="0" max="100" step="any"');
  if(prop==='polarization') html=field('Initial polarization (mV)','edit-value',c.initial_polarization.value*1000,'number','step="any"')+'<p class="field-hint">The starting voltage of the cell’s polarization element, relative to its recorded reference.</p>';
  if(prop==='step') html=field('Maximum time step (s)','edit-value',d.simulation.dt_s,'number','min="0.000001" step="any"')+'<p class="field-hint">Smaller steps produce more saved samples and take longer to run.</p>';
  if(prop==='load') html='<div id="load-rows"></div><button id="add-interval" class="text-button" type="button">Add another interval</button><p class="field-hint">Positive current discharges the module. Negative current charges it. Use 0 A for a rest.</p>';
  if(prop==='temperature') html=field('Ambient temperature (°C)','edit-value',d.scenario.temperature.assumed_ambient_C,'number','step="any"')+'<p class="field-hint">Starting cell surface temperatures</p><div class="load-fields">'+d.scenario.temperature.assumed_surface_C.map((v,i)=>field(`Cell ${i+1} (°C)`,`surface-${i}`,v,'number','step="any"')).join('')+'</div><p class="field-hint">The thermal model uses these assumptions. It does not change electrical parameters with temperature.</p>';
  if(prop==='requirements') html=field('Minimum terminal voltage (V)','minimum-voltage',d.requirements.minimum_terminal_voltage_V??'','number','step="any"')+field('Permitted time below it (s)','excursion',d.requirements.maximum_contiguous_excursion_s??'','number','min="0" step="any"')+field('Requirement source','requirement-source',d.requirements.documented_source??'','text')+'<p class="field-hint">Leave unknown values blank. The requirement is only configured when all fields are supplied.</p>';
  if(prop==='thermal') {
    const sub=Object.hasOwn(THERMAL,state.subProperty)?state.subProperty:'heat_capacity',t=THERMAL[sub],q=d.thermal?.[t.key]||{};
    html=`<label>Thermal parameter<select id="thermal-property" name="thermal-property">${subOptions(THERMAL,sub)}</select></label>`+(t.count?'<div class="load-fields">'+q.value.map((v,i)=>field(`${sub==='neighbour_conductance'?`Cells ${i+1}–${i+2}`:`Cell ${i+1}`} (${t.unit})`,`thermal-value-${i}`,v,'number','min="0" step="any"')).join('')+'</div>':field('Heat fraction delivered to cells','edit-value',q.value??'','number','min="0" max="1" step="any"'))+`<details class="model-details"><summary>Model assumptions & source</summary><p>${h(q.source||'Declared thermal parameters')}</p><p>One surface-equivalent node per cell. Temperature does not feed back into the electrical model. Reversible heat is omitted. Not experimentally validated.</p></details>`;
  }
  if(prop==='limits') {
    const sub=Object.hasOwn(LIMITS,state.subProperty)?state.subProperty:'peak_branch_current',l=LIMITS[sub],q=d.engineering_requirements?.[l.key]||{};
    html=`<label>Limit to configure<select id="limit-property" name="limit-property">${subOptions(LIMITS,sub)}</select></label>`+field(`Upper limit (${l.show})`,'limit-value',q.limit??'','number','step="any"')+field('Source of this limit','limit-source',q.documented_source??'','text','maxlength="500"')+'<p class="field-hint">A requirement, datasheet reference or clearly stated proposal. Both fields are required to set a limit. Leave the value blank to clear it.</p>';
    $('classification').value='proposed_requirement';
  }
  $('edit-fields').innerHTML=html;
  if(prop==='load') renderLoadFields(d.scenario.load_profile);
  invalidatePreview();
}
function invalidatePreview(){state.preview=null;if($('edit-feedback')) $('edit-feedback').textContent=state.dirty?'Preview and save this change before running a simulation.':'';buttons();}
function collectEdit() {
  const prop=$('edit-property').value,id=state.selected,d=state.info.design;
  const source=$('edit-source').value.trim(); if(!source) throw new Error('Add a source or reason for this input.');
  const edit={target:'cell',id,property:'initial_soc',value:null,unit:'fraction',source,classification:$('classification').value};
  if(prop==='resistance') Object.assign(edit,{target:'connection',property:'resistance',unit:'ohm',value:finiteInput($('edit-value').value)/1000});
  if(prop==='soc') edit.value=finiteInput($('edit-value').value)/100;
  if(prop==='polarization') Object.assign(edit,{property:'initial_polarization',unit:'V',value:finiteInput($('edit-value').value)/1000});
  if(prop==='load') Object.assign(edit,{target:'scenario',property:'load_profile',unit:'A,s',value:loadProfile(loadDraft())});
  if(prop==='temperature') Object.assign(edit,{target:'scenario',property:'temperature',unit:'degC',value:{...d.scenario.temperature,assumed_ambient_C:finiteInput($('edit-value').value),assumed_surface_C:ids.map((_,i)=>finiteInput($('surface-'+i).value))}});
  if(prop==='step') Object.assign(edit,{target:'simulation',property:'dt_s',unit:'s',value:finiteInput($('edit-value').value)});
  if(prop==='requirements') Object.assign(edit,{target:'requirements',property:'voltage_requirement',unit:'V,s',value:{minimum_terminal_voltage_V:$('minimum-voltage').value.trim()?finiteInput($('minimum-voltage').value):null,maximum_contiguous_excursion_s:$('excursion').value.trim()?finiteInput($('excursion').value):null,documented_source:$('requirement-source').value.trim()||null}});
  if(prop==='thermal') {
    const sub=$('thermal-property').value; if(!Object.hasOwn(THERMAL,sub)) throw new Error('Choose a thermal parameter.');
    const t=THERMAL[sub],value=t.count?Array.from({length:t.count},(_,i)=>finiteInput($('thermal-value-'+i).value)):finiteInput($('edit-value').value);
    if(t.count&&value.length!==t.count) throw new Error(`Enter ${t.count} comma-separated numbers.`);
    Object.assign(edit,{target:'thermal',property:sub,unit:t.unit,value});
  }
  if(prop==='limits') {
    const sub=$('limit-property').value; if(!Object.hasOwn(LIMITS,sub)) throw new Error('Choose an engineering limit.');
    const raw=$('limit-value').value.trim();
    if(raw&&!$('limit-source').value.trim()){ $('limit-source').focus();throw new Error('Add the source of this limit, or label it as a proposed target.'); }
    Object.assign(edit,{target:'engineering_requirements',property:sub,unit:LIMITS[sub].unit,value:{limit:raw?finiteInput(raw):null,documented_source:$('limit-source').value.trim()||null}});
  }
  return edit;
}
async function previewEdit() {
  const args={variant_id:state.variant,edit:collectEdit(),expected_revision:state.info.revision_id};
  const preview=await api('validate_edit',args);
  if(args.variant_id!==state.variant || args.expected_revision!==state.info.revision_id || JSON.stringify(args.edit)!==JSON.stringify(collectEdit())) {
    notice('The input changed while validation was running. Preview it again.'); return;
  }
  state.preview=args;
  const edit=args.edit,prop=$('edit-property').selectedOptions[0].textContent;
  let description='';
  if(edit.target==='connection') description=`${n(state.info.design.connections[edit.id].resistance.value*1000,2)} → ${n(edit.value*1000,2)} mΩ`;
  else if(edit.property==='load_profile') description=edit.value.map(v=>`${n(v.current_A,2)} A for ${durationLabel(v.end_s-v.start_s)}`).join('; ');
  else if(edit.target==='engineering_requirements') description=edit.value.limit===null?'Clear this limit.':`${LIMITS[edit.property].name}: ${n(edit.value.limit,2)} ${LIMITS[edit.property].show}`;
  else if(edit.target==='thermal') description=`${THERMAL[edit.property].label}: ${Array.isArray(edit.value)?edit.value.map(v=>n(v,4)).join(', '):n(edit.value,4)}`;
  else if(edit.property==='initial_soc') description=`${n(edit.value*100,2)}% initial state of charge`;
  else if(edit.property==='initial_polarization') description=`${n(edit.value*1000,2)} mV initial polarization`;
  else if(edit.property==='temperature') description=`Ambient ${n(edit.value.assumed_ambient_C,1)} °C; cells ${edit.value.assumed_surface_C.map(v=>n(v,1)).join(', ')} °C`;
  else if(edit.property==='dt_s') description=`Maximum time step: ${n(edit.value,4)} s`;
  else description=prop;
  const count=preview.invalidated_run_ids.length;
  $('edit-feedback').innerHTML=`<div class="preview"><strong>${preview.physics_changed?'Ready to save':'No change to the design'}</strong><p>${h(description)}</p><p>${count?`${count} saved result${count===1?'':'s'} will be marked outdated. You can still view ${count===1?'it':'them'} in history.`:'Previous results will be retained.'}</p><details><summary>Exact change & evidence notes</summary><pre>${h(JSON.stringify(args.edit,null,2))}</pre>${(preview.warnings||[]).map(x=>`<p>${h(x)}</p>`).join('')}</details></div>`;
}
async function applyEdit() {
  if(!state.preview) return;
  const args=state.preview, preferred=state.run?.run_id||'',draftKey=editorKey();
  await api('apply_edit',args);editorDrafts.delete(draftKey);state.dirty=false; await refresh(args.variant_id,preferred);
  notice('Change saved. Run the simulation to update this design’s results.');
}

function renderRunPicker() {
  $('run-select').innerHTML='<option value="">Select a saved run</option>'+state.info.runs.toReversed().map(r=>`<option value="${h(r.run_id)}">${h(resultLabel(r))}</option>`).join('');
}
async function loadRun(run_id,offset=0) {
  const epoch=seriesEpoch.begin(),variant=state.variant;
  state.run=null;state.series=null;state.index=0;renderResults();drawCanvas();
  if(!run_id) return;
  $('run-state').textContent='Loading this run’s saved outputs…';
  const [run,...series]=await Promise.all([api('get_run',{variant_id:variant,run_id}),...state.info.output_components.map(component_id=>api('series',{variant_id:variant,run_id,component_id,offset,limit:5000}))]);
  if(!seriesEpoch.current(epoch)||variant!==state.variant) return;
  state.run=run;state.series=Object.fromEntries(series.map(s=>[s.component_id,s]));state.offset=offset;
  renderResults();drawCanvas();updateReadout();
}
function metric(label,value,unit,digits=3){return `<div class="metric"><span>${h(label)}</span><strong>${n(value,digits)}</strong><small>${h(unit)}</small></div>`;}
function renderResults() {
  const r=state.run,summary=r?.summary;
  $('run-state').className='run-state';
  $('metrics').innerHTML='';$('extra-metrics').innerHTML='';$('result-explanation').textContent='';$('timeline').hidden=true;
  if(!r) {
    $('engineering').innerHTML='';
    $('run-state').textContent=state.info?.runs.length?'No current result selected. Choose a saved run or run this design.':'Ready for your first experiment. Set the operating conditions and run the simulation.';
    $('plots').className='plots empty';$('plots').innerHTML='<div><h3>No result selected</h3><p>Run this design or select a saved run. The curves will use that run’s recorded outputs.</p></div>';
    $('metrics').hidden=true;
    $('panel-evidence').innerHTML='<div class="page-heading"><h1>Understand the model</h1><p>Run the design, then inspect its sources, model coverage and assumptions here.</p></div><div class="evidence-banner"><strong>Experimental validation pending</strong><p>The electrical model uses recorded cell fits. Thermal outputs use declared assumptions. Neither establishes validated module accuracy.</p></div>';return;
  }
  $('metrics').hidden=false;
  $('run-state').classList.add(r.freshness==='outdated'?'outdated':r.execution_status);
  $('run-state').textContent=`${r.execution_status==='failed'?'Simulation stopped. Partial results only.':r.freshness==='outdated'?'Outdated for this design. Run again to update the results.':'Current for this design'} · ${r.run_id}${r.scenario_id==='nominal'?'':' · Sensitivity experiment'}${r.error?' · '+failureMessage(r.error):''}`;
  $('run-state').title=r.outdated_reasons.join('; ');
  $('result-explanation').textContent='Whole-run results are shown below. Move the time slider to inspect an individual moment in the assembly.';
  const thermal=summary.thermal;
  $('metrics').innerHTML=metric('Peak branch current',summary.maximum_branch_current_A,'A',2)+(thermal?.status==='completed'?metric('Peak cell temperature',thermal.peak_cell_temperature_C,'°C',2):'<div class="metric unavailable"><span>Cell temperature</span><strong>Unavailable</strong><small>See model & evidence for details</small></div>')+metric('Minimum terminal voltage',summary.minimum_terminal_voltage_V,'V')+metric('Delivered energy',summary.delivered_net_Wh,'Wh',2);
  $('extra-metrics').innerHTML=metric('Mean delivered power',summary.mean_delivered_power_W,'W',2)+metric('Maximum temperature spread',thermal?.status==='completed'?thermal.maximum_spread_K:null,'K',2)+metric('Current imbalance',summary.engineering?.metrics?.current_imbalance_pct?.value,'%',1);
  const requirements=Object.values(summary.engineering?.requirements||{}),configured=requirements.filter(x=>x.status!=='requirement not configured'),violations=configured.filter(x=>x.status==='simulated violation of configured limit'),clear=configured.length&&configured.every(x=>x.status==='no sampled exceedance; insufficient evidence for a pass');
  const screen=violations.length?`${violations.length} configured limit${violations.length===1?'':'s'} exceeded in this simulation.`:!configured.length?'No engineering limits set. Add a limit to detect violations.':clear?`${configured.length} configured limit${configured.length===1?'':'s'}: no sampled exceedance. This is not a safety pass.`:'Some configured limits could not be evaluated. Review the details.';
  $('engineering').innerHTML=`<div class="requirement-summary ${violations.length?'violation':''}"><p>${h(screen)}</p><button id="configure-limits" class="text-button">Edit limits</button></div><details><summary>Limits, margins & sources</summary>${requirementsHTML(summary.engineering)}<p class="evidence-note">Voltage requirement: ${h(summary.voltage_requirement?.status||'requirement not configured')}</p></details>`;
  const rows=state.series.module.rows;
  if(rows.length){
    $('plots').className='plots';renderCharts();$('timeline').hidden=false;$('time').max=rows.length-1;$('time').value=0;
    $('sample-window').textContent=`Samples ${state.offset+1}–${state.offset+rows.length} of ${state.series.module.total_samples} · saved solver samples`;
    document.querySelector('.pagination').hidden=state.offset===0&&state.series.module.next_offset===null;
    $('previous-page').disabled=state.offset===0;$('next-page').disabled=state.series.module.next_offset===null;
    setTime(rows.length-1);
  } else { $('plots').className='plots empty';$('plots').innerHTML='<div><h3>No valid simulation samples</h3><p>Inspect the failure and assumptions before rerunning.</p></div>'; }
  const coverage=summary.coverage?.cells||{};
  $('panel-evidence').innerHTML=`<div class="page-heading"><h1>Understand the model</h1><p>Sources, assumptions and coverage for ${h(r.owner_variant_id)} · ${h(r.run_id)}.</p></div><div class="evidence-banner"><strong>Simulated results. Experimental validation pending.</strong><p>Fitted cell models and declared connection assumptions predict this module’s electrical behaviour. Temperature uses a one-way lumped model with assumed parameters; it does not feed back into the electrical calculation.</p></div><h2>How to read these results</h2><p>Coverage describes the recorded model support. It does not validate a new load waveform, duration, module or sensor signal. The thermal result describes a surface-equivalent temperature, not a cell’s core or internal temperature distribution.</p><p>${h((summary.decision_reasons||[]).join('. '))}</p><div class="table-wrap"><table><thead><tr><th>Cell</th><th>State of charge</th><th>Current range (A)</th><th>Reference support</th></tr></thead><tbody>${Object.entries(coverage).map(([id,c])=>`<tr><td>${h(id)}</td><td>${c.SOC_range.map(x=>n(x*100,1)).join('–')}%</td><td>${c.current_range_A.map(x=>n(x,2)).join(' to ')}</td><td>${c.mathematical_support?'Within reference':'Unsupported'}</td></tr>`).join('')}</tbody></table></div><details><summary>Thermal assumptions & result status</summary><pre>${h(JSON.stringify(summary.thermal||{status:'unavailable'},null,2))}</pre></details><details><summary>Fitting, assessment & unsupported intervals</summary><pre>${h(JSON.stringify(summary.coverage,null,2))}</pre></details><details><summary>Requirement checks & loss accounting</summary><pre>${h(JSON.stringify({...summary,coverage:undefined,thermal:undefined},null,2))}</pre></details><details><summary>Exact run identity</summary><pre>${h(JSON.stringify({variant:r.owner_variant_id,revision:r.revision_id,snapshot:r.snapshot_id,scenario:r.scenario_id,classification:r.classification,freshness:r.freshness},null,2))}</pre></details>`;
}
function chart(key,unit,terminal=false,title=null,subtitle=null) {
  const rows=state.series.module.rows,t0=rows[0].time_s,t1=rows.at(-1).time_s;
  const channels=ids.map((id,i)=>({rows:state.series[id].rows,key,css:`chart-line c${i+1}`}));
  if(terminal) channels.push({rows,key:'terminal_V',css:'chart-module'});
  const [lo,hi]=bounds(channels.flatMap(c=>c.rows.map(r=>r[c.key]))),x=t=>40+(t-t0)/(t1-t0||1)*340,y=v=>154-(v-lo)/(hi-lo)*127;
  let svg='';
  for(let i=0;i<4;i++){const val=lo+(hi-lo)*i/3,yy=y(val);svg+=`<path class="chart-grid" d="M40 ${yy} H380"/><text class="chart-label" x="34" y="${yy+3}" text-anchor="end">${n(val,2)}</text>`;}
  for(let i=0;i<4;i++){const t=t0+(t1-t0)*i/3;svg+=`<text class="chart-label" x="${x(t)}" y="174" text-anchor="middle">${n(t,0)}</text>`;}
  for(const c of channels) svg+=`<path class="${c.css}" d="${c.rows.map((r,i)=>`${i?'L':'M'}${x(r.time_s).toFixed(2)},${y(r[c.key]).toFixed(2)}`).join(' ')}"/>`;
  svg+='<path class="chart-cursor" d="M40 22 V155"/><text class="chart-label" x="380" y="191" text-anchor="end">Time (s)</text>';
  return `<div class="plot"><div class="plot-title"><h3>${h(title||(terminal?'Cell & terminal voltage':'Current sharing'))}</h3><span>${unit} · ${h(subtitle||(terminal?'pk − nk':'discharge positive'))}</span></div><svg viewBox="0 0 400 198" role="img" aria-label="${h(title||(terminal?'Voltage':'Branch current'))} versus time, saved simulated outputs">${svg}</svg><div class="legend">${ids.map((id,i)=>`<span><i class="dot c${i+1}"></i>${h(state.info.design.cells[id].identity)}</span>`).join('')}${terminal?'<span>┄ Module p1 − n1</span>':''}</div></div>`;
}
function renderCharts(){
  const hasThermal=Number.isFinite(state.series?.cell_1?.rows?.[0]?.temperature_C);
  if(state.chart==='temperature'&&!hasThermal) state.chart='current';
  for(const b of $('chart-controls').querySelectorAll('button')){b.setAttribute('aria-pressed',String(b.dataset.chart===state.chart));b.disabled=b.dataset.chart==='temperature'&&!hasThermal;}
  $('plots').innerHTML=state.chart==='temperature'?chart('temperature_C','°C',false,'Cell temperature','surface-equivalent · simulated'):state.chart==='voltage'?chart('voltage_V','V',true):chart('current_A','A');
}
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
  if(!state.run||!row){el.innerHTML='<p>Select a saved run to inspect this component at any simulated time.</p>';return;}
  const title=`${componentLabel(state.selected)} · ${n(row.time_s,2)} s`;
  const value=(label,number,unit,digits=2)=>`<span>${h(label)}<strong>${n(number,digits)} <small>${h(unit)}</small></strong></span>`;
  const metadata=`<p class="field-hint">${h(state.run.run_id)} · ${state.run.freshness==='outdated'?'Outdated result':'Saved simulation'}</p>`;
  if(state.selected.startsWith('rail_')) {
    el.innerHTML=`<strong>${h(title)}</strong><div class="readout-values">${value('Current',row.current_A,'A')}${value('Voltage drop',row.voltage_drop_V*1000,'mV')}${value('Heat loss',row.loss_W,'W',4)}</div>${metadata}`;
    return;
  }
  const module=state.selected==='module';
  el.innerHTML=`<strong>${h(title)}</strong><div class="readout-values">${value('Current',row.current_A,'A')}${value('Voltage',module?row.terminal_V:row.voltage_V,'V',3)}${!module&&Number.isFinite(row.temperature_C)?value('Temperature',row.temperature_C,'°C'):''}</div>${module?`<p>${n(row.power_W,2)} W power · ${n(row.delivered_net_Wh,2)} Wh delivered so far</p>`:`<p>${n(row.soc*100,1)}% state of charge${Number.isFinite(row.temperature_C)?' · surface-equivalent temperature':''}</p>`}${metadata}`;
}

async function waitJob(id) {
  for(;;){const job=await request('/api/jobs/'+id);if(job.state==='completed'||job.state==='failed'){
    if(job.response.status!=='ok')throw new Error(job.response.error.message);return job.response.result;
  }notice(`${job.operation==='run'?'Simulating electrical behaviour':job.operation==='investigate'?'Running failure investigation':'Preparing reproducible export'}… ${Math.max(0,Math.round(Date.now()/1000-job.started_at))} s elapsed.`, 'busy');await new Promise(resolve=>setTimeout(resolve,600));}
}
async function runSimulation() {
  state.busy=true;buttons();const variant=state.variant;
  try{const {job_id}=await request('/api/jobs',{operation:'run',arguments:{variant_id:variant,expected_revision:state.info.revision_id,scenario_id:state.scenario}});
    const result=await waitJob(job_id);
    if(state.variant===variant) await refresh(variant,result.run_id);else await catalogRuns();
    notice(result.execution_status==='failed'?`Simulation stopped. Any valid partial results are saved in ${result.run_id}.`:`Simulation saved. Inspect the assembly or explore the result charts.`,result.execution_status==='failed'?'error':'');
  }finally{state.busy=false;buttons();}
}
function renderInvestigationForm() { if(!state.info) return; $('investigation-form').innerHTML=state.info.design.connections?investigationFormHTML(state.info.design):'';updateInvestigationPreview(); }
function investigationPlan(){return parsePlan({segments:[...document.querySelectorAll('[id^="inv-seg-"]:checked')].map(e=>e.value),added:$('inv-added').value,loads:$('inv-loads').value,ambient:$('inv-ambient').value,max:$('inv-max').value});}
function updateInvestigationPreview(){
  if(!$('inv-preview'))return;
  try{const p=investigationPlan(),total=Math.max(p.load_current_A.length,1)*Math.max(p.ambient_C.length,1)*(1+p.rail_segments.length*p.added_resistance_ohm.length);$('inv-preview').textContent=`${Math.min(total,p.max_cases)} of ${total} cases will run. Includes the unchanged connections for each load and temperature.`;}
  catch(e){$('inv-preview').textContent=e.message;}
}
function showInvestigation(record) {
  state.investigation=record;
  const stale=record&&record.revision_id!==state.info?.revision_id?'<p class="evidence-note">This investigation was run on a different revision of this variant. Run it again to screen the current design.</p>':'';
  $('investigation-results').innerHTML=record?stale+investigationHTML(record):'';
}
async function showLatestInvestigation(epoch=designEpoch.value) {
  try {
    const last=(await api('list_investigations')).filter(x=>x.variant_id===state.variant).at(-1);
    const record=last?await api('get_investigation',{investigation_id:last.investigation_id}):null;
    if(designEpoch.current(epoch)) showInvestigation(record);
  } catch(e) { if(designEpoch.current(epoch)) {showInvestigation(null);$('investigation-results').innerHTML=`<p class="error" role="alert">${h(e.message)}</p>`;} }
}
async function runInvestigation() {
  const plan=investigationPlan();
  state.busy=true;buttons();
  try{
    const {job_id}=await request('/api/jobs',{operation:'investigate',arguments:{variant_id:state.variant,expected_revision:state.info.revision_id,plan}});
    const record=await waitJob(job_id);
    showInvestigation(record);
    notice(`Investigation ${record.investigation_id}: evaluated ${record.coverage.evaluated} of ${record.coverage.requested} cases. Simulated; worst case only within this set.`);
  } finally{state.busy=false;buttons();}
}
async function openCase(caseId) {
  const record=state.investigation; if(!record) throw new Error('Run an investigation first.');
  const taken=new Set(Object.keys(state.info.variants).map(v=>v.toLowerCase())); let k=1; while(taken.has('c'+k)) k++; const vid='C'+k;
  const selectedCase=record.cases.find(c=>c.case_id===caseId);
  const name=selectedCase?.rail_segment?`${componentLabel(selectedCase.rail_segment)} study`:'Operating condition study';
  await api('open_case',{investigation_id:record.investigation_id, case_id:caseId, variant_id:vid, name});
  await refresh(vid);
  showTab('results');notice(`Created ${vid} from the selected case. Run the simulation to save its results.`);
}
async function compareRuns() {
  const selections=[$('compare-first').value,$('compare-second').value].map(id=>state.catalog.find(r=>r.run_id===id)).map(r=>({variant_id:r.variant_id,run_id:r.run_id}));
  if(selections[0].run_id===selections[1].run_id)throw new Error('Select two different saved runs.');
  const result=await api('compare',{selections});
  const labels={maximum_branch_current_A:['Peak branch current','A',2],minimum_terminal_voltage_V:['Minimum terminal voltage','V',3],delivered_net_Wh:['Delivered energy','Wh',2],peak_cell_temperature_C:['Peak cell temperature','°C',2],maximum_temperature_spread_K:['Temperature spread','K',2],current_imbalance_pct:['Current imbalance','%',1],minimum_cell_voltage_V:['Minimum cell voltage','V',3],mean_delivered_power_W:['Mean delivered power','W',2],delivered_charge_Ah:['Delivered charge','Ah',3],cell_R0_loss_Wh:['Cell ohmic loss','Wh',4],rail_loss_Wh:['Connection loss','Wh',4],R1_loss_Wh:['Polarization loss','Wh',4],above_4_9A_cell_seconds:['Time above 4.9 A','cell·s',2]};
  const [a,b]=result.ordered_results,delta=result.deltas_vs_first[0];
  const table=(keys)=>`<div class="table-wrap"><table><thead><tr><th>Result</th><th>Reference · ${h(a.variant_id)}<br><span class="small-label">${h(a.run_id)}</span></th><th>Alternative · ${h(b.variant_id)}<br><span class="small-label">${h(b.run_id)}</span></th><th>Change</th></tr></thead><tbody>${keys.map(k=>{const [name,unit,digits]=labels[k],value=delta?.[k];return `<tr><td>${name} (${unit})</td><td>${n(a[k],digits)}</td><td>${n(b[k],digits)}</td><td>${Number.isFinite(value)&&value>0?'+':''}${n(value,digits)}</td></tr>`;}).join('')}</tbody></table></div>`;
  const limitName=Object.fromEntries(Object.values(LIMITS).map(l=>[l.key,l.name]));
  const statuses=r=>Object.entries(r.engineering_requirements||{}).map(([k,v])=>`<li>${h(limitName[k]||k)}: ${h(limitLabel(v))}</li>`).join('');
  const keys=Object.keys(labels);
  $('comparison').innerHTML=`<div class="evidence-banner"><strong>Same operating conditions. Direct comparison.</strong><p>${h(result.conditions)}${result.historical_results?' · Includes outdated saved results.':''} Change means alternative minus reference.</p></div>${table(keys.slice(0,6))}<details class="comparison-details"><summary>Power, losses & delivered charge</summary>${table(keys.slice(6))}</details><details class="comparison-details"><summary>Requirements, freshness & evidence</summary><h3>Reference · ${h(a.variant_id)}</h3><ul>${statuses(a)}</ul><p>Voltage requirement: ${h(a.requirement)} · ${h(a.freshness)}</p><h3>Alternative · ${h(b.variant_id)}</h3><ul>${statuses(b)}</ul><p>Voltage requirement: ${h(b.requirement)} · ${h(b.freshness)}</p><p>${h(result.evidence)}</p></details><p class="evidence-note">These are simulated differences. No repair ranking or measured performance gain is established. Runs with different loads or thermal assumptions cannot enter this comparison.</p>`;
}

function exportDialog() {
  $('export-choices').innerHTML=state.catalog.map(r=>`<label><input type="checkbox" value="${h(r.run_id)}" ${r.run_id===state.run?.run_id?'checked':''}>${h(resultLabel(r))}</label>`).join('');
  $('export-error').textContent='';$('download').textContent='';$('export-dialog').showModal();
}
async function exportRuns() {
  const checked=[...$('export-choices').querySelectorAll('input:checked')].map(el=>el.value);
  if(!checked.length)throw new Error('Select at least one saved run.');
  const selections=checked.map(id=>state.catalog.find(r=>r.run_id===id)).map(r=>({variant_id:r.variant_id,run_id:r.run_id}));
  state.busy=true;buttons();
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
  if(state.view==='assembly')return;
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
  if(state.view==='circuit'&&id.startsWith('cell_')&&e.key.startsWith('Arrow')&&!state.busy&&!state.action){e.preventDefault();const [x,y]=position(ids.indexOf(id));state.selected=id;state.display.positions[id]=[Math.max(110,Math.min(780,x+(e.key==='ArrowRight'?10:e.key==='ArrowLeft'?-10:0))),Math.max(132,Math.min(176,y+(e.key==='ArrowDown'?5:e.key==='ArrowUp'?-5:0)))];drawCanvas();$('canvas').querySelector(`[data-component="${id}"]`)?.focus();action(saveDisplay);}
});
$('variants').addEventListener('click',e=>{const el=e.target.closest('[data-variant]');if(el)action(async()=>{rememberEditor();$('project-panel').hidePopover();await refresh(el.dataset.variant);showTab('results');notice(`Opened ${el.dataset.variant}.`);});});
$('components').addEventListener('click',e=>{const el=e.target.closest('[data-component]');if(el)selectComponent(el.dataset.component);});
$('inspector-content').addEventListener('change',e=>{if(e.target.id==='edit-property'){state.subProperty='';renderEditFields();}else if(e.target.id==='thermal-property'||e.target.id==='limit-property'){const id=e.target.id;state.subProperty=e.target.value;renderEditFields();$(id)?.focus();}else if(e.target.id==='scenario'){state.scenario=e.target.value;notice(`Next run: ${scenarios[state.scenario]}. The displayed run has not changed.`);}else invalidatePreview();});
$('inspector-content').addEventListener('input',e=>{if(e.target.id!=='scenario'){state.dirty=true;invalidatePreview();}});
$('inspector-content').addEventListener('click',e=>{if(e.target.id==='discard-edit'){editorDrafts.delete(editorKey());state.dirty=false;renderEditFields();}if(e.target.id==='add-interval')action(()=>{const profile=loadProfile(loadDraft());const end=profile.at(-1).end_s;profile.push({start_s:end,end_s:end+60,current_A:profile.at(-1).current_A});renderLoadFields(profile);state.dirty=true;invalidatePreview();});if(e.target.closest('.remove-interval'))action(()=>{const rows=loadDraft();rows.splice(Number(e.target.closest('.remove-interval').dataset.interval),1);renderLoadFields(loadProfile(rows));state.dirty=true;invalidatePreview();});if(e.target.id==='preview-edit')action(async()=>{try{await previewEdit();}catch(err){$('edit-feedback').innerHTML=`<p class="error" role="alert">${h(err.message)}</p>`;throw err;}});if(e.target.id==='apply-edit')action(applyEdit);});
$('run').addEventListener('click',()=>action(runSimulation));
$('run-select').addEventListener('change',()=>action(()=>loadRun($('run-select').value)));
$('overlay').addEventListener('change',drawCanvas);
$('view-assembly').addEventListener('click',()=>setView('assembly'));
$('view-circuit').addEventListener('click',()=>setView('circuit'));
$('time').addEventListener('input',()=>setTime(Number($('time').value)));
$('previous-page').addEventListener('click',()=>action(()=>loadRun(state.run.run_id,Math.max(0,state.offset-5000))));
$('next-page').addEventListener('click',()=>action(()=>loadRun(state.run.run_id,state.series.module.next_offset)));
$('reset-layout').addEventListener('click',()=>action(async()=>{state.display.positions={};drawCanvas();await saveDisplay();}));
const viewNames=['results','investigate','compare','evidence'];
function showTab(name) {
  if(!viewNames.includes(name))return;
  document.querySelector('.workbench').dataset.mode=name;
  for(const tab of viewNames){const active=tab===name;$('tab-'+tab).setAttribute('aria-selected',String(active));$('tab-'+tab).tabIndex=active?0:-1;$('panel-'+tab).hidden=!active;}
  const url=new URL(location.href);url.searchParams.set('view',name);history.replaceState(null,'',url);
}
for(const name of viewNames) $('tab-'+name).addEventListener('click',()=>showTab(name));
document.querySelector('.tabs').addEventListener('keydown',e=>{
  const tabs=[...document.querySelectorAll('[role=tab]')];let i=tabs.indexOf(document.activeElement);if(i<0)return;
  if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();i=e.key==='Home'?0:e.key==='End'?tabs.length-1:(i+(e.key==='ArrowRight'?1:tabs.length-1))%tabs.length;tabs[i].focus();tabs[i].click();}
});
$('toggle-inspector').addEventListener('click',()=>inspectorOpen($('toggle-inspector').getAttribute('aria-expanded')!=='true',true));
$('close-inspector').addEventListener('click',()=>{inspectorOpen(false);$('toggle-inspector').focus();});
$('configure-module').addEventListener('click',()=>selectComponent('module'));
function configureLimits(){showTab('results');selectComponent('module');$('edit-property').value=state.info.design.engineering_requirements?'limits':'requirements';renderEditFields();$('edit-property').focus();}
$('engineering').addEventListener('click',e=>{if(e.target.closest('#configure-limits'))configureLimits();});
$('menu-help').addEventListener('click',()=>{$('project-panel').hidePopover();$('quick-guide').hidden=false;$('help-toggle').setAttribute('aria-expanded','true');$('quick-guide').scrollIntoView({block:'start'});});
$('help-toggle').addEventListener('click',()=>{const open=$('quick-guide').hidden;$('quick-guide').hidden=!open;$('help-toggle').setAttribute('aria-expanded',String(open));});
$('chart-controls').addEventListener('click',e=>{const button=e.target.closest('[data-chart]');if(!button||!state.series)return;state.chart=button.dataset.chart;renderCharts();setTime(state.index);});
window.addEventListener('beforeunload',e=>{if(state.dirty||editorDrafts.size){e.preventDefault();e.returnValue='';}});
$('compare').addEventListener('click',()=>action(async()=>{ $('comparison').textContent='';try{await compareRuns();}catch(e){$('comparison').innerHTML=`<p class="error" role="alert">${h(e.message)}</p>`;throw e;} }));
$('panel-investigate').addEventListener('input',updateInvestigationPreview);
$('panel-investigate').addEventListener('change',updateInvestigationPreview);
$('panel-investigate').addEventListener('click',e=>{
  const button=e.target.closest('button');if(!button)return;
  if(button.id==='configure-inv-limits')configureLimits();
  else if(button.id==='inv-run')action(async()=>{try{await runInvestigation();}catch(e){$('investigation-results').innerHTML=`<p class="error" role="alert">${h(e.message)}</p>`;throw e;}});
  else if(button.classList.contains('open-case'))action(()=>openCase(button.dataset.case));
});
for(const id of ['compare-first','compare-second'])$(id).addEventListener('change',()=>{$('comparison').textContent='';});
$('new-variant').addEventListener('click',()=>{$('project-panel').hidePopover();let i=1;while(state.info.variants['A'+i])i++;$('variant-id-input').value='A'+i;$('variant-name').value='Connection study';$('variant-error').textContent='';$('variant-dialog').showModal();$('variant-id-input').focus();});
$('cancel-variant').addEventListener('click',()=>$('variant-dialog').close());
$('variant-form').addEventListener('submit',e=>{e.preventDefault();action(async()=>{try{const id=$('variant-id-input').value;await api('create_variant',{source_variant:state.variant,variant_id:id,name:$('variant-name').value,expected_revision:state.info.revision_id});$('variant-dialog').close();await refresh(id);notice(`Created ${id}. Inherited results are outdated for this variant; run it to obtain owned results.`);}catch(err){$('variant-error').textContent=err.message;}});});
$('export').addEventListener('click',exportDialog);$('close-export').addEventListener('click',()=>$('export-dialog').close());
$('make-export').addEventListener('click',()=>action(async()=>{try{$('export-error').textContent='';await exportRuns();}catch(err){$('export-error').textContent=err.message;}}));

try {
  const session=await request('/api/session');state.token=session.token;$('project-location').textContent=session.project;
  await refresh();showTab(new URL(location.href).searchParams.get('view')||'results');notice('');
  if(session.active_job){state.busy=true;buttons();try{await waitJob(session.active_job);await refresh();notice('Previous job finished. Saved runs are available.');}finally{state.busy=false;buttons();}}
} catch(e) {notice(e.message,'error');}
