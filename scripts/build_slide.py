"""Build the one-slide pitch on the official Teliport template, from one data file."""
from copy import deepcopy
from pathlib import Path
import argparse
import json
import sys

from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Pt

BLUE, DEEP, TINT, INK, MUTED, LINE = '00A7E1', '3C90CE', 'F0F6FB', '231F20', '5B6673', 'D5E3EE'
ORANGE, ORANGE_TINT, GREEN, WHITE = 'E2571E', 'FFF3EC', '12805C', 'FFFFFF'
BIG, BODY, NOTE = 19, 9, 6.5
rgb = RGBColor.from_string


def text(slide, x, y, w, h, runs, size=BODY, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, bold=False, name=None, spacing=None):
    """runs: a string, or paragraphs of (text, style) pieces. '*' bolds, '#' adds the accent."""
    box = slide.shapes.add_textbox(Pt(x), Pt(y), Pt(w), Pt(h)); frame = box.text_frame
    frame.word_wrap = True; frame.vertical_anchor = anchor
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
    if name: box.name = name
    paragraphs = [[(runs, 'b' if bold else '')]] if isinstance(runs, str) else runs
    for index, pieces in enumerate(paragraphs):
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph(); p.alignment = align
        if spacing: p.space_after = Pt(spacing)
        for content, style in pieces:
            r = p.add_run(); r.text = content; r.font.size = Pt(size); r.font.name = 'Calibri'
            r.font.bold = 'b' in style or '#' in style
            r.font.color.rgb = rgb(BLUE if '#' in style and color != WHITE else ORANGE if 'o' in style else GREEN if 'g' in style else color)
    return box


def box(slide, x, y, w, h, fill=None, line=None, radius=.08, name=None):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Pt(x), Pt(y), Pt(w), Pt(h)); s.adjustments[0] = radius
    if fill: s.fill.solid(); s.fill.fore_color.rgb = rgb(fill)
    else: s.fill.background()
    if line: s.line.color.rgb = rgb(line); s.line.width = Pt(.75)
    else: s.line.fill.background()
    s.shadow.inherit = False
    if name: s.name = name
    return s


def heading(slide, x, y, w, label):
    text(slide, x, y, w, 12, label, size=BODY+1, bold=True, name='Section: '+label)
    rule = slide.shapes.add_connector(1, Pt(x), Pt(y+13.5), Pt(x+w), Pt(y+13.5)); rule.line.color.rgb = rgb(BLUE); rule.line.width = Pt(1)


def cell_set(cell, value, size=BODY-1, bold=False, color=INK, fill=None, align=PP_ALIGN.CENTER):
    cell.margin_left = cell.margin_right = Pt(2.5); cell.margin_top = cell.margin_bottom = Pt(1.2); cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    frame = cell.text_frame; p = frame.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = str(value); r.font.size = Pt(size); r.font.bold = bold; r.font.name = 'Calibri'; r.font.color.rgb = rgb(color)
    if fill: cell.fill.solid(); cell.fill.fore_color.rgb = rgb(fill)
    else: cell.fill.background()


def table(slide, x, y, w, row_h, rows, widths, highlight=None, first_left=True, name=None):
    frame = slide.shapes.add_table(len(rows), len(rows[0]), Pt(x), Pt(y), Pt(w), Pt(row_h*len(rows)))
    if name: frame.name = name
    grid = frame.table
    props = grid._tbl.tblPr
    for key in ('firstRow', 'bandRow'): props.set(key, '0')
    style = props.find(qn('a:tableStyleId'))
    if style is not None: style.text = '{2D5ABB26-0587-4C30-8999-92F81FD0307C}'
    total = sum(widths)
    for i, width in enumerate(widths): grid.columns[i].width = Pt(w*width/total)
    for r, row in enumerate(rows):
        grid.rows[r].height = Pt(row_h)
        for c, value in enumerate(row):
            head = r == 0; marked = highlight == r
            color = value[1] if isinstance(value, tuple) else (WHITE if head else INK)
            shown = value[0] if isinstance(value, tuple) else value
            cell_set(grid.cell(r, c), shown, bold=head or marked or isinstance(value, tuple), color=color, fill=DEEP if head else TINT if marked else None,
                     align=PP_ALIGN.LEFT if first_left and c == 0 else PP_ALIGN.CENTER)
    return frame


def crop(source, target, box_):
    with Image.open(source) as image: image.crop(box_).save(target)


def lakh(value): return f'{value/1e5:.1f} lakh'
def inr(value): return f'₹{value:,.0f}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--canvas', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    d = json.loads(args.data.read_text()); prs = Presentation(args.template)
    best, four, save = d['best'], d['four'], d['saving']; rec = d['study']['recommended']
    n = best['count']; base2 = next(r for r in d['table'] if r['cells'] == n)
    cover, s = prs.slides[0], prs.slides[1]
    for shape in cover.shapes:
        if shape.has_text_frame and 'Case Study No' in shape.text_frame.text:
            shape.text_frame.paragraphs[0].runs[0].text = 'Case Study 2'
            for extra in shape.text_frame.paragraphs[0].runs[1:]: extra.text = ''
    for shape in list(s.placeholders):
        if shape.placeholder_format.idx != 0: shape._element.getparent().remove(shape._element)
    title = s.shapes.title; title.left, title.top, title.width, title.height = Pt(192), Pt(4), Pt(690), Pt(29)
    frame = title.text_frame; frame.word_wrap = True; frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0; frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = frame.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    for content, accent in (('VOLT-FORGE found a Raspberry Pi 5 backup passes on ', False), (f'{n} cells, not 4', True)):
        r = p.add_run(); r.text = content; r.font.size = Pt(BIG); r.font.bold = True; r.font.name = 'Calibri'; r.font.color.rgb = rgb(BLUE if accent else INK)
    text(s, 192, 34, 690, 13, 'A virtual platform that helps students and engineers design, test, compare and improve battery systems before buying parts', size=BODY+.5, color=MUTED, align=PP_ALIGN.CENTER, name='Qualifier')

    # Headline numbers.
    x0, gap, w = 14, 7, (932-4*7)/5
    tiles = [(f'{n} cells', 'smallest qualifying design tested, from 4'), (inr(save['cost_inr']), f"less on cells: {inr(save['cost_from'])} to {inr(save['cost_to'])}"),
             (f"{save['mass_g']:.0f} g", f"less cell mass: {save['mass_from']:.0f} g to {save['mass_to']:.0f} g"), (f"{d['study']['cases']:,}", 'simulated cases behind the result'),
             (f"{d['replay']['passed']} of {d['replay']['cases']}", 'exports replay exactly; tampering refused')]
    for i, (big, small) in enumerate(tiles):
        x = x0+i*(w+gap); box(s, x, 59, w, 45, fill=BLUE, radius=.12, name='Tile: '+big)
        text(s, x+4, 61, w-8, 24, big, size=BIG, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
        text(s, x+4, 86, w-8, 14, small, size=BODY-.5, color=WHITE, align=PP_ALIGN.CENTER)

    cols = [14, 14+(932-20)/3+10, 14+2*((932-20)/3+10)]; cw = (932-20)/3
    top, mid = 110, 303

    # 1. The job.
    heading(s, cols[0], top, cw, '1  The job: keep a Pi 5 gateway alive in a power cut')
    chip = lambda t: (t, BLUE if t == 'sourced' else ORANGE if t == 'assumed' else MUTED)
    table(s, cols[0], top+17, cw, 13.2, [['Requirement', 'Value', 'Basis'], ['Pi supply power', '25 W', chip('sourced')], ['Converter efficiency', '90%', chip('assumed')],
          ['Battery current at the floor', '8.42 A', chip('calculated')], ['Run time', '10 min', chip('assumed')], ['Lowest battery voltage', '3.3 V', chip('assumed')],
          ['Room temperature', '23 °C', chip('assumed')]], [5, 2, 2], name='Requirements')
    text(s, cols[0], top+113, cw, 60, [[('Why it is hard: ', 'b'), ('more cells cost more and weigh more, too few hit current limits, and ', ''), ('uneven sharing stresses some cells', 'b'), ('.', '')],
         [('Real part: ', 'b'), (f"the {d['board']['name']} (US${d['board']['usd']:.0f}) holds ", ''), ('four 21700 cells', 'b'), (', so 4 cells is the starting design.', '')]], spacing=2, name='Challenge')

    # 2. Build and test.
    heading(s, cols[1], top, cw, '2  Build it, test it, read the verdict')
    pic_w = cw; pic_h = pic_w*(BOX[3]-BOX[1])/(BOX[2]-BOX[0])
    picture = s.shapes.add_picture(str(args.canvas), Pt(cols[1]), Pt(top+17), Pt(pic_w), Pt(pic_h)); picture.name = 'Product screenshot'
    picture.line.color.rgb = rgb(LINE); picture.line.width = Pt(.75)
    text(s, cols[1], top+21+pic_h, cw, 26, [[('Wire real cells', 'b'), (' on the canvas, pick a load, run. ', ''), ('Find the smallest design', '#'), (' then rebuilds and tests 1 to 4 cells by itself.', '')]], name='Workflow')

    # 3. What the tool found.
    heading(s, cols[2], top, cw, '3  What the tool found')
    rows = [['Cells', 'Verdict', 'Lowest V', 'Peak A', 'Warmest', 'Cells cost', 'Mass']]
    for r in d['table']:
        ok = r['qualifies']; refused = r['outcome'] == 'refused'
        rows.append([r['cells'], ('Refused', ORANGE) if refused else ('Qualifies', GREEN) if ok else ('Fails', ORANGE), '—' if refused else f"{r['voltage']:.2f}", '—' if refused else f"{r['current']:.2f}",
                     '—' if refused else f"{r['temperature']:.1f} °C", inr(r['cost_inr']), f"{r['mass_g']:.0f} g"])
    table(s, cols[2], top+17, cw, 15, rows, [1.1, 2, 1.6, 1.4, 1.7, 1.8, 1.3], highlight=n, first_left=False, name='Trade-offs')
    effects = d['study']['option_effects'].get(f"{n}_{rec['option']}_pi", {})
    text(s, cols[2], top+97, cw, 76, [[(f"{n} cells passed all {best['required_cases']} required Pi cases", 'b'), (f": every position mismatched, cooling, heat and converter sensitivities. Worst case {best['worst_required']['highest_cell_current_A']:.2f} A against a 7.275 A limit, and {best['worst_required']['highest_temperature_C']:.1f} °C.", '')],
         [('One cell is refused', 'b'), (' because it would exceed that limit. Comparing with V3 links: ', ''), (OPTION[rec['option']], 'b'), (f" trims nominal peak current to {best['nominal']['peak_cell_current_A']:.2f} A.", '')]], spacing=2, name='Finding')

    # 4. Proof.
    heading(s, cols[0], mid, cw, '4  Proof: how far to trust it')
    chart = CategoryChartData(); chart.categories = [p_['name'] for p_ in d['proof']]
    for label, key in (('Measured', 'measured'), ('Sim, low cooling', 'low'), ('Sim, default', 'default'), ('Sim, high cooling', 'high')):
        chart.add_series(label, [round(p_[key], 1) for p_ in d['proof']])
    frame = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Pt(cols[0]), Pt(mid+16), Pt(cw*.62), Pt(100), chart); frame.name = 'Peak temperature rise, measured and simulated'
    c = frame.chart; c.has_legend = True; c.legend.position = XL_LEGEND_POSITION.BOTTOM; c.legend.include_in_layout = False; c.legend.font.size = Pt(NOTE); c.font.size = Pt(NOTE+.5); c.font.name = 'Calibri'
    c.has_title = True; c.chart_title.text_frame.text = 'Peak temperature rise (K)'; c.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(NOTE+1); c.chart_title.text_frame.paragraphs[0].runs[0].font.bold = True
    axis = c.value_axis; axis.visible = False; axis.has_major_gridlines = False; c.category_axis.format.line.color.rgb = rgb(LINE)
    plot = c.plots[0]; plot.gap_width = 45; plot.overlap = -5; plot.has_data_labels = True; plot.data_labels.font.size = Pt(NOTE); plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END; plot.data_labels.number_format = '0.0'; plot.data_labels.number_format_is_linked = False
    for series, color in zip(plot.series, (INK, 'A8DDF2', BLUE, DEEP)):
        series.format.fill.solid(); series.format.fill.fore_color.rgb = rgb(color)
    tx = cols[0]+cw*.64; tw = cw*.36
    text(s, tx, mid+17, tw, 100, [[(f"{d['pybamm']['passed']} of {d['pybamm']['cases']}", 'b'), (' PyBaMM voltage and heat checks passed.', '')], [('First-law check', 'b'), (' now ties electrical loss to heat, and fails on the V3 formula.', '')],
         [('Real data missed', 'b'), (f": all {d['proof_cases']} pre-declared cases fell outside their bands.", '')]], size=BODY-.5, spacing=2, name='Verification')
    text(s, cols[0], mid+118, cw, 24, [[('Heat tracks the single cell only at low cooling; the rig ran cooler. ', ''), ('So temperatures are a range, not a prediction.', 'b')]], name='Proof reading')

    # 5. Value.
    heading(s, cols[1], mid, cw, '5  Value: test before you buy')
    m = d['market']; steps = [(lakh(m['tam_students']), 'TAM: engineering students in India'), (lakh(m['sam_students']), 'SAM: electrical, electronics, mechanical'), (f"{m['som_colleges']:.0f} colleges", f"SOM: 5% of {m['colleges']:,}, assumed")]
    for i, (big, small) in enumerate(steps):
        y = mid+17+i*21.5; inset = i*13; box(s, cols[1]+inset, y, cw*.60-2*inset, 19.5, fill=BLUE if i == 2 else DEEP if i == 1 else TINT, radius=.15, name='Funnel: '+big)
        text(s, cols[1]+inset, y, cw*.60-2*inset, 19.5, big, size=BODY+1, bold=True, color=WHITE if i else INK, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        text(s, cols[1]+cw*.62, y+1, cw*.38, 19, small, size=BODY-1, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
    text(s, cols[1], mid+84, cw, 58, [[('Free for students, paid for teams and labs. ', 'b'), (f"At an assumed {inr(m['licence_inr'])} a lab, SOM is about ₹{m['som_inr']/1e5:.0f} lakh a year. Hypothesis, untested.", '')],
         [('Works with any cell', 'b'), (' through custom imports. A test runs in ', ''), ('seconds', 'b'), (f". The saving above is cell purchase only, not a whole unit.", '')]], spacing=2, name='Business')

    # 6. Honest finding.
    heading(s, cols[2], mid, cw, '6  Honest finding and next step')
    box(s, cols[2], mid+17, cw, 133, fill=ORANGE_TINT, radius=.05, name='Honest Finding')
    stress = best['stress']; sample = best['samples'].get('stress', {}); pi_sample = best['samples'].get('pi', {})
    text(s, cols[2]+7, mid+21, cw-14, 126, [[('The vulnerability: ', 'bo'), (f"{n} cells leave less margin. ", ''), (f"Under the 12 A stress test, {sample.get('cases', 0)-sample.get('passed', 0)} of {sample.get('cases', 0)} mixed-mismatch samples failed", 'b'), ('.', '')],
         [('The reality: ', 'bo'), (f"all {pi_sample.get('cases', 0)} mixed samples passed at the Pi load." if pi_sample.get('passed') == pi_sample.get('cases') else f"{pi_sample.get('passed', 0)} of {pi_sample.get('cases', 0)} mixed samples passed at the Pi load.", '')],
         [('Not proven: ', 'bo'), ('the board running on two cells, a real Pi draw, or measured accuracy. Voltage limit and run time are study assumptions.', '')],
         [('Next, Round 2: ', 'bo'), ('bench-test two cells on the board, and run observed trials with students and engineers.', '')]], size=BODY-.5, spacing=2, name='Honest Finding text')

    # So-what and sources.
    box(s, 14, 459, 932, 25, fill=BLUE, radius=.2, name='So what')
    text(s, 22, 459, 916, 25, [[('Test a design in seconds before you buy parts: ', 'b'), (f'the tool found a smaller battery that still does the job in simulation, at half the cell cost and mass.', '')]], size=BODY+2, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name='So what text')
    text(s, 14, 488, 932, 46, [[('Simulation, not hardware. ', 'b'), ('Published LG M50T tables, 4-cell parallel starting design with same-end outputs. 8.42 A is 25 W ÷ (0.9 × 3.3 V), held constant as an approximation. Prices: Robu LG M50T ₹1,206 incl. GST, listed out of stock; Geekworm, one listing; checked 30 Oct 2026, excluding shipping and fabrication. '
         f"Measured data: Chen et al. 2020 (LG M50, a related cell; zenodo.4032561) and Piombo et al. 2024 test 28 (exact M50T; 10.17632/zh58byr53c.2). Bars show means; low, default and high cooling are 0.076, 0.15 and 0.18 W/K, compared after the frozen result. Market: AISHE 2021-22; price and 5% reach are assumptions, and counts do not show willingness to pay. {n}-cell claim: {d['study']['claim'].lower()}.", '')]], size=NOTE, color=MUTED, name='Sources')
    prs.save(args.out)


OPTION = dict(baseline='keeping the same-end links', thicker='thicker links', opposite='the opposite-end output', combined='thicker links with the opposite-end output')
BOX = (0, 160, 2560, 1330)
if __name__ == '__main__':
    main()
