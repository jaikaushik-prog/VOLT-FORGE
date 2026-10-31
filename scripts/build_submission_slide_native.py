"""Create an editable single-slide PPTX and matching PDF using installed PowerPoint.

Uses frozen evidence from slide_round1_review_v1; never reruns or changes models.
Requires Windows, PowerPoint, pywin32 and Pillow. No external AI or network calls.
Run with --out pointing to a fresh output directory; existing final files are refused.
"""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile
import xml.etree.ElementTree as ET

from PIL import Image
import pythoncom
import win32com.client

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'reports/slide_round1_review_v1/source_data.json'
W, H = 960, 540
NAME = 'VOLT-FORGE_Round1_Editable'
NAVY = '163449'
BLUE = '007BAC'
INK = '243E4F'
MUTED = '536B7B'
WHITE = 'FFFFFF'
PALE = 'EAF6FC'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def color(value):
    r, g, b = (int(value[i:i+2], 16) for i in (0, 2, 4))
    return r + (g << 8) + (b << 16)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    pptx = out / (NAME + '.pptx')
    pdf = out / (NAME + '.pdf')
    png = out / (NAME + '.png')
    if any(p.exists() for p in (pptx, pdf, png)):
        raise FileExistsError('Use a fresh output directory; final artifacts are preserved.')
    data = json.loads(DATA.read_text(encoding='utf-8'))
    for source in data['sources'].values():
        assert sha(ROOT / source['path']) == source['sha256'], source['path']
    rows = data['comparison']['rows']
    assert [r['cells'] for r in rows] == [4, 3, 2]
    assert data['evidence']['numerical']['passed'] == 15
    assert data['evidence']['measured']['total'] == 12
    assert data['evidence']['measured']['voltage_band_passed'] == 0
    assert data['evidence']['measured']['temperature_band_passed'] == 0

    pythoncom.CoInitialize()
    app = win32com.client.DispatchEx('PowerPoint.Application')
    pres = app.Presentations.Add(0)
    # Do not quit the application: PowerPoint may share its process with user decks.
    text_checks = []
    try:
        pres.PageSetup.SlideWidth = W
        pres.PageSetup.SlideHeight = H
        slide = pres.Slides.Add(1, 12)
        slide.FollowMasterBackground = 0
        slide.Background.Fill.Solid()
        slide.Background.Fill.ForeColor.RGB = color(WHITE)

        def text(name, value, x, y, w, h, size, bold=False, fill=INK, align=1, link=None):
            shape = slide.Shapes.AddTextbox(1, x, y, w, h)
            shape.Name = name
            frame = shape.TextFrame
            frame.MarginLeft = frame.MarginRight = frame.MarginTop = frame.MarginBottom = 0
            frame.WordWrap = -1
            frame.AutoSize = 0
            frame.VerticalAnchor = 1
            r = frame.TextRange
            r.Text = value
            r.Font.Name = 'Arial'
            r.Font.Size = size
            r.Font.Bold = -1 if bold else 0
            r.Font.Color.RGB = color(fill)
            r.ParagraphFormat.Alignment = align
            r.ParagraphFormat.SpaceBefore = 0
            r.ParagraphFormat.SpaceAfter = 0
            shape.TextFrame2.AutoSize = 0
            shape.Width = w
            shape.Height = h
            if link:
                r.ActionSettings(1).Hyperlink.Address = link
            text_checks.append((name, shape))
            return shape

        def image(name, rel, x, y, w):
            path = ROOT / rel
            iw, ih = Image.open(path).size
            shape = slide.Shapes.AddPicture(str(path), 0, -1, x, y, w, w*ih/iw)
            shape.Name = name
            shape.AlternativeText = name

        image('TELIPORT logo', 'reports/slide_v4/assets/logo_teliport.png', 27, 24, 109)
        image('Tata Elxsi logo', 'reports/slide_v4/assets/logo_tata.png', 879, 18, 53)
        text('Product', 'VOLT-FORGE', 159, 16, 555, 39, 30, True, NAVY)
        text('Product purpose', 'A visual workspace for battery trade-offs', 160, 55, 602, 27, 18, False, MUTED)
        text('Case', 'CASE STUDY 2', 749, 32, 114, 20, 12, True, BLUE)

        text('Finding', 'Two cells are a simulation candidate', 27, 89, 906, 32, 25, True, NAVY)
        text('Trade-off', "Smallest qualifying count tested (1-4 cells): half the baseline's cell cost and mass, with less electrical margin.",
             28, 124, 902, 22, 14.5)
        text('Conditions', 'Pi 5 backup | LG M50T | 25 W supply-rating scenario | 10 min | 23°C | 70% starting SOC',
             28, 154, 904, 19, 13.5)
        text('Assumptions', '90% converter assumed | 3.3 V study floor | 8.42 A constant-current proxy | actual Pi draw not measured',
             28, 175, 904, 18, 12.1, False, MUTED)

        text('Workflow heading', 'BUILD, TEST, UNDERSTAND', 28, 219, 355, 20, 12.5, True, BLUE)
        image('Original V4 editor screenshot; illustrative circuit, not the study table',
              'reports/slide_v4/assets/circuit.png', 28, 245, 360)
        text('Screenshot qualification', 'Original V4 editor; illustrative circuit, not the study table.',
             28, 355, 362, 16, 10.2, False, MUTED)
        text('User value', 'For students and lab instructors: edit a circuit, inspect\ncurrent, voltage and simulated temperature, then\ncompare alternatives and export the evidence.',
             28, 376, 365, 48, 12.7)

        text('Comparison heading', 'BASELINE + TWO ALTERNATIVES', 415, 219, 517, 20, 12.5, True, BLUE)
        ts = slide.Shapes.AddTable(4, 6, 415, 245, 517, 112)
        ts.Name = 'Editable frozen-study comparison'
        table = ts.Table
        widths = [100, 70, 82, 99, 65, 101]
        for i, width in enumerate(widths, 1): table.Columns(i).Width = width
        table.Rows(1).Height = 34
        for i in (2, 3, 4): table.Rows(i).Height = 27
        values = [['Parallel\ndesign', 'Required\npasses', 'Worst cell\ncurrent', 'Worst cell\ntemperature', 'Cell\nmass', 'Listed\ncell cost']]
        for row in rows:
            values.append([f"{row['cells']} cells",
                           f"{row['required_passed']}/{row['required_cases']}",
                           f"{row['worst_cell_current_A']:.2f} A",
                           f"{row['worst_cell_temperature_C']:.1f}°C",
                           f"{row['cell_mass_g']:.0f} g", f"₹{row['listed_cell_cost_inr']:,.0f}"])
        cell_checks = []
        for ri, row in enumerate(values, 1):
            for ci, value in enumerate(row, 1):
                cell = table.Cell(ri, ci)
                shape = cell.Shape
                shape.Fill.Solid()
                shape.Fill.ForeColor.RGB = color(NAVY if ri == 1 else PALE if ri == 4 else WHITE)
                for side in (1, 2, 3, 4):
                    cell.Borders(side).ForeColor.RGB = color('DCE6EC')
                    cell.Borders(side).Weight = 0.4
                f = shape.TextFrame
                f.MarginLeft = f.MarginRight = 7
                f.MarginTop = f.MarginBottom = 3
                f.VerticalAnchor = 3
                r = f.TextRange
                r.Text = value
                r.Font.Name = 'Arial'
                r.Font.Size = 10.6 if ri == 1 else 12.2 if ci == 1 else 14.3
                r.Font.Bold = -1 if ri in (1, 4) else 0
                r.Font.Color.RGB = color(WHITE if ri == 1 else INK)
                r.ParagraphFormat.SpaceAfter = 0
                r.ParagraphFormat.SpaceBefore = 0
                r.ParagraphFormat.Alignment = 1
                cell_checks.append((f'table r{ri}c{ci}',shape))
        scope = text('Table scope', 'Frozen V4: same-end outputs; mismatch, thermal and converter sensitivity cases.\nCounts vary by cell position. Temperatures simulated; cell-only cost and mass.',
             415, 367, 518, 35, 10.8, False, MUTED)

        # Flat evidence columns; no decorative cards or fabricated scientific visuals.
        text('Evidence heading', 'EVIDENCE', 28, 438, 285, 16, 11.7, True, BLUE)
        text('Evidence result', '15/15 numerical checks passed', 28, 458, 287, 21, 14.3, True, NAVY)
        text('Evidence limit', 'All 12 comparison cases missed voltage and\ntemperature bands. Measured accuracy is\nnot established.',
             28, 483, 287, 48, 12.0)
        text('Limits heading', 'LIMITS THAT MATTER', 337, 438, 285, 16, 11.7, True, BLUE)
        text('Limits result', 'Conditional, not build-ready', 337, 458, 287, 21, 14.3, True, NAVY)
        text('Limits body', 'No spare cell. Board current limits unverified.\nVirtual cutoffs modelled; physical protection\nhas not been demonstrated.',
             337, 483, 287, 48, 12.0)
        text('Buyer heading', 'USER + BUYER HYPOTHESIS', 647, 438, 285, 16, 11.7, True, BLUE)
        text('Buyer result', 'Start with teaching labs', 647, 458, 287, 21, 14.3, True, NAVY)
        text('Buyer body', 'Free student use; paid lab licences untested.\nNo observed user trials yet. Next user task:\ncomplete and explain a comparison.',
             647, 483, 287, 48, 12.0)

        # Compact top and middle slightly to leave a clear next-step/footer band.
        # All positions remain explicit in the final package and geometry receipt.
        for shape in slide.Shapes:
            if shape.Top >= 219: shape.Top -= 20
        for shape in slide.Shapes:
            if shape.Name in ('Evidence heading','Evidence result','Evidence limit','Limits heading',
                              'Limits result','Limits body','Buyer heading','Buyer result','Buyer body'):
                shape.Top -= 11
        scope.Top = ts.Top + ts.Height + 6
        text('Next action', 'NEXT  Measure load and converter behavior; bench-check with supervised cutoffs; observe student tasks.',
             28, 505, 904, 17, 11.6)
        text('Evidence link', 'Source + code: github.com/jaikaushik-prog/VOLT-FORGE', 28, 526, 540, 11, 8.8, False, BLUE,
             link='https://github.com/jaikaushik-prog/VOLT-FORGE/tree/v4')
        text('Version', 'Team StratWise | Frozen V4 study | Submission draft', 612, 526, 320, 11, 8.8, False, MUTED, 3)

        notes = (
            'Slide purpose: one-page submission draft; not submitted.\n'
            'Two cells are the smallest qualifying simulated count among the tested 1-4-cell parallel arrangements. '
            'No claim of a global optimum, measured improvement, hardware approval or total-system cost reduction.\n'
            'Table: frozen same-end-output baseline rows, not the opposite-output recommendation and not the new nominal examples. '
            'Worst values are across the declared required cases; counts differ with cell positions. '
            'Source software 97ca199f2fd21aac, pinned commit '+data['source_commit']+'.\n'
            '25 W is a supply-rating scenario, not measured Pi workload. 90% conversion and 3.3 V floor are study assumptions. '
            '8.42 A is a constant-current proxy, not a dynamic constant-power converter simulation.\n'
            '15/15 numerical checks use synthetic electrical/heat-generation cases; they do not validate temperature predictions. '
            'All 12 measured-comparison cases missed both bands; cases are not 12 independent module experiments. '
            'Current reconciliation and transfer to new assemblies remain uncertain.\n'
            'Screenshot: original V4 circuit image, not the revised UI and not the comparison-table topology.\n'
            'Latest implementation changes: d184a49; 515 Python and 71 JavaScript checks passed, 8 archive-dependent checks skipped. '
            'They establish software behavior, not experimental battery accuracy. No live browser/user trial claimed.\n'
            'Buyer/pricing proposal is a hypothesis. No real participant study is claimed. '
            'Next actions require suitable measurement access; no outreach performed.\n\nSources:\n'+
            '\n'.join('https://github.com/jaikaushik-prog/VOLT-FORGE/blob/'+data['source_commit']+'/'+s['path'] for s in data['sources'].values())
        )
        pres.BuiltInDocumentProperties('Title').Value = 'VOLT-FORGE | Round 1 submission draft'
        pres.BuiltInDocumentProperties('Author').Value = 'Team StratWise'
        slide.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange.Text = notes
        geometry=[]
        for name, shape in text_checks + cell_checks:
            tr=shape.TextFrame2.TextRange
            available=float(shape.Height)-float(shape.TextFrame.MarginTop)-float(shape.TextFrame.MarginBottom)
            geometry.append({'name':name,'text_height':float(tr.BoundHeight),'available_height':available,
                             'left':float(shape.Left),'top':float(shape.Top),'width':float(shape.Width),'height':float(shape.Height)})
        issues=[g for g in geometry if g['text_height']>g['available_height']+1]
        if issues: raise ValueError('Text fit issues: '+json.dumps(issues))
        pres.SaveAs(str(pptx), 24)
        pres.SaveAs(str(pdf), 32)
        slide.Export(str(png),'PNG',1920,1080)
    finally:
        pres.Close()
        pythoncom.CoUninitialize()
    with zipfile.ZipFile(pptx) as z:
        assert z.testzip() is None
        slide_xml=ET.fromstring(z.read('ppt/slides/slide1.xml'))
        ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
        assert len(slide_xml.findall('.//a:tbl',ns))==1
        actual_text='\n'.join(e.text or '' for e in slide_xml.findall('.//a:t',ns))
        for required in ('51/51','42/42','33/33','15/15','All 12','3.34 A','5.49 A','₹2,412'):
            assert required in actual_text,required
        assert 'ppt/slides/slide2.xml' not in z.namelist()
    receipt={'schema':'voltforge.submission-slide/1','authoring':'Native PowerPoint COM; local Artifact Tool runtime unavailable',
             'slide_count':1,'native_tables':1,'editable_text':True,'sources_sha256':sha(DATA),
             'source_commit':data['source_commit'],'implementation_commit':'d184a49f093636ea2b7e9a9fb1e1ad14f5f2b806',
             'output_hashes':{p.name:sha(p) for p in (pptx,pdf,png)},'text_fit':geometry,
             'visual_review':'Required separately; not asserted by generation',
             'preserved_source_checks':len(data['sources'])}
    (out/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    (out/'source_data.json').write_bytes(DATA.read_bytes())
    print(json.dumps({'outputs':[str(p) for p in (pptx,pdf,png)],'editable_table':True,'text_fit':'passed'}))


if __name__=='__main__': main()
