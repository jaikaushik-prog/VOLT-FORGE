"""Render reports/slide_v4/slide.html to the slide PNG with headless Chrome."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT/'reports/slide_v4/VOLT-FORGE_Round1_Slide.png'
subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--window-size=1920,1080', '--force-device-scale-factor=2', '--virtual-time-budget=4000', f'--screenshot={out}', (ROOT/'reports/slide_v4/slide.html').as_uri()], check=True, capture_output=True)
print(out)
