import {esc,describeConnection} from './studio-state.mjs';

// A blank draft is never a physical zero. Null is reserved for optional checks.
export function numericDraft(raw,{optional=false,min=-Infinity,max=Infinity,label='Value',badInput=false}={}) {
  const text=String(raw??'').trim();
  if(badInput)return {ok:false,message:`Enter ${label.toLowerCase()} as a number in the displayed unit.`};
  if(!text)return optional?{ok:true,value:null}:{ok:false,message:`Enter ${label.toLowerCase()}. The saved value has not changed.`};
  if(!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(text)||!Number.isFinite(Number(text)))return {ok:false,message:`Enter ${label.toLowerCase()} as a finite number in the displayed unit.`};
  const value=Number(text);
  if(value<min||value>max)return {ok:false,message:`${label} must be ${Number.isFinite(min)?'at least '+min:''}${Number.isFinite(min)&&Number.isFinite(max)?' and ':''}${Number.isFinite(max)?'at most '+max:''}. The saved value has not changed.`};
  return {ok:true,value};
}

export function flattenChanges(changes=[]) {
  const rows=[];
  const visit=(path,before,after)=>{
    if(Object.is(before,after))return;
    const object=x=>x!==null&&typeof x==='object';
    if(object(before)||object(after)){
      const keys=[...new Set([...Object.keys(object(before)?before:{}),...Object.keys(object(after)?after:{})])];
      if(keys.length){for(const key of keys)visit(`${path}${Array.isArray(before)||Array.isArray(after)?'['+key+']':'.'+key}`,before?.[key],after?.[key]);return;}
    }
    rows.push({path,before,after});
  };
  for(const row of changes)visit(row.path,row.before,row.after);
  return rows;
}

const propertyLabels={charge_pct:'starting charge (%)',temperature_C:'cell temperature (°C)',polarization_V:'relaxation voltage (V)',resistance_mohm:'resistance (mΩ)',current_A:'current (A)',start_s:'start time (s)',end_s:'end time (s)',ambient_C:'room temperature (°C)',heat_capacity_J_K:'heat capacity (J/°C)',ambient_conductance_W_K:'cooling to room (W/°C)',conductance_W_K:'thermal contact (W/°C)',min_voltage_V:'minimum voltage (V)',imbalance_pct:'current difference (%)',dt_s:'time step (s)',length_mm:'path length (mm)',width_mm:'width (mm)',thickness_mm:'thickness (mm)',contact_mohm:'end contacts (mΩ)',resistivity_ohm_m:'resistivity (Ω·m)',density_kg_m3:'density (kg/m³)',reference_temperature_C:'reference temperature (°C)',model:'cell model',source:'source or assumption',x:'drawing x',y:'drawing y',a:'first terminal or cell',b:'second terminal or cell',id:'component identity',positive:'positive output',negative:'negative output',profile:'load intervals'};
export function proposalRows(proposal,graph={},library=[]) {
  const rows=flattenChanges(proposal.diff),names=new Map((graph.cells||[]).map(c=>[c.id,c.name]));
  for(const r of rows){const m=r.path.match(/(?:^|\.)cells\.([^.]+)\.name$/);if(m)names.set(m[1],r.after??r.before);}
  const value=v=>{
    if(v===undefined)return 'Absent';if(v===null)return 'Not set';if(v===true)return 'On';if(v===false)return 'Off';
    if(typeof v==='object')return Array.isArray(v)?'Empty list':'Empty object';
    if(typeof v==='string'&&/^[^:]+:[pn]$/.test(v)){const [id,p]=v.split(':');return `${names.get(id)||id} ${p==='p'?'positive':'negative'}`;}
    return library.find(m=>m.key===v)?.name||String(v);
  };
  return rows.map(r=>{
    let path=r.path.replace(/^design\./,'');
    for(const w of graph.connections||[])path=path.replace(`connections.${w.id}`,`Connection ${describeConnection(graph,w)}`);
    path=path.replace(/cells\.([^.]+)/g,(_,id)=>names.get(id)||id.replace(/^cell/,'Cell '));
    path=path.split('.').map(p=>propertyLabels[p]||p.replaceAll('_',' ')).join(' / ');
    return {...r,label:path,beforeText:value(r.before),afterText:value(r.after)};
  });
}
export function proposalPreview(proposal,graph,library) {
  const rows=proposalRows(proposal,graph,library),ready=proposal.readiness;
  const copy=proposal.new_design||proposal.changes?.some(x=>x.startsWith('Create a separate design'));
  return `<p>${copy?'Creates a separate editable design. Your baseline stays saved.':'Updates this design. Changed physics makes its previous tests historical.'}</p><p class="helper">Review all ${rows.length} changed values before applying.</p>${rows.length?`<div class="proposal-diff"><table><thead><tr><th>Property</th><th>Before</th><th>After</th></tr></thead><tbody>${rows.map(r=>`<tr><th scope="row">${esc(r.label)}</th><td>${esc(r.beforeText)}</td><td>${esc(r.afterText)}</td></tr>`).join('')}</tbody></table></div>`:'<p class="error-inline">A complete change preview is unavailable. Ask for a new proposal before applying.</p>'}${ready?`<div class="${ready.ready?'info-inline':'error-inline'}"><strong>${ready.ready?'Ready for review':'Test setup needs attention'}</strong><p>${esc(ready.message||'The proposed design passes the current preflight checks. This is not hardware acceptance.')}</p>${ready.warnings?.length?`<ul>${ready.warnings.map(w=>`<li>${esc(w.message||w)}</li>`).join('')}</ul>`:''}</div>`:''}`;
}

export function contextModels(graph,library=[],savedTest=null) {
  const selected=savedTest?.graph||graph;
  return [...new Set((selected?.cells||[]).map(c=>c.model))].map(key=>savedTest
    ? savedTest.model_cards?.[key]||{key,name:key,status:'Saved model details unavailable for this historical test',missing:true}
    : library.find(m=>m.key===key)||{key,name:key,status:'Model unavailable',missing:true});
}
export function comparisonConditions(c) {
  const designChanges=c.design_changes||[],preparation=designChanges.some(d=>/charge_pct|temperature_C|polarization_V/.test(d.path)),thermal=designChanges.some(d=>/thermal|heat_capacity|conductance/.test(d.path));
  return [
    {label:c.identical_test_conditions?'Same load and test settings':'Different load or test settings',match:c.identical_test_conditions===true},
    {label:preparation?'Cell preparation changed':'Cell preparation unchanged',match:!preparation},
    {label:thermal?'Heat assumptions changed':'Heat assumptions unchanged',match:!thermal},
    {label:c.model_versions_match?'Same model versions':'Model versions differ or are unknown',match:c.model_versions_match===true},
    {label:c.solver_versions_match?'Same solver version':'Solver versions differ or are unknown',match:c.solver_versions_match===true},
    {label:c.requirements_match?'Same requirements':'Requirements differ or are unknown',match:c.requirements_match===true},
    {label:c.comparable_duration?'Same calculated duration':'Different calculated durations',match:c.comparable_duration===true},
    {label:c.tests?.every(t=>t.summary?.coverage?.complete&&t.summary?.assessment?.requested_demand_met)?'Both completed requested service':'Partial or unserved demand: review each test',match:c.tests?.every(t=>t.summary?.coverage?.complete&&t.summary?.assessment?.requested_demand_met)===true}
  ];
}
export function comparisonNotice(c) {
  const flags=comparisonConditions(c);
  return `<section class="comparison-conditions" aria-label="Comparison conditions"><h2>${flags.every(f=>f.match)?'Matching conditions':'Review the comparison conditions'}</h2><ul>${flags.map(f=>`<li class="${f.match?'matching':'changed'}">${esc(f.label)}</li>`).join('')}</ul><p class="helper">${flags.every(f=>f.match)?'Design changes are listed below. These remain simulated results.':'Differences may have more than one cause. Do not attribute the deltas to cell count or wiring alone.'}</p></section>`;
}
export function verdictContext(test) {
  const s=test.summary,limits=test.settings?.limits||{},configured=Object.values(limits).filter(v=>v!==null&&v!==undefined).length;
  const served=s.coverage?.complete&&s.assessment?.requested_demand_met;
  const coverage=s.operating_limit_coverage;
  return `${served?'Calculated service completed for this saved test.':'Requested service was not fully calculated or served.'} ${configured} design target${configured===1?'':'s'} configured; ${Math.max(0,4-configured)} not set.${!coverage?' Cell operating-limit coverage was not recorded for this historical test.':coverage.complete!==true?' Some cell operating limits are unknown.':''} Hardware acceptance and board compatibility are not established by this simulation.`;
}
export function copilotAvailability(catalog) {
  const c=catalog?.copilot;
  if(!c?.available)return {available:false,label:'AI unavailable',message:'AI is not configured for this workspace. You can continue building, testing and exporting.'};
  return {available:true,label:c.connection_verified?`${c.provider||'AI'} connection verified`:`${c.provider||'AI'} configured; connection unverified`,message:c.connection_verified?'Your request will use the context shown below.':'Availability is based on configuration. A provider response has not yet verified the connection.'};
}
export function persistenceCopy(runtime) {
  if(runtime?.persistence==='browser_session')return {temporary:true,saved:'In this tab',description:'Temporary browser session. Export your test and download a design backup before closing this tab.'};
  if(runtime?.persistence==='local_workspace')return {temporary:false,saved:'Saved',description:'Designs are saved by this local workspace on this computer. Export a test or download a design backup to keep a separate copy.'};
  return {temporary:false,saved:'Saved in workspace',description:'Storage lifetime has not been reported by this workspace. Download a design backup and export important tests.'};
}
export function safeFileName(name,suffix='json') {
  return `${String(name||'volt-forge').normalize('NFKC').replace(/[^\p{L}\p{N}._-]+/gu,'-').replace(/^-+|-+$/g,'').slice(0,100)||'volt-forge'}.${suffix}`;
}
export function draftBackup(doc,graph,settings,fields=[]) {
  return {format:'voltforge.design-backup/1',source_design_id:doc.id,source_version:doc.version,name:graph.name,graph:structuredClone(graph),settings:structuredClone(settings),unfinished_fields:fields,notice:'Saved-result history is not included. Unfinished field text is not a simulation input.'};
}
export function recoveredName(name){const suffix=' recovered copy';return String(name||'Battery').slice(0,100-suffix.length)+suffix;}
export function recoveryRequest(backup) {
  if(backup?.format!=='voltforge.design-backup/1'||!backup.graph||!backup.settings)throw new Error('Choose a VOLT-FORGE design backup. An experiment ZIP is a report/replay package.');
  // Import can cross workspaces. An old ID must not imply lineage to a same-ID local design.
  return {name:recoveredName(backup.name||backup.graph.name),graph:structuredClone(backup.graph),settings:structuredClone(backup.settings)};
}
