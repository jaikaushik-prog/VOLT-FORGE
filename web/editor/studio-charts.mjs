import {esc,fmt,timeLabel} from './studio-state.mjs';
import {palette} from './studio-canvas.mjs';

export function nearestIndex(rows,time) {
  let a=0,b=rows.length-1;
  while(a<b){const m=Math.floor((a+b)/2);if(rows[m].time_s<time)a=m+1;else b=m;}
  a=a>0&&Math.abs(rows[a-1].time_s-time)<Math.abs(rows[a].time_s-time)?a-1:a;
  // A timestamp at a load change defaults to its right-hand value. The slider
  // still exposes both distinct, saved one-sided samples.
  while(a+1<rows.length&&rows[a+1].time_s===rows[a].time_s)a++;
  return a;
}
export const chartFields={current:{field:'cell_current_A',unit:'A',title:'How the cells share the load'},temperature:{field:'temperature_C',unit:'°C',title:'How the cells warm up'},voltage:{field:'cell_voltage_V',unit:'V',title:'Voltage at each cell'},charge:{field:'charge_pct',unit:'%',title:'Charge remaining'}};
export function chartSvg(test,metric='current',index=0,hidden=new Set()) {
  const field=chartFields[metric]||chartFields.current,rows=test.rows,n=test.graph.cells.length;
  if(metric==='temperature'&&rows.every(r=>r.temperature_C.every(v=>v===null)))return '<div class="chart-unavailable"><h3>Temperature is not modeled for this test.</h3><p>Add measured heat capacity and cooling data to the custom cell to calculate warming. You can still inspect current, voltage and charge.</p></div>';
  const W=1020,H=306,L=58,R=22,T=24,B=42,pw=W-L-R,ph=H-T-B;
  let lo=Infinity,hi=-Infinity;
  for(const r of rows) for(let i=0;i<n;i++) if(!hidden.has(i)){const v=r[field.field][i];if(v!==null){lo=Math.min(lo,v);hi=Math.max(hi,v);}}
  if(!Number.isFinite(lo)){lo=0;hi=1;}
  const pad=Math.max((hi-lo)*.14,metric==='temperature'?.15:metric==='voltage'?.01:.05);lo-=pad;hi+=pad;
  const duration=rows.at(-1).time_s||1,x=t=>L+t/duration*pw,y=v=>T+(hi-v)/(hi-lo)*ph;
  const ticks=Array.from({length:5},(_,i)=>lo+(hi-lo)*i/4);
  const tickDigits=Math.min(4,Math.max(metric==='voltage'?2:1,-Math.floor(Math.log10((hi-lo)/4))));
  const grid=ticks.map(v=>`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="#e4eaf1"/><text x="${L-12}" y="${y(v)+4}" text-anchor="end" fill="#5b6a7d" font-size="12">${fmt(v,tickDigits)}</text>`).join('');
  const axes=`<text class="axis-unit" x="${L-34}" y="${T-10}" fill="#5b6a7d" font-size="12" font-weight="600">${esc(field.unit)}</text><text class="axis-unit" x="${W-R-30}" y="${H-28}" fill="#5b6a7d" font-size="12" font-weight="600">Time</text>`;
  const xticks=Array.from({length:5},(_,i)=>duration*i/4).map(t=>`<text x="${x(t)}" y="${H-12}" text-anchor="middle" fill="#5b6a7d" font-size="12">${esc(timeLabel(t))}</text>`).join('');
  // Extrema-preserving buckets retain spikes when trajectories exceed screen resolution.
  const paths=[];
  for(let k=0;k<n;k++){
    if(hidden.has(k))continue;
    const points=[];const bucket=Math.max(1,Math.floor(rows.length/1000));
    for(let j=0;j<rows.length;j+=bucket){
      const end=Math.min(rows.length,j+bucket);let min=j,max=j;
      for(let p=j+1;p<end;p++){if(rows[p][field.field][k]<rows[min][field.field][k])min=p;if(rows[p][field.field][k]>rows[max][field.field][k])max=p;}
      const events=[];for(let p=j;p<end;p++)if(rows[p].event_side==='before'||rows[p].event_side==='after')events.push(p);
      for(const p of [...new Set([j,min,max,end-1,...events])].sort((a,b)=>a-b))if(rows[p][field.field][k]!==null)points.push(`${x(rows[p].time_s).toFixed(2)},${y(rows[p][field.field][k]).toFixed(2)}`);
    }
    paths.push(`<polyline points="${points.join(' ')}" fill="none" stroke="${palette[k%4]}" stroke-width="2.6" stroke-linejoin="round"/>`);
  }
  const selected=rows[Math.min(index,rows.length-1)],cx=x(selected.time_s);
  const probes=selected[field.field].map((v,i)=>hidden.has(i)||v===null?'':`<circle cx="${cx}" cy="${y(v)}" r="4.6" fill="${palette[i%4]}" stroke="#fff" stroke-width="2"/>`).join('');
  return `<svg id="result-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${field.title}. Use the time control below or hover to inspect values." data-left="${L}" data-width="${pw}" data-total="${W}" data-duration="${duration}" data-min="${lo}" data-max="${hi}">${axes}${grid}${xticks}${paths.join('')}<g id="chart-probe"><line x1="${cx}" x2="${cx}" y1="${T}" y2="${H-B}" stroke="#7f92aa" stroke-dasharray="4 4"/>${probes}</g><rect x="${L}" y="${T}" width="${pw}" height="${ph}" fill="transparent" class="chart-hit"/></svg>`;
}
export function probeSvg(test,metric,index,hidden,lo,hi,duration){
  const field=chartFields[metric],row=test.rows[index],cx=58+row.time_s/duration*940;
  return `<line x1="${cx}" x2="${cx}" y1="24" y2="264" stroke="#7f92aa" stroke-dasharray="4 4"/>`+row[field.field].map((v,i)=>hidden.has(i)||v===null?'':`<circle cx="${cx}" cy="${24+(hi-v)/(hi-lo)*240}" r="4.6" fill="${palette[i%4]}" stroke="#fff" stroke-width="2"/>`).join('');
}
export function pointValues(test,metric,index,hidden=new Set()) {
  const field=chartFields[metric],row=test.rows[index];
  const change=row.event_kind==='protective_disconnect'?'protection disconnect':'load change';
  const side=row.event_side==='before'?' · before '+change:row.event_side==='after'?' · after '+change:'';
  return `<div class="probe-time">${esc(timeLabel(row.time_s)+side)}</div>`+test.graph.cells.map((c,i)=>hidden.has(i)?'':`<div class="probe-value"><span class="series-dot series-${i%4}"></span><span>${esc(c.name)}</span><strong>${row[field.field][i]===null?'Not modeled':fmt(row[field.field][i],metric==='voltage'?3:2)+' <small>'+field.unit+'</small>'}</strong></div>`).join('');
}
