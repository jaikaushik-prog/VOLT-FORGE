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
.one{top:27px}.two{top:347px}
.proofs{position:absolute;left:0;right:0;top:772px;display:grid;grid-template-columns:repeat(3,1fr);gap:28px}
.proofs div{font-size:18px;font-weight:500;line-height:1.42;color:#3F4E5D}
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
    d = json.loads(args.data.read_text()); best, m, cost = d['best'], d['market'], d['cost']
    n = best['count']; k = d['kpi']
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>VOLT-FORGE Round 1</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&display=swap" rel="stylesheet"><style>{CSS}</style></head><body><div class="slide">
<img class="logo-left" src="assets/logo_teliport.png" alt="Teliport"><img class="logo-right" src="assets/logo_tata.png" alt="Tata Elxsi">
<header><h1>Test a battery <em>before you build it</em></h1><p>VOLT-FORGE connects every battery design decision to what it physically changes</p></header>
<section class="col left">
<div class="c"><h2>Problem understanding</h2><h3>Cells never share the load evenly</h3><p>Say you need a Raspberry Pi 5 gateway to survive a <b>10-minute power cut at 25 W</b>. Four cells in parallel sounds easy, until the cell closest to the output takes more current than the rest, runs hotter and sets the limit for the whole pack.</p></div>
<div class="c"><h2>Desirability</h2><h3>You shouldn't need a lab to learn that</h3><p>Right now you find out by buying parts and hoping. A student can't afford that, and an engineer can't wait for it. Here you wire the circuit on screen, run it and see which cell struggles <b>before spending a rupee</b>.</p></div>
<div class="c"><h2>Technical feasibility</h2><h3>So how few cells can do this job?</h3><p>We tested it. <b>Two cells</b> kept the Pi running for the full 10 minutes in all {best['required_cases']} tests, even with one weak cell, and never hit their limit. One cell couldn't: the app refused it before it started. And the whole thing runs on a normal laptop.</p></div>
</section>
<section class="proto"><h2>Prototype &amp; evidence<span>The real Pi design, then 4 cells against 2 under the same load</span></h2>
<div class="shot one"><img src="assets/circuit.png" alt="The 4-cell Pi backup circuit in VOLT-FORGE with the properties of Cell 1 open"></div>
<div class="shot two"><img src="assets/compare.png" alt="VOLT-FORGE comparing the 4-cell and 2-cell designs, with the full results table"></div>
<div class="proofs"><div><b>{k['study_runs']:,} what-if runs.</b> Weak cells, bad links, poor cooling: we tried to break it first.</div><div><b>{k['lab_experiments']} published lab experiments.</b> Real four-cell test data, with all {k['data_files']} files verified intact.</div><div><b>{k['sealed_total']} tests kept sealed.</b> Held back from every fit, so the final exam uses unseen data.</div></div>
</section>
<section class="col right">
<div class="c"><h2>Engineering quality</h2><h3>Now, why should you trust that?</h3><p>Heat is just electricity that never reached the load. So every run has to balance: energy out of the cells equals energy delivered plus heat. If it doesn't, the result gets flagged. Cooling varies by rig, so temperature stays a <b>range</b>.</p></div>
<div class="c"><h2>Innovation</h2><h3>You don't have to guess the answer</h3><p>You could try every cell count by hand. Or press <b>Find the smallest design</b>: it rebuilds the circuit at each size, tests them all and shows what survives. For the Pi, that meant {n} cells, not 4, at half the cell cost.</p></div>
<div class="c"><h2>Business viability</h2><div class="market"><svg width="118" height="118" viewBox="0 0 176 176" role="img" aria-label="TAM, SAM and SOM nested circles"><circle cx="88" cy="88" r="88" fill="#D5ECF8"/><circle cx="88" cy="118" r="58" fill="#59B9E6"/><circle cx="88" cy="146" r="30" fill="#0B6FA8"/></svg>
<ul><li><b>{lakh(m['tam_students'])}</b>TAM, engineering students</li><li><b>{lakh(m['sam_students'])}</b>SAM, electrical, electronics, mechanical</li><li><b>{m['som_colleges']:.0f}</b>SOM, colleges, 5% assumed</li></ul></div>
<div class="cost">₹{cost['total_crore']:.0f} crore</div><p>to build all of it, from a measured dataset to the full app. {cost['person_years']:.0f} person-years, about 2% of AspenTech's yearly R&amp;D.</p></div>
</section>
<footer><span><b>These results are simulated.</b>&nbsp; Next we bench-test real cells and put it in front of students and engineers.</span></footer>
</div></body></html>"""
    args.out.write_text(html)


if __name__ == '__main__':
    main()
