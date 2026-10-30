"""Run the core user flow in each installed browser engine and record what happened."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PORT = 8799
ENGINES = dict(webkit=dict(kind='webkit'), firefox=dict(kind='firefox'), edge=dict(kind='chromium', channel='msedge'), chrome=dict(kind='chromium', channel='chrome'))


def flow(page):
    r = {}; errors = []
    page.on('pageerror', lambda e: errors.append(str(e)[:160]))
    page.on('console', lambda m: errors.append(m.text[:160]) if m.type == 'error' else None)
    page.goto(f'http://127.0.0.1:{PORT}/'); page.wait_for_selector('[data-act="new"]', timeout=15000)
    page.click('[data-act="tour:start"]'); page.wait_for_timeout(1200); r['guide'] = page.locator('#walkthrough').count() > 0
    page.evaluate("document.querySelector('[data-act=\"tour:dismiss\"]')?.click()"); page.wait_for_timeout(500)
    page.evaluate("document.querySelector('[data-act=\"home\"]')?.click()"); page.wait_for_timeout(800)
    page.click('[data-act="new"]'); page.wait_for_timeout(500)
    page.click('[data-act="setup-next"]'); page.wait_for_timeout(300); page.click('[data-act="setup-next"]'); page.wait_for_timeout(300)
    page.click('#new-form button[type=submit]'); page.wait_for_selector('.load-block', timeout=15000); r['load_block'] = True
    page.click('[data-cell="cell2"]'); page.wait_for_selector('.selection-card', timeout=8000); r['cell_size'] = 'mm' in page.inner_text('.selection-card')
    page.evaluate("document.querySelector('[data-act=\"close-panel\"]')?.click()"); page.wait_for_timeout(400)
    r['live_cost'] = page.inner_text('#live-cost') if page.locator('#live-cost').count() else None
    page.click('[data-act="view:test"]'); page.wait_for_timeout(700); page.click('#test-form button[type=submit]')
    page.wait_for_selector('.verdict', timeout=60000); r['verdict'] = ' / '.join(page.inner_text('.verdict').split('\n'))[:220]
    r['chart'] = page.locator('svg, canvas').count() > 0
    r['preset_kept'] = 'custom' not in page.inner_text('main').lower() and '8.42 A' in page.inner_text('main')
    page.set_viewport_size(dict(width=390, height=844)); page.wait_for_timeout(500)
    r['phone_scroll_ok'] = page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    r['console_errors'] = errors[:6]
    return r


def main():
    folder = Path(tempfile.mkdtemp(prefix='vf-browsers-')); out = {}
    server = subprocess.Popen([str(ROOT/'.venv/bin/python'), 'scripts/run_editor.py', '--project', str(folder/'project'), '--port', str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            urlopen(f'http://127.0.0.1:{PORT}/', timeout=1); break
        except OSError: time.sleep(.5)
    try:
        with sync_playwright() as p:
            for name, e in ENGINES.items():
                try:
                    browser = getattr(p, e['kind']).launch(**({'channel': e['channel']} if 'channel' in e else {}))
                    page = browser.new_page(viewport=dict(width=1440, height=900)); out[name] = dict(version=browser.version, **flow(page)); browser.close()
                except Exception as exc:
                    out[name] = dict(error=str(exc)[:300])
                print(name, json.dumps(out[name], ensure_ascii=False)[:600], flush=True)
    finally:
        server.terminate()
    (ROOT/'reports/v4_release/browser_check.json').write_text(json.dumps(out, indent=1, ensure_ascii=False)+'\n')


if __name__ == '__main__': main()
