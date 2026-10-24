"""Read-only FreeTwinEV development-record adapter; no model or electrical inference."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
ALLOCATION = 'configs/freetwinev_viewer_v1.json'
ALLOCATION_SHA256 = '4b94d7d76ea3a934a0ff975a9e2486fc8101767b43878448a0954493ba2d4f01'
COLUMNS = ['timesamp', 'current', 'voltage', 'SOC', 'liquid_flow',
           'temp_ambient', 'temp_inlet', 'temp_outlet'] + [f'temp_TH{i}' for i in range(1, 11)] + [
           f'temp_cell-{cell}_TH{sensor}' for cell, sensors in [(1, range(20,23)), (2, range(17,20)),
           (3, range(14,17)), (4, range(11,14))] for sensor in sensors]
UNITS = ['s', 'A', 'V', '%', 'L/min'] + ['K'] * 25
LIMITATIONS = [
    'Development measurement, not a model prediction or fresh independent assessment.',
    'Module current only: branch sharing and current-conservation residual are not assessable.',
    'Module voltage only: individual cell voltage and sense-point equivalence are not established.',
    'Calibration_Table referenced by Protocol!A19 is absent; conversion and calibration uncertainty remain unresolved.',
    'Preparation compliance, source SOC calculation and inter-channel timing accuracy are unverified.',
    'Measured temperatures are available; thermal prediction is unavailable.',
    'No application voltage requirement is configured; design decisions have insufficient evidence.',
]


class MeasurementError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bounded_integer(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise MeasurementError('invalid_request', f'{name} must be an integer from {low} to {high}.')
    return value


def parse_csv(data):
    """Exact known schema + explicit units row. No guessed units, row sorting or repair."""
    try:
        reader = csv.reader(io.StringIO(data.decode('utf-8-sig'), newline=''), strict=True)
        if next(reader, None) != COLUMNS or next(reader, None) != UNITS:
            raise MeasurementError('invalid_measurement', 'Expected FreeTwinEV columns and explicit source units on CSV lines 1 and 2.')
        rows = []
        for raw in reader:
            line = reader.line_num
            if len(raw) != len(COLUMNS):
                raise MeasurementError('invalid_measurement', f'CSV line {line}: expected {len(COLUMNS)} fields.')
            values = {}
            for index, (name, token) in enumerate(zip(COLUMNS, raw)):
                if not token.strip() and index >= 3:
                    values[name] = None
                else:
                    try:
                        number = float(token)
                    except ValueError:
                        raise MeasurementError('invalid_measurement', f'CSV line {line}, {name}: expected numeric source value.') from None
                    if not math.isfinite(number):
                        raise MeasurementError('invalid_measurement', f'CSV line {line}, {name}: nonfinite reading.')
                    values[name] = number
            if rows and values['timesamp'] <= rows[-1]['values']['timesamp']:
                raise MeasurementError('invalid_measurement', f'CSV line {line}: timestamps must strictly increase; no reordering performed.')
            origin = rows[0]['values']['timesamp'] if rows else values['timesamp']
            rows.append(dict(source_line=line, raw_timestamp=raw[0], elapsed_s=values['timesamp']-origin, values=values))
        if len(rows) < 2:
            raise MeasurementError('invalid_measurement', 'At least two samples are required.')
        return rows
    except (UnicodeDecodeError, csv.Error) as exc:
        raise MeasurementError('invalid_measurement', f'CSV decoding failed: {exc}') from None


def summarize(rows):
    intervals = [b['elapsed_s']-a['elapsed_s'] for a,b in zip(rows,rows[1:])]
    median = statistics.median(intervals)
    ranges, missing = {}, {}
    for name in COLUMNS:
        values = [r['values'][name] for r in rows if r['values'][name] is not None]
        ranges[name] = dict(min=min(values), max=max(values)) if values else dict(min=None, max=None)
        missing[name] = len(rows)-len(values)
    return dict(sample_count=len(rows), first_source_line=rows[0]['source_line'], last_source_line=rows[-1]['source_line'],
                duration_s=rows[-1]['elapsed_s'], ranges=ranges, missing_readings=missing,
                sampling=dict(min_interval_s=min(intervals), median_interval_s=median, max_interval_s=max(intervals),
                    gap_rule='interval > 2 * median; diagnostic only, not a missing-sample reconstruction',
                    gaps=[dict(before_line=b['source_line'], interval_s=dt) for b,dt in zip(rows[1:],intervals) if dt>2*median]),
                requirement_status='requirement not configured', validation_status='awaiting suitable measurements',
                current_conservation_status='not assessable: individual branch currents absent')


def overview(rows, name, bins, gap_limit):
    """Per chronological bin retain first/last/min/max in each continuous valid segment.

    Never connect across a missing value or long timestamp gap. The point count
    can exceed 4*bins if many gaps occur; it is always bounded by source rows.
    """
    width = max(1, math.ceil(len(rows)/bins))
    groups, segment, previous = {}, 0, None
    for index, row in enumerate(rows):
        value = row['values'][name]
        if value is None:
            segment += 1
            previous = None
            continue
        if previous is not None and row['elapsed_s']-previous > gap_limit:
            segment += 1
        previous = row['elapsed_s']
        groups.setdefault((segment, index//width), []).append([row['elapsed_s'], value, row['source_line'], segment])
    points = []
    for group in groups.values():
        chosen = {0, len(group)-1, min(range(len(group)), key=lambda i:group[i][1]), max(range(len(group)), key=lambda i:group[i][1])}
        points.extend(group[i] for i in sorted(chosen))
    return points


class MeasurementStore:
    def __init__(self, root=ROOT, allocation_sha256=ALLOCATION_SHA256):
        self.root = Path(root).resolve()
        allocation_bytes = (self.root/ALLOCATION).read_bytes()
        if digest(allocation_bytes) != allocation_sha256:
            raise MeasurementError('integrity_error', 'Predeclared allocation changed; review and version the access procedure.')
        self.allocation_hash = allocation_sha256
        self.allocation = json.loads(allocation_bytes)
        inventory_bytes = (self.root/self.allocation['inventory']).read_bytes()
        if digest(inventory_bytes) != self.allocation['inventory_sha256'] or digest((self.root/self.allocation['plan']).read_bytes()) != self.allocation['plan_sha256']:
            raise MeasurementError('integrity_error', 'Allocation inventory or plan changed.')
        self.inventory = json.loads(inventory_bytes)
        self.source = self.root/self.inventory['source_folder']

    def catalogue(self):
        return dict(schema_version='voltforge.measurement_viewer/1', dataset='FreeTwinEV P45B 1s4p',
            doi=self.allocation['dataset_doi'], source_url='https://zenodo.org/records/18405243',
            allocation_sha256=self.allocation_hash, records=[dict(id=r['id'], access=r['access'], reason=r['reason']) for r in self.allocation['records']],
            limitations=LIMITATIONS, predictions_available=False)

    def original(self, record_id):
        # Authorization precedes ANY source path lookup/read. Never parse protected outcomes.
        record = next((r for r in self.allocation['records'] if r['id']==record_id), None)
        if record is None:
            raise MeasurementError('not_found', 'Unknown measurement ID.')
        if record['access'] != 'development':
            raise MeasurementError('protected_record', 'Complete record remains unopened; a new evidence allocation is required.')
        path = (self.source/record['csv']).resolve()
        if not path.is_relative_to(self.source.resolve()):
            raise MeasurementError('integrity_error', 'Source path escapes dataset directory.')
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            raise MeasurementError('source_missing', 'Download the original Zenodo v1 archive and extract 1s4p Battery Module Measurement into the repository root.') from None
        if digest(data) != record['sha256']:
            raise MeasurementError('integrity_error', 'Source hash differs from the declared original; no data were decoded.')
        return record, data

    def read(self, record_id='ID01', view='overview', offset=0, limit=250, bins=250):
        if view not in ('overview', 'rows', 'summary'):
            raise MeasurementError('invalid_request', 'view must be overview, rows or summary.')
        bounded_integer(offset, 'offset', 0, 10000000)
        bounded_integer(limit, 'limit', 1, 1000)
        bounded_integer(bins, 'bins', 10, 1000)
        record, data = self.original(record_id)
        rows = parse_csv(data)
        summary = summarize(rows)
        result = dict(schema_version='voltforge.measurement_viewer/1', record_id=record_id, classification='measured development data',
            cell_type='Molicel INR21700-P45B', topology='1s4p; detailed electrical connection mapping unverified',
            units=dict(zip(COLUMNS,UNITS)), unit_source='CSV line 2', current_polarity='negative discharge; positive charge (Measurement_Protocol.xlsx Protocol!C13:C14)',
            time_basis='source timesamp in seconds; elapsed_s = timesamp minus first timesamp; no alignment correction',
            provenance=dict(source_file=(Path(self.inventory['source_folder'])/record['csv']).as_posix(), source_sha256=record['sha256'],
                dataset_doi=self.allocation['dataset_doi'], allocation=ALLOCATION, allocation_sha256=self.allocation_hash,
                inventory_sha256=self.allocation['inventory_sha256'], parser_sha256=digest(Path(__file__).read_bytes()),
                source_access='ID01 CSV only; other 13 records and all measurement XLSX outcomes unopened',
                attribution='Plzak, Berta, Urge and Bata (2026), FreeTwinEV / STU Bratislava. DOI 10.5281/zenodo.18405243. CC BY 4.0.'),
            limitations=LIMITATIONS, summary=summary, predictions_available=False)
        if view == 'rows':
            result.update(rows=rows[offset:offset+limit], offset=offset,
                next_offset=offset+limit if offset+limit<len(rows) else None)
        elif view == 'overview':
            result.update(overview=dict(method='Per channel, first/last/min/max per sample bin and valid segment; no averaging or interpolation. Use row inspector for exact samples.',
                bins=bins, point_fields=['elapsed_s','value','source_line','segment'],
                channels={name:overview(rows,name,bins,2*summary['sampling']['median_interval_s']) for name in COLUMNS[1:]}))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['catalogue', 'summary', 'rows', 'overview'])
    parser.add_argument('--record', default='ID01')
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--limit', type=int, default=250)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    try:
        store = MeasurementStore()
        result = store.catalogue() if args.command=='catalogue' else store.read(args.record,args.command,args.offset,args.limit)
        text = json.dumps(result,indent=2,allow_nan=False)+'\n'
        if args.out:
            dest = args.out.resolve()
            # Keep CLI exports out of raw data, sealed reports and implementation.
            if not any(dest.is_relative_to(ROOT/name) for name in ('tmp','workspace')):
                raise MeasurementError('invalid_request', 'CLI exports must use a new file under tmp/ or workspace/.')
            dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('x',encoding='utf-8',newline='\n') as stream:stream.write(text)
            print(dest)
        else:
            print(text)
    except (MeasurementError,FileExistsError) as exc:
        raise SystemExit(str(exc)) from None


if __name__ == '__main__':
    main()
