"""Build the one-slide pitch on the official Teliport template, from one data file."""
from copy import deepcopy
from pathlib import Path
import argparse
import json
import sys

from PIL import Image, ImageFont
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Pt

# Sampled from the template: Teliport 00A0E0, Tata Elxsi 3880C0. NAVY is a darker
# shade of that blue so white labels stay readable. Orange marks diagnosis only.
BLUE, DEEP, NAVY, TINT, INK, MUTED, LINE = '00A0E0', '3880C0', '1B5E96', 'EAF4FB', '231F20', '56616E', 'C9D8E4'
ORANGE, WHITE = 'D9480F', 'FFFFFF'
BIG, BODY, NOTE = 23, 10, 7.5
rgb = RGBColor.from_string
FONT_DIR = Path('/opt/homebrew/share/fonts')
REGULAR_FONT, BOLD_FONT = '', ''


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
            r.font.color.rgb = rgb(NAVY if '#' in style and color != WHITE else ORANGE if 'o' in style else color)
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


def width_of(words, size, bold=False):
    """Text width in points, so a rule can match its text exactly."""
    return ImageFont.truetype(BOLD_FONT if bold else REGULAR_FONT, 100).getlength(words)*size/100


def rule(slide, x, y, w, color=BLUE, weight=1):
    line = slide.shapes.add_connector(1, Pt(x), Pt(y), Pt(x+w), Pt(y)); line.line.color.rgb = rgb(color); line.line.width = Pt(weight)
    return line


def heading(slide, x, y, w, label, color=INK, line=BLUE):
    text(slide, x, y, w, 13, label, size=BODY+1, bold=True, color=color, name='Section: '+label)
    rule(slide, x, y+14, min(w, width_of(label, BODY+1, True)), line)


def cell_set(cell, value, size=BODY, bold=False, color=INK, fill=None, align=PP_ALIGN.CENTER):
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
    global REGULAR_FONT, BOLD_FONT
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--canvas', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--font', required=True, help='Regular metric-compatible Calibri font, for measuring rules')
    parser.add_argument('--font-bold', required=True)
    args = parser.parse_args()
    REGULAR_FONT, BOLD_FONT = args.font, args.font_bold
    d = json.loads(args.data.read_text()); prs = Presentation(args.template)
    best, four, save = d['best'], d['four'], d['saving']; rec = d['study']['recommended']; n = best['count']
    cover, s = prs.slides[0], prs.slides[1]
    for shape in cover.shapes:
        if shape.has_text_frame and 'Case Study No' in shape.text_frame.text:
            shape.text_frame.paragraphs[0].runs[0].text = 'Case Study 2'
            for extra in shape.text_frame.paragraphs[0].runs[1:]: extra.text = ''
    for shape in list(s.placeholders):
        if shape.placeholder_format.idx != 0: shape._element.getparent().remove(shape._element)

    # Claim as the title, with a rule exactly as wide as the qualifier.
    title = s.shapes.title; title.left, title.top, title.width, title.height = Pt(190), Pt(5), Pt(692), Pt(28)
    frame = title.text_frame; frame.word_wrap = True; frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0; frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = frame.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
    for content, accent in (('A Raspberry Pi 5 backup passes on ', False), (f'{n} cells, not 4', True)):
        r = p.add_run(); r.text = content; r.font.size = Pt(BIG); r.font.bold = True; r.font.name = 'Calibri'; r.font.color.rgb = rgb(BLUE if accent else INK)
    qualifier = 'VOLT-FORGE lets students and engineers test a battery design before buying parts'
    text(s, 190, 34, 692, 13, qualifier, size=BODY+1, color=MUTED, name='Qualifier')
    rule(s, 190, 49, width_of(qualifier, BODY+1), BLUE, 1.25)

    # The story: solid nodes are labels, outlined cards are detail.
    left, total, gap = 14, 932, 8
    node_w = (total-4*gap)/5; d_ = 44; node_y = 56; card_y = node_y+d_+7; card_h = 50
    stages = [('Define', [('Keep a Pi 5 gateway alive through a power cut: ', ''), ('10 minutes', 'b'), (' at ', ''), ('25 W', 'b')]),
              ('Build', [('Wire real cells', 'b'), (' on a canvas, with the load shown on the design', '')]),
              ('Test', [('Circuit and heat solved ', ''), ('in seconds', 'b'), (', with cell limits enforced', '')]),
              ('Improve', [('Find the smallest design', 'b'), (' rebuilds and tests 1 to 4 cells', '')]),
              ('Decide', [('Compare ', ''), ('cost, mass and margin', 'b'), (', then stress the winner', '')])]
    line = rule(s, left+node_w/2, node_y+d_/2, 4*(node_w+gap), DEEP, 1.5); line.name = 'Chain'
    for i, (label, runs) in enumerate(stages):
        x = left+i*(node_w+gap); cx = x+node_w/2
        stub = s.shapes.add_connector(1, Pt(cx), Pt(node_y+d_), Pt(cx), Pt(card_y)); stub.line.color.rgb = rgb(DEEP); stub.line.width = Pt(1.5)
        c = s.shapes.add_shape(MSO_SHAPE.OVAL, Pt(cx-d_/2), Pt(node_y), Pt(d_), Pt(d_)); c.fill.solid(); c.fill.fore_color.rgb = rgb(NAVY); c.line.fill.background(); c.shadow.inherit = False; c.name = 'Node: '+label
        text(s, cx-d_/2-8, node_y, d_+16, d_, label, size=BODY, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        box(s, x, card_y, node_w, card_h, line=NAVY, radius=.1, name='Card: '+label)
        text(s, x+7, card_y, node_w-14, card_h, [runs], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

    # Hero row: the real product beside the result.
    row2 = card_y+card_h+9; panel = 340; rx = left+panel+14; rw = total-panel-14
    heading(s, left, row2, panel, f"The starting design: {d['board']['name'].split(' UPS')[0]}, four 21700 slots")
    pic_h = panel*(BOX[3]-BOX[1])/(BOX[2]-BOX[0])
    picture = s.shapes.add_picture(str(args.canvas), Pt(left), Pt(row2+17), Pt(panel), Pt(pic_h)); picture.name = 'Product screenshot'
    chips = [('25 W', 'supply · sourced'), ('90%', 'converter · assumed'), ('8.42 A', '· calculated'), ('10 min', '· assumed'), ('3.3 V', 'floor · assumed'), ('23 °C', 'room · assumed')]
    chip_w = panel/3
    for i, (value, note) in enumerate(chips):
        x = left+(i % 3)*chip_w; y = row2+18+pic_h+4+(i//3)*13
        text(s, x, y, chip_w, 12, [[(value+' ', 'b'), (note, '')]], name='Requirement: '+value)

    heading(s, rx, row2, rw, 'What the tool found, with same-end outputs')
    stat_w = rw/4
    stats = [(f'{n} cells', 'smallest qualifying, from 4'), (inr(save['cost_inr']), f"less on cells, {inr(save['cost_from'])} to {inr(save['cost_to'])}"),
             (f"{save['mass_g']:.0f} g", f"less cell mass, {save['mass_from']:.0f} to {save['mass_to']:.0f} g"), (f"{best['required_passed']} of {best['required_cases']}", 'required Pi cases passed')]
    for i, (big, small) in enumerate(stats):
        x = rx+i*stat_w
        text(s, x, row2+17, stat_w-6, 28, big, size=BIG, color=NAVY, bold=True, name='Stat: '+big)
        text(s, x, row2+45, stat_w-4, 12, small, color=MUTED)
    rows = [['Cells', 'Verdict', 'Lowest V', 'Peak cell A', 'Warmest', 'Worst-case A', 'Worst-case °C', 'Cell cost', 'Cell mass']]
    for r in d['table']:
        refused = r['outcome'] == 'refused'
        rows.append([r['cells'], ('Refused', ORANGE) if refused else ('Qualifies', NAVY) if r['qualifies'] else ('Fails', ORANGE)]+(['—']*5 if refused else [f"{r['voltage']:.2f}", f"{r['current']:.2f}", f"{r['temperature']:.1f}", f"{r['worst_current']:.2f}", f"{r['worst_temperature']:.1f}"])+[inr(r['cost_inr']), f"{r['mass_g']:.0f} g"])
    table(s, rx, row2+61, rw, 16.5, rows, [.7, 1.2, 1, 1.2, 1, 1.3, 1.4, 1.1, 1.1], highlight=n, first_left=False, name='Trade-offs')

    # Three supports.
    row3 = row2+61+16.5*5+12; third = (total-2*14)/3; xs = [left, left+third+14, left+2*(third+14)]
    heading(s, xs[0], row3, third, 'How far to trust it')
    chart = CategoryChartData(); chart.categories = [p_['name'] for p_ in reversed(d['proof'])]
    for label, key in (('Simulated, low cooling', 'low'), ('Simulated, default', 'default'), ('Measured', 'measured')):
        chart.add_series(label, [round(p_[key], 1) for p_ in reversed(d['proof'])])
    frame = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Pt(xs[0]-3), Pt(row3+17), Pt(third*.62), Pt(106), chart); frame.name = 'Peak temperature rise in K, measured and simulated'
    c = frame.chart; c.has_title = False; c.has_legend = True; c.legend.position = XL_LEGEND_POSITION.BOTTOM; c.legend.include_in_layout = False; c.legend.font.size = Pt(NOTE-.5); c.font.size = Pt(NOTE); c.font.name = 'Calibri'
    c.value_axis.visible = False; c.value_axis.has_major_gridlines = False; c.value_axis.minimum_scale = 0; c.category_axis.format.line.color.rgb = rgb(LINE)
    plot = c.plots[0]; plot.gap_width = 40; plot.overlap = 0; plot.has_data_labels = True; plot.data_labels.font.size = Pt(NOTE); plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END; plot.data_labels.number_format = '0.0'; plot.data_labels.number_format_is_linked = False
    for series, color in zip(plot.series, ('A9D8F0', BLUE, INK)):
        series.format.fill.solid(); series.format.fill.fore_color.rgb = rgb(color)
    text(s, xs[0]+third*.62+2, row3+19, third*.38-2, 104, [[('Peak rise in K. ', 'b'), (f"All {d['proof_cases']} pre-set real-data cases ", ''), ('missed their bands', 'b'), (', so temperatures are a range.', '')],
         [(f"PyBaMM {d['pybamm']['passed']} of {d['pybamm']['cases']}", 'b'), (' on voltage and heat. Energy balance closes.', '')]], spacing=2, name='Verification')

    heading(s, xs[1], row3, third, 'Who it is for, and what it is worth')
    m = d['market']; steps = [('TAM', lakh(m['tam_students']), 'engineering students in India'), ('SAM', lakh(m['sam_students']), 'electrical, electronics, mechanical'), ('SOM', f"{m['som_colleges']:.0f} colleges", f"5% of {m['colleges']:,}, assumed")]
    for i, (tag, big, small) in enumerate(steps):
        y = row3+20+i*20; box(s, xs[1], y, 34, 17, fill=NAVY, radius=.3, name='Label: '+tag)
        text(s, xs[1], y, 34, 17, tag, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        text(s, xs[1]+40, y, 74, 17, big, bold=True, anchor=MSO_ANCHOR.MIDDLE); text(s, xs[1]+112, y, third-112, 17, small, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
    text(s, xs[1], row3+83, third, 40, [[('Free for students, paid for labs and teams. ', 'b'), (f"At an assumed {inr(m['licence_inr'])} a lab, that is ₹{m['som_inr']/1e5:.0f} lakh a year. ", ''), ('Works with any cell', 'b'), (' through custom imports.', '')]], name='Business')

    stress = best['samples'].get('stress', {}); pi_sample = best['samples'].get('pi', {}); pending = not stress.get('cases') or not pi_sample.get('cases')
    effect = d['study']['option_effects'].get(f"{n}_{rec['option']}_pi", {}); same_end = d['baseline_best']['worst_required']['highest_cell_current_A']
    box(s, xs[2], row3, third, 124, line=ORANGE, radius=.05, name='Honest Finding')
    text(s, xs[2]+6, row3+3, third-12, 120, [[('Honest finding', 'bo')],
         [('Less margin: ', 'b'), ('mixed-mismatch samples are still running.' if pending else f"{stress['cases']-stress['passed']} of {stress['cases']} mixed samples were refused at 12 A, while all {pi_sample['cases']} passed at the Pi load.", '')],
         [('No link option wins every case: ', 'b'), (f"moving the output to the far cell eased worst-case current from {same_end:.2f} to {best['worst_required']['highest_cell_current_A']:.2f} A, yet raised peak current in {effect.get('raised_peak_current', 0)} of {effect.get('pairs', 0)} pairs.", '')],
         [('Not proven: ', 'b'), ('the board on two cells, a real Pi draw or measured accuracy. The saving is cells only.', '')],
         [('Next, Round 2: ', 'b'), ('bench-test two cells on the board and run user trials.', '')]], spacing=1.5, name='Honest Finding text')

    # So-what and sources.
    so = row3+130
    box(s, left, so, total, 24, fill=NAVY, radius=.25, name='So what')
    text(s, left+8, so, total-16, 24, [[('Test a design in seconds before you buy parts: ', 'b'), ('the tool found a smaller battery that still does the job in simulation, at half the cell cost and mass.', '')]], size=BODY+1, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name='So what text')
    text(s, left, so+28, total, 30, [[('Simulation, not hardware. ', 'b'), (f"{d['study']['cases']:,} simulated cases on published LG M50T tables. {d['study']['claim']}. 8.42 A = 25 W ÷ (0.9 × 3.3 V), held constant. Prices checked 30 Oct 2026, excluding shipping and fabrication: Robu ₹1,206 incl. GST, out of stock; Geekworm US${d['board']['usd']:.0f}, one listing. "
         "Measured: Chen et al. 2020 (LG M50, zenodo.4032561) and Piombo et al. 2024 test 28 (M50T, 10.17632/zh58byr53c.2); low-cooling bars are post-hoc. Market: AISHE 2021-22; price and 5% reach are assumptions.", '')]], size=NOTE, color=MUTED, name='Sources')
    prs.save(args.out)


OPTION = dict(baseline='keeping the same-end links', thicker='thicker links', opposite='the opposite-end output', combined='thicker links with the opposite-end output')
BOX = (220, 520, 2480, 1190)
if __name__ == '__main__':
    main()
