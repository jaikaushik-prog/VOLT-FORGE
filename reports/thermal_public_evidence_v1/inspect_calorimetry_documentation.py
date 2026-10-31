"""Extract only declared notebook source; never execute code or load measurement arrays."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / 'data/raw/thermal_public_evidence/calorimetry_docs_001/raw_data_with_example_Python_usage.zip'
EXPECTED = '5e4ff4ddbfa6e51263f08ea1b3722e0dd3e30d526f2cf7b82ab345f6e37f71c1'
MEMBER = 'example_code.ipynb'


def inspect(out):
    out = Path(out).resolve()
    if out.exists() or not out.is_relative_to(ROOT / 'data/raw/thermal_public_evidence'):
        raise ValueError('Choose a fresh ignored documentation output directory')
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('Source archive hash differs')
    with ZipFile(ARCHIVE) as archive:
        info = archive.getinfo(MEMBER)
        if info.file_size != 343779 or sum(i.filename == MEMBER for i in archive.infolist()) != 1:
            raise ValueError('Notebook identity differs')
        raw = archive.read(MEMBER)
    notebook = json.loads(raw)
    sources, skipped = [], 0
    for index, cell in enumerate(notebook['cells']):
        if cell['cell_type'] not in ('markdown', 'code', 'raw'):
            raise ValueError('Unexpected cell type')
        source = cell.get('source', [])
        source = ''.join(source) if isinstance(source, list) else source
        if not isinstance(source, str):
            raise ValueError('Unexpected source field')
        sources.append(f"CELL {index} ({cell['cell_type']})\n{source}\n")
        skipped += len(cell.get('outputs', []))
    text = '\n'.join(sources)
    out.mkdir(parents=True)
    target = out / 'example_source.txt'
    target.write_text(text, encoding='utf-8')
    receipt = dict(schema='voltforge.thermal_notebook_source_review/1', archive_sha256=EXPECTED,
        opened_members=[MEMBER], member_sha256=hashlib.sha256(raw).hexdigest(),
        code_executed=False, numerical_members_opened=0, saved_outputs_displayed=0,
        skipped_saved_outputs=skipped, cells=len(sources),
        source_path=target.relative_to(ROOT).as_posix(),
        source_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    print(json.dumps(inspect(parser.parse_args().out),indent=2))
