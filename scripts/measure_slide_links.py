"""Record where the slide's links sit, so the PowerPoint can make them clickable."""
from pathlib import Path
import json

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome'); page = browser.new_page(viewport=dict(width=1920, height=1080))
    page.goto((ROOT/'reports/slide_v4/slide.html').as_uri()); page.wait_for_timeout(1500)
    boxes = page.evaluate("Object.fromEntries([['site','#site-link'],['appendix','#appendix-link']].map(([k,s])=>{const r=document.querySelector(s).getBoundingClientRect();return [k,[r.x-4,r.y-4,r.width+8,r.height+8]]}))")
    browser.close()
(ROOT/'reports/slide_v4/link_boxes.json').write_text(json.dumps(boxes)+'\n'); print(boxes)
