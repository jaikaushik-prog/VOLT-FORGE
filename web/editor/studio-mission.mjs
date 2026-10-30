import {esc,fmt} from './studio-state.mjs';

export const loadChoices={
 discharge:[['pi5_gateway_backup','Raspberry Pi 5 gateway backup','25 W for 10 minutes through a short power cut.'],['stress_12a','12 A stress test','A harder load, to see where the design runs out of margin.'],['custom_amps','Custom load in amps','Enter the battery current yourself.'],['custom_watts','Custom load in watts','Enter power and converter efficiency.']],
 charge:[['custom_amps','Charging current','Enter the charging current. The test stops at the cell limits.']],
 custom:[['custom_amps','Start from one load','Add changing loads, charging and rest on the Test page.']]
};
export const testTypes=[['discharge','Discharge','Power something from the battery.'],['charge','Charge','Put energy back into the cells.'],['custom','Custom cycle','Mix loads, charging and rest.']];
export const presetValues={pi5_gateway_backup:{minutes:10,floor:3.3,ambient:23},stress_12a:{minutes:10,floor:3.3,ambient:23}};
export const newSetup=()=>({step:1,test_type:'discharge',preset:'pi5_gateway_backup',current:5,power:25,efficiency:90,minutes:10,floor:3.3,ambient:23});

const number=(id,name,label,value,unit,attrs='')=>`<div class="field"><label for="${id}">${label}</label><div class="input-unit"><input id="${id}" name="${name}" type="number" step="any" value="${value??''}" ${attrs}><span>${unit}</span></div></div>`;

export function setupTypeStep(s){return `<p>What should this battery do?</p><div class="template-options">${testTypes.map(([key,title,text])=>`<button type="button" data-act="setup-type:${key}" class="template-option ${s.test_type===key?'active':''}"><span><strong>${title}</strong><span>${text}</span></span><span class="chosen"></span></button>`).join('')}</div>`;}

export function setupLoadFields(s){
 const custom=s.preset.startsWith('custom'),watts=s.preset==='custom_watts';
 const load=!custom?'':watts?`<div class="field-row">${number('setup-power','power','Load power',s.power,'W','min="0.001" required')}${number('setup-efficiency','efficiency','Converter efficiency',s.efficiency,'%','min="1" max="100" required')}</div>`:number('setup-current','current','Battery current',s.current,'A','min="0.001" max="200" required');
 const floor=s.test_type==='charge'?'':number('setup-floor','floor','Lowest battery voltage',s.floor,'V',`min="0.1" ${watts?'required':''}`);
 return `${load}<div class="field-row">${number('setup-minutes','minutes','Run time',s.minutes,'min','min="0.02" max="1440" required')}${floor}</div>${number('setup-ambient','ambient','Room temperature',s.ambient,'°C','min="-40" max="100" required')}<p class="helper">${custom?'These values are saved as custom.':'Change any value here or on the Test page. A changed value is labelled custom.'}</p>`;
}

export function setupLoadStep(s){return `<p>Choose what the battery has to do.</p><div class="template-options">${loadChoices[s.test_type].map(([key,title,text])=>`<button type="button" data-act="setup-load:${key}" class="template-option ${s.preset===key?'active':''}"><span><strong>${title}</strong><span>${text}</span></span><span class="chosen"></span></button>`).join('')}</div><form id="setup-load-form"><div id="setup-fields">${setupLoadFields(s)}</div></form>`;}

export function readSetupFields(form,s){const d=new FormData(form),next={...s};for(const key of ['current','power','efficiency','minutes','floor','ambient'])if(d.has(key)&&d.get(key)!=='')next[key]=Number(d.get(key));else if(key==='floor'&&d.has(key))next.floor=null;return next;}

export function missionRequest(s){
 const r={test_type:s.test_type,preset:s.preset};
 if(s.preset.startsWith('custom'))Object.assign(r,{duration_s:s.minutes*60,ambient_C:s.ambient,voltage_floor_V:s.test_type==='charge'?null:s.floor});
 if(s.preset==='custom_amps')r.current_A=s.current;
 if(s.preset==='custom_watts')Object.assign(r,{power_W:s.power,efficiency:s.efficiency/100});
 return r;
}

// Preset values come from the backend, so a change made during setup is applied
// afterwards and the saved requirement relabels itself as custom.
export function presetEdits(s,settings){
 const base=presetValues[s.preset];if(!base)return false;let changed=false;
 if(s.minutes!==base.minutes){settings.profile[0].end_s=s.minutes*60;changed=true;}
 if(s.floor!==base.floor){settings.limits.min_voltage_V=s.floor;changed=true;}
 if(s.ambient!==base.ambient){settings.ambient_C=s.ambient;changed=true;}
 return changed;
}

function requirementValue(r){if(r.value===null||r.value===undefined)return 'Varies';if(r.unit==='s')return `${fmt(r.value/60,r.value%60?2:0)} min`;if(r.unit==='ratio')return `${fmt(100*r.value,0)}%`;return `${fmt(r.value,r.unit==='A'?2:1)} ${esc(r.unit)}`;}
export function applicationLine(application){
 if(!application)return '';
 return `<details class="application-line"><summary><strong>${esc(application.name)}</strong><span>${esc(application.purpose)}</span></summary><table class="requirement-table"><thead><tr><th>Requirement</th><th>Value</th><th>Basis</th><th>Why</th></tr></thead><tbody>${application.requirements.map(r=>`<tr><td>${esc(r.label)}</td><td>${requirementValue(r)}</td><td><span class="basis-chip ${esc(r.basis)}">${esc(r.basis)}</span></td><td>${esc(r.reason)}${r.source_url?` <a href="${esc(r.source_url)}" target="_blank" rel="noreferrer">Source</a>`:''}</td></tr>`).join('')}</tbody></table>${application.approximation?`<p class="helper">${esc(application.approximation)}</p>`:''}</details>`;
}

const mark=state=>`<span class="verdict-mark ${state}" aria-label="${state==='pass'?'Met':state==='fail'?'Not met':'Information'}">${state==='pass'?'✓':state==='fail'?'✕':'•'}</span>`;
export function verdictRows(test,timeLabel){
 const s=test.summary,m=s.metrics,names=Object.fromEntries(test.graph.cells.map(c=>[c.id,c.name])),cells=test.graph.cells.length;
 const requested=s.coverage.requested_duration_s,served=s.assessment.requested_demand_met&&s.coverage.complete;
 const load=Math.max(...test.settings.profile.map(p=>Math.abs(p.current_A))),even=cells?load/cells:0;
 const above=even>0&&s.metrics.imbalance_pct!==null?100*(m.peak_cell_current_A/even-1):null;
 const target=test.settings.limits.min_voltage_V,check=s.checks.find(c=>c.metric==='min_voltage_V');
 const rows=[];
 if(s.charging)rows.push(['Charging',served?'pass':'info',`${fmt(s.charging.charge_gained_Ah,2)} Ah gained in ${timeLabel(s.charging.elapsed_s)}`,s.charging.stop_message]);
 else rows.push(['Backup time',served?'pass':'fail',served?`Full ${timeLabel(requested)}`:`Stopped at ${timeLabel(m.duration_s)} of ${timeLabel(requested)}`,'']);
 if(!s.charging)rows.push(['Lowest voltage',check?check.status==='exceeded'?'fail':check.status==='within_target'?'pass':'info':'info',`${fmt(m.minimum_voltage_V,2)} V`,target==null?'No target set':`Target ${fmt(target,2)} V`]);
 rows.push(['Busiest cell','info',`${esc(names[m.busiest_cell])}: ${fmt(m.peak_cell_current_A,2)} A`,above!==null&&above>.5?`${fmt(above,0)}% above an even share`:'']);
 rows.push(['Warmest cell','info',m.warmest_cell?`${esc(names[m.warmest_cell])}: ${fmt(m.peak_temperature_C)} °C`:'Temperature not modeled','']);
 return `<div class="verdict" aria-label="Test verdict">${rows.map(([label,state,value,note])=>`<div class="verdict-row">${mark(state)}<span class="verdict-label">${label}</span><strong>${value}</strong><span class="verdict-note">${esc(note)}</span></div>`).join('')}</div>`;
}

const symbols={INR:'₹',USD:'US$',GBP:'£'};
const money=(value,currency)=>`${symbols[currency]||currency+' '}${value.toLocaleString('en-IN',{maximumFractionDigits:value<100?2:0})}`;
export function costLabel(parts){if(!parts)return '—';const sums=Object.entries(parts.subtotals).map(([c,v])=>money(v,c)).join(' + ');return (sums||'Nothing priced')+(parts.unpriced.length?' + unpriced parts':'');}
export function partsPanel(parts){
 if(!parts)return '';
 return `<details class="parts-panel"><summary><strong>Parts and listed cost</strong><span>${esc(costLabel(parts))}</span></summary><table class="requirement-table"><thead><tr><th>Part</th><th>Quantity</th><th>Unit price</th><th>Cost</th></tr></thead><tbody>${parts.lines.map(l=>`<tr><td>${esc(l.part)}${l.specification?`<p class="helper">${esc(l.specification)}</p>`:''}${l.limits?`<p class="helper">${esc(l.limits)}</p>`:''}</td><td>${fmt(l.quantity,l.quantity%1?2:0)} ${esc(l.unit)}</td><td>${l.priced?`${money(l.unit_price,l.currency)}<p class="helper">${l.listing_count===1?'One listing':`Average of ${l.listing_count} listings`}${(l.listings||[]).map(x=>` · <a href="${esc(x.url)}" target="_blank" rel="noreferrer">${esc(x.seller)}</a>`).join('')}</p>`:esc(l.note)}</td><td>${l.priced?money(l.cost,l.currency):'—'}</td></tr>`).join('')}</tbody></table><p class="helper">${esc(parts.scope)} Prices checked ${esc(parts.checked||'')}.${parts.listed_mass_g!=null?` Listed mass ${fmt(parts.listed_mass_g,0)} g.`:''}</p></details>`;
}

export function warningList(warnings){if(!warnings?.length)return '';return `<div class="design-warnings" role="status"><strong>Check this wiring</strong><ul>${warnings.map(w=>`<li>${esc(w.message)}</li>`).join('')}</ul></div>`;}

const sizingLabels={qualifies:'Qualifies',failed:'Misses a target',refused:'Refused: over a cell limit',unsupported:'Outside model support',incomplete:'Not fully assessed'};
export function sizingTable(inv,busy,openButton){
 const best=inv.sizing?.smallest_cell_count,cases=inv.cases;
 return `${best?`<div class="limit-finding sizing-answer"><h2>${best} ${best===1?'cell':'cells'}</h2><p>${esc(inv.sizing.claim)}.</p><p class="helper">${esc(inv.sizing.scope)}</p></div>`:inv.complete?`<p class="limits-observation">None of these parallel arrangements qualified.</p>`:''}${cases.length?`<div class="limits-table-wrap"><table class="limits-table sizing-table"><thead><tr><th>Cells</th><th>Verdict</th><th>Lowest voltage</th><th>Busiest cell</th><th>Warmest</th><th>Listed cost</th><th>Cell mass</th><th></th></tr></thead><tbody>${cases.map((c,i)=>{const m=c.summary?.metrics;return `<tr class="${c.cell_count===best?'selected':''}"><td>${c.cell_count}</td><td><span class="limit-status ${c.sizing==='qualifies'?'ok':'hit'}">${sizingLabels[c.sizing]||esc(c.sizing)}</span></td><td>${m?fmt(m.minimum_voltage_V,2)+' V':'—'}</td><td>${m?fmt(m.peak_cell_current_A,2)+' A':'—'}</td><td>${m?.peak_temperature_C!=null?fmt(m.peak_temperature_C)+' °C':'—'}</td><td>${esc(costLabel(c.parts))}</td><td>${c.parts?.cell_mass_g!=null?fmt(c.parts.cell_mass_g,0)+' g':'—'}</td><td>${openButton(i,busy)}</td></tr>`;}).join('')}</tbody></table></div>`:''}`;
}

export function tradeoffRows(a,b,deltaLabel){
 const margin=t=>{const target=t.settings.limits.min_voltage_V;return target==null?null:t.summary.metrics.minimum_voltage_V-target;};
 const cell=t=>t.parts?.cell_mass_g,rows=[['Cells',a.graph.cells.length,b.graph.cells.length,''],['Listed cost',costLabel(a.parts),costLabel(b.parts),null],['Cell mass',cell(a),cell(b),'g'],['Margin above voltage target',margin(a),margin(b),'V']];
 return rows.filter(([, x,y])=>x!=null||y!=null).map(([label,x,y,unit])=>unit===null?`<tr><td>${label}</td><td>${esc(x)}</td><td>${esc(y)}</td><td></td></tr>`:`<tr><td>${label}</td><td>${x==null?'—':fmt(x,unit==='V'?2:0)} <small>${unit}</small></td><td>${y==null?'—':fmt(y,unit==='V'?2:0)} <small>${unit}</small></td><td>${x==null||y==null?'':deltaLabel(y-x)} <small>${unit}</small></td></tr>`).join('');
}

export function loadBlockModel(application,settings){
 if(!application)return null;
 const p=settings.profile,current=p.length===1?`${fmt(Math.abs(p[0].current_A),2)} A`:'Changing load';
 return {name:application.name,detail:`${current} · ${fmt(p.at(-1).end_s/60,p.at(-1).end_s%60?1:0)} min`,charging:p.every(r=>r.current_A<=0)&&p.some(r=>r.current_A<0)};
}
