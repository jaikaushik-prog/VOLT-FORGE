"""Collect every slide number into one file, each traced to a V4 result or source."""
from pathlib import Path
import argparse
import json

ROOT = Path(__file__).resolve().parents[1]


def read(path): return json.loads((ROOT/path).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', default='reports/design_study_v2/run1')
    parser.add_argument('--out', type=Path, default=ROOT/'reports/slide_v4/data.json')
    args = parser.parse_args()
    summary = read(f'{args.run}/summary.json'); market = read('configs/market_sizing_v1.json'); receipt = read('reports/v4_release/replay_receipt.json')
    pybamm = read('reports/numerical_reference_v2/run1/verification.json'); diagnostic = read('reports/measured_comparison_v1/post_hoc_diagnostic.json')
    prices = read('configs/parts_prices_v1.json'); gate = read('reports/model_catalogue_v2/gate.json')
    measured = read('reports/measured_comparison_v1/final/result.json')
    rec = summary['recommended'] or dict(count=None, option='baseline')
    designs = {(d['count'], d['option']): d for d in summary['designs']}
    table = []
    for count in (1, 2, 3, 4):
        d = designs.get((count, 'baseline'))
        if not d: continue
        n = d['nominal'] or {}
        table.append(dict(cells=count, qualifies=d['qualifies'], outcome=n.get('outcome'), voltage=n.get('min_voltage_V'), current=n.get('peak_cell_current_A'), temperature=n.get('peak_temperature_C'),
                          worst_voltage=d['worst_required'].get('lowest_voltage_V'), worst_current=d['worst_required'].get('highest_cell_current_A'), worst_temperature=d['worst_required'].get('highest_temperature_C'),
                          required=f"{d['required_passed']}/{d['required_cases']}", cost_inr=d['cell_cost_inr'], mass_g=d['cell_mass_g']))
    best = designs.get((rec['count'], rec['option'])); four = designs.get((4, 'baseline'))
    def group(name, label): return [c for c in diagnostic['cases'] if c['case'].startswith(name) and c['cooling'] == label]
    def mean(rows, key): return sum(r[key] for r in rows)/len(rows)
    proof = []
    for title, name in (('Single cell, 5 A', 'warwick cell0'), ('Four-cell rig, 14.6 A', 'test28 cycler')):
        rows = [c for c in diagnostic['cases'] if c['case'].startswith(name) and '2.5A' not in c['case']]
        pick = lambda label: [c for c in rows if c['cooling'] == label]
        proof.append(dict(name=title, measured=mean(pick('deployed'), 'peak_rise_measured_K'), low=mean(pick('declared_low'), 'peak_rise_simulated_K'),
                          default=mean(pick('deployed'), 'peak_rise_simulated_K'), high=mean(pick('declared_high'), 'peak_rise_simulated_K')))
    s = market['sourced']; a = market['assumed']
    sam = s['electronics_engineering_enrolment']+s['mechanical_engineering_enrolment']+s['electrical_engineering_enrolment']
    colleges = s['engineering_technology_colleges']*a['first_stage_college_share']['value']
    data = dict(study=dict(cases=summary['cases'], refused=summary['refused'], recommended=rec, claim=summary['claim'], half_step=summary['half_step'], option_effects=summary['option_effects']),
                best=best, four=four, table=table, baseline_best=designs.get((rec['count'], 'baseline')),
                saving=dict(cost_inr=four['cell_cost_inr']-best['cell_cost_inr'], mass_g=four['cell_mass_g']-best['cell_mass_g'], cost_from=four['cell_cost_inr'], cost_to=best['cell_cost_inr'], mass_from=four['cell_mass_g'], mass_to=best['cell_mass_g']) if best and four else None,
                board=dict(name=prices['items']['converter']['name'], usd=prices['items']['converter']['listings'][0]['price']),
                proof=proof, proof_cases_within_band=sum(1 for c in measured['cases'] if c.get('voltage_within_band') and c.get('temperature_within_band')), proof_cases=len(measured['cases']),
                pybamm=dict(cases=len(pybamm['checks']), passed=sum(c['passed'] for c in pybamm['checks']), max_voltage_V=max(c['studio_to_library']['maximum_voltage_difference_V'] for c in pybamm['checks']), max_heat_J=max(c['studio_to_library']['maximum_heat_energy_difference_J'] for c in pybamm['checks'])),
                replay=dict(cases=len(receipt['checks']), passed=sum(c['replay_passed'] for c in receipt['checks'])),
                samsung=gate['checks']['samsung']['6A'],
                market=dict(tam_students=s['engineering_technology_enrolment'], sam_students=sam, colleges=s['engineering_technology_colleges'], som_colleges=colleges, licence_inr=a['annual_lab_licence_inr']['value'], som_inr=colleges*a['annual_lab_licence_inr']['value']))
    data['cost'] = read('reports/build_cost_v1/result.json'); data['kpi'] = read('reports/slide_v4/kpi.json')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: data[k] for k in ('table', 'saving', 'proof')}, indent=0)[:1500])


if __name__ == '__main__':
    main()
