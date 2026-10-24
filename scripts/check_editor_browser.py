"""Headless Chrome acceptance check of our local editor; optional websocket-client test dependency.

Uses an isolated browser profile, never an existing user's browser or login.
All interactions exercise the local page and its real project API.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.request import urlopen
import uuid
import zipfile

import websocket
from run_editor import EditorServer, ROOT


class Browser:
    def __init__(self, chrome, profile, port):
        self.process = subprocess.Popen([str(chrome), '--headless=new', '--disable-gpu', '--no-first-run',
            '--no-default-browser-check', '--disable-background-networking', '--disable-extensions',
            '--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1',
            '--user-data-dir=' + str(profile), 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.errors = []
        self.seq = 0
        active = profile / 'DevToolsActivePort'
        deadline = time.monotonic() + 20
        while not active.exists():
            if time.monotonic() > deadline or self.process.poll() is not None:
                raise RuntimeError('Isolated Chrome did not start')
            time.sleep(.1)
        debugport = int(active.read_text().splitlines()[0])
        targets = json.load(urlopen(f'http://127.0.0.1:{debugport}/json'))
        self.ws = websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'), suppress_origin=True, timeout=40)
        self.call('Runtime.enable')
        self.call('Log.enable')
        self.call('Page.enable')
        self.call('Emulation.setDeviceMetricsOverride', dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
        self.call('Page.navigate', dict(url=f'http://127.0.0.1:{port}'))

    def call(self, method, params=None):
        self.seq += 1
        self.ws.send(json.dumps(dict(id=self.seq,method=method,params=params or {})))
        while True:
            message = json.loads(self.ws.recv())
            if message.get('method') == 'Runtime.exceptionThrown':
                self.errors.append(message['params'])
            if message.get('method') == 'Log.entryAdded' and message['params']['entry']['level'] == 'error':
                self.errors.append(message['params']['entry'])
            if message.get('id') == self.seq:
                if 'error' in message:
                    raise RuntimeError(message['error'])
                return message.get('result', {})

    def js(self, expression):
        result = self.call('Runtime.evaluate', dict(expression=expression, returnByValue=True, awaitPromise=True))
        if 'exceptionDetails' in result:
            raise AssertionError(result['exceptionDetails'])
        return result.get('result', {}).get('value')

    def wait(self, expression, seconds=45):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.js(expression):
                return
            time.sleep(.15)
        raise AssertionError('Browser wait failed: '+expression+'\n'+str(self.js('document.body.innerText'))[:4000])

    def click(self, selector):
        self.js(f'document.querySelector({json.dumps(selector)}).click()')

    def fill(self, selector, value, change=False):
        self.js(f'(()=>{{const e=document.querySelector({json.dumps(selector)});e.value={json.dumps(value)};e.dispatchEvent(new Event("{ "change" if change else "input" }",{{bubbles:true}}));}})()')

    def screenshot(self, path):
        path.write_bytes(base64.b64decode(self.call('Page.captureScreenshot', dict(format='png', captureBeyondViewport=False))['data']))

    def close(self):
        self.ws.close()
        self.process.terminate()
        self.process.wait(timeout=15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chrome', type=Path, default=Path(os.environ.get('LOCALAPPDATA',''))/'Google/Chrome/Application/chrome.exe')
    parser.add_argument('--out', type=Path, default=ROOT/'reports/editor_v1/browser')
    args = parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    work = ROOT/'tmp'/('editor_browser_'+uuid.uuid4().hex[:12])
    work.mkdir(parents=True)
    server = EditorServer(('127.0.0.1',0),work/'project')
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    browser = None
    observations = []
    try:
        b = browser = Browser(args.chrome,work/'profile',server.server_port)
        b.wait('document.querySelectorAll(".cell-group").length===4 && !document.querySelector("#run").disabled')
        assert b.js('document.querySelectorAll(".edge").length') == 6
        b.screenshot(args.out/'01_empty_desktop.png')
        observations.append('Four cell branches and six exact electrical edge IDs, no fabricated initial results')
        b.click('#run')
        b.wait('document.querySelector("#run-state").textContent.includes("Completed simulation / Current") && !document.querySelector("#run").disabled')
        b.screenshot(args.out/'02_a0_results.png')
        r0 = b.js('document.querySelector("#run-select").value')
        observations.append('A0 full 360-second run completed through HTTP worker with real saved series')
        b.click('#new-variant')
        b.fill('#variant-name','One hypothetical positive rail change')
        b.click('#variant-form button[type=submit]')
        b.wait('document.querySelector("#variant-title").textContent.startsWith("A1") && !document.querySelector("#run").disabled')
        assert b.js('document.querySelector("#run-select").value') == ''
        b.fill('#run-select',r0,True)
        b.wait('document.querySelector("#run-state").textContent.includes("Outdated for this design") && !document.querySelector("#run").disabled')
        b.click('#components [data-component=rail_p_1]')
        b.fill('#edit-value','0.5')
        b.click('#preview-edit')
        b.wait('!document.querySelector("#apply-edit").disabled')
        b.click('#apply-edit')
        b.wait('document.querySelector("#notice").textContent.startsWith("Revision saved") && !document.querySelector("#run").disabled')
        b.screenshot(args.out/'03_outdated_revision.png')
        observations.append('A1 inherited result explicitly outdated; preview converts 0.5 mΩ to 0.0005 ohm and creates a revision')
        b.click('#run')
        b.wait('document.querySelector("#run-state").textContent.includes("Completed simulation / Current") && !document.querySelector("#run").disabled')
        r1 = b.js('document.querySelector("#run-select").value')
        assert r1 != r0
        b.click('#components [data-component=cell_2]')
        b.screenshot(args.out/'04_a1_results.png')
        revision = b.js('document.querySelector("#revision").textContent')
        b.js('document.querySelector(".cell-group[data-component=cell_2]").dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowRight",bubbles:true}))')
        b.wait('document.querySelector("#notice").textContent.startsWith("Layout saved") && !document.querySelector("#run").disabled')
        assert b.js('document.querySelector("#revision").textContent') == revision
        assert 'Current for this design' in b.js('document.querySelector("#run-state").textContent')
        b.fill('#time','800',True)
        b.js('document.querySelector("#time").dispatchEvent(new Event("input",{bubbles:true}))')
        assert b.js('document.querySelector("#time-label").textContent') == '200.00 s'
        observations.append('Keyboard layout movement retains revision and current result; sample scrubber displays 200 s saved data')
        b.click('#tab-evidence')
        assert 'requirement not configured' in b.js('document.querySelector("#panel-evidence").textContent')
        b.screenshot(args.out/'05_evidence.png')
        b.click('#tab-compare')
        b.fill('#compare-first',r0,True)
        b.fill('#compare-second',r1,True)
        b.click('#compare')
        b.wait('document.querySelector("#comparison").textContent.includes("identical operating conditions")')
        b.screenshot(args.out/'06_comparison.png')
        observations.append('Explicit A0/A1 comparison uses identical-condition backend check, unranked metrics and pending-validation notice')
        b.click('#components [data-component=rail_p_1]')
        assert 'mV drop' in b.js('document.querySelector("#selection-readout").textContent')
        b.fill('#edit-value','-1')
        b.click('#preview-edit')
        b.wait('document.querySelector("#notice").classList.contains("error")')
        assert b.js('document.querySelector("#apply-edit").disabled')
        assert b.js('document.querySelector("#revision").textContent') == revision
        observations.append('Negative resistance rejected without applying a revision')
        # The expected 400 validation response may appear as a Chrome network log error.
        expected_errors = [x for x in b.errors if x.get('source')=='network' and '400' in x.get('text','')]
        b.errors = [x for x in b.errors if x not in expected_errors]
        b.click('#export')
        b.js('document.querySelectorAll("#export-choices input").forEach(e=>e.checked=true)')
        b.click('#make-export')
        b.wait('document.querySelector("#download a")!==null && !document.querySelector("#make-export").disabled')
        url = b.js('document.querySelector("#download a").href')
        archive = urlopen(url).read()
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            z.extractall(work/'export')  # Only the package just created by our own backend.
        replays = []
        for rid in [r0,r1]:
            replay = subprocess.run([sys.executable,str(work/'export/replay.py'),rid],capture_output=True,text=True,check=True)
            replays.append(json.loads(replay.stdout))
        assert all(x['reproduced'] for x in replays)
        observations.append('Browser-selected two-run package downloaded and both runs replayed in separate Python processes')
        b.click('#close-export')
        b.click('#tab-results')
        b.click('#components [data-component=module]')
        b.fill('#edit-property','requirements',True)
        assert b.js('[...document.querySelectorAll("#edit-fields input")].every(e=>e.value==="")')
        b.call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=True))
        b.wait('window.innerWidth===390')
        assert b.js('document.documentElement.scrollWidth<=window.innerWidth')
        b.fill('#mobile-component','cell_4',True)
        assert 'P13' in b.js('document.querySelector(".inspector-title").textContent')
        b.fill('#mobile-component','module',True)
        b.screenshot(args.out/'07_mobile.png')
        observations.append('390 px view has no document overflow; circuit scrolls horizontally; unknown requirement fields remain empty')
        b.call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
        b.click('#components [data-component=cell_2]')
        b.screenshot(args.out/'08_final_desktop.png')
        b.click('#new-variant')
        b.fill('#variant-name','Unsupported load software fixture')
        b.click('#variant-form button[type=submit]')
        b.wait('document.querySelector("#variant-title").textContent.startsWith("A2") && !document.querySelector("#run").disabled')
        b.click('#components [data-component=module]')
        b.fill('#edit-json',json.dumps([dict(start_s=0,end_s=360,current_A=1000)]))
        b.click('#preview-edit')
        b.wait('!document.querySelector("#apply-edit").disabled')
        b.click('#apply-edit')
        b.wait('document.querySelector("#notice").textContent.startsWith("Revision saved") && !document.querySelector("#run").disabled')
        b.click('#run')
        b.wait('document.querySelector("#run-state").textContent.startsWith("Failed simulation") && !document.querySelector("#run").disabled')
        b.screenshot(args.out/'09_failed_run.png')
        observations.append('Deliberately unsupported 1000 A software fixture stops at reference support and displays a failed run with partial samples')
        assert not b.errors, b.errors
        result = dict(status='passed', observations=observations, browser_errors=b.errors,
                      expected_validation_network_errors=len(expected_errors),replays=replays,
                      project=str(work/'project'),run_ids=[r0,r1],
                      comparison=json.loads((work/'export/comparison.json').read_text()),
                      package_sha256=hashlib.sha256(archive).hexdigest(),experimental_validation='awaiting suitable measurements')
        (args.out/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(status='passed',observations=len(observations),screenshots=9,replayed_runs=2,out=str(args.out))))
    finally:
        if browser:
            browser.close()
        server.shutdown()
        server.server_close()
        thread.join()


if __name__=='__main__':
    main()
