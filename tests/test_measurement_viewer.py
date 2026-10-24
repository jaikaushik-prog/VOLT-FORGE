"""Synthetic fixtures only: access separation, honest source decoding and real HTTP."""
import csv
import io
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import measurement_viewer as mv
from test_editor_server import server, http, editor


def fixture_bytes(times=(10,15,20), mutate=None):
    data=[mv.COLUMNS.copy(),mv.UNITS.copy()]
    for t in times:
        data.append([str(t),'-20','4.1','100','1.5']+['298.15']*25)
    if mutate:mutate(data)
    stream=io.StringIO(newline='');csv.writer(stream).writerows(data)
    return stream.getvalue().encode()


@pytest.fixture
def store(tmp_path):
    source=tmp_path/'raw';source.mkdir()
    raw=fixture_bytes();(source/'ID01.csv').write_bytes(raw)
    inventory={'source_folder':'raw'}
    inv=json.dumps(inventory).encode();(tmp_path/'inventory.json').write_bytes(inv)
    (tmp_path/'plan.md').write_bytes(b'Synthetic access declaration')
    allocation=dict(inventory='inventory.json',inventory_sha256=mv.digest(inv),plan='plan.md',
        plan_sha256=mv.digest(b'Synthetic access declaration'),dataset_doi='synthetic fixture',
        records=[dict(id='ID01',csv='ID01.csv',sha256=mv.digest(raw),access='development',reason='synthetic'),
                 dict(id='ID02',csv='ID02.csv',sha256='unopened',access='protected',reason='synthetic holdout')])
    data=json.dumps(allocation).encode();path=tmp_path/mv.ALLOCATION;path.parent.mkdir();path.write_bytes(data)
    return mv.MeasurementStore(tmp_path,mv.digest(data))


def test_exact_source_values_units_polarity_and_lines():
    rows=mv.parse_csv(fixture_bytes())
    assert rows[0]['raw_timestamp']=='10' and rows[0]['elapsed_s']==0
    assert rows[-1]['source_line']==5 and rows[-1]['elapsed_s']==10
    assert rows[0]['values']['current']==-20
    assert rows[0]['values']['temp_cell-1_TH20']==298.15
    assert mv.summarize(rows)['sampling']['median_interval_s']==5


@pytest.mark.parametrize('change',[
    lambda d:d[0].__setitem__(0,'timestamp'),
    lambda d:d[1].__setitem__(5,'degC'),
    lambda d:d[2].__setitem__(0,'2026-01-01T00:00:00'),
    lambda d:d[2].__setitem__(1,''),
    lambda d:d[2].__setitem__(2,'NaN'),
    lambda d:d[2].__setitem__(8,'inf'),
    lambda d:d[3].__setitem__(0,'10'),
    lambda d:d[3].__setitem__(0,'9'),
    lambda d:d[2].pop(),
],ids=['unknown-column','wrong-unit','unsupported-calendar-time','missing-current','nan-voltage','infinite-optional','duplicate-time','backwards-time','ragged-row'])
def test_invalid_data_rejected_without_repair(change):
    with pytest.raises(mv.MeasurementError):mv.parse_csv(fixture_bytes(mutate=change))


def test_missing_and_sampling_gaps_remain_visible():
    rows=mv.parse_csv(fixture_bytes((0,1,2,20,21),lambda d:d[3].__setitem__(8,'')))
    summary=mv.summarize(rows)
    assert summary['missing_readings']['temp_TH1']==1
    assert summary['sampling']['gaps']==[dict(before_line=6,interval_s=18)]
    points=mv.overview(rows,'temp_TH1',10,2)
    assert len(points)==4 and [p[3] for p in points]==[0,1,2,2]
    assert rows[1]['values']['temp_TH1'] is None


def test_overview_retains_short_extrema_and_source_order():
    def change(d):
        d[12][1]='-123';d[22][1]='32'
    rows=mv.parse_csv(fixture_bytes(range(100),change))
    points=mv.overview(rows,'current',10,2)
    assert min(p[1] for p in points)==-123 and max(p[1] for p in points)==32
    assert [p[2] for p in points]==sorted(set(p[2] for p in points))
    assert points[0][2]==3 and points[-1][2]==102 and len(points)<=40


def test_protected_and_unknown_ids_reject_before_any_source_read(store,monkeypatch):
    def forbidden(*a,**k):pytest.fail('Protected record touched filesystem')
    monkeypatch.setattr(Path,'read_bytes',forbidden)
    assert len(store.catalogue()['records'])==2
    for id,code in [('ID02','protected_record'),('../ID01','not_found')]:
        with pytest.raises(mv.MeasurementError) as exc:store.read(id)
        assert exc.value.code==code


def test_hash_changed_rejects_before_decode(store,monkeypatch):
    (store.source/'ID01.csv').write_bytes(b'corrupt')
    monkeypatch.setattr(mv,'parse_csv',lambda *_:pytest.fail('Decoded unverified source'))
    with pytest.raises(mv.MeasurementError,match='hash differs'):store.read()


def test_allocation_and_plan_integrity(store):
    with pytest.raises(mv.MeasurementError,match='allocation changed'):mv.MeasurementStore(store.root,'bad')
    (store.root/'plan.md').write_bytes(b'changed')
    with pytest.raises(mv.MeasurementError,match='plan changed'):mv.MeasurementStore(store.root,store.allocation_hash)


def test_missing_source_catalogue_available(store):
    (store.source/'ID01.csv').unlink()
    assert store.catalogue()['predictions_available'] is False
    with pytest.raises(mv.MeasurementError) as exc:store.read()
    assert exc.value.code=='source_missing'


def test_original_download_cannot_be_used_as_editor_working_project():
    with pytest.raises(ValueError):
        editor.project_destination(editor.ROOT/'1s4p Battery Module Measurement'/'working_project')


def test_pagination_provenance_and_no_fabricated_branch_data(store):
    a=store.read(view='rows',offset=0,limit=2);b=store.read(view='rows',offset=a['next_offset'],limit=2)
    assert [r['source_line'] for r in a['rows']+b['rows']]==[3,4,5]
    assert b['next_offset'] is None
    assert a['provenance']['source_sha256']==mv.digest(fixture_bytes())
    assert not a['predictions_available'] and set(a['rows'][0]['values'])==set(mv.COLUMNS)
    assert a['units']['temp_TH1']=='K'
    assert a['summary']['requirement_status']=='requirement not configured'


@pytest.mark.parametrize('kwargs',[{'limit':0},{'offset':-1},{'bins':1001},{'limit':True},{'view':'predict'}])
def test_bad_requests_reject(store,kwargs):
    with pytest.raises(mv.MeasurementError):store.read(**kwargs)


def test_http_measurement_routes_and_protections(server,store,monkeypatch):
    monkeypatch.setattr(editor,'MeasurementStore',lambda:store)
    for path in ['/measurements','/measurements.js','/measurements.css']:
        status,body,headers=http(server,path);assert status==200
        assert "default-src 'self'" in headers['Content-Security-Policy']
    assert http(server,'/api/measurements')[1]['result']['records'][1]['access']=='protected'
    assert http(server,'/api/measurements/ID01?view=rows&offset=1&limit=1')[1]['result']['rows'][0]['source_line']==4
    status,data,headers=http(server,'/api/measurements/ID01/original')
    assert status==200 and data==fixture_bytes() and 'attachment' in headers['Content-Disposition']
    assert http(server,'/api/measurements/ID02')[0]==403
    assert http(server,'/api/measurements/ID02/original')[0]==403
    assert http(server,'/api/measurements/ID01?view=rows&view=overview')[0]==400
    assert http(server,'/api/measurements/ID01?offset=no')[0]==400
    assert http(server,'/api/measurements/ID01?path=ID02')[0]==400
    assert http(server,'/api/measurements/ID01?view=rows',headers={'Origin':'https://foreign.example'})[0]==403
    assert http(server,'/api/measurements/ID01',headers={'Host':'foreign.example'})[0]==403

