"""Additional UI preview checks, run through browser-harness after check_v1_browser.py.

Uses the same disposable project on VOLT_FORGE_BROWSER_PORT (default 8793).
B1 is the unrun variant created by the full workflow check. No edits are saved.
"""
import json
import os
import time
from pathlib import Path

ROOT=Path.cwd()
OUT=ROOT/'reports/ui_cleanup'
PORT=int(os.environ.get('VOLT_FORGE_BROWSER_PORT','8793'))
checks=[]

def value(expression):return js(expression)
def wait_until(expression):
    end=time.monotonic()+20
    while not value(expression):
        assert time.monotonic()<end,expression
        time.sleep(.1)
def set_value(selector,content,event='input'):
    value(f"(()=>{{const e=document.querySelector({json.dumps(selector)});e.value={json.dumps(str(content))};e.dispatchEvent(new Event({json.dumps(event)},{{bubbles:true}}));return true}})()")
def click(selector):
    value(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block:'center'}})")
    capture_screenshot(str(OUT/'before_form_action.png'))
    rect=value(f"(()=>{{const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}}}})()")
    click_at_xy(rect['x'],rect['y'])
    time.sleep(.1)
def preview(name,expected,unit):
    click('#preview-edit')
    wait_until("!document.querySelector('#apply-edit').disabled")
    edit=json.loads(value("document.querySelector('#edit-feedback pre').textContent"))
    assert edit['value']==expected,(name,edit)
    assert edit['unit']==unit,(name,edit)
    checks.append(dict(check=name,value=expected,unit=unit,status='PASS'))
    click('#discard-edit')

goto_url(f'http://127.0.0.1:{PORT}')
wait_for_load()
cdp('Emulation.setDeviceMetricsOverride',width=1440,height=900,deviceScaleFactor=1,mobile=False)
cdp('Runtime.enable');drain_events()
wait_until("!document.querySelector('#run').disabled")
assert 'tmp/v1-release-project' in value("document.querySelector('#project-location').textContent")
click('#project-toggle');click('#variants [data-variant="B1"]')
wait_until("document.querySelector('#variant-id').textContent==='B1' && !document.querySelector('#run').disabled")
set_value('#edit-property','temperature','change');set_value('#edit-value','30')
for i in range(4):set_value('#surface-'+str(i),22+i)
click('#preview-edit');wait_until("!document.querySelector('#apply-edit').disabled")
edit=json.loads(value("document.querySelector('#edit-feedback pre').textContent"))
assert edit['value']['assumed_ambient_C']==30 and edit['value']['assumed_surface_C']==[22,23,24,25] and edit['unit']=='degC'
checks.append(dict(check='Ambient and four independent starting temperatures retain cell order',status='PASS'))
click('#discard-edit')
set_value('#edit-property','thermal','change')
for i in range(4):set_value('#thermal-value-'+str(i),70+i)
preview('Per-cell heat capacity',[70,71,72,73],'J/K')
set_value('#thermal-property','neighbour_conductance','change')
for i,v in enumerate([.02,.03,.04]):set_value('#thermal-value-'+str(i),v)
preview('Three neighbour-pair conductances',[.02,.03,.04],'W/K')
set_value('#thermal-property','rail_heat_to_cells_fraction','change');set_value('#edit-value','.35')
preview('Rail heat fraction',.35,'fraction')
click('#canvas [data-component="cell_2"]')
set_value('#edit-value','95');preview('State of charge percent to fraction',.95,'fraction')
set_value('#edit-property','polarization','change');set_value('#edit-value','2.5');preview('Polarization millivolts to volts',.0025,'V')
for prefix in ['p','n']:
    for k in range(1,4):
        connection=f'rail_{prefix}_{k}'
        click(f'#canvas [data-component="{connection}"]')
        assert value("document.querySelector('#inspector-heading').textContent")=='Connection properties',connection
        set_value('#edit-value','2.5');preview(f'{connection}: expanded click target and milliohms to ohms',.0025,'ohm')
assert not [e for e in drain_events() if e.get('method')=='Runtime.exceptionThrown']
(OUT/'form_binding_checks.json').write_text(json.dumps(dict(status='PASS',scope='Preview binding only, disposable project; no model fitting or user-project edit',checks=checks),indent=2)+'\n')
goto_url('http://127.0.0.1:8792');wait_for_load()
cdp('Emulation.setDeviceMetricsOverride',width=1440,height=900,deviceScaleFactor=1,mobile=False)
wait_until("document.querySelector('#run-state').textContent.includes('Current for this design') && !document.querySelector('#export').disabled && document.querySelector('#notice').textContent===''")
capture_screenshot(str(OUT/'after_desktop.png'))
print(json.dumps(checks,indent=2))
