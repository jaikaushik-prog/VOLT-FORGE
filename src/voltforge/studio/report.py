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
            ('Warmest cell',names[metrics['warmest_cell']]),
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
            fig=Figure(figsize=(9,3.2),layout='constrained');ax=fig.subplots()
            for i,c in enumerate(graph['cells']):ax.plot(time,[r[field][i] for r in record['rows']],label=c['name'],linewidth=1.6)
            ax.set(xlabel='Time (min)',ylabel=unit,title=title);ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
            ax.legend(fontsize=8,ncols=min(4,len(graph['cells'])),frameon=False)
            stream=StringIO();FigureCanvasSVG(fig).print_svg(stream)
            svg=stream.getvalue();plots.append(svg[svg.index('<svg'):]);fig.clear()
    cells=[(c['name'],'LG M50T sample '+str(('P7','P17','P19','P13').index(c['model'])+1),val(c['charge_pct'],'%'),val(c['temperature_C'],'°C')) for c in graph['cells']]
    def terminal(t):
        cid,pole=t.split(':');return names[cid]+(' positive' if pole=='p' else ' negative')
    links=[(terminal(w['a']),terminal(w['b']),val(w['resistance_mohm'],'mΩ'),w['source']) for w in graph['connections']]
    loads=[(val(p['start_s']/60,'min'),val(p['end_s']/60,'min'),val(p['current_A'],'A')) for p in settings['profile']]
    stopped='<p class="notice">'+escape(record['stop']['message'])+'</p>' if record['stop'] else ''
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>VOLT-FORGE experiment report</title><style>body{font:15px/1.65 system-ui;color:#213247;max-width:900px;padding:40px 24px;margin:auto}h1{font-size:32px;line-height:1.2}h2{font-size:21px;margin:34px 0 12px}p{max-width:80ch;color:#52647a}table{width:100%;border-collapse:collapse;font-size:13px}td{padding:10px 14px 10px 0;border-bottom:1px solid #dfe6ee}svg{max-width:100%;height:auto}a{color:#2458c5}.notice{padding:14px;background:#f5f0e7}.meta{font-size:12px}footer{margin-top:40px;border-top:1px solid #dfe6ee;font-size:12px;color:#596b80}@media print{body{padding:0}svg,table{break-inside:avoid}h2{break-after:avoid}}</style>'''+f'<h1>{escape(record["design_name"])}</h1><p>{escape(record["name"])}</p><p class="meta">Saved {escape(record["created_utc"])} · Numerical simulation</p>'+stopped+'<h2>Results</h2>'+table(values)+'<h2>What this experiment shows</h2>'+''.join('<p>'+escape(i)+'</p>' for i in record['summary']['insights'])+''.join(plots)+'<h2>Test conditions</h2><p>Positive current discharges through the chosen battery output. Negative current charges. Room temperature: '+val(settings['ambient_C'],'°C')+'. Solver step: '+val(settings['dt_s'],'s')+'.</p>'+table([('Start','End','Battery current')]+loads)+'<h2>Cells and starting states</h2>'+table([('Cell','Model profile','Starting charge','Starting temperature')]+cells)+'<h2>Electrical connections</h2>'+table([('First terminal','Second terminal','Resistance','Source')]+links)+'<h2>Model and evidence</h2><p>Electrical behaviour uses fitted LG M50T reference and relaxation models. Heat comes from electrical resistor losses and the saved heat-transfer network. The current model uses nominal-temperature electrical parameters; independent module prediction accuracy and wider temperature operation require the calibration and assessment described in the project science plan.</p><p><a href="https://data.mendeley.com/datasets/zh58byr53c/2">Original cell and module experimental campaign</a>. The experiment file contains all thermal properties, contacts, targets, model hashes and conservation diagnostics. This report does not constitute a hardware safety assessment.</p><footer>Open results.csv for the numeric series. Run replay.py with requirements.txt to reproduce this experiment using its captured model and source versions.</footer></html>'
