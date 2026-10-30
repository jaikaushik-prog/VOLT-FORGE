"""Turn the V4 study cases into qualification results, using the frozen protocol's rules."""
from pathlib import Path
import argparse
import json
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'src'))
from run_design_study_v2 import BANK, P, build
from voltforge.studio.parts import estimate, load_prices

LIMIT_A = 7.275


def worst(rows):
    done = [r for r in rows if 'min_voltage_V' in r]
    if not done: return dict(calculated=0)
    return dict(calculated=len(done), lowest_voltage_V=min(r['min_voltage_V'] for r in done), highest_cell_current_A=max(r['peak_cell_current_A'] for r in done),
                highest_temperature_C=max(r['peak_temperature_C'] for r in done))


def design_key(r): return r['count'], r['option']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, default=ROOT/'reports/design_study_v2/run1')
    args = parser.parse_args()
    cases = [json.loads(line) for line in open(args.run/'cases.jsonl')]
    required = set(P['qualification']['required_tiers']); prices = load_prices(ROOT)
    designs = sorted({design_key(r) for r in cases})
    results = []
    for key in designs:
        count, option = key; rows = [r for r in cases if design_key(r) == key]
        gate = [r for r in rows if r['mission'] == 'pi' and r['tier'] in required]
        failed = [r for r in gate if not r['passed']]
        stress = [r for r in rows if r['mission'] == 'stress' and r['tier'] in required]
        samples = {m: [r for r in rows if r['tier'] == 'combined_sample' and r['mission'] == m] for m in P['missions']}
        graph = build(dict(count=count, option=option, mission='pi'))[0]; parts = estimate(graph, {P['cell_model']: BANK[P['cell_model']]}, prices)
        nominal = next((r for r in gate if r['tier'] == 'nominal'), None); bad_stress = [r for r in stress if not r['passed']]
        pi_worst = worst(gate)
        results.append(dict(count=count, option=option, required_cases=len(gate), required_passed=len(gate)-len(failed), qualifies=bool(gate) and not failed,
                            nominal={k: nominal.get(k) for k in ('passed', 'outcome', 'reason', 'min_voltage_V', 'peak_cell_current_A', 'peak_temperature_C')} if nominal else None,
                            failures=[dict(tier=r['tier'], label=r['label'], outcome=r['outcome'], reason=r.get('reason')) for r in failed[:12]], failure_count=len(failed),
                            worst_required=pi_worst, current_margin_A=LIMIT_A-pi_worst['highest_cell_current_A'] if pi_worst.get('calculated') else None,
                            voltage_margin_V=pi_worst['lowest_voltage_V']-P['common']['voltage_floor_V'] if pi_worst.get('calculated') else None,
                            stress=dict(cases=len(stress), passed=len(stress)-len(bad_stress), first_failures=[r['label'] for r in bad_stress[:6]], worst=worst(stress)),
                            samples={m: dict(cases=len(s), passed=sum(r['passed'] for r in s), worst=worst(s)) for m, s in samples.items() if s},
                            cell_cost_inr=next(l['cost'] for l in parts['lines'] if l['slot'] == 'cell'), cell_mass_g=parts['cell_mass_g'], listed_mass_g=parts['listed_mass_g']))
    qualifying = [r for r in results if r['qualifies']]
    ranked = sorted(qualifying, key=lambda r: (r['count'], -r['current_margin_A'], -r['voltage_margin_V']))
    half = []
    for r in cases:
        if r['tier'] != 'half_step' or 'min_voltage_V' not in r: continue
        base = next((b for b in cases if b['tier'] == 'nominal' and design_key(b) == design_key(r) and b['mission'] == r['mission'] and 'min_voltage_V' in b), None)
        if base: half.append((abs(r['min_voltage_V']-base['min_voltage_V']), abs(r['peak_cell_current_A']-base['peak_cell_current_A']), abs(r['peak_temperature_C']-base['peak_temperature_C'])))
    paired = {}
    for option in ('thicker', 'opposite', 'combined'):
        for count in (2, 3, 4):
            for mission in P['missions']:
                d = {r['id']: r for r in cases}
                lookup = {(r['tier'], r['mission'], r['label'], r['count'], r['option']): r for r in cases}
                pairs = []
                for r in cases:
                    if r['count'] == count and r['option'] == option and r['mission'] == mission and r['tier'] in ('position_mismatch', 'combined_sample', 'nominal'):
                        b = lookup.get((r['tier'], r['mission'], r['label'], count, 'baseline'))
                        if b and 'min_voltage_V' in r and 'min_voltage_V' in b: pairs.append((r['peak_cell_current_A']-b['peak_cell_current_A'], r['peak_temperature_C']-b['peak_temperature_C']))
                if pairs:
                    paired[f'{count}_{option}_{mission}'] = dict(pairs=len(pairs), median_current_change_A=statistics.median(p[0] for p in pairs), raised_peak_current=sum(p[0] > 1e-9 for p in pairs),
                                                                  median_temperature_change_K=statistics.median(p[1] for p in pairs), raised_peak_temperature=sum(p[1] > 1e-9 for p in pairs))
    summary = dict(version='voltforge.design-study-summary/2', cases=len(cases), refused=sum(r['outcome'] == 'refused' for r in cases), claim=P['qualification']['claim'],
                   qualification_rule=P['qualification']['a_design_qualifies_only_if'], smallest_qualifying_cell_count=ranked[0]['count'] if ranked else None,
                   recommended=dict(count=ranked[0]['count'], option=ranked[0]['option']) if ranked else None, designs=results, ranked=[dict(count=r['count'], option=r['option']) for r in ranked],
                   half_step=dict(pairs=len(half), max_voltage_change_V=max((h[0] for h in half), default=None), max_current_change_A=max((h[1] for h in half), default=None), max_temperature_change_K=max((h[2] for h in half), default=None)),
                   option_effects=paired, experimental_validation=False)
    (args.run/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    print('cases', summary['cases'], 'refused', summary['refused'], 'recommended', summary['recommended'])
    for r in results:
        n = r['nominal'] or {}
        print(f"{r['count']} {r['option']:9} qualifies={str(r['qualifies']):5} {r['required_passed']}/{r['required_cases']} nominal V={n.get('min_voltage_V') or 0:.3f} I={n.get('peak_cell_current_A') or 0:.2f} T={n.get('peak_temperature_C') or 0:.1f} worst I={r['worst_required'].get('highest_cell_current_A', 0):.2f} T={r['worst_required'].get('highest_temperature_C', 0):.1f} stress {r['stress']['passed']}/{r['stress']['cases']}")


if __name__ == '__main__':
    main()
