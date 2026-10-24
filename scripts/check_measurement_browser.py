"""Exercise the local P45B viewer in an isolated test browser. Opens allocated ID01 only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import threading
import uuid
from urllib.request import urlopen

from check_editor_browser import Browser
from run_editor import EditorServer, ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chrome',type=Path,default=Path(os.environ.get('LOCALAPPDATA',''))/'Google/Chrome/Application/chrome.exe')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    work=ROOT/'tmp'/('measurement_browser_'+uuid.uuid4().hex[:12]);work.mkdir(parents=True)
    server=EditorServer(('127.0.0.1',0),work/'project')
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    browser=None;checks=[]
    try:
        b=browser=Browser(args.chrome,work/'profile',server.server_port)
        b.wait("document.querySelector('a[href=\"/measurements\"]')!==null")
        b.click('a[href="/measurements"]')
        b.wait('document.querySelector("#sample-position")?.textContent.includes("CSV line 3")')
        assert b.js('document.querySelectorAll("#record-list button:disabled").length')==13
        assert b.js('document.querySelectorAll("#current-plot path").length')==1
        assert '−20 A' in b.js('document.querySelector(".measurement-heading").textContent')
        b.screenshot(args.out/'01_desktop.png');checks.append('Measured ID01 opens via simulator link; 13 protected records disabled; source polarity visible')
        b.fill('#sample-number','600',True)
        b.wait('document.querySelector("#sample-position").textContent.includes("CSV line 603")')
        b.fill('#sensor-channel','temp_cell-4_TH11',True)
        assert 'temp_cell-4_TH11' in b.js('document.querySelector("#sample-values").textContent')
        assert '[K]' in b.js('document.querySelector("#sensor-channel").selectedOptions[0].textContent')
        checks.append('Exact sample selection preserves CSV line and source sensor K units')
        # Rapid changes must settle on the final requested sample.
        b.fill('#sample-index','200');b.fill('#sample-index','1200')
        b.wait('document.querySelector("#sample-position").textContent.includes("CSV line 1203")')
        b.screenshot(args.out/'02_source_inspector.png');checks.append('Latest request wins during rapid sample navigation')
        base=f'http://127.0.0.1:{server.server_port}'
        summary=json.load(urlopen(base+'/api/measurements/ID01?view=summary'))['result']
        original=urlopen(base+'/api/measurements/ID01/original').read()
        assert hashlib.sha256(original).hexdigest()==summary['provenance']['source_sha256']
        b.call('Browser.setDownloadBehavior',dict(behavior='allow',downloadPath=str(args.out.resolve())))
        b.click('#download-summary')
        import time
        deadline=time.monotonic()+10
        download=args.out/'freetwinev_ID01_measured_summary.json'
        while not download.exists() and time.monotonic()<deadline:time.sleep(.1)
        assert json.loads(download.read_text())==summary
        checks.append('Browser JSON export matches API summary; original CSV download matches declared hash')
        b.call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=False))
        b.js('window.scrollTo(0,0)')
        assert b.js('document.documentElement.scrollWidth<=window.innerWidth')
        b.screenshot(args.out/'03_mobile.png')
        b.js('document.querySelector(".sample-inspector").scrollIntoView()')
        b.screenshot(args.out/'04_mobile_inspector.png')
        checks.append('390px layout fits viewport and exact-source inspector remains usable')
        b.click('.back-link')
        b.wait('document.querySelectorAll(".cell-group").length===4')
        assert 'LG M50T' in b.js('document.body.innerText')
        checks.append('Return to unchanged four-cell LG simulator succeeds')
        assert not b.errors,b.errors
        (args.out/'verification.json').write_text(json.dumps(dict(checks=checks,browser_errors=b.errors,
            source_record='ID01 only',experimental_validation='awaiting suitable measurements'),indent=2)+'\n',encoding='utf-8')
        print(f'Passed {len(checks)} browser checks; four screenshots saved.')
    finally:
        if browser:browser.close()
        server.shutdown();server.server_close();thread.join()


if __name__=='__main__':main()
