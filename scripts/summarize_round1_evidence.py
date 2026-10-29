"""Derive a conditional engineering recommendation from the frozen study results.

Reads completed artifacts only. Does not rerun, refit or access raw observations.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def summarize(study, output):
    paths = {
        'comparison': study / 'comparison.json',
        'protocol': study / 'protocol.json',
        'replay': study / 'replay_verification.json',
        'electrical_reference': ROOT / 'reports/numerical_reference_v1/run1/verification.json',
        'cooling_identification': ROOT / 'reports/thermal_fixture_reanalysis_v1/run1/identification.json',
        'thermal_sources': ROOT / 'configs/thermal_sources_v1.json',
    }
    data = {key: json.loads(path.read_text()) for key, path in paths.items()}
    study_data, protocol = data['comparison'], data['protocol']
    analysis, records = study_data['analysis'], study_data['experiments']
    scenarios = {s['key']: s for s in protocol['scenarios']}
    options = {o['key']: o for o in protocol['options']}
    by = {(r['scenario'], r['option']): r for r in records}
    expected = {(s, o) for s in scenarios for o in options}
    if len(records) != len(expected) or set(by) != expected:
        raise ValueError('The study is missing or repeats a scenario/design pair.')
    refined = analysis['all_case_step_refinement']
    if ({(r['scenario'], r['option']) for r in refined} != expected
            or len(refined) != len(expected)
            or not analysis['all_case_step_refinement_passed']):
        raise ValueError('Every design/scenario must have a successful refinement check.')
    if not data['electrical_reference']['passed']:
        raise ValueError('The independent electrical reference has not passed.')
    replay = data['replay']
    if {r['option'] for r in replay} != set(options) or any(r['returncode'] != 0 for r in replay):
        raise ValueError('Each nominal experiment must reproduce from its own export.')
    eligible = all(r['status'] == 'completed' and r['summary']['assessment']['requested_demand_met']
                   and r['summary']['checks']
                   and all(c['status'] == 'within_target' for c in r['summary']['checks']) for r in records)
    if not eligible:
        raise ValueError('Review incomplete service or target violations before recommending an option.')
    paired = analysis['paired_changes']
    metrics = ('peak_cell_current_A', 'peak_temperature_C', 'delivered_energy_Wh', 'minimum_voltage_V')
    changes = {}
    for key in ('thicker', 'opposite'):
        rows = [r for r in paired if r['option'] == key]
        changes[key] = {}
        for metric in metrics:
            values = [r['delta'][metric] for r in rows]
            improves = (lambda x: x < 0) if metric.startswith('peak_') else (lambda x: x > 0)
            changes[key][metric] = dict(minimum=min(values), maximum=max(values),
                                       improved_cases=sum(improves(x) for x in values), cases=len(values))
    peak_diff = changes['thicker']['peak_cell_current_A']
    energy_diff = changes['thicker']['delivered_energy_Wh']
    consistent = peak_diff['improved_cases'] == len(scenarios) == energy_diff['improved_cases']
    recommendation = ('Use thicker internal copper links as the preferred candidate for the declared backup study. '
                      'They reduced peak cell current and increased delivered energy in every tested scenario.'
                      if consistent else 'There is no consistently preferred candidate across these scenarios.')
    maxima = {metric: max(r['checks'][metric]['difference'] for r in refined) for metric in metrics}
    result = dict(version='voltforge.round1-evidence-summary/1',
                  input_sha256={k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in paths.items()},
                  study_software_hash=study_data['manifest']['software_hash'],
                  scenarios=len(scenarios), design_options=len(options),
                  coarse_calculations=len(records), refinement_calculations=len(refined),
                  numerical_comparison_eligible=eligible, conditional_recommendation=recommendation,
                  comparison_ranges=changes, maximum_refinement_difference=maxima,
                  ordering_reversals=analysis['ordering_reversals'],
                  experimental_accuracy_established=False,
                  uncertainty_type='Paired deterministic scenarios, not a probability distribution or measured accuracy interval')
    lines = [
        '# Round 1 engineering decision', '', recommendation, '',
        'This choice applies to four parallel LG M50T cells supplying 12 A for 10 minutes, '
        'starting at 70% charge and 23 °C, with a 3.3 V minimum output target. '
        'The study keeps the same cell models, test conditions and preparation in every physical alternative.', '',
        '| Design | Peak cell current (A) | Peak cell temperature (°C) | Delivered energy (Wh) | Lowest output (V) | Specified copper (g) |',
        '| --- | ---: | ---: | ---: | ---: | ---: |',
    ]
    for key, option in options.items():
        m = by['nominal', key]['summary']['metrics']
        lines.append(f"| {option['name']} | {m['peak_cell_current_A']:.4f} | {m['peak_temperature_C']:.3f} | "
                     f"{m['delivered_energy_Wh']:.5f} | {m['minimum_voltage_V']:.4f} | {m['conductor_mass_g']:.4f} |")
    base = by['nominal', 'baseline']['summary']['metrics']
    thick = by['nominal', 'thicker']['summary']['metrics']
    opp = changes['opposite']['peak_cell_current_A']
    lines += ['', '## Why this candidate', '',
        f"Doubling the internal copper thickness from 0.08 to 0.16 mm reduces nominal peak current by "
        f"{base['peak_cell_current_A']-thick['peak_cell_current_A']:.4f} A "
        f"({100*(1-thick['peak_cell_current_A']/base['peak_cell_current_A']):.1f}%), "
        f"adds {thick['delivered_energy_Wh']-base['delivered_energy_Wh']:.5f} Wh of delivered energy, "
        f"and adds {thick['conductor_mass_g']-base['conductor_mass_g']:.4f} g of specified copper. "
        'Contact resistance and external output routes stay unchanged.', '',
        f"Across {len(scenarios)} paired scenarios, its peak-current change ranges from "
        f"{peak_diff['minimum']:.4f} to {peak_diff['maximum']:.4f} A. "
        f"Delivered-energy gain ranges from {energy_diff['minimum']:.5f} to {energy_diff['maximum']:.5f} Wh. "
        'Every case completed the same requested duty and stayed within the declared simulation targets.', '',
        'Opposite-end collection shares current more evenly in the nominal preparation. '
        f"It improves peak current in {opp['improved_cases']} of {opp['cases']} scenarios. "
        'A +25 mV reference-voltage change in Cell 4 reverses that advantage relative to the baseline. '
        'Lower initial charge, differential voltage and a non-rested cell also reverse some rankings '
        'between the two alternatives. Its longer negative return adds 90 mm of copper, '
        'increases material mass and reduces delivered energy in every tested case.', '',
        '## What was varied', '',
        'The paired cases vary initial charge and relaxation, capacity by ±5%, DC and relaxation '
        'resistance by ±10%, reference voltage by ±25 mV, room temperature, contacts, heat capacity, '
        'cooling and the fraction of connection heat entering cells. One case combines lower charge, '
        'lower capacity, higher resistance and non-rested preparation. These are declared scenarios; '
        'they do not establish manufacturing distributions or exhaustive worst cases. '
        'The parameter variations primarily target the two end cells; arbitrary combinations remain untested.', '',
        '## Calculation evidence', '',
        f"The study contains {len(records)} matched experiments and {len(refined)} half-step repeats. "
        'Every refinement check passed its predeclared numerical resolution. '
        f"The largest temperature difference was {maxima['peak_temperature_C']:.7f} °C; "
        f"the largest energy difference was {maxima['delivered_energy_Wh']:.8f} Wh. "
        'All three nominal ZIP exports independently reproduced their 1,201 saved samples.', '',
        'Fifteen independent synthetic electrical cases compared the production solver against native '
        'PyBaMM Thevenin and closed-form solutions, covering discharge, charge, rest, zero/one/three '
        'relaxation branches and non-rested states. A separate state-dependent two-cell SciPy ODE '
        'reference checks coupled temperature feedback. Accounting residuals and step refinement '
        'serve different checks; small residuals alone do not prove numerical convergence.', '',
        '## Temperature evidence and the hardware decision', '',
        'The new LG model uses 58.5 J/K from the exact-M50T whole-cell reference in '
        '[Steinhardt et al. (2021)](https://doi.org/10.1016/j.est.2021.103065). '
        'Cooling uses the separately recorded 0.1524918708 W/K effective fixture estimate. '
        'That estimate uses measured changing chamber temperature and independently supplied heat capacity; '
        'it no longer infers heat capacity and cooling from one time constant. '
        'Earlier and later rests yield different estimates, and sensor offset and residual heating '
        'remain confounded. The tested cooling range carries that sensitivity into the design comparison.', '',
        'The sub-degree temperature differences between designs are model predictions. '
        'Neither the fitted cooling residual nor the small numerical error is an independent '
        'temperature-accuracy interval. Before a hardware change, measure initial cell voltages/charge, '
        'joint resistance and actual fixture cooling, and qualify conductor current capacity, insulation '
        'and packaging. The current evidence supports this conditional design comparison and '
        'reproducible experiment; it does not establish a hardware safety rating.', '',
        '## Reproduce', '',
        'The source study directory contains `protocol.json`, `comparison.json`, `comparison.csv`, '
        'the three nominal experiment ZIPs and their replay results. Each ZIP contains `report.html`, '
        'parameters, solver source and `replay.py`. The JSON alongside this note records every '
        'input artifact hash used to derive this recommendation. No raw or reserved observations '
        'are opened by the summarizer.', '',
    ]
    output.mkdir(parents=True, exist_ok=True)
    (output / 'recommendation.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    (output / 'RECOMMENDATION.md').write_text('\n'.join(lines))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, default=ROOT / 'reports/round1_robustness_v1/run1')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.study.resolve(), args.out.resolve())
    print(f"Derived a conditional recommendation from {result['coarse_calculations']} matched cases "
          f"and {result['refinement_calculations']} refinement calculations.")
