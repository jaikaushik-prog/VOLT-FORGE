"""Final read-only layout checks through browser-harness, after check_workspace_forms.py.

The user's app is at 8792. VOLT_FORGE_BROWSER_PORT identifies the disposable
project from check_v1_browser.py, including its unrun B1 variant.
"""
import hashlib
import json
import os
import time
from pathlib import Path

ROOT=Path.cwd();OUT=ROOT/'reports/ui_cleanup';checks=[]
PORT=int(os.environ.get('VOLT_FORGE_BROWSER_PORT','8793'))
def value(expression):return js(expression)
def wait_until(expression):
    end=time.monotonic()+20
    while not value(expression):
        assert time.monotonic()<end,expression
        time.sleep(.1)
def click(selector):
    value(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block:'center'}})")
    capture_screenshot(str(OUT/'before_render_action.png'))
    rect=value(f"(()=>{{const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}}}})()")
    click_at_xy(rect['x'],rect['y']);time.sleep(.1)
def actual_workspace():
    goto_url('http://127.0.0.1:8792');wait_for_load()
    wait_until("document.querySelector('#run-state').textContent.includes('Current for this design') && !document.querySelector('#export').disabled && document.querySelector('#notice').textContent===''")
    assert 'workspace/editor_project' in value("document.querySelector('#project-location').textContent")

actual_workspace()
cdp('Runtime.enable');cdp('Log.enable');drain_events()
assert value("document.querySelector('#time').value===document.querySelector('#time').max")
for width,height,name in [(1440,900,'after_desktop'),(1280,800,'after_laptop'),(820,1180,'after_tablet'),(393,852,'after_mobile')]:
    cdp('Emulation.setDeviceMetricsOverride',width=width,height=height,deviceScaleFactor=1,mobile=False)
    value('window.scrollTo(0,0)');time.sleep(.1)
    assert value('document.documentElement.scrollWidth<=innerWidth+1'),name
    if width==1280:assert value("document.querySelector('#metrics').getBoundingClientRect().bottom<=innerHeight"),'Key results must fit the laptop viewport'
    capture_screenshot(str(OUT/(name+'.png')))
    checks.append(dict(check=name,width=width,height=height,page_overflow=False,status='PASS'))
click('#project-toggle');click('#menu-help')
assert not value("document.querySelector('#quick-guide').hidden")
checks.append(dict(check='Mobile guide through the project menu',status='PASS'))
colours=json.loads(value("JSON.stringify([...document.querySelectorAll('#canvas .asm-cell')].map(c=>({background:c.querySelector('.asm-body').getAttribute('fill'),foreground:c.querySelector('.asm-val').getAttribute('fill')})))"))
def luminance(colour):
    rgb=[int(colour[i:i+2],16)/255 for i in (1,3,5)]
    linear=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in rgb]
    return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))
ratios=[]
for pair in colours:
    a,b=luminance(pair['background']),luminance(pair['foreground']);ratios.append((max(a,b)+.05)/(min(a,b)+.05))
assert min(ratios)>=4.5
checks.append(dict(check='Actual cell overlay text contrast',minimum_ratio=min(ratios),status='PASS'))
goto_url(f'http://127.0.0.1:{PORT}');wait_for_load()
cdp('Emulation.setDeviceMetricsOverride',width=1440,height=900,deviceScaleFactor=1,mobile=False)
wait_until("!document.querySelector('#run').disabled")
assert 'tmp/v1-release-project' in value("document.querySelector('#project-location').textContent")
click('#project-toggle');click('#variants [data-variant="B1"]')
wait_until("document.querySelector('#variant-id').textContent==='B1' && !document.querySelector('#run').disabled")
assert not value("document.querySelector('#run-select').value")
assert value("document.querySelectorAll('#canvas .asm-swatch').length")==0
capture_screenshot(str(OUT/'after_unrun_variant.png'))
checks.append(dict(check='Unrun/inherited variant has no fabricated numerical colour scale',status='PASS'))
actual_workspace()
cdp('Emulation.setDeviceMetricsOverride',width=1440,height=900,deviceScaleFactor=1,mobile=False)
value('window.scrollTo(0,0)');capture_screenshot(str(OUT/'after_desktop.png'))
errors=[e for e in drain_events() if e.get('method')=='Runtime.exceptionThrown' or (e.get('method')=='Log.entryAdded' and e.get('params',{}).get('entry',{}).get('level')=='error')]
assert not errors,errors
checks.append(dict(check='No browser errors after final refinements',status='PASS'))
files=[p for p in (ROOT/'web/editor').iterdir() if p.suffix in ('.js','.mjs','.html','.css')]
report=dict(status='PASS',checks=checks,source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
(OUT/'final_render_checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(checks,indent=2))
