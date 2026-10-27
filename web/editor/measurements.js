import {escapeHTML as esc, bounds, number, RequestEpoch} from '/state.mjs';
const $ = s => document.querySelector(s);
const epoch = new RequestEpoch();
let record, selectedRow;
async function api(path) {
  const response = await fetch(path);
  const body = await response.json();
  if (!response.ok || body.status !== 'ok') throw new Error(body.error?.message || 'Measurement request failed.');
  return body.result;
}
function notice(text, error=false) {
  $('#measurement-notice').hidden=!text;$('#measurement-notice').textContent=text;
  $('#measurement-notice').className='notice'+(error?' error':'');
}
function chart(selector, name, width, css) {
  const points=record.overview.channels[name].map(p=>[p[0],displayValue(name,p[1]),p[2],p[3]]), height=220, left=56, right=16, top=18, bottom=35;
  const [lo,hi]=bounds(points.map(p=>p[1]));
  const duration=record.summary.duration_s;
  const x=t=>left+t/duration*(width-left-right), y=v=>height-bottom-(v-lo)/(hi-lo)*(height-top-bottom);
  const parts=[];
  for(let i=0;i<5;i++) {
    const v=lo+(hi-lo)*i/4, t=duration*i/4;
    parts.push(`<line class="chart-grid" x1="${left}" x2="${width-right}" y1="${y(v)}" y2="${y(v)}"/><text class="measurement-axis" x="${left-9}" y="${y(v)+4}" text-anchor="end">${number(v,hi-lo<1?3:1)}</text><text class="measurement-axis" x="${x(t)}" y="${height-15}" text-anchor="middle">${number(t/60,1)}</text>`);
  }
  let segment=null;
  const d=points.map(p=>{const command=p[3]===segment?'L':'M';segment=p[3];return `${command}${x(p[0]).toFixed(2)},${y(p[1]).toFixed(2)}`;}).join(' ');
  parts.push(`<path class="measurement-line ${css}" d="${d}"/><text class="measurement-axis" x="${width-right}" y="${height-1}" text-anchor="end">Time (min)</text>`);
  if(selectedRow)parts.push(`<line class="measurement-cursor" x1="${x(selectedRow.elapsed_s)}" x2="${x(selectedRow.elapsed_s)}" y1="${top}" y2="${height-bottom}"/>`);
  $(selector).innerHTML=`<title>${esc(name)} (${esc(record.units[name])}), source measurements</title>`+parts.join('');
}
function plots() {
  chart('#current-plot','current',580,'');chart('#voltage-plot','voltage',580,'voltage-line');
  // Responsive viewBox keeps sensor axis labels readable on phones.
  const width=window.innerWidth<800?580:1160;
  $('#sensor-plot').setAttribute('viewBox',`0 0 ${width} 220`);
  chart('#sensor-plot',$('#sensor-channel').value,width,'sensor-line');
}
function sampleValues() {
  const sensor=$('#sensor-channel').value;
  const fields=['current','voltage',sensor,'SOC','liquid_flow'].filter((name,i,a)=>a.indexOf(name)===i);
  $('#sample-values').innerHTML=fields.map(name=>`<div><span>${esc(signalName(name))}</span><strong>${number(displayValue(name,selectedRow.values[name]),2)} <small>${esc(displayUnit(name))}</small></strong></div>`).join('');
}
async function sample(index) {
  if(!Number.isInteger(index)||index<0||index>=record.summary.sample_count) {
    notice('Choose an integer sample index within the recorded range.',true);return;
  }
  const request=epoch.begin();
  $('#sample-index').value=index;$('#sample-number').value=index;
  selectedRow=null;plots();
  $('#sample-position').textContent=`Loading sample ${index}…`;
  $('#sample-values').textContent='Loading exact source sample…';
  try {
    const data=await api(`/api/measurements/ID01?view=rows&offset=${index}&limit=1`);
    if(!epoch.current(request))return;
    selectedRow=data.rows[0];
    $('#sample-position').textContent=`${number(selectedRow.elapsed_s/60,2)} minutes into the experiment`;
    $('#sample-previous').disabled=index===0;$('#sample-next').disabled=index===record.summary.sample_count-1;
    sampleValues();plots();
    notice('');
  }catch(error){if(epoch.current(request))notice(error.message,true);}
}
function downloadSummary() {
  const {overview,...summary}=record;
  const blob=new Blob([JSON.stringify(summary,null,2)+'\n'],{type:'application/json'});
  const url=URL.createObjectURL(blob), link=document.createElement('a');
  link.href=url;link.download='freetwinev_ID01_measured_summary.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
async function start() {
  try {
    const catalogue=await api('/api/measurements');
    $('#source-access').textContent=catalogue.development_available?'A development experiment is available below. Other experiments are reserved for independent assessment.':'The original measurements are available from the published dataset.';
    if(!catalogue.development_available)return;
    record=await api('/api/measurements/ID01?view=overview');
    const s=record.summary;
    $('#measurement-metrics').hidden=false;
    const metrics=[['Recorded samples',s.sample_count.toLocaleString()],['Recorded span',number(s.duration_s/60,1)+' min'],['Source current range',number(s.ranges.current.min,2)+' to '+number(s.ranges.current.max,2)+' A'],['Source voltage range',number(s.ranges.voltage.min,3)+' to '+number(s.ranges.voltage.max,3)+' V']];
    $('#measurement-metrics').innerHTML=metrics.map(([label,value])=>`<div><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join('');
    $('#sensor-channel').innerHTML=Object.keys(record.units).filter(n=>!['timesamp','current','voltage'].includes(n)).map(n=>`<option value="${esc(n)}">${esc(signalName(n))} (${esc(displayUnit(n))})</option>`).join('');
    $('#sensor-channel').value='temp_cell-1_TH20';
    $('#measurement-limitations').innerHTML=record.limitations.map(t=>`<li>${esc(t)}</li>`).join('');
    $('#measurement-provenance').textContent='Source: Plzak, Berta, Urge and Bata, FreeTwinEV (2026). The original sample times and readings are preserved. No model predictions are overlaid on these measurements.';
    $('#sample-index').max=s.sample_count-1;$('#sample-number').max=s.sample_count-1;
    $('#measurement-content').hidden=false;
    await sample(0);
    $('#sample-index').addEventListener('input',e=>sample(Number(e.target.value)));
    $('#sample-number').addEventListener('change',e=>sample(e.target.value.trim()?Number(e.target.value):NaN));
    $('#sample-previous').addEventListener('click',()=>sample(Number($('#sample-index').value)-1));
    $('#sample-next').addEventListener('click',()=>sample(Number($('#sample-index').value)+1));
    $('#sensor-channel').addEventListener('change',()=>{plots();if(selectedRow)sampleValues();});
    $('#download-summary').addEventListener('click',downloadSummary);
    window.addEventListener('resize',plots);
  }catch(error){notice('The measured experiment could not be opened. The source dataset remains available through the link above.',true);}
}
function displayValue(name,value){return value===null?null:record.units[name]==='K'?value-273.15:value;}
function displayUnit(name){return record.units[name]==='K'?'°C':record.units[name];}
function signalName(name){const names={current:'Module current',voltage:'Module voltage',SOC:'Recorded state of charge',liquid_flow:'Coolant flow',temp_ambient:'Ambient temperature',temp_inlet:'Coolant inlet temperature',temp_outlet:'Coolant outlet temperature'};return names[name]||name.replace(/^temp_cell-(\d)_TH(\d+)$/,'Cell $1 · temperature sensor $2').replace(/^temp_TH(\d+)$/,'Temperature sensor $1');}
async function modelSources(){try{const {result}=await fetch('/api/studio').then(r=>r.json());$('#model-data-rows').innerHTML=result.library.map((m,i)=>`<tr><td>Measured sample ${i+1}</td><td>${number(m.capacity_Ah,2)} Ah</td><td>${number(m.resistance_mohm,1)} mΩ</td></tr>`).join('');}catch{ $('#model-data-rows').innerHTML='<tr><td colspan="3">Open the published experiments to inspect the original source.</td></tr>';}}
modelSources();start();
