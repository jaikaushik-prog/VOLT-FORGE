"""Walk the public site end to end: video, real engine, smallest design and AI draft."""
from pathlib import Path
import json
import sys
import time

from playwright.sync_api import sync_playwright

URL = sys.argv[1].rstrip('/')
ROOT = Path(__file__).resolve().parents[1]


def main():
    r = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome'); page = browser.new_page(viewport=dict(width=1440, height=900)); errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:200]))
        page.on('console', lambda m: errors.append(m.text[:200]) if m.type == 'error' else None)
        page.goto(URL+'/'); page.wait_for_selector('video'); page.wait_for_timeout(1500)
        r['video_playing'] = page.evaluate("(()=>{const v=document.querySelector('video');return !v.paused&&v.currentTime>0})()")
        started = time.time(); page.click('a.button.main'); page.wait_for_selector('[data-act="new"]', timeout=120000); r['load_seconds'] = round(time.time()-started, 1)
        page.click('[data-act="new"]'); page.wait_for_timeout(400); page.click('[data-act="setup-next"]'); page.wait_for_timeout(250); page.click('[data-act="setup-next"]'); page.wait_for_timeout(250)
        page.click('#new-form button[type=submit]'); page.wait_for_selector('.load-block', timeout=20000)
        page.click('[data-act="view:test"]'); page.wait_for_timeout(600); started = time.time(); page.click('#test-form button[type=submit]'); page.wait_for_selector('.verdict', timeout=90000)
        r['test_seconds'] = round(time.time()-started, 1); r['verdict'] = ' / '.join(page.inner_text('.verdict').split('\n'))[:170]
        started = time.time(); page.click('[data-act="smallest"]')
        for _ in range(180):
            page.wait_for_timeout(1000)
            if 'Investigation complete' in page.inner_text('main'): break
        r['smallest_seconds'] = round(time.time()-started, 1); text = page.inner_text('main'); r['smallest'] = '2 cells' in text and 'Smallest qualifying design' in text and 'US$46' in text
        page.evaluate("document.querySelector('[data-act=\"view:results\"]')?.click()"); page.wait_for_timeout(1200)
        with page.expect_download(timeout=30000) as download: page.evaluate("document.querySelector('[data-act=\"export\"]')?.click()")
        r['export_bytes'] = Path(download.value.path()).stat().st_size
        page.click('[data-act="ai"]'); page.wait_for_selector('#chat-input', timeout=8000)
        page.fill('#chat-input', sys.argv[2] if len(sys.argv) > 2 else 'Why is Cell 1 the busiest?'); page.keyboard.press('Enter'); page.wait_for_timeout(400)
        page.evaluate("document.querySelector('.ai-panel form button[type=submit]')?.click()"); page.wait_for_timeout(15000)
        r['ai_panel'] = page.inner_text('.ai-panel')[-260:].replace('\n', ' ')
        r['console_errors'] = errors[:6]; browser.close()
    print(json.dumps(r, indent=1, ensure_ascii=False))


if __name__ == '__main__': main()
