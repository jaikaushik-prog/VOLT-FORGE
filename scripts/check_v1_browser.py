"""Run with browser-harness in an isolated browser against a fresh disposable editor project.

Example: BU_NAME=volt-forge-v1 BU_CDP_URL=http://127.0.0.1:9228
         browser-harness < scripts/check_v1_browser.py
The editor for this check is at 127.0.0.1:8792. It must not point at a user's project.
Browser helpers are pre-imported by browser-harness, not by the application.
"""
import json
import os
import socket
import subprocess
import time
import zipfile
from pathlib import Path

ROOT = Path.cwd()
PORT = int(os.environ.get('VOLT_FORGE_BROWSER_PORT', '8792'))
OUT = ROOT / 'reports/v1_release/browser'
OUT.mkdir(parents=True, exist_ok=True)
checks = []


def value(expression):
    return js(expression)


def wait_until(expression, timeout=30):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        if value(expression):
            return
        time.sleep(0.1)
    raise AssertionError('Timed out: '+expression)


def shot(name):
    return capture_screenshot(str(OUT / (name+'.png')))


def click(selector, label):
    encoded = json.dumps(selector)
    rect = json.loads(value(f"JSON.stringify((()=>{{const e=document.querySelector({encoded});if(!e)throw Error('Missing control');e.scrollIntoView({{block:'center'}});const r=e.getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}}}})())"))
    shot('before_'+label)
    click_at_xy(rect['x'], rect['y'])
    time.sleep(0.1)


def set_value(selector, content, event='input'):
    value(f"(()=>{{const e=document.querySelector({json.dumps(selector)});e.value={json.dumps(str(content))};e.dispatchEvent(new Event({json.dumps(event)},{{bubbles:true}}));return true}})()")


def text(selector):
    return value(f'document.querySelector({json.dumps(selector)}).innerText')


def passed(name, **details):
    checks.append(dict(check=name, status='PASS', **details))
    print('PASS '+name, flush=True)


def run_current():
    old = value("document.querySelector('#run-select').value")
    click('#run', 'run')
    wait_until("!document.querySelector('#run').disabled && document.querySelector('#run-select').value !== "+json.dumps(old)+" && document.querySelector('#run-state').textContent.includes('Current for this design')")
    assert 'Simulation stopped' not in text('#run-state'), text('#run-state')
    return value("document.querySelector('#run-select').value")


deadline = time.monotonic()+30
while True:
    try:
        with socket.create_connection(('127.0.0.1', PORT), timeout=1):
            break
    except OSError:
        if time.monotonic() >= deadline:
            raise AssertionError(f'Start a fresh disposable editor on port {PORT}')
        time.sleep(.1)
goto_url(f'http://127.0.0.1:{PORT}')
wait_for_load()
cdp('Emulation.setDeviceMetricsOverride', width=1440, height=900, deviceScaleFactor=1, mobile=False)
cdp('Runtime.enable'); cdp('Log.enable'); drain_events()
wait_until("document.querySelector('#run')?.disabled === false")
assert 'tmp/v1-release-project' in value("document.querySelector('#project-location').textContent"), 'Use a disposable browser-check project'
if not value("document.querySelector('#run-select').value"):
    run_current()
wait_until("document.querySelector('#run-state').textContent.includes('Current for this design')")
assert value("document.querySelectorAll('#metrics .metric').length") == 4
assert not value("document.querySelector('#chart-details').open")
assert not value("document.querySelector('#project-panel').matches(':popover-open')")
shot('01_clean_workspace')
passed('Focused workspace: four key results, assembly default and advanced detail collapsed')

width_before = value("document.querySelector('.canvas-area').getBoundingClientRect().width")
click('#toggle-inspector', 'hide_properties')
assert value("document.querySelector('.canvas-area').getBoundingClientRect().width") > width_before+200
shot('02_focus_mode')
click('#toggle-inspector', 'restore_properties')
passed('Properties collapse to give the canvas more space')

# Normal inputs must produce the exact engineering load profile. No raw JSON is edited.
set_value('[data-load-duration]', '0')
click('#preview-edit', 'invalid_duration')
wait_until("document.querySelector('#edit-feedback').textContent.includes('greater than zero')")
assert value("document.querySelector('#apply-edit').disabled")
set_value('[data-load-duration]', '300')
click('#add-interval', 'add_rest_interval')
set_value('.load-interval:last-child [data-load-current]', '0')
click('#preview-edit', 'load_preview')
wait_until("!document.querySelector('#apply-edit').disabled")
preview = json.loads(value("document.querySelector('#edit-feedback pre').textContent"))
assert preview['value'] == [dict(start_s=0,end_s=300,current_A=14.55),dict(start_s=300,end_s=360,current_A=0)]
assert value("document.querySelector('#run').disabled"), 'An unsaved edit must not be mistaken for the run input'
click('#apply-edit', 'load_save')
wait_until("document.querySelector('#run-state').textContent.includes('Outdated for this design')")
run_current()
passed('Load form, rest interval, invalid-duration recovery, preview/save and stale-result tracking')

# A draft survives selecting a different component, but is never applied without Preview and Save.
set_value('.load-interval:first-child [data-load-current]', '13')
click('#canvas [data-component="cell_1"]', 'select_cell_during_draft')
click('#configure-module', 'return_to_load_draft')
assert value("document.querySelector('[data-load-current]').value") == '13'
assert value("document.querySelector('#run').disabled")
click('#discard-edit', 'discard_load_draft')
assert value("document.querySelector('[data-load-current]').value") == '14.55'
assert not value("document.querySelector('#run').disabled")
passed('Draft preservation across component selection and explicit discard')

click('#configure-limits', 'configure_limits')
set_value('#limit-value', '5')
set_value('#limit-source', 'Proposed demonstration target; not a manufacturer rating')
click('#preview-edit', 'limit_preview')
wait_until("!document.querySelector('#apply-edit').disabled")
click('#apply-edit', 'limit_save')
wait_until("document.querySelector('#run-state').textContent.includes('Outdated for this design')")
shot('03_outdated_result')
baseline = run_current()
assert 'no sampled exceedance' in text('#engineering')
passed('Sourced engineering limit and fresh electrical/thermal screen', run_id=baseline)

click('#canvas [data-component="cell_3"]', 'cell_readout')
set_value('#time', value("document.querySelector('#time').max"))
assert 'surface-equivalent' in text('#selection-readout')
assert '360.00 s' in text('#selection-readout')
click('#chart-details > summary', 'expand_charts')
click('[data-chart="temperature"]', 'temperature_chart')
assert 'Cell temperature' in text('#plots')
assert value("document.querySelectorAll('#plots .plot').length") == 1
click('[data-chart="voltage"]', 'voltage_chart')
assert 'Cell & terminal voltage' in text('#plots')
shot('04_selected_cell_and_chart')
click('#chart-details > summary', 'collapse_charts')
passed('Saved-time readout and one selected chart at a time')

click('#tab-investigate', 'investigate')
assert not value("document.querySelector('.canvas-area').checkVisibility()")
assert not value("document.querySelector('#inspector').checkVisibility()")
click('#inv-seg-rail_p_1', 'positive_connection')
click('#inv-seg-rail_n_1', 'negative_connection')
assert '5 of 5 cases will run' in text('#inv-preview')
click('.inv-advanced > summary', 'advanced_search')
set_value('#inv-max', '5')
click('#inv-run', 'run_investigation')
wait_until("!document.querySelector('#inv-run').disabled && document.querySelector('#investigation-results').textContent.includes('Evaluated 5 of 5')")
assert 'Limit exceeded' in text('#investigation-results')
assert '0 thermal failures' in text('#investigation-results')
shot('05_failure_investigation')
case_id = value("document.querySelector('#investigation-results .open-case').dataset.case")
click('#investigation-results .open-case', 'open_case')
wait_until("document.querySelector('#variant-id').textContent.startsWith('C') && !document.querySelector('#run').disabled")
variant = text('#variant-id')
assert value("document.querySelector('.workbench').dataset.mode") == 'results'
candidate = run_current()
assert 'configured limit exceeded' in text('#engineering')
passed('Focused finite investigation and automatic return to a runnable case variant', case_id=case_id, variant=variant, run_id=candidate)

click('#tab-compare', 'compare_tab')
set_value('#compare-first', baseline, 'change');set_value('#compare-second', candidate, 'change')
click('#compare', 'compare_runs')
wait_until("document.querySelector('#comparison table') !== null")
assert 'identical operating conditions' in text('#comparison')
assert 'Peak cell temperature' in text('#comparison') and 'Current imbalance' in text('#comparison')
assert 'No repair ranking' in text('#comparison')
assert value("[...document.querySelectorAll('#comparison table')].filter(t=>t.checkVisibility()).length") == 1
shot('06_controlled_comparison')
passed('Six main comparison metrics, deeper accounting collapsed and honest evidence labels')

click('#tab-evidence', 'evidence')
assert 'Understand the model' in text('#panel-evidence')
assert 'Experimental validation pending' in text('#panel-evidence')
assert 'core or internal temperature' in text('#panel-evidence')
shot('07_model_evidence')
passed('Dedicated model/evidence view with readable assumptions and recorded coverage')

click('#export', 'export_dialog')
click(f'#export-choices input[value="{baseline}"]', 'include_baseline')
click('#make-export', 'prepare_export')
wait_until("document.querySelector('#download a') !== null")
download_folder = OUT/'downloads'/str(time.time_ns());download_folder.mkdir(parents=True)
cdp('Browser.setDownloadBehavior',behavior='allow',downloadPath=str(download_folder))
click('#download a', 'download_export')
archive=download_folder/'volt-forge-result-package.zip'
deadline=time.monotonic()+30
while time.monotonic()<deadline and not archive.is_file():time.sleep(.1)
assert archive.is_file()
extracted=ROOT/'tmp/v1-browser-export'/download_folder.name;extracted.mkdir(parents=True)
with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None
    assert all((extracted/member).resolve().is_relative_to(extracted.resolve()) for member in bundle.namelist())
    bundle.extractall(extracted)
replays=[]
for run_id in (baseline,candidate):
    result=subprocess.run([str(ROOT/'.venv/bin/python'),str(extracted/'replay.py'),run_id],cwd=extracted,text=True,capture_output=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    record=json.loads(result.stdout);assert record['reproduced'] and record['thermal_reproduced'];replays.append(record)
passed('Downloaded package and two standalone electrical/thermal replays', replays=replays)
click('#close-export', 'close_export')

click('#tab-results','workspace_tab')
click('#project-toggle','open_project_menu')
click('#new-variant','new_variant')
set_value('#variant-id-input','B1');set_value('#variant-name','Independent study')
click('#variant-form button[type="submit"]','create_variant')
wait_until("document.querySelector('#variant-id').textContent==='B1' && !document.querySelector('#run').disabled")
assert not value("document.querySelector('#run-select').value"), 'Inherited results cannot become current'
assert value("document.querySelectorAll('#canvas .asm-swatch').length") == 0, 'An unselected result must not display a numerical colour scale'
click('#project-toggle','return_project_menu')
click(f'#variants [data-variant="{variant}"]','return_case_variant')
wait_until("document.querySelector('#run-state').textContent.includes('Current for this design')")
passed('Variant creation through the project menu and historical-result isolation')

cdp('Emulation.setDeviceMetricsOverride',width=393,height=852,deviceScaleFactor=1,mobile=False)
value('window.scrollTo(0,0)')
assert value('document.documentElement.scrollWidth<=innerWidth+1')
shot('08_mobile_workspace')
click('#tab-investigate','mobile_investigate')
assert value('document.documentElement.scrollWidth<=innerWidth+1')
shot('09_mobile_investigation')
click('#tab-results','mobile_workspace')
click('#configure-module','mobile_properties')
assert value("document.querySelector('#inspector').getBoundingClientRect().top") < 60
shot('10_mobile_properties')
passed('393px layout, scrollable assembly, focused investigation and reachable operating inputs')

cdp('Emulation.setDeviceMetricsOverride',width=1440,height=900,deviceScaleFactor=1,mobile=False)
value("document.querySelector('#tab-compare').focus()")
cdp('Input.dispatchKeyEvent',type='keyDown',key='Home',code='Home',windowsVirtualKeyCode=36)
cdp('Input.dispatchKeyEvent',type='keyUp',key='Home',code='Home',windowsVirtualKeyCode=36)
assert value("document.querySelector('#tab-results').getAttribute('aria-selected')==='true'")
cdp('Input.dispatchKeyEvent',type='keyDown',key='End',code='End',windowsVirtualKeyCode=35)
cdp('Input.dispatchKeyEvent',type='keyUp',key='End',code='End',windowsVirtualKeyCode=35)
assert value("document.querySelector('#tab-evidence').getAttribute('aria-selected')==='true'")
click('#tab-results','final_workspace')
value('window.scrollTo(0,0)')
shot('11_final_workspace')
passed('Keyboard tab navigation and view state in the URL')
assert value("new URL(location.href).searchParams.get('view')")=='results'
events=drain_events()
errors=[e for e in events if e.get('method')=='Runtime.exceptionThrown' or (e.get('method')=='Log.entryAdded' and e.get('params',{}).get('entry',{}).get('level')=='error')]
assert not errors,errors
passed('No uncaught exceptions or error-level browser logs during the workflow')
report=dict(status='PASS',scope='Clean workspace UI, engineering-input binding and software reproduction; not experimental validation',checks=checks,baseline_run=baseline,candidate_run=candidate)
(OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
(ROOT/'reports/ui_cleanup/verification.json').write_text(json.dumps(report,indent=2)+'\n')
print('BROWSER WORKFLOW PASS',flush=True)
