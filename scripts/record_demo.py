"""Record a short captioned walkthrough of the real app on a fresh project."""
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'reports/demo_v1/VOLT-FORGE_demo.mp4'
def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); return probe.getsockname()[1]


PORT = free_port()
SIZE = dict(width=1600, height=900)
CAPTION = """(text)=>{let c=document.querySelector('#demo-caption');if(!c){c=document.createElement('div');c.id='demo-caption';c.style.cssText='position:fixed;left:50%;bottom:28px;transform:translateX(-50%);max-width:1180px;background:#0B6FA8;color:#fff;font:600 25px/1.35 Arial,sans-serif;padding:14px 28px;border-radius:14px;z-index:99999;text-align:center;box-shadow:0 8px 28px rgba(0,0,0,.25)';document.body.append(c)}c.textContent=text}"""


def say(page, text, seconds=3.2):
    page.evaluate(CAPTION, text); page.wait_for_timeout(int(seconds*1000))


def walk(page):
    page.goto(f'http://127.0.0.1:{PORT}/'); page.wait_for_selector('[data-act="new"]', timeout=15000)
    say(page, 'Say a Raspberry Pi 5 gateway has to survive a 10-minute power cut at 25 W.', 3.6)
    page.click('[data-act="new"]'); page.wait_for_timeout(700)
    say(page, 'Start by saying what the battery has to do.', 2.4)
    page.click('[data-act="setup-next"]'); page.wait_for_timeout(900); page.click('[data-act="setup-next"]'); page.wait_for_timeout(900)
    page.click('#new-form button[type=submit]'); page.wait_for_selector('.load-block', timeout=15000)
    page.evaluate("document.querySelector('[data-act=\"mode:circuit\"]')?.click()"); page.wait_for_timeout(800)
    say(page, 'Four LG M50T cells in parallel. This is the real circuit the solver runs.', 3.4)
    page.click('[data-cell="cell1"]'); page.wait_for_selector('.selection-card', timeout=8000)
    say(page, 'Click a cell to see and change what is inside it.', 3.0)
    page.evaluate("document.querySelector('[data-act=\"close-panel\"]')?.click()"); page.wait_for_timeout(500)
    page.click('[data-act="view:test"]'); page.wait_for_timeout(800)
    say(page, 'The test uses the job we set: 8.42 A for 10 minutes.', 2.6)
    page.click('#test-form button[type=submit]'); page.wait_for_selector('.verdict', timeout=60000); page.wait_for_timeout(600)
    say(page, 'It holds for 10 minutes. But Cell 1 carries 25% more than an even share.', 4.2)
    page.evaluate(CAPTION, 'So how few cells could do this job? It rebuilds the circuit at each size and tests them.')
    page.click('[data-act="smallest"]')
    for _ in range(120):
        page.wait_for_timeout(1000)
        if page.locator('[data-act^="limit-open:"]').count() > 2 and 'Investigation complete' in page.inner_text('main'): break
    page.evaluate("document.querySelector('[data-act=\"limit-open:0\"]')?.scrollIntoView({block:'center'})"); page.wait_for_timeout(500)
    say(page, 'One cell is refused. Two cells qualify, at half the cell cost.', 4.6)
    say(page, 'Every number stays traceable, and the same test gives the same answer.', 3.4)
    say(page, 'VOLT-FORGE. Test a battery before you build it. These results are simulated.', 3.6)


def main():
    folder = Path(tempfile.mkdtemp(prefix='vf-demo-')); OUT.parent.mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen([str(ROOT/'.venv/bin/python'), 'scripts/run_editor.py', '--project', str(folder/'project'), '--port', str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            urlopen(f'http://127.0.0.1:{PORT}/', timeout=1); break
        except OSError: time.sleep(.5)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome')
            context = browser.new_context(viewport=SIZE, record_video_dir=str(folder/'video'), record_video_size=SIZE)
            page = context.new_page(); walk(page); context.close(); browser.close()
    finally:
        server.terminate()
    source = next((folder/'video').glob('*.webm'))
    subprocess.run([shutil.which('ffmpeg'), '-y', '-loglevel', 'error', '-i', str(source), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-movflags', '+faststart', str(OUT)], check=True)
    print(OUT, OUT.stat().st_size)


if __name__ == '__main__': sys.exit(main())
