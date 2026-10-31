"""Render the one-slide pitch as HTML from the slide data file, so every number stays traceable."""
from pathlib import Path
import argparse
import json

ROOT = Path(__file__).resolve().parents[1]


def lakh(value): return f'{value/1e5:.1f} lakh'


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;background:#fff;font-family:'Manrope',sans-serif;color:#10202F;overflow:hidden;-webkit-font-smoothing:antialiased}
.slide{position:relative;width:1920px;height:1080px}
.logo-left{position:absolute;left:6px;top:0;height:104px}
.logo-right{position:absolute;right:6px;top:0;height:100px}
header{position:absolute;left:0;right:0;top:12px;text-align:center}
h1{font-size:52px;font-weight:800;letter-spacing:-1.4px;line-height:1.08}
h1 em{font-style:normal;color:#0091CC}
header p{font-size:23px;font-weight:500;color:#566575;margin-top:4px}
.col{position:absolute;top:118px;width:376px;height:872px;display:flex;flex-direction:column;justify-content:space-between}
.left{left:36px}.right{right:36px}
.c h2,.proto h2{font-size:16px;font-weight:800;color:#0091CC;letter-spacing:.3px;text-transform:uppercase}
.c h3{font-size:27px;font-weight:800;letter-spacing:-.5px;line-height:1.18;margin-top:5px;text-wrap:balance}
.c p{font-size:19px;font-weight:500;line-height:1.42;color:#3F4E5D;margin-top:6px}
.c p b,.kpi b{font-weight:800;color:#10202F}
.proto{position:absolute;left:436px;top:118px;width:1048px;height:872px}
.proto h2{text-align:center}
.proto h2 span{color:#566575;font-weight:600;text-transform:none;letter-spacing:0;margin-left:10px}
.shot{position:absolute;left:0;width:1048px;border:2px solid #D3DFE8;border-radius:12px;overflow:hidden;background:#fff}
.shot img{display:block;width:100%}
.one{top:27px}.two{top:370px}
.caption{position:absolute;left:0;right:0;margin:0;text-align:center;font-size:17px;font-weight:500;color:#3F4E5D;line-height:1.3}
.caption b{font-weight:800;color:#10202F}.capone{top:342px}.captwo{top:726px}
.proto h2 a{color:#0B6FA8;font-weight:800}
.applink{position:absolute;left:0;right:0;top:846px;margin:0;text-align:center;font-size:17px;font-weight:500;color:#3F4E5D}
.applink a{color:#0B6FA8;font-weight:800}
.proofs{position:absolute;left:0;right:0;top:756px;display:grid;grid-template-columns:repeat(3,1fr);gap:28px}
.proofs div{font-size:17px;font-weight:500;line-height:1.36;color:#3F4E5D}
.proofs b{font-weight:800;color:#10202F}
.market{display:flex;align-items:center;gap:14px;margin-top:8px}
.market svg{flex:none}
.market ul{list-style:none}
.market li{font-size:14.5px;font-weight:600;color:#3F4E5D;line-height:1.22;margin-bottom:5px}
.market li b{font-size:19px;font-weight:800;color:#10202F;margin-right:5px}
.cost{font-size:34px;font-weight:800;letter-spacing:-.8px;color:#0B6FA8;line-height:1.1;margin-top:8px}
footer{position:absolute;left:36px;right:36px;bottom:16px;height:52px;border-radius:26px;background:#0B6FA8;color:#fff;display:flex;align-items:center;justify-content:center;font-size:23px;font-weight:600}
footer b{font-weight:800}
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=ROOT/'reports/slide_v4/data.json')
    parser.add_argument('--out', type=Path, default=ROOT/'reports/slide_v4/slide.html')
    args = parser.parse_args()
    d = json.loads(args.data.read_text()); best, m, cost, biz = d['best'], d['market'], d['cost'], d['business']
    links = json.loads((args.data.parents[2]/'configs/public_site.json').read_text())
    share, tenmin = d['checks']['post_hoc']['share_detail'][0]['first_10pct'], max(x['ratio'] for x in d['checks']['post_hoc']['ten_minute_rise'])
    n = best['count']; k = d['kpi']
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>VOLT-FORGE Round 1</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&display=swap" rel="stylesheet"><style>{CSS}</style></head><body><div class="slide">
<img class="logo-left" src="assets/logo_teliport.png" alt="Teliport"><img class="logo-right" src="assets/logo_tata.png" alt="Tata Elxsi">
<header><h1>Test a battery <em>before you build it</em></h1><p>VOLT-FORGE connects your battery design decisions to what they physically change</p></header>
<section class="col left">
<div class="c"><h2>Problem understanding</h2><h3>Cells rarely share the load evenly</h3><p>Say a Raspberry Pi 5 gateway must survive a <b>10-minute power cut at 25 W</b>, its full supply rating, at 23 °C. Four cells in parallel sounds easy, until the cell closest to the output takes more current at first and warms sooner. Ageing and packaging come later.</p></div>
<div class="c"><h2>Desirability</h2><h3>You shouldn't need a lab to learn that</h3><p>Today that takes a bench, a paid simulation tool or your own code. Students can't afford that and engineers can't wait. Here you wire the circuit on screen, run it and see which cell struggles <b>before spending a rupee</b>.</p></div>
<div class="c"><h2>Technical feasibility</h2><h3>So how few cells can do this job?</h3><p>We compared 3 and 2 cells against the <span style="white-space:nowrap">4-cell</span> start. <b>Two cells</b> held the Pi for 10 minutes in all {best['required_cases']} simulated tests, even with one weak cell. One cell was refused. It should fit a two-cell Pi UPS board, though we haven't built it, and the tool runs on a laptop.</p></div>
</section>
<section class="proto"><h2>Prototype &amp; evidence<span>Test it out: <a id="site-link">{links['address']}</a></span></h2>
<div class="shot one"><img src="assets/circuit.png" alt="The 4-cell Pi backup circuit in VOLT-FORGE with the properties of Cell 1 open"></div>
<p class="caption capone"><b>Build it.</b> This is the real circuit the solver runs. Click any cell to see and change what's inside it.</p>
<div class="shot two"><img src="assets/compare.png" alt="VOLT-FORGE comparing the 4-cell and 2-cell designs, with the full results table"></div>
<p class="caption captwo"><b>Compare it.</b> Same 25 W job: 2 cells cost and weigh half, but work harder with less voltage margin.</p>
<div class="proofs"><div><b>{k['study_runs']:,} simulated cases.</b> {d['designs']} designs against weak cells, bad links and poor cooling. A full rerun matched exactly.</div><div><b>{k['lab_experiments']} published four-cell experiments.</b> All {k['data_files']} dataset files verified intact, 2 tests compared with the model so far.</div><div><b>{d['pybamm']['passed']} of {d['pybamm']['cases']} solver checks.</b> PyBaMM, an independent solver, matched our voltage and heat.</div></div>
<p class="applink">Every cost, source and check is in the full appendix: <a id="appendix-link">{links['address']}/appendix</a></p>
</section>
<section class="col right">
<div class="c"><h2>Engineering quality</h2><h3>Why should you trust it?</h3><p>Every run must balance its energy, which catches solver errors, not a wrong model. Against published data, voltage and temperature missed all {d['proof_cases']} checks. Current sharing came closer but also missed: the nearest cell took <b>{share['measured'][0]:.0f}%</b> early on, the model said <b>{share['simulated'][0]:.0f}%</b>. Over 10 minutes, real heating stayed within {tenmin:.2f} times the model.</p></div>
<div class="c"><h2>Innovation</h2><h3>You don't have to guess</h3><p>Press <b>Find the smallest design</b>. It rebuilds the circuit at each size and tests it under normal conditions. For the Pi: {n} cells, not 4, at half the cell cost. Our study then stress-tested that.</p></div>
<div class="c"><h2>Business viability</h2><div class="market"><svg width="118" height="118" viewBox="0 0 176 176" role="img" aria-label="TAM, SAM and SOM nested circles"><circle cx="88" cy="88" r="88" fill="#D5ECF8"/><circle cx="88" cy="118" r="58" fill="#59B9E6"/><circle cx="88" cy="146" r="30" fill="#0B6FA8"/></svg>
<ul><li><b>{lakh(m['tam_students'])}</b>TAM, engineering students</li><li><b>{lakh(m['sam_students'])}</b>SAM, electrical, electronics, mechanical</li><li><b>{biz['labs']}</b>SOM, labs at ₹50,000, 5% assumed</li></ul></div>
<div class="cost">₹{cost['total_crore']:.0f} crore</div><p>to build it all. Stage one is ₹{biz['stage1_crore']:.0f} crore: {biz['labs']} labs and {biz['stage1_teams']} teams at ₹{biz['team_price_inr']/1e5:.0f} lakh a year would repay it in {biz['repay_years']} years, before running costs. Students use it free. No customer has seen these prices.</p></div>
</section>
<footer><span><b>Simulated</b> with an assumed 90% converter and 3.3 V floor. <b>Next:</b> a bench test with voltage, current and heat cutoffs, then student and engineer trials.</span></footer>
</div></body></html>"""
    args.out.write_text(html)


if __name__ == '__main__':
    main()
