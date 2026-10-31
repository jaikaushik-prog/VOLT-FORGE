"""Download this search's fixed public metadata/document list, never measurement files."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    'kokam_metadata.json': 'https://zenodo.org/api/records/13903526',
    'oregan_metadata.json': 'https://zenodo.org/api/records/5171874',
    'chen_metadata.json': 'https://zenodo.org/api/records/4032560',
    'thenaisie_landing.html': 'https://data.mendeley.com/datasets/98thdkgp8z/1',
    'nist_description.txt': 'https://data.nist.gov/od/ds/mds2-4027/Data%20Descriptions.txt',
    'failure_databank.html': 'https://nrel.sitefinity.cloud/transportation/battery-failure',
    'oregan_methodology.pdf': 'https://wrap.warwick.ac.uk/id/eprint/196287/2/WRAP-Thermal-electrochemical-parameters-high-energy-22.pdf',
    'thenaisie_files.json': 'https://data.mendeley.com/public-api/datasets/98thdkgp8z/files?folder_id=root&version=1',
    'thenaisie_crossref.json': 'https://api.crossref.org/works/10.1016/j.powera.2022.100097',
    'oregan_preprint.pdf': 'https://chemrxiv.org/engage/api-gateway/chemrxiv/assets/orp/resource/item/61e2fd304a603d7d99314784/original/thermal-electrochemical-parameters-of-a-high-energy-lithium-ion-cylindrical-battery.pdf',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--only', nargs='+', choices=tuple(SOURCES), help='Subset of the fixed documentation list')
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() or not out.is_relative_to(ROOT / 'data/raw/thermal_public_evidence'):
        raise ValueError('Choose a fresh ignored thermal_public_evidence subdirectory')
    out.mkdir(parents=True)
    def fetch(item):
        name, url = item
        record = dict(name=name, url=url, started_utc=datetime.now(timezone.utc).isoformat(),
                      access='metadata_or_published_document_only')
        try:
            request = urllib.request.Request(url, headers={'User-Agent':'VOLT-FORGE public research metadata audit'})
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read(5_000_001)
                if len(body)>5_000_000:
                    raise ValueError('Documentation size exceeds declared 5 MB limit')
                record.update(final_url=response.url, content_type=response.headers.get('Content-Type'))
            (out/name).write_bytes(body)
            record.update(status='downloaded', bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                          local_path=(out/name).relative_to(ROOT).as_posix())
        except Exception as exc:
            record.update(status='failed', error_type=type(exc).__name__, error=str(exc))
        return record
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(fetch, ((k,SOURCES[k]) for k in (args.only or SOURCES))))
    receipt = dict(schema='voltforge.thermal_public_metadata_download/1',
                   measurement_files_downloaded=0, sources=records)
    (out/'downloads.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([{'name':r['name'],'status':r['status'],'bytes':r.get('bytes'),
                       'error':r.get('error')} for r in records],indent=2))


if __name__ == '__main__':
    main()
