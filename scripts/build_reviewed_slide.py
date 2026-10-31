"""Create a separate, source-traceable Round 1 review draft without changing studies.

From the repository root (Windows PowerShell):
  & C:/Users/DELL/anaconda3/python.exe scripts/build_reviewed_slide.py \
      --pdfium-path C:/Users/DELL/Desktop/volt-forge/tmp/pdf_runtime

Requires ReportLab, Pillow, and pypdfium2 (the latter may be in --pdfium-path).
Writes only reports/slide_round1_review_v1/. No model runs, network, or git writes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/slide_round1_review_v1"
PIN = "c2339a569876da5fc20969ea578a91ae57f33384"
PDF_NAME = "VOLT-FORGE_Round1_Reviewed_Draft.pdf"
W, H = 1600, 900
NAVY = colors.HexColor("#163449")
BLUE = colors.HexColor("#007BAC")
INK = colors.HexColor("#243E4F")
MUTED = colors.HexColor("#536B7B")
PALE = colors.HexColor("#EAF6FC")
LINE = colors.HexColor("#CEDFE8")
PANEL = colors.HexColor("#F5F8FA")
WHITE = colors.white

PATHS = {
    "study": "reports/design_study_v2/run1/summary.json",
    "repeat": "reports/v4_release/study_repeat.json",
    "protocol": "configs/round1_design_study_v2.json",
    "numerical": "reports/numerical_reference_v2/locked_97ca199/verification.json",
    "numerical_protocol": "reports/numerical_reference_v2/locked_97ca199/protocol.json",
    "measured": "reports/measured_comparison_v1/final/result.json",
    "measured_protocol": "configs/measured_comparison_v1.json",
    "recommendation": "reports/design_study_v2/RECOMMENDATION.md",
    "user_trial": "reports/user_trial_v1/KIT.md",
    "business": "configs/business_case_v1.json",
    "screenshot": "reports/slide_v4/assets/circuit.png",
    "logo_teliport": "reports/slide_v4/assets/logo_teliport.png",
    "logo_tata": "reports/slide_v4/assets/logo_tata.png",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(key: str):
    return json.loads((ROOT / PATHS[key]).read_text(encoding="utf-8"))


def extract():
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    sources = {}
    for key, relative in PATHS.items():
        pinned_bytes = subprocess.check_output(["git", "show", f"{PIN}:{relative}"], cwd=ROOT)
        pinned_sha = hashlib.sha256(pinned_bytes).hexdigest()
        current_sha = sha(ROOT / relative)
        if current_sha != pinned_sha:
            raise ValueError(f"Frozen input differs from {PIN}: {relative}")
        sources[key] = {"path": relative, "sha256": current_sha,
                        "pinned_git_sha256": pinned_sha, "matches_pinned_source": True}
    study, protocol = load("study"), load("protocol")
    rows = []
    for n in (4, 3, 2):
        matches = [r for r in study["designs"] if r["count"] == n and r["option"] == "baseline"]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one same-end baseline row for {n} cells")
        r = matches[0]
        if not r["qualifies"] or r["required_cases"] != r["required_passed"]:
            raise ValueError(f"Unexpected qualification result for {n} cells")
        rows.append({
            "cells": n, "source_selector": f"designs[count={n}, option=baseline]",
            "required_passed": r["required_passed"], "required_cases": r["required_cases"],
            "worst_cell_current_A": r["worst_required"]["highest_cell_current_A"],
            "worst_cell_temperature_C": r["worst_required"]["highest_temperature_C"],
            "worst_battery_voltage_V": r["worst_required"]["lowest_voltage_V"],
            "cell_mass_g": r["cell_mass_g"], "listed_cell_cost_inr": r["cell_cost_inr"],
        })
    numerical, measured = load("numerical"), load("measured")
    numerical_count = len(numerical["checks"])
    numerical_passed = sum(bool(x["passed"]) for x in numerical["checks"])
    measured_count = len(measured["cases"])
    voltage_passed = sum(bool(x["voltage_within_band"]) for x in measured["cases"])
    temperature_passed = sum(bool(x["temperature_within_band"]) for x in measured["cases"])
    # Fail closed if a future source update would make the fixed explanatory copy stale.
    assert (numerical_count, numerical_passed) == (15, 15)
    assert (measured_count, voltage_passed, temperature_passed) == (12, 0, 0)
    assert numerical["temperature_comparison_performed"] is False
    assert study["smallest_qualifying_cell_count"] == 2
    assert protocol["common"]["charge_pct"] == 70
    assert protocol["common"]["ambient_C"] == 23
    assert protocol["common"]["duration_s"] == 600
    assert protocol["missions"]["pi"]["power_W"] == 25
    assert protocol["missions"]["pi"]["converter_efficiency"] == 0.9
    assert protocol["common"]["voltage_floor_V"] == 3.3
    assert rows[0]["listed_cell_cost_inr"] == rows[2]["listed_cell_cost_inr"] * 2
    assert rows[0]["cell_mass_g"] == rows[2]["cell_mass_g"] * 2
    return {
        "artifact_status": "Review draft; not published or submitted",
        "source_commit": PIN,
        "checkout_head_at_generation": actual,
        "source_software_id": load("repeat")["locked_software"],
        "review_date": "2026-10-31",
        "comparison": {
            "option": "baseline", "description": protocol["options"]["baseline"],
            "base_conditions": protocol["common"], "mission": protocol["missions"]["pi"],
            "required_tiers": protocol["qualification"]["required_tiers"],
            "rows": rows,
            "cost_mass_scope": "Cells only; listed cost, not a complete system price or stock quote",
            "temperature_scope": "Simulated output; measured accuracy not established",
        },
        "evidence": {
            "numerical": {"passed": numerical_passed, "total": numerical_count,
                          "temperature_comparison_performed": False,
                          "scope": numerical["scope"]},
            "measured": {"total": measured_count, "voltage_band_passed": voltage_passed,
                         "temperature_band_passed": temperature_passed,
                         "experimental_validation": measured["experimental_validation"]},
        },
        "copy_provenance": {
            "conditional_result": "study.smallest_qualifying_cell_count; protocol.scope/qualification",
            "limitations": "recommendation: What argues against it; Checks on the decision",
            "buyer_hypothesis": "business.status/model; user_trial: introductory paragraph",
            "protection": "recommendation: Checks on the decision / Virtual protection",
            "screenshot": "Original V4 circuit image; illustrative UI, not the study comparison topology",
            "next_step": "Proposed next action; not a completed experiment or user trial",
        },
        "sources": sources,
        "generator_sha256": sha(Path(__file__)),
    }


def register_fonts(font_dir: Path):
    for name, filename in (("Arial", "arial.ttf"), ("ArialBold", "arialbd.ttf")):
        font_path = font_dir / filename
        if not font_path.is_file():
            raise FileNotFoundError(f"Required font missing: {font_path}")
        pdfmetrics.registerFont(TTFont(name, str(font_path)))
    pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="ArialBold", italic="Arial", boldItalic="ArialBold")


def build_pdf(data):
    pdf_path = OUT / PDF_NAME
    c = canvas.Canvas(str(pdf_path), pagesize=(W, H), pageCompression=1, invariant=1)
    c.setTitle("VOLT-FORGE | Round 1 revised submission draft | Frozen V4 study")
    c.setAuthor("Team StratWise")
    c.setSubject("Conditional small-module simulation comparison; review draft, not submitted")

    def box(x, y, w, h, fill, radius=0, stroke=None):
        c.setFillColor(fill)
        c.setStrokeColor(stroke or fill)
        if radius:
            c.roundRect(x, H-y-h, w, h, radius, stroke=bool(stroke), fill=1)
        else:
            c.rect(x, H-y-h, w, h, stroke=bool(stroke), fill=1)

    def txt(text, x, y, size=18, bold=False, color=INK):
        c.setFont("ArialBold" if bold else "Arial", size)
        c.setFillColor(color)
        c.drawString(x, H-y-size, text)

    def para(text, x, y, w, max_h, size=18, color=INK, leading=None, bold=False):
        style = ParagraphStyle("body", fontName="ArialBold" if bold else "Arial", fontSize=size,
                               leading=leading or size*1.25, textColor=color, spaceAfter=0)
        p = Paragraph(text, style)
        _, h = p.wrap(w, max_h)
        if h > max_h + 0.1:
            raise ValueError(f"Text overflow ({h:.1f} > {max_h}): {text[:80]}")
        p.drawOn(c, x, H-y-h)
        return h

    def pic(key, x, y, w, max_h):
        path = ROOT / PATHS[key]
        with Image.open(path) as im:
            iw, ih = im.size
        h = w * ih / iw
        if h > max_h:
            w *= max_h / h
            h = max_h
        c.drawImage(str(path), x, H-y-h, width=w, height=h, mask="auto")
        return h

    box(0, 0, W, H, WHITE)
    box(0, 0, W, 8, BLUE)
    pic("logo_teliport", 42, 31, 190, 79)
    pic("logo_tata", 1458, 28, 100, 83)
    txt("VOLT-FORGE", 267, 27, 39, True, NAVY)
    txt("Fewer cells. Clearer trade-offs.", 269, 78, 26, False, MUTED)
    txt("CASE STUDY 2", 1265, 74, 16, True, BLUE)

    box(42, 133, 1516, 99, PALE, 12)
    txt("Two cells are a simulation candidate.", 65, 145, 30, True, NAVY)
    para("Smallest qualifying count among the <b>1-4-cell parallel arrangements tested</b> for this backup job.<br/>"
         "Half the four-cell baseline's cell cost and mass, with less current and voltage margin.",
         66, 185, 1450, 42, 18, leading=21)

    txt("COMMON BASE CASE", 43, 245, 15, True, BLUE)
    txt("Pi 5 backup  |  LG M50T cells  |  25 W supply-rating scenario  |  10 min  |  23 °C  |  70% starting charge", 244, 241, 19)
    txt("90% converter assumed  |  3.3 V floor  |  8.42 A constant-current proxy  |  actual Pi draw not measured", 244, 269, 17, color=MUTED)

    txt("BUILD, TEST, UNDERSTAND", 43, 309, 18, True, BLUE)
    txt("BASELINE + TWO OPTIONS", 728, 309, 18, True, BLUE)
    image_h = pic("screenshot", 43, 346, 650, 193)
    txt("Original V4 editor view; illustrative circuit, not the study table.", 44, 346+image_h+12, 14, color=MUTED)
    para("For students and lab instructors: edit a circuit, see how current and heat change, then compare alternatives. "
         "The search rebuilds and tests each cell count.",
         44, 583, 650, 47, 18, leading=22)

    tx, ty, tw = 728, 344, 830
    widths = [168, 112, 142, 142, 110, 156]
    headers = ["Parallel<br/>design", "Required<br/>cases pass", "Worst cell<br/>current", "Worst cell<br/>temperature", "Cell<br/>mass", "Listed<br/>cell cost"]
    box(tx, ty, tw, 51, NAVY, 7)
    col = tx
    for header, width in zip(headers, widths):
        para(header, col+14, ty+8, width-20, 40, 16, WHITE, leading=18, bold=True)
        col += width
    for i, row in enumerate(data["comparison"]["rows"]):
        y = ty+51+i*51
        box(tx, y, tw, 51, PALE if row["cells"] == 2 else (PANEL if i == 0 else WHITE))
        label = f'{row["cells"]} cells' + (" | baseline" if row["cells"] == 4 else "")
        values = [label, f'{row["required_passed"]}/{row["required_cases"]}',
                  f'{row["worst_cell_current_A"]:.2f} A',
                  f'{row["worst_cell_temperature_C"]:.1f} °C',
                  f'{row["cell_mass_g"]:.0f} g', f'₹{row["listed_cell_cost_inr"]:,.0f}']
        col = tx
        for value, width in zip(values, widths):
            txt(value, col+14, y+14, 19 if col == tx else 21, row["cells"] == 2, NAVY)
            col += width
    para("Same-end outputs and declared study links throughout. Cases include mismatch, thermal and converter sensitivities; "
         "counts vary with cell positions. All temperatures are simulated. Cost and mass cover cells only.",
         tx+1, 561, tw-4, 66, 17, color=MUTED, leading=21)

    cards = [(42, 490), (555, 490), (1068, 490)]
    for x, width in cards:
        box(x, 649, width, 160, PANEL, 10)
    txt("EVIDENCE", 61, 662, 15, True, BLUE)
    txt("15/15 numerical checks passed", 61, 686, 23, True, NAVY)
    para("PyBaMM / analytic verification.<br/><b>All 12 comparison cases missed the voltage and temperature bands.</b> "
         "Measured accuracy is not established.", 61, 723, 449, 80, 17, leading=20)

    txt("LIMITS THAT MATTER", 574, 662, 15, True, BLUE)
    txt("Conditional, not build-ready", 574, 686, 23, True, NAVY)
    para("Two cells have no spare. Board battery-current limits remain unverified. "
         "Virtual cutoffs are modeled; physical protection has not been demonstrated.",
         574, 723, 448, 79, 17, leading=20)

    txt("USER + BUYER HYPOTHESIS", 1087, 662, 15, True, BLUE)
    txt("Start with teaching labs", 1087, 686, 23, True, NAVY)
    para("Free student use; paid lab licences are an untested pricing hypothesis. "
         "No observed user trials yet. Next user test: complete and explain a comparison.",
         1087, 723, 447, 79, 17, leading=20)

    txt("NEXT", 43, 825, 16, True, BLUE)
    txt("Measure actual load and converter behavior; bench-check a candidate with supervised cutoffs; observe student tasks.", 109, 822, 19)
    box(42, 858, 1516, 1, LINE)
    demo_label = "Try: volt-forge-app.vercel.app"
    separator = "   |   "
    evidence_label = "Evidence: volt-forge-app.vercel.app/appendix"
    txt(demo_label+separator+evidence_label, 43, 870, 14, color=BLUE)
    demo_end = 43 + pdfmetrics.stringWidth(demo_label, "Arial", 14)
    evidence_start = demo_end + pdfmetrics.stringWidth(separator, "Arial", 14)
    evidence_end = evidence_start + pdfmetrics.stringWidth(evidence_label, "Arial", 14)
    c.linkURL("https://volt-forge-app.vercel.app", (43, H-889, demo_end, H-868), relative=0)
    c.linkURL("https://volt-forge-app.vercel.app/appendix", (evidence_start, H-889, evidence_end, H-868), relative=0)
    txt("Team StratWise  |  Revised submission draft  |  Frozen V4 study  |  Not submitted", 1040, 872, 12, color=MUTED)
    c.showPage()
    c.save()
    return pdf_path


def verify_render(pdf_path: Path, pdfium_path: Path | None):
    if pdfium_path:
        sys.path.insert(0, str(pdfium_path.resolve()))
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf_path))
    assert len(doc) == 1, f"Expected one page, found {len(doc)}"
    page = doc[0]
    textpage = page.get_textpage()
    extracted = textpage.get_text_range()
    textpage.close()
    for phrase in ("51/51", "42/42", "33/33", "15/15", "All 12 comparison cases", "Revised submission draft", "No observed user trials", "Frozen V4 study"):
        if phrase not in extracted:
            raise AssertionError(f"Missing extracted content: {phrase}")
    if "35 crore" in extracted or "₹35" in extracted:
        raise AssertionError("Unexpected roadmap cost in draft")
    (OUT / "extracted_text.txt").write_text(extracted.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    bitmap = page.render(scale=1.25)
    bitmap.to_pil().save(OUT / "reviewed_slide.png")
    bitmap.close()
    normal = page.render(scale=0.9)
    normal.to_pil().save(OUT / "reviewed_slide_normal_view.png")
    normal.close()
    page.close()
    doc.close()
    return {"pages": 1, "required_text_present": True,
            "render_files": ["reviewed_slide.png", "reviewed_slide_normal_view.png"],
            "visual_review": "Required separately after generation; not asserted by automated checks"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdfium-path", type=Path)
    parser.add_argument("--font-dir", type=Path, default=Path("C:/Windows/Fonts"))
    args = parser.parse_args()
    data = extract()
    register_fonts(args.font_dir)
    data["fonts"] = {n: sha(args.font_dir / n) for n in ("arial.ttf", "arialbd.ttf")}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "source_data.json").write_text(json.dumps(data, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    pdf_path = build_pdf(data)
    checks = verify_render(pdf_path, args.pdfium_path)
    checks["pdf_sha256"] = sha(pdf_path)
    checks["source_data_sha256"] = sha(OUT / "source_data.json")
    (OUT / "verification.json").write_text(json.dumps(checks, indent=2)+"\n", encoding="utf-8")
    (OUT / "README.md").write_text(
        "# Revised Round 1 review draft\n\n"
        "One content page, separate from the original cover and submission. Not published or submitted. "
        "The team must verify portal file/format rules and deadline before submission.\n\n"
        "## Rebuild\n\nFrom the pinned repository root in PowerShell:\n\n"
        "```powershell\n& C:/Users/DELL/anaconda3/python.exe scripts/build_reviewed_slide.py "
        "--pdfium-path C:/Users/DELL/Desktop/volt-forge/tmp/pdf_runtime\n```\n\n"
        f"Pinned input commit: `{PIN}`. The generator reads frozen source reports; it does not rerun or modify a model. "
        "The source-data JSON includes selectors, original values and SHA-256 hashes for every input and font. "
        "The screenshot is the original V4 editor and is labelled as illustrative; its wiring is not the study table. "
        "No claim is made about subsequent live-app fixes.\n\n"
        "`verification.json` records page/text/render checks. The generated PNGs require visual inspection after each rebuild. "
        "No hardware accuracy, protection certification, customer evidence or live deployment identity is inferred.\n",
        encoding="utf-8")
    print(json.dumps({"pdf": str(pdf_path), "checks": checks}, indent=2))


if __name__ == "__main__":
    main()
