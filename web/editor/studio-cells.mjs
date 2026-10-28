import {esc,fmt} from './studio-state.mjs';

export function customCellForm(model=null){
 const field=(id,label,value,unit,min,max)=>`<div class="field"><label for="custom-${id}">${label}</label><div class="input-unit"><input id="custom-${id}" name="${id}" type="number" step="any" min="${min}" max="${max}" value="${value}" required><span>${unit}</span></div></div>`;
 return `<form id="custom-cell-form" data-parent="${esc(model?.key||'')}"><p>Start with a simple electrical estimate. These values belong to your cell and stay attached to each saved test.</p><div class="field"><label for="custom-name">Cell name</label><input id="custom-name" name="name" maxlength="80" value="${esc(model?.name||'My custom cell')}" required></div><div class="field-row">${field('capacity','Capacity',model?.capacity_Ah||5,'Ah',.001,10000)}${field('voltage','Nominal voltage',model?.nominal_voltage_V||3.7,'V',.001,1000)}</div><div class="field-row">${field('resistance','DC resistance',model?.resistance_mohm||20,'mΩ',.000001,1e6)}<p class="field-note">Capacity is stored charge. Resistance sets the immediate voltage drop and heating under load.</p></div><p class="helper">A basic estimate holds the reference voltage and electrical parameters constant. Add your measured voltage curve or an advanced model below for more detail.</p><details><summary>Source and operating limits</summary><div class="field"><label for="custom-source">Datasheet or measurement link</label><input id="custom-source" name="source" type="url" placeholder="https://…" value="${esc(model?.source_url||'')}"></div><p class="helper">Use limits from your own source. An empty field leaves that limit unknown.</p><div class="field-row"><div class="field"><label for="custom-discharge">Discharge limit (A)</label><input id="custom-discharge" name="discharge" type="number" min="0" max="100000" step="any" value="${model?.operating_limits?.max_discharge_A??''}" placeholder="Unknown"></div><div class="field"><label for="custom-charge">Charge limit (A)</label><input id="custom-charge" name="charge" type="number" min="0" max="100000" step="any" value="${model?.operating_limits?.max_charge_A??''}" placeholder="Unknown"></div></div></details><div class="field thermal-choice"><label for="custom-thermal-mode">Temperature estimate</label><select id="custom-thermal-mode" name="thermal_mode"><option value="example" selected>Use example cylindrical-cell heat properties</option><option value="custom">Use my own heating and cooling data</option><option value="none">Electrical results only</option></select><p class="helper">The example estimates heating with assumed properties. You can replace them below.</p></div><details><summary>My heating and cooling data</summary><p class="helper">Choose “Use my own heating and cooling data” above, then enter both values.</p><div class="field-row"><div class="field"><label for="custom-heat">Heat capacity (J/°C)</label><input id="custom-heat" name="heat" type="number" min="0.001" max="100000000" step="any" placeholder="Optional"></div><div class="field"><label for="custom-cooling">Cooling to room (W/°C)</label><input id="custom-cooling" name="cooling" type="number" min="0" max="1000000" step="any" placeholder="Optional"></div></div></details><details><summary>Import a measured curve or model</summary><p class="helper">CSV: two columns named <code>soc_pct,voltage_V</code>, with charge in percent. The other values above still apply. JSON: a complete cell model using the <a href="/custom-cell-format.md" target="_blank" rel="noopener">import format</a>; it replaces the values above.</p><div class="field"><label for="custom-file">Cell data file</label><input id="custom-file" name="file" type="file" accept=".csv,.json,text/csv,application/json"></div></details><div id="custom-cell-error" role="alert"></div><div class="dialog-footer"><button type="button" class="quiet" data-act="close-dialog">Cancel</button><button type="submit" class="primary">${model?'Save new cell version':'Save cell'}</button></div></form>`;
}

export async function readCustomCell(form){
 const d=new FormData(form),definition={name:d.get('name').trim(),capacity_Ah:Number(d.get('capacity')),nominal_voltage_V:Number(d.get('voltage')),resistance_mohm:Number(d.get('resistance')),source:d.get('source').trim(),operating_limits:{}};
 for(const [name,key] of [['discharge','max_discharge_A'],['charge','max_charge_A']])if(d.get(name)!=='')definition.operating_limits[key]=Number(d.get(name));
 if(d.get('thermal_mode')==='custom'){
  if(d.get('heat')===''||d.get('cooling')==='')throw new Error('Provide both heat capacity and cooling conductance, or leave both empty.');
  definition.thermal_defaults={heat_capacity_J_K:Number(d.get('heat')),ambient_conductance_W_K:Number(d.get('cooling'))};
 }
 if(d.get('thermal_mode')==='example')definition.thermal_preset='example_cylindrical/1';
 if(d.get('thermal_mode')==='none')definition.thermal_defaults=null;
 const file=form.querySelector('#custom-file').files[0];let args={definition};
 if(file){
  if(file.size>120000)throw new Error('Choose a cell file smaller than 120 KB.');
  const text=await file.text();
  if(file.name.toLowerCase().endsWith('.json')){try{args={definition:JSON.parse(text)};}catch{throw new Error('The JSON file could not be read. Check its syntax and try again.');}}
  else if(file.name.toLowerCase().endsWith('.csv'))args={csv_text:text,metadata:definition};
  else throw new Error('Choose a JSON model or a CSV voltage curve.');
 }
 if(form.dataset.parent)args.parent_key=form.dataset.parent;
 return args;
}

export function modelDescription(m){return m.custom?(m.basic?'Your basic electrical estimate':'Your imported electrical model'):m.legacy?'Original nominal-temperature fit':'Temperature-dependent model';}
