"""Derive the declared thermal-v1 defaults from the measured post-discharge cooling of test 53.

Input: the official raw export `M1_NMC_Unaged_R0_T25.xlsx` (test 53, already opened by the
reconciliation). Pass it explicitly; its SHA-256 is checked. Only rest steps 4 and 6 are fitted.
The discharge itself is not used to set any parameter.

Method: each thermocouple's baseline is the mean of its last 120 s of pre-discharge rest
(step 4), which removes the persistent sensor/position offsets. With equal per-cell ambient
conductance, the module-mean excess temperature during the step-6 rest decays with
tau = Cth/G_ambient exactly, because neighbour exchange cancels in the mean. Cth is not measured:
it is nominal mass (Piombo Table 1) times an assumed specific heat. So G_ambient = Cth/tau inherits
that assumption, while tau itself is measured. In-sample, one run, chamber- and fixture-specific.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SHA256 = '4596d3fed65277b548176bca7dd3dfa9efcd0bd2167722effc87ac38975c24bc'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
MASS_KG = 0.06925  # Piombo et al. 2024, Table 1, nominal LG INR21700-M50T mass
SPECIFIC_HEAT = 1000.0  # J/(kg K); assumed typical cylindrical Li-ion value, not measured here
NEIGHBOUR_W_PER_K = 0.05  # assumed weak coupling through the copper bars and air; not identified
RAIL_FRACTION = 0.5  # assumed share of rail-segment heat entering the two adjacent cells


def column(ref):
    value = 0
    for letter in re.match(r'[A-Z]+', ref).group():
        value = value*26 + ord(letter) - 64
    return value - 1


def read_sheet(path):
    with zipfile.ZipFile(path) as archive:
        shared = [''.join(t.text or '' for t in s.iter(NS+'t')) for s in ET.fromstring(archive.read('xl/sharedStrings.xml')).iter(NS+'si')]
        rows = []
        for _, element in ET.iterparse(archive.open('xl/worksheets/sheet2.xml')):
            if element.tag != NS+'row':
                continue
            values = {}
            for cell in element.findall(NS+'c'):
                v = cell.find(NS+'v')
                if v is not None:
                    values[column(cell.get('r'))] = shared[int(v.text)] if cell.get('t') == 's' else float(v.text)
            rows.append(values)
            element.clear()
    header = {v: k for k, v in rows[0].items()}
    return header, rows[1:]


def derive(xlsx):
    digest = hashlib.sha256(Path(xlsx).read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError('Unexpected input bytes; this derivation is pinned to the official test-53 raw export')
    header, rows = read_sheet(xlsx)
    get = lambda name: np.array([r.get(header[name], np.nan) for r in rows], float)
    time, step = get('Test_Time(s)'), get('Step_Index')
    names = sorted([h for h in header if h.startswith('Aux_Temperature')], key=lambda s: int(s.rsplit('_', 1)[1]))
    temps = np.array([get(name) for name in names])  # 1-4 cell surfaces, 5 chamber ambient (Piombo 2024, section 4)
    baseline = temps[:, np.flatnonzero(step == 4)[-120:]].mean(axis=1)
    rest = np.flatnonzero(step == 6)
    elapsed = time[rest] - time[rest[0]]
    excess = (temps[:4, rest] - baseline[:4, None]).mean(axis=0)
    fit = least_squares(lambda p: p[0]*np.exp(-elapsed/p[1]) + p[2] - excess, [excess[0], 600., 0.],
                        bounds=([0, 10, -1], [10, 1e5, 1]))
    tau = float(fit.x[1])
    per_cell = []
    for k in range(4):
        y = temps[k, rest] - baseline[k]
        r = least_squares(lambda p: p[0]*np.exp(-elapsed/p[1]) + p[2] - y, [y[0], 600., 0.], bounds=([0, 10, -1], [10, 1e5, 1]))
        per_cell.append(dict(cell_position=k+1, tau_s=float(r.x[1]), rms_residual_K=float(np.sqrt(np.mean(r.fun**2)))))
    capacity = MASS_KG*SPECIFIC_HEAT
    return dict(input=dict(file=Path(xlsx).name, sha256=digest, run='Piombo test 53, M1_NMC_Unaged_R0_T25'),
        sensor_baselines_C=[float(x) for x in baseline], baseline_window='last 120 samples of step 4 (pre-discharge rest)',
        fitted_segment='step 6 (post-discharge rest), module-mean excess over each sensor baseline',
        module_mean_fit=dict(initial_excess_K=float(fit.x[0]), tau_s=tau, asymptote_K=float(fit.x[2]),
            rms_residual_K=float(np.sqrt(np.mean(fit.fun**2))), samples=int(len(rest))),
        per_cell_fits=per_cell,
        derived=dict(heat_capacity_J_per_K=capacity, ambient_conductance_W_per_K=capacity/tau),
        assumptions=dict(mass_kg=MASS_KG, specific_heat_J_per_kgK=SPECIFIC_HEAT, neighbour_conductance_W_per_K=NEIGHBOUR_W_PER_K,
            rail_heat_to_cells_fraction=RAIL_FRACTION, equal_cells='Equal Cth and ambient conductance for all four cells'),
        limitations=['In-sample fit to one already-opened run; no held-out thermal assessment',
            'Specific heat assumed; ambient conductance scales with it', 'Chamber airflow and fixture specific',
            'Discharge heating was not used to set any parameter'])


def config(record):
    tau, capacity, ambient = record['module_mean_fit']['tau_s'], *record['derived'].values()
    where = 'reports/thermal_v1/cooling_derivation.json'
    return dict(schema_version=1, model='lumped_four_node_v1', derivation=where, derivation_input_sha256=record['input']['sha256'],
        heat_capacity_J_per_K=dict(value=[round(capacity, 4)]*4, unit='J/K', classification='assumed',
            source=f'Nominal mass 69.25 g (Piombo et al. 2024, Table 1) x assumed specific heat {SPECIFIC_HEAT:g} J/(kg K); not measured'),
        ambient_conductance_W_per_K=dict(value=[round(ambient, 6)]*4, unit='W/K', classification='assumed',
            source=f'Cth/tau with tau = {tau:.1f} s fitted to the measured post-discharge cooling of Piombo test 53 ({where}); in-sample, chamber-specific'),
        neighbour_conductance_W_per_K=dict(value=[NEIGHBOUR_W_PER_K]*3, unit='W/K', classification='assumed',
            source='Assumed weak cell-to-cell coupling through copper bars and air; not identified from data'),
        rail_heat_to_cells_fraction=dict(value=RAIL_FRACTION, unit='fraction', classification='assumed',
            source='Assumed: half of each rail-segment loss heats its two adjacent cells equally; the rest leaves to ambient'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xlsx', type=Path, required=True, help='Official raw export M1_NMC_Unaged_R0_T25.xlsx (test 53)')
    args = parser.parse_args()
    record = derive(args.xlsx)
    out = ROOT / 'reports/thermal_v1'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'cooling_derivation.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
    (ROOT / 'configs/thermal_v1.json').write_text(json.dumps(config(record), indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f"tau {record['module_mean_fit']['tau_s']:.1f} s -> G_ambient {record['derived']['ambient_conductance_W_per_K']:.5f} W/K "
          f"(Cth {record['derived']['heat_capacity_J_per_K']:.2f} J/K)")


if __name__ == '__main__':
    main()
