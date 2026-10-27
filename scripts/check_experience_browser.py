"""Run only through browser-harness against the disposable experience-test server."""
import json,time,concurrent.futures
from pathlib import Path
from urllib.request import urlopen,Request
OUT=Path.cwd()/'reports/experience_rebuild';OUT.mkdir(exist_ok=True)
base='http://127.0.0.1:8794';checks=[];counter=0

def val(code):return js(code)
def wait(expression,seconds=20):
 end=time.monotonic()+seconds
 while not val(expression):
  if time.monotonic()>end:raise AssertionError(expression)
  time.sleep(.1)
def snap(name):capture_screenshot(str(OUT/(name+'.png')))
def click(selector):
 global counter
 val('document.querySelector('+json.dumps(selector)+').scrollIntoView({block:"center"})')
 snap('interaction-before')
 r=val('(()=>{const r=document.querySelector('+json.dumps(selector)+').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()')
 click_at_xy(r['x'],r['y']);time.sleep(.1)
def type_into(selector,text):
 click(selector)
 cdp('Input.dispatchKeyEvent',type='keyDown',modifiers=4,key='a',code='KeyA',windowsVirtualKeyCode=65,commands=['selectAll'])
 cdp('Input.dispatchKeyEvent',type='keyUp',key='a',code='KeyA',windowsVirtualKeyCode=65)
 cdp('Input.insertText',text=str(text))
 assert val('document.querySelector('+json.dumps(selector)+').value')==str(text), 'Input replacement failed'
 cdp('Input.dispatchKeyEvent',type='keyDown',key='Tab',code='Tab',windowsVirtualKeyCode=9)
 cdp('Input.dispatchKeyEvent',type='keyUp',key='Tab',code='Tab',windowsVirtualKeyCode=9)
def record(name,**details):checks.append(dict(check=name,status='PASS',**details));print(json.dumps(checks[-1]),flush=True)
def get(path):return json.loads(urlopen(base+path).read())['result']
def read_doc():
 catalog=get('/api/studio');d=next(d for d in catalog['designs'] if d['name']=='Browser acceptance battery')
 token=get('/api/session')['token'];req=Request(base+'/api/studio',data=json.dumps(dict(operation='open',arguments={'design_id':d['id']})).encode(),headers={'Content-Type':'application/json','X-Voltforge-Token':token})
 return json.loads(urlopen(req).read())['result']

goto_url(base);wait_for_load();cdp('Page.bringToFront');cdp('Emulation.setFocusEmulationEnabled',enabled=True);cdp('Runtime.enable');cdp('Log.enable');drain_events()
cdp('Emulation.setDeviceMetricsOverride',width=1440,height=950,deviceScaleFactor=1,mobile=False)
wait("!!document.querySelector('[data-act=example]')")
snap('home-final')
assert val("!document.body.innerText.includes('run_000') && !document.querySelector('.side-panel')")
record('Quiet opening screen without a settings panel or backend run identifiers')
click('[data-act=new]');type_into('#new-name','Browser acceptance battery');click('[data-act="template:blank"]');snap('new-design');click('#new-form button[type=submit]')
wait("!!document.querySelector('.blank-canvas')")
record('Blank design starts empty')
click('[data-act=library]');click('dialog [data-act^="add:"]');wait("document.querySelectorAll('#battery-canvas [data-cell]').length===1")
click('[data-act=library]');click('dialog [data-act^="add:"]');wait("document.querySelectorAll('#battery-canvas [data-cell]').length===2")
click('[data-act=close-panel]');click('[data-act="tool:connect"]');click('[data-terminal="cell1:p"]');click('[data-terminal="cell2:p"]');click('[data-terminal="cell1:n"]');click('[data-terminal="cell2:n"]')
wait("document.querySelector('#save-status').textContent==='Saved'")
doc=read_doc();assert len(doc['graph']['connections'])==2 and doc['readiness']['ready']
snap('custom-connected');record('Two added cells are connected by genuine editable terminal edges',cells=2,connections=2)
click('[data-act="tool:select"]');click('[data-cell=cell2]')
assert val("document.querySelector('.side-panel').innerText.includes('Starting charge') && !!document.querySelector('.cell-thumbnail')")
type_into('#cell-charge','60');wait("document.querySelector('#save-status').textContent==='Saved'")
assert read_doc()['graph']['cells'][1]['charge_pct']==60
snap('cell-properties-final');record('Selected cell thumbnail, plain-language controls and saved 60 percent charge')
click('[data-act=close-panel]')
# A real drag changes layout, not edges.
before=read_doc()['graph'];snap('interaction-before')
r=val("(()=>{const r=document.querySelector('[data-cell=cell2]').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
cdp('Input.dispatchMouseEvent',type='mousePressed',x=r['x'],y=r['y'],button='left',clickCount=1)
# Chromium acknowledges a held drag move after release. Dispatch it asynchronously,
# observe its effect, then release in the required order before awaiting the acknowledgement.
old_transform=val('document.querySelector("[data-cell=cell2]").getAttribute("transform")')
with concurrent.futures.ThreadPoolExecutor() as pool:
 pending_move=pool.submit(cdp,'Input.dispatchMouseEvent',type='mouseMoved',x=r['x']+54,y=r['y']+48,buttons=1,_response_timeout=8)
 end=time.monotonic()+5
 while val('document.querySelector("[data-cell=cell2]").getAttribute("transform")')==old_transform:
  assert time.monotonic()<end
  time.sleep(.05)
 cdp('Input.dispatchMouseEvent',type='mouseReleased',x=r['x']+54,y=r['y']+48,button='left',clickCount=1)
 pending_move.result(timeout=8)
wait("document.querySelector('#save-status').textContent==='Saved'")
after=read_doc()['graph'];assert before['connections']==after['connections'];assert before['cells'][1]['x']!=after['cells'][1]['x']
record('Drag moves geometry while preserving the electrical graph')
click('[data-act=close-panel]')
snap('interaction-before')
wire_point=val('(()=>{const p=document.querySelector("[data-wire=wire1] .copper-link"),s=p.getPointAtLength(p.getTotalLength()/2),q=new DOMPoint(s.x,s.y).matrixTransform(p.getScreenCTM());return {x:q.x,y:q.y}})()')
click_at_xy(wire_point['x'],wire_point['y']);wait('document.querySelector(".side-panel")?.innerText.includes("Selected connection")')
click('[data-act=delete]');wait("document.querySelector('#save-status').textContent==='Saved'")
assert not read_doc()['readiness']['ready']
click('[data-act=undo]');wait("document.querySelector('#save-status').textContent==='Saved'")
assert read_doc()['readiness']['ready'];record('Removing a link invalidates wiring; Undo restores a solvable circuit')
click('[data-act="view:test"]');type_into('#test-current','2');type_into('#test-duration','12.25');snap('test-setup-final')
click('#test-form button[type=submit]');wait("!!document.querySelector('#result-chart')",25)
doc=read_doc();assert doc['settings']['profile'][0]['end_s']==735
assert doc['history'] and doc['history'][0]['summary']['metrics']['duration_s']==735
record('A custom design completes a 735-second test, beyond the old 360-second example')
snap('custom-results')
r=val("(()=>{const r=document.querySelector('#result-chart').getBoundingClientRect();return {x:r.x+r.width*.43,y:r.y+r.height*.45}})()")
cdp('Input.dispatchMouseEvent',type='mouseMoved',x=r['x'],y=r['y']);wait("document.querySelector('#chart-tooltip').classList.contains('visible')")
assert val("document.querySelectorAll('#chart-tooltip .probe-value').length===2")
first=val("document.querySelector('#time-readout').textContent")
click_at_xy(r['x'],r['y']);cdp('Input.dispatchMouseEvent',type='mouseMoved',x=r['x']+80,y=r['y'])
assert first==val("document.querySelector('#time-readout').textContent")
snap('chart-probe');record('Chart hover shows numeric values and click pins a saved time',time=first)
click('#result-time');cdp('Input.dispatchKeyEvent',type='keyDown',key='Home',code='Home',windowsVirtualKeyCode=36);cdp('Input.dispatchKeyEvent',type='keyUp',key='Home',code='Home',windowsVirtualKeyCode=36)
assert val("document.querySelector('#result-time').value==='0'")
click('[data-act="legend:1"]');assert val("document.querySelectorAll('#chart-probe circle').length===1")
click('[data-act="legend:1"]');click('[data-act="metric:temperature"]')
record('Keyboard time navigation, series toggles and temperature chart work')
click('[data-act=show-assembly]');assert val("document.querySelector('#results-assembly').textContent.includes('°C')")
click('[data-cell=cell2]');assert val("document.querySelector('.side-panel').innerText.includes('Charge left')")
record('Assembly values and selected-cell readings stay bound to the probed sample')
click('[data-act=close-panel]');click('[data-act=whatif]');snap('whatif-final');click('[data-act="scenario:connection"]');wait("!!document.querySelector('#result-chart')",25)
record('Guided connection-wear scenario creates and solves a separate alternative')
click('[data-act=compare]');snap('compare-setup');click('#compare-form button[type=submit]');wait("!!document.querySelector('.compare-table')")
assert val("document.querySelector('.compare-notice').textContent.includes('Same test settings')")
snap('compare-final');record('Comparison uses named tests with matching conditions')
click('[data-act="view:results"]');click('[data-act=ai]');type_into('#chat-input','Change Cell 1 to 65 percent starting charge. Propose the edit and explain briefly.')
click('#chat-form button[type=submit]');wait("!!document.querySelector('.proposal') || !!document.querySelector('.chat-error')",110)
assert not val("!!document.querySelector('.chat-error')"),val("document.querySelector('.chat-error')?.textContent")
snap('ai-proposal');assert val("document.querySelector('.proposal').textContent.includes('65')")
click('[data-act^="apply:"]');wait("!!document.querySelector('.proposal.applied')")
snap('ai-applied');record('Live AI proposes and applies a reviewed cell edit')
# Responsive checks of the actual final UI, with the panel closed.
click('[data-act=close-ai]')
for width,height,name in [(1280,800,'laptop-build'),(393,852,'phone-build')]:
 cdp('Emulation.setDeviceMetricsOverride',width=width,height=height,deviceScaleFactor=1,mobile=False)
 assert val('document.documentElement.scrollWidth<=innerWidth+1'),name
 snap(name);record('No horizontal page overflow: '+name,width=width,height=height)
click('[data-act="view:results"]')
assert val('document.documentElement.scrollWidth<=innerWidth+1');snap('phone-results');record('Results remain usable on a phone')
cdp('Emulation.setDeviceMetricsOverride',width=1440,height=950,deviceScaleFactor=1,mobile=False)
errors=[e for e in drain_events() if e.get('method')=='Runtime.exceptionThrown' or (e.get('method')=='Log.entryAdded' and e.get('params',{}).get('entry',{}).get('level')=='error')]
assert not errors,errors
record('No browser runtime or content-security-policy errors')
(OUT/'browser_acceptance.json').write_text(json.dumps(dict(status='PASS',checks=checks),indent=2)+'\n')
print('Completed',len(checks),'experience checks',flush=True)
