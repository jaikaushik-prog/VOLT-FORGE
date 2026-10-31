"""Build the two demo designs and capture the slide's product screens from the real app."""
from pathlib import Path
import io
import json
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'workspace/demo_final'
def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); return probe.getsockname()[1]


PORT = free_port()
ASSETS = ROOT/'reports/slide_v4/assets'
PICK = """()=>{const f=[...document.querySelectorAll('#compare-form select')];const pick=(s,t)=>{const o=[...s.options].find(x=>x.textContent.includes(t));s.value=o.value;s.dispatchEvent(new Event('change',{bubbles:true}))};pick(f[0],'Starting design');pick(f[1],'Smaller, cheaper')}"""


def main():
    if PROJECT.exists(): shutil.rmtree(PROJECT)
    env = dict(PYTHONPATH='src', PYTHONDONTWRITEBYTECODE='1', PATH='/usr/bin:/bin')
    subprocess.run([str(ROOT/'.venv/bin/python'), 'scripts/build_demo_designs.py'], cwd=ROOT, env=env, check=True)
    server = subprocess.Popen([str(ROOT/'.venv/bin/python'), 'scripts/run_editor.py', '--project', str(PROJECT), '--port', str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            urlopen(f'http://127.0.0.1:{PORT}/', timeout=1); break
        except OSError: time.sleep(.5)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome')
            page = browser.new_page(viewport=dict(width=1560, height=700), device_scale_factor=3)
            page.goto(f'http://127.0.0.1:{PORT}/'); page.wait_for_selector('.design-item', timeout=15000)
            page.locator('.design-item', has_text='Starting design').first.click(); page.wait_for_timeout(1500)
            page.evaluate("document.querySelector('[data-act=\"mode:circuit\"]')?.click()"); page.wait_for_timeout(900)
            page.click('[data-cell="cell1"]'); page.wait_for_selector('.selection-card'); page.wait_for_timeout(800)
            circuit = Image.open(io.BytesIO(page.screenshot()))
            circuit.crop((0, 234, circuit.width, 1614)).save(ASSETS/'circuit.png')
            page.evaluate("document.querySelector('[data-act=\"close-panel\"]')?.click()"); page.wait_for_timeout(500)
            page.set_viewport_size(dict(width=1560, height=900))
            page.evaluate("document.querySelector('[data-act=\"view:results\"]')?.click()"); page.wait_for_timeout(1500)
            page.evaluate("document.querySelector('[data-act=\"compare\"]')?.click()"); page.wait_for_selector('#compare-form select', timeout=8000); page.wait_for_timeout(800)
            page.evaluate(PICK); page.click('#compare-form button[type=submit]'); page.wait_for_selector('.compare-designs', timeout=10000); page.wait_for_timeout(1500)
            page.evaluate("document.querySelectorAll('.compare-designs svg,.compare-designs .battery-canvas').forEach(e=>e.style.setProperty('height','208px','important'))"); page.wait_for_timeout(500)
            page.evaluate("document.querySelector('.compare-designs').scrollIntoView({block:'start'})"); page.wait_for_timeout(700)
            box = page.evaluate("(()=>{const a=document.querySelector('.compare-designs').getBoundingClientRect(),b=document.querySelector('.compare-tables').getBoundingClientRect();return [a.left,a.top,a.right,b.bottom]})()")
            rows = page.evaluate("[...document.querySelectorAll('.compare-table tbody tr')].map(r=>r.innerText.replace(/\\s+/g,' '))")
            shot = Image.open(io.BytesIO(page.screenshot()))
            left, top, right, bottom = box
            shot.crop((int((left-2)*3), int((top-4)*3), int((right+2)*3), int(min(bottom+4, 900)*3))).save(ASSETS/'compare.png')
            print(json.dumps(dict(box=box, rows=rows), ensure_ascii=False))
            browser.close()
    finally:
        server.terminate()


if __name__ == '__main__': sys.exit(main())
