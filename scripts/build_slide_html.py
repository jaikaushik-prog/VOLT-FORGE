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
.logo-left{position:absolute;left:6px;top:0;height:112px}
.logo-right{position:absolute;right:6px;top:0;height:108px}
header{position:absolute;left:0;right:0;top:20px;text-align:center}
h1{font-size:60px;font-weight:800;letter-spacing:-1.6px;line-height:1.05}
h1 em{font-style:normal;color:#0091CC}
header p{font-size:25px;font-weight:500;color:#566575;margin-top:8px}
.col{position:absolute;top:150px;width:392px;height:820px;display:flex;flex-direction:column;justify-content:space-between}
.left{left:48px}.right{right:48px}
.c h2{font-size:18px;font-weight:800;color:#0091CC;letter-spacing:.2px;text-transform:uppercase}
.c .big{font-size:50px;font-weight:800;letter-spacing:-1.3px;line-height:1.12;margin-top:6px;color:#10202F}
.c p{font-size:21px;font-weight:500;line-height:1.36;color:#3F4E5D;margin-top:6px}
.c p b{font-weight:800;color:#10202F}
.proto{position:absolute;left:470px;top:150px;width:980px;height:820px}
.proto h2{font-size:18px;font-weight:800;color:#0091CC;letter-spacing:.2px;text-transform:uppercase;text-align:center}
.window{position:absolute;border-radius:16px;overflow:hidden;background:#fff}
.back{left:0;top:34px;width:980px;border:2px solid #D3DFE8}
.back img,.front img{display:block;width:100%}
.front{right:-14px;top:448px;width:590px;border:3px solid #0B6FA8}
.proofs{position:absolute;left:0;right:0;bottom:0;display:flex;justify-content:space-between;padding:0 6px}
.proofs div{font-size:21px;font-weight:600;color:#3F4E5D}
.proofs b{font-weight:800;color:#10202F}
.market{display:flex;align-items:center;gap:16px;margin-top:8px}
.market svg{flex:none}
.market ul{list-style:none}
.market li{font-size:17px;font-weight:600;color:#3F4E5D;line-height:1.25;margin-bottom:9px}
.market li b{display:block;font-size:24px;font-weight:800;color:#10202F}
.value{font-size:21px;font-weight:500;color:#3F4E5D;line-height:1.36;margin-top:6px}
.value b{font-weight:800;color:#10202F}
footer{position:absolute;left:48px;right:48px;bottom:26px;height:58px;border-radius:29px;background:#0B6FA8;color:#fff;display:flex;align-items:center;justify-content:center;font-size:25px;font-weight:600}
footer b{font-weight:800}
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=ROOT/'reports/slide_v4/data.json')
    parser.add_argument('--out', type=Path, default=ROOT/'reports/slide_v4/slide.html')
    args = parser.parse_args()
    d = json.loads(args.data.read_text()); best, save, m = d['best'], d['saving'], d['market']
    n = best['count']
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>VOLT-FORGE Round 1</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&display=swap" rel="stylesheet"><style>{CSS}</style></head><body><div class="slide">
<img class="logo-left" src="assets/logo_teliport.png" alt="Teliport"><img class="logo-right" src="assets/logo_tata.png" alt="Tata Elxsi">
<header><h1>Test a battery <em>before you build it</em></h1><p>VOLT-FORGE, a virtual design platform for students and engineers</p></header>
<section class="col left">
<div class="c"><h2>Problem understanding</h2><div class="big">10 min at 25 W</div><p>Keep a Raspberry Pi 5 gateway running through a power cut, inside every cell limit.</p></div>
<div class="c"><h2>Desirability</h2><div class="big">No parts needed</div><p>Students and engineers see what a design does before spending on hardware.</p></div>
<div class="c"><h2>Technical feasibility</h2><div class="big">{best['required_passed']} of {best['required_cases']}</div><p>required Pi cases pass with <b>{n} LG M50T cells</b>. Simple, and within limits.</p></div>
</section>
<section class="proto"><h2>Prototype &amp; evidence</h2>
<div class="window back"><img src="assets/build.png" alt="The VOLT-FORGE canvas with four cells wired to a Raspberry Pi 5 load"></div>
<div class="window front"><img src="assets/results.png" alt="The VOLT-FORGE test verdict for two cells"></div>
<div class="proofs"><div><b>{d['study']['cases']:,}</b> simulated cases</div><div><b>{d['pybamm']['passed']} of {d['pybamm']['cases']}</b> PyBaMM checks</div><div><b>{d['replay']['passed']} of {d['replay']['cases']}</b> exports replay exactly</div></div>
</section>
<section class="col right">
<div class="c"><h2>Engineering quality</h2><div class="big">Energy adds up</div><p>Heat matches electrical loss in every run. Cooling stays a <b>range</b>, not a prediction.</p></div>
<div class="c"><h2>Innovation</h2><div class="big">4 → {n} cells</div><p>The tool finds the smallest design that still does the job.</p></div>
<div class="c"><h2>Business viability</h2><div class="market"><svg width="176" height="176" viewBox="0 0 176 176" role="img" aria-label="TAM, SAM and SOM nested circles"><circle cx="88" cy="88" r="88" fill="#D5ECF8"/><circle cx="88" cy="118" r="58" fill="#59B9E6"/><circle cx="88" cy="146" r="30" fill="#0B6FA8"/></svg>
<ul><li><b>{lakh(m['tam_students'])}</b>TAM: engineering students</li><li><b>{lakh(m['sam_students'])}</b>SAM: electrical, electronics, mechanical</li><li><b>{m['som_colleges']:.0f} colleges</b>SOM: 5%, assumed</li></ul></div>
<p class="value"><b>₹{save['cost_inr']:,.0f} less</b> on cells. Free for students, paid for labs.</p></div>
</section>
<footer><span><b>Simulated, not yet built.</b>&nbsp; Temperature still differs from real data, so next: bench-test real cells, then user trials.</span></footer>
</div></body></html>"""
    args.out.write_text(html)


if __name__ == '__main__':
    main()
