"""Header-only archive inventory and experimentally labelled CSV adapter.

The CLI never decodes experimental or author-prediction rows. The normalization
function is tested only on synthetic fixtures in this intake stage. No model fit.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
DOI = '10.5281/zenodo.19052626'
ARCHIVE = 'molicel_p45b_data.zip'
EXPERIMENTAL = ['t_s', 'I_exp_A', 'V_exp_V', 'T_exp_degC']
AUTHOR_OUTPUTS = ['I_sim_A', 'V_sim_V', 'SOC_sim', 'E_OCV_V', 'T_sim_degC', 'Q_sim_W']
PARAMETERS = ['SOC','Q_Ah','T_degC','E_OCV_ch_V','E_OCV_dch_V','R_R0_Ohm',
              'R_R1_Ohm','C_C1_F','R_R2_Ohm','C_C2_F','gamma','dUdT']
# Published checksums, verified against the public Zenodo API and record.
RELEASE = {
    ARCHIVE: ('0bd40f92dfabcea679900696cc2c0077', 'experimental and author-simulation archive'),
    'Molicel P45B Data Release Data Format Documentation.pdf': ('addcc323b21e48e147b3833a2a0f7239', 'format documentation; two pages inspected'),
    'Molicel P45B ECM Validation Matrix.xlsx': ('3acb090dbe48829935f0db184b96328c', 'protected author validation outcomes; binary hash only'),
    'Molicel_INR-21700-P45B_ECM.csv': ('2b670bf683b99e59124f4b2454f17a75', 'base fitted parameter table; header only'),
    'Molicel_INR-21700-P45B_ECM-charge.csv': ('fe6583f5d019f26de3933b46824e5cf2', 'charge-optimized fitted parameter table; header only'),
    'readme_Molicel_P45B_dataset_AE.txt': ('fe0d319f7ec39825fca2006db8997654', 'release documentation; inspected'),
}
NAME = re.compile(r'MOLICEL_P45B_(010|025|040|060)degC_(1C_Ch|1C_Dch|3C_Ch|3C_Dch|10C_Dch|Co30_Ch|Co30_Dch|GITT_Ch|GITT_Dch|WLTP|eVTOL)(-charge)?\.csv')
DEV_PROTOCOLS = {'Co30_Ch','Co30_Dch','GITT_Ch','GITT_Dch','1C_Ch','1C_Dch'}


def hashes(path):
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            sha.update(block);md5.update(block)
    return dict(bytes=Path(path).stat().st_size,sha256=sha.hexdigest(),md5=md5.hexdigest())


def header(stream):
    """One binary line only: the UTF-8 decoder never sees outcome bytes."""
    line=stream.readline(65537)
    if len(line)>65536 or not line.endswith(b'\n'):
        raise ValueError('Missing, oversized or unterminated header')
    fields=next(csv.reader([line.decode('utf-8-sig').rstrip('\r\n')],strict=True))
    if not fields or any(not x for x in fields) or len(set(fields))!=len(fields):
        raise ValueError('Empty or duplicate header field')
    return fields


def record_metadata(name):
    match=NAME.fullmatch(name)
    if not match:raise ValueError('Unrecognized or unsafe archive filename: '+name)
    temp, protocol, variant=match.groups()
    family=f'MOLICEL_P45B_{temp}degC_{protocol}'
    proposed='development_candidate' if int(temp)==25 and protocol in DEV_PROTOCOLS else (
        'assessment_candidate' if int(temp)==25 else 'reserved_temperature_transfer')
    return dict(name=name,family_id=family,nominal_temperature_degC=int(temp),protocol=protocol,
        author_parameter_variant='charge_optimized' if variant else ('none' if protocol.startswith(('Co30','GITT')) else 'base'),
        proposed_allocation=proposed,access='protected_unopened',
        family_identity_basis='filename and format documentation; equality of repeated experimental values not yet tested')


def archive_inventory(path, expected_md5=None):
    before=hashes(path)
    if expected_md5 is not None and before['md5']!=expected_md5:
        raise ValueError('Archive differs from the published release; no headers decoded')
    records=[]
    with ZipFile(path) as archive:
        infos=[i for i in archive.infolist() if not i.is_dir()]
        if len({i.filename for i in infos})!=len(infos):raise ValueError('Duplicate archive member names')
        for info in sorted(infos,key=lambda i:i.filename):
            record=record_metadata(info.filename)
            with archive.open(info) as stream:columns=header(stream)
            expected=EXPERIMENTAL if record['author_parameter_variant']=='none' else EXPERIMENTAL+AUTHOR_OUTPUTS
            if columns!=expected:raise ValueError('Unexpected channel schema: '+info.filename)
            sha=hashlib.sha256()
            with archive.open(info) as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):sha.update(block)
            record.update(bytes=info.file_size,sha256=sha.hexdigest(),columns=columns,
                          experimental_columns=EXPERIMENTAL,author_output_columns=columns[4:])
            records.append(record)
    if hashes(path)!=before:raise ValueError('Source archive changed during inspection')
    families=sorted({r['family_id'] for r in records})
    grouped=[]
    for family in families:
        members=[r for r in records if r['family_id']==family]
        if not any(r['author_parameter_variant']!='charge_optimized' for r in members):
            raise ValueError('Charge variant has no corresponding base experimental family')
        grouped.append(dict(family_id=family,members=[r['name'] for r in members],
            nominal_temperature_degC=members[0]['nominal_temperature_degC'],protocol=members[0]['protocol'],
            proposed_allocation=members[0]['proposed_allocation'],access='protected_unopened'))
    return dict(archive=before,records=records,families=grouped,file_count=len(records),family_count=len(grouped),
        files_with_author_simulations=sum(bool(r['author_output_columns']) for r in records),
        outcomes_decoded=0,author_simulation_rows_decoded=0,archive_extracted=False)


def inventory(source):
    source=Path(source)
    files={}
    for name,(md5,role) in RELEASE.items():
        result=hashes(source/name)
        if result['md5']!=md5:raise ValueError('Published file checksum mismatch: '+name)
        files[name]={**result,'role':role,'published_md5_matches':True}
    for name in ['Molicel_INR-21700-P45B_ECM.csv','Molicel_INR-21700-P45B_ECM-charge.csv']:
        with (source/name).open('rb') as stream:columns=header(stream)
        if columns!=PARAMETERS:raise ValueError('Unexpected parameter-table header: '+name)
        files[name]['columns']=columns
        files[name]['parameter_rows_decoded']=0
    archive=archive_inventory(source/ARCHIVE,RELEASE[ARCHIVE][0])
    if archive['file_count']!=51 or archive['family_count']!=43:
        raise ValueError('Unexpected release inventory')
    for name,before in files.items():
        if hashes(source/name)['sha256']!=before['sha256']:raise ValueError('Source changed: '+name)
    return dict(schema_version='voltforge.ae_p45b_intake/1',doi=DOI,version='v1',
        source_url='https://zenodo.org/records/19052626',source_location='repository root; original user-supplied files',
        license='CC BY 4.0; confirmed in public Zenodo API metadata',files=files,**archive,
        source_unchanged=True,validation_workbook_opened=False,models_changed=False,
        allocation_status='proposal only; every outcome remains protected until a frozen procedure is committed',
        limitations=['43 filename families are not proof of 43 independent cells or experiments.',
            'Author predictions and parameter tables do not provide independent measured SOC, OCV or branch currents.',
            'Separate single-cell evidence; no established identity mapping to the FreeTwinEV module cells.'])


def experimental_rows(data):
    """Normalize experimental fields only. Caller must enforce prospective allocation.

    No CLI route calls this on the real archive at this stage. Author simulation
    tokens are never converted, interpolated or used to supply missing inputs.
    """
    with io.BytesIO(data) as stream:columns=header(stream)
    if columns not in (EXPERIMENTAL,EXPERIMENTAL+AUTHOR_OUTPUTS):raise ValueError('Unsupported measurement schema')
    try:
        reader=csv.reader(io.StringIO(data.decode('utf-8-sig'),newline=''),strict=True)
        next(reader)
        rows=[]
        for raw in reader:
            if len(raw)!=len(columns):raise ValueError(f'CSV line {reader.line_num}: wrong field count')
            try:time,current,voltage,temp=map(float,raw[:4])
            except ValueError:raise ValueError(f'CSV line {reader.line_num}: missing or invalid experimental reading') from None
            if not all(math.isfinite(v) for v in (time,current,voltage,temp)):
                raise ValueError(f'CSV line {reader.line_num}: nonfinite experimental reading')
            if rows and time<=rows[-1]['time_s']:raise ValueError('Timestamps must strictly increase; no sorting performed')
            rows.append(dict(source_line=reader.line_num,raw_time=raw[0],time_s=time,
                source_current_A=current,current_discharge_positive_A=-current,voltage_V=voltage,
                controlled_temperature_degC=temp))
        if not rows:raise ValueError('No experimental rows')
        return dict(rows=rows,units=dict(time_s='s',source_current_A='A',current_discharge_positive_A='A',
            voltage_V='V',controlled_temperature_degC='degC'),
            transformations=['current_discharge_positive_A = -I_exp_A; source current also retained'],
            excluded_author_fields=columns[4:],source_sha256=hashlib.sha256(data).hexdigest(),
            initial_soc=None,initial_polarization=None,thermal_model=False,
            sampling_assumption='Measured samples only; integration convention must be declared by the modelling procedure')
    except (UnicodeDecodeError,csv.Error) as exc:raise ValueError('Invalid CSV encoding or structure') from exc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    dest=args.out.resolve()
    if dest.exists():raise SystemExit('Choose a new output path; previous inventories remain unchanged.')
    if not any(dest.is_relative_to(ROOT/name) for name in ('reports','tmp','workspace')):
        raise SystemExit('Write inventories under reports/, tmp/ or workspace/, outside original downloads.')
    result=inventory(args.source)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('x',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    print(f"Verified six published files; {result['file_count']} CSVs in {result['family_count']} filename families; zero outcome rows decoded.")


if __name__=='__main__':main()
