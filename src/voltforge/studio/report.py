"""Readable engineering report built from the immutable experiment, never invented metrics."""
from html import escape
from io import StringIO
import threading

_plot_lock=threading.Lock()


def html_report(record):
    metrics=record['summary']['metrics'];graph=record['graph'];settings=record['settings']
    names={c['id']:c['name'] for c in graph['cells']}
    def val(value,unit='',digits=2):
        return 'Not applicable' if value is None else f'{value:.{digits}f} {unit}'.strip()
    values=[('Highest cell temperature',val(metrics['peak_temperature_C'],'°C')),
            ('Warmest cell',names.get(metrics['warmest_cell'],'Temperature not modeled')),
            ('Largest cell current',val(metrics['peak_cell_current_A'],'A')),
            ('Lowest battery voltage',val(metrics['minimum_voltage_V'],'V',3)),
            ('Energy delivered',val(metrics['delivered_energy_Wh'],'Wh')),
            ('Energy received',val(metrics.get('received_energy_Wh'),'Wh')),
            ('Elapsed test time',val(metrics['duration_s']/60,'min')),
            ('Largest temperature difference',val(metrics['maximum_temperature_spread_C'],'°C'))]
    table=lambda rows:'<table>'+''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</table>'
    plots=[]
    # Matplotlib is already part of the fitted-model runtime. Keep its rendering serialized.
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_svg import FigureCanvasSVG
    time=[r['time_s']/60 for r in record['rows']]
    with _plot_lock:
        for field,title,unit in [('cell_current_A','Cell currents','A'),('temperature_C','Cell temperatures','°C'),('cell_voltage_V','Cell voltages','V')]:
            if field=='temperature_C' and not record['summary'].get('thermal_available',True):continue
            fig=Figure(figsize=(9,3.2),layout='constrained');ax=fig.subplots()
            for i,c in enumerate(graph['cells']):ax.plot(time,[r[field][i] for r in record['rows']],label=c['name'],linewidth=1.6)
            ax.set(xlabel='Time (min)',ylabel=unit,title=title);ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
            ax.legend(fontsize=8,ncols=min(4,len(graph['cells'])),frameon=False)
            stream=StringIO();FigureCanvasSVG(fig).print_svg(stream)
            svg=stream.getvalue();plots.append(svg[svg.index('<svg'):]);fig.clear()
    cards=record.get('model_cards',{})
    legacy_names={key:f'Original LG M50T sample {i+1}' for i,key in enumerate(('P7','P17','P19','P13'))}
    cells=[(c['name'],cards.get(c['model'],{}).get('name',legacy_names.get(c['model'],c['model'])),val(c['charge_pct'],'%'),val(c['temperature_C'],'°C')) for c in graph['cells']]
    def terminal(t):
        cid,pole=t.split(':');return names[cid]+(' positive' if pole=='p' else ' negative')
    links=[(terminal(w['a']),terminal(w['b']),val(w['resistance_mohm'],'mΩ'),w['source']) for w in graph['connections']]
    loads=[(val(p['start_s']/60,'min'),val(p['end_s']/60,'min'),val(p['current_A'],'A')) for p in settings['profile']]
    stopped='<p class="notice">'+escape(record['stop']['message'])+'</p>' if record['stop'] else ''
    coverage=record['summary'].get('coverage',{})
    checks=[('Quantity','Calculated value','Target','Outcome')]
    check_names={'temperature_C':'Highest cell temperature (°C)','current_A':'Largest cell current (A)','min_voltage_V':'Lowest battery voltage (V)','imbalance_pct':'Current difference (%)'}
    status_names={'within_target':'Within nominal model target','exceeded':'Exceeded','inconclusive':'Incomplete mission; inconclusive','not_applicable':'Not applicable','not_modeled':'Not modeled'}
    for c in record['summary']['checks']:
        checks.append((check_names.get(c['metric'],c['metric']),val(c['value']),val(c['target']),status_names.get(c['status'],c['status'])))
    complete=coverage.get('complete',record['status']=='completed')
    service_met=record['summary'].get('assessment',{}).get('requested_demand_met',complete)
    completion='The full time horizon was calculated. '+('The requested current duty was served.' if service_met else 'The requested duty was not fully served.') if complete else 'This partial calculation cannot establish requirements for the uncalculated remainder.'
    assessment='<h2>Requirements and coverage</h2><p>Calculated '+val(coverage.get('completed_duration_s',metrics['duration_s']),'s')+' of '+val(coverage.get('requested_duration_s',metrics['duration_s']),'s')+'. '+completion+'</p>'+ (table(checks) if len(checks)>1 else '<p>No application targets were configured. Component and model-use checks still apply.</p>')
    limit_coverage=record['summary'].get('operating_limit_coverage')
    if limit_coverage:
        rows=[('Cell','Calculated current directions','Operating-limit coverage')]
        for entry in limit_coverage['cells']:
            rows.append((names.get(entry['cell'],entry['cell']),', '.join(entry['directions']) or 'Rest',
                         'Recorded for these directions' if entry['complete'] else 'Missing: '+', '.join(entry['missing'])))
        assessment+='<h2>Cell operating-limit coverage</h2>'+table(rows)+'<p>'+escape(limit_coverage['note'])+'</p>'
    else:
        assessment+='<p>Cell operating-limit coverage was not recorded in this historical result; a completed calculation does not establish that all limits were assessed.</p>'
    control=record['summary'].get('protection');service=record['summary'].get('service')
    if control:
        config=control['config'];event=control['event']
        assessment+='<h2>Virtual sensing and protection</h2><p>'+escape(control['sensing'])+'. '+escape(control['actuator'])+'.</p>'
        assessment+=table([('Sensor sample interval',val(config['sample_period_s'],'s')),('Declared response delay',val(config['response_delay_s'],'s')),
                           ('Cell-current threshold',val(config['current_max_A'],'A')),('Cell-voltage floor',val(config['voltage_min_V'],'V')),
                           ('Cell-temperature ceiling',val(config['temperature_max_C'],'°C')),('Source or assumption',config['source'])])
        if event:
            assessment+=table([('Triggering cell',names.get(event['cell'],'Cell')),('Detected at',val(event['detected_time_s'],'s')),
                               ('True simulated value',val(event['true_value'],event['unit'])),('Virtual measured value',val(event['measured_value'],event['unit'])),
                               ('Threshold',val(event['threshold'],event['unit'])),('Scheduled disconnect',val(event['disconnect_time_s'],'s')),
                               ('Actuated within calculated horizon','Yes' if control['actuated'] else 'No')])
        assessment+=table([('Requested demand met','Yes' if service['requested_demand_met'] else 'Not established or not met'),
                           ('Known unserved demand',val(service['unserved_demand_s'],'s')),('Unconfirmed remaining demand',val(service['unconfirmed_requested_demand_s'],'s')),
                           ('Unserved requested charge',val(service['unserved_requested_charge_As'],'A·s'))])
        assessment+='<p>Calculating the time horizon does not establish delivery of the requested duty after a disconnect. Parallel-cell currents can continue internally while external current is zero.</p>'
    physical=record['summary'].get('physical_components',{})
    if physical.get('conductors') or physical.get('output_routes'):
        assessment+='<h2>Physical connection trade-offs</h2>'+table([('Dimensioned conductor mass',val(physical['conductor_mass_g'],'g')),('Connections without dimensions',physical['undimensioned_connections'])])
        for link in physical['conductors']+physical.get('output_routes',[]):
            c=link['definition']
            assessment+='<h3>'+escape(link['connection'])+'</h3>'+table([('Material',c['material']),('Length × width × thickness',f'{c["length_mm"]:g} × {c["width_mm"]:g} × {c["thickness_mm"]:g} mm'),
                ('Bulk resistance',val(link['bulk_resistance_mohm'],'mΩ',4)),('Total end-contact resistance',val(link['contact_mohm'],'mΩ',4)),
                ('Total connection resistance',val(link['resistance_mohm'],'mΩ',4)),('Conductor mass',val(link['mass_g'],'g',3)),
                ('Material reference temperature',val(c['reference_temperature_C'],'°C')),('Material source',c['material_source']),('Dimension/contact source or assumption',c['assumption_source'])])
        assessment+='<p>'+escape(physical['scope'])+'</p>'
    card_rows=[('Cell model','Source','Evidence')]+[(c.get('name',key),c.get('source_url','Source recorded with model'),c.get('status','User-provided or historical model')) for key,c in cards.items()]
    model_text=escape(record['summary'].get('model','Saved equivalent electrical and thermal model'))
    thermal_assumptions=record['summary'].get('thermal_assumptions',[])
    evidence='<h2>Model and evidence</h2><p>'+model_text+'. Heat-transfer parameters and contacts are the saved fixture assumptions. Numerical reproduction does not establish physical module accuracy or a hardware safety rating.</p>'+(table(card_rows) if len(card_rows)>1 else '')+(''.join('<p>'+escape(names.get(a['cell'],'Cell')+': '+a['status']+'. '+str(a.get('source','')))+'.</p>' for a in thermal_assumptions))
    for entry in thermal_assumptions:
        parameters=entry.get('parameters',{})
        rows=[('Heat property','Value','Source or assumption')]
        for key,title,unit in [('heat_capacity_J_K','Heat capacity','J/K'),('ambient_conductance_W_K','Cooling to surroundings','W/K')]:
            if key in parameters:
                item=parameters[key];rows.append((title,val(item['value'],unit,4),item['source']))
        if len(rows)>1:evidence+='<h3>'+escape(names.get(entry['cell'],'Cell'))+'</h3>'+table(rows)
    case=record.get('case',record['summary'].get('case'))
    if case:
        assessment='<h2>'+escape(case['description']['name'])+'</h2><p>'+escape(case['description']['purpose'])+'</p><p>'+escape(case['description']['source'])+'</p><p class="meta">Application record '+escape(case['fingerprint'])+'; requirements '+escape(case['requirements_fingerprint'])+'</p>'+assessment
    application=record['summary'].get('application')
    if application:
        rows=[('Requirement','Value','Basis','Why')]+[(r['label'],val(r['value'],r['unit'],4),r['basis'],r['reason']) for r in application['requirements']]
        assessment='<h2>'+escape(application['name'])+'</h2><p>'+escape(application['purpose'])+'</p>'+table(rows)+('<p>'+escape(application['approximation'])+'</p>' if application['approximation'] else '')+assessment
    warnings=record['summary'].get('design_warnings')
    if warnings:
        assessment+='<h2>Wiring warnings</h2><ul>'+''.join('<li>'+escape(w['message'])+'</li>' for w in warnings)+'</ul>'
    charging=record['summary'].get('charging')
    if charging:
        rows=[('Quantity','Value'),('Elapsed time',val(charging['elapsed_s'],'s',4))]
        if charging.get('version')=='voltforge.pack-charge/2':
            rows += [('Pack charge received (gross)',val(charging['received_charge_Ah'],'Ah',4)),
                     ('Pack charge delivered (gross)',val(charging['delivered_charge_Ah'],'Ah',4)),
                     ('Net pack charge gained',val(charging['net_charge_gained_Ah'],'Ah',4))]
            rows += [(names.get(cell,cell)+' net charge gained',val(value,'Ah',4)) for cell,value in charging['per_cell_charge_gained_Ah'].items()]
        else:
            rows.append(('Aggregate cell charge gained (historical; not pack Ah)',val(charging.get('charge_gained_Ah'),'Ah',4)))
        rows += [('Energy received',val(charging['energy_received_Wh'],'Wh',4)),('Why it stopped',charging['stop_message'])]
        assessment+='<h2>Charging result</h2>'+table(rows)+'<p>'+escape(charging['note'])+'</p>'
    link_checks=record['summary'].get('link_checks')
    if link_checks:
        rows=[('Connection','Peak current','Peak resistive loss')]
        for link in link_checks['links']:
            # Historical zero-ohm summaries used zero for an uncomputed current.
            wire=next((w for w in graph['connections'] if w['id']==link['connection']),None)
            current=None if wire and wire['resistance_mohm']==0 else link.get('peak_current_A')
            rows.append((link['connection'],'Not computed (ideal link)' if current is None else val(current,'A',4),val(link['peak_loss_W'],'W',4)))
        assessment+='<h2>Calculated connection currents</h2>'+table(rows)+'<p>'+escape(link_checks['note'])+'</p>'
    parts=record.get('parts')
    if parts:
        rows=[('Part','Quantity','Unit price','Cost','Compatibility')]
        for line in parts['lines']:
            compatibility=line.get('compatibility')
            status=compatibility['status'].replace('_',' ') if compatibility else 'Not assessed' if line.get('slot') in ('converter','protection') else 'Listed item'
            rows.append((line['part'],f'{line["quantity"]:.4g} {line["unit"]}',f'{line["currency"]} {line["unit_price"]:,.2f}' if line['priced'] else line['note'],
                         f'{line["currency"]} {line["cost"]:,.2f}' if line['priced'] else 'Not priced',status))
        assessment+='<h2>Parts and listed cost</h2>'+table(rows)+'<p>'+escape(' + '.join(f'{k} {v:,.2f}' for k,v in parts['subtotals'].items()))+(' plus unpriced parts' if parts['unpriced'] else '')+'. '+escape(parts['scope'])+' Prices checked '+escape(str(parts.get('checked')))+'.</p>'
        for line in parts['lines']:
            compatibility=line.get('compatibility')
            if compatibility:
                details=compatibility.get('reasons',[])+compatibility.get('conditions',[])
                assessment+='<p>'+escape(line['part']+': '+' '.join(details))+'</p>'
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>VOLT-FORGE experiment report</title><style>body{font:15px/1.65 system-ui;color:#213247;max-width:900px;padding:40px 24px;margin:auto}h1{font-size:32px;line-height:1.2}h2{font-size:21px;margin:34px 0 12px}p{max-width:80ch;color:#52647a}table{width:100%;border-collapse:collapse;font-size:13px}td{padding:10px 14px 10px 0;border-bottom:1px solid #dfe6ee}svg{max-width:100%;height:auto}a{color:#2458c5}.notice{padding:14px;background:#f5f0e7}.meta{font-size:12px}footer{margin-top:40px;border-top:1px solid #dfe6ee;font-size:12px;color:#596b80}@media print{body{padding:0}svg,table{break-inside:avoid}h2{break-after:avoid}}</style>'''+f'<h1>{escape(record["design_name"])}</h1><p>{escape(record["name"])}</p><p class="meta">Saved {escape(record["created_utc"])} · Numerical simulation</p>'+stopped+assessment+'<h2>Results</h2>'+table(values)+'<h2>What this experiment shows</h2>'+''.join('<p>'+escape(i)+'</p>' for i in record['summary']['insights'])+''.join(plots)+'<h2>Test conditions</h2><p>Positive current discharges through the chosen battery output. Negative current charges. Room temperature: '+val(settings['ambient_C'],'°C')+'. Solver step: '+val(settings['dt_s'],'s')+'.</p>'+table([('Start','End','Battery current')]+loads)+'<h2>Cells and starting states</h2>'+table([('Cell','Model profile','Starting charge','Starting temperature')]+cells)+'<h2>Electrical connections</h2>'+table([('First terminal','Second terminal','Resistance','Source')]+links)+evidence+'<footer>Open results.csv for the numeric series. Run replay.py with requirements.txt to reproduce this experiment using its captured model and source versions.</footer></html>'
