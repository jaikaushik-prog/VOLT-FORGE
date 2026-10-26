"""Metadata-only M50T intake. Never reads numerical ZIP members or fits a model."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'configs/thermal_m50t_allocation_v1.json'
DOCUMENT = 'M50/M50 Data ReadMe.txt'
PARTITIONS = ('development_candidate', 'unused_development_reserve', 'assessment_reserve')
ROLES = {'thermal_raw', 'thermal_processed', 'electrical_raw'}
NAME = re.compile(r'M50_(?P<soc>25|50|75)SOC(?:_(?P<temperature>10|20|30)deg)?'
                  r'_cell(?P<cell>[12])_test(?P<test>[0-9]+)(?:_(?P<suffix>[A-Za-z0-9]+))?\.(?P<ext>txt|mat)')


def digest(path, algorithm='sha256'):
    result = hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def checked_path(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT / 'data/raw/thermal_m50t'):
        raise ValueError('Source must remain inside the M50T raw-data folder')
    return path


def parse_member(name):
    path = PurePosixPath(name)
    match = NAME.fullmatch(path.name)
    if not match or path.parent.as_posix() not in ('M50', 'M50/Electrical'):
        raise ValueError('Unrecognized measurement member: ' + name)
    fields = match.groupdict()
    if path.parent.as_posix() == 'M50/Electrical':
        if fields['ext'] != 'txt' or fields['suffix'] not in ('CF8', 'CC3'):
            raise ValueError('Unsupported electrical representation: ' + name)
        role = 'electrical_raw'
    else:
        if fields['suffix'] is not None:
            raise ValueError('Unexpected thermal filename suffix: ' + name)
        role = 'thermal_raw' if fields['ext'] == 'txt' else 'thermal_processed'
    cell, test = int(fields['cell']), int(fields['test'])
    return dict(family_id=f'cell_{cell}_test_{test}', cell=cell, test=test, role=role,
                nominal_soc_percent=int(fields['soc']),
                nominal_temperature_degC=int(fields['temperature']) if fields['temperature'] else None,
                condition_source='literal filename; not a measured outcome')


def inspect_archive(path):
    """Read the central directory and one exact README. No extraction occurs."""
    members, families, seen = [], {}, set()
    with ZipFile(path) as archive:
        for info in archive.infolist():
            name = info.filename
            pure = PurePosixPath(name)
            if ('\\' in name or ':' in name or pure.is_absolute() or '..' in pure.parts
                    or name.casefold() in seen or info.flag_bits & 1
                    or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError('Unsafe, duplicate or encrypted ZIP member: ' + name)
            seen.add(name.casefold())
            row = dict(name=name, bytes=info.file_size, compressed_bytes=info.compress_size,
                       crc32=f'{info.CRC:08x}', directory=info.is_dir(), payload_opened=False)
            if info.is_dir():
                if name not in ('M50/', 'M50/Electrical/'):
                    raise ValueError('Unexpected archive directory: ' + name)
                row['kind'] = 'directory'
            elif name == DOCUMENT:
                if not 0 < info.file_size <= 16_384:
                    raise ValueError('Unexpected README size')
                row['kind'] = 'documentation'
            else:
                fields = parse_member(name)
                row.update(fields, kind='measurement')
                family = families.setdefault(fields['family_id'], dict(family_id=fields['family_id'],
                    cell=fields['cell'], test=fields['test'], members={}, metadata_flags=[]))
                if fields['role'] in family['members']:
                    raise ValueError('Duplicate representation in family ' + fields['family_id'])
                family['members'][fields['role']] = name
            members.append(row)
        for family in families.values():
            if set(family['members']) != ROLES:
                raise ValueError('Incomplete experiment family: ' + family['family_id'])
            rows = [r for r in members if r.get('family_id') == family['family_id']]
            socs = {r['nominal_soc_percent'] for r in rows}
            temperatures = {r['nominal_temperature_degC'] for r in rows if r['nominal_temperature_degC'] is not None}
            if len(socs) != 1 or len(temperatures) != 1:
                raise ValueError('Conflicting/unknown family conditions: ' + family['family_id'])
            family['nominal_soc_percent'] = next(iter(socs))
            family['nominal_temperature_degC'] = next(iter(temperatures))
            family['condition_source'] = 'nonmissing filename labels; not verified protocol or measurements'
            for row in rows:
                if row['nominal_temperature_degC'] is None:
                    family['metadata_flags'].append('Temperature absent in ' + row['name'] + '; member value remains null')
        # This is the only member-payload read in the entire implementation.
        document = archive.read(DOCUMENT)
    for row in members:
        if row['name'] == DOCUMENT:
            row['payload_opened'] = True
    return dict(members=members, families=sorted(families.values(), key=lambda f: (f['cell'], f['test'])),
                internal_document_sha256=hashlib.sha256(document).hexdigest(),
                document_text=document.decode('utf-8-sig'),
                measurement_payloads_opened=0, archive_extracted=False)


def assign_allocation(inventory, policy):
    if (policy.get('schema') != 'voltforge.thermal_m50t_allocation/1'
            or policy.get('assessment_opening_authorized') is not False
            or policy.get('fitting_authorized_by_this_procedure') is not False
            or policy.get('current_access') != 'directory_metadata_and_allowlisted_readme_only'
            or policy.get('internal_document') != DOCUMENT):
        raise ValueError('This tool only supports the sealed metadata-only allocation')
    assignments = {}
    for partition in PARTITIONS:
        entries = policy.get(partition)
        if not isinstance(entries, list) or any(not isinstance(v, str) for v in entries):
            raise ValueError('Allocation must list complete family IDs')
        for family_id in entries:
            if family_id in assignments:
                raise ValueError('Family appears in multiple allocation entries: ' + family_id)
            assignments[family_id] = partition
    if set(assignments) != {f['family_id'] for f in inventory['families']}:
        raise ValueError('Allocation must cover every family exactly once')
    result = []
    for family in inventory['families']:
        partition = assignments[family['family_id']]
        if (family['cell'] == 2) != (partition == 'assessment_reserve'):
            raise ValueError('The assessment specimen must remain separate from development')
        result.append(dict(family, allocation=partition, payload_access='unopened', fitting_permitted=False))
    if policy['development_candidate'] != ['cell_1_test_103']:
        raise ValueError('First development candidate must remain the declared nominal case')
    return result


def build(policy_path=POLICY):
    policy = json.loads(Path(policy_path).read_text(encoding='utf-8'))
    archive = checked_path(policy['archive_path'])
    readme = checked_path(policy['external_readme_path'])
    for path, expected in ((archive, policy['archive_sha256']), (readme, policy['external_readme_sha256'])):
        if digest(path) != expected:
            raise ValueError('Source SHA-256 mismatch: ' + path.name)
    if digest(archive, 'md5') != policy['archive_md5']:
        raise ValueError('Published archive MD5 mismatch')
    result = inspect_archive(archive)
    if result['internal_document_sha256'] != policy['internal_document_sha256']:
        raise ValueError('Internal README hash mismatch')
    result['families'] = assign_allocation(result, policy)
    result.update(schema='voltforge.thermal_m50t_intake/1', source_url='https://zenodo.org/records/6421061',
        archive_sha256=digest(archive), archive_bytes=archive.stat().st_size,
        allocation_sha256=digest(policy_path), counts=dict(
            measurement_members=sum(r['kind'] == 'measurement' for r in result['members']),
            experiment_families=len(result['families']),
            **{p:sum(f['allocation'] == p for f in result['families']) for p in PARTITIONS}),
        external_readme_sha256=digest(readme), raw_measurement_outcomes_used=0,
        model_fitted=False, experimental_module_validation='awaiting suitable measurements')
    # Column names are author documentation, not a verified measurement schema.
    result['document_text'] = result['document_text'].replace('\r\r\n', '\n').replace('\r\n', '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path, help='Compare a saved inventory to a fresh metadata-only reconstruction')
    parser.add_argument('--out', type=Path, help='Write a new inventory; never overwrite')
    args = parser.parse_args()
    if bool(args.verify) == bool(args.out):
        parser.error('Choose exactly one of --out or --verify')
    result = build()
    if args.verify:
        saved = json.loads(args.verify.read_text(encoding='utf-8'))
        if saved != result:
            raise ValueError('Inventory/allocation differs from saved receipt')
        print(json.dumps(dict(status='verified', **result['counts'], measurement_payloads_opened=0)))
    else:
        out = args.out.resolve()
        if not any(out.is_relative_to(ROOT / p) for p in ('tmp', 'reports/thermal_m50t_intake_v1')):
            raise ValueError('Choose an output under tmp or this intake report')
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
        print(json.dumps(dict(status='recorded', **result['counts'], measurement_payloads_opened=0)))


if __name__ == '__main__':
    main()
