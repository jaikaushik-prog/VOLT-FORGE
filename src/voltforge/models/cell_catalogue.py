"""Traceable whole-cell ECM surfaces. Kelvin is used only in reversible heat.

Lookup coordinates are cell SOC and cell temperature, never ambient temperature.
Positive current leaves the positive terminal. The conserved SOC coordinate uses
one fixed capacity; changing temperature cannot create or remove stored charge.
"""
from pathlib import Path
import json
import math

import numpy as np

LEGACY_KEYS = ('P7', 'P17', 'P19', 'P13')
ADDITIONAL_KEYS = ('LG_M50T_ECN', 'SAMSUNG_30T')
ALL_KEYS = LEGACY_KEYS + ADDITIONAL_KEYS
KIND = 'temperature_dependent_ecm/1'
BASIC_KIND = 'basic_resistive/1'


class CellModel:
    def __init__(self, record):
        self.record = record
        self.basic = record.get('kind') == BASIC_KIND
        self.custom = record.get('origin') == 'user'
        self.has_thermal = not self.custom or bool(record.get('thermal_defaults'))
        self.legacy = record.get('kind') not in (KIND,BASIC_KIND)
        if self.basic:
            self.name=record['name'];self.capacity=float(record['capacity_Ah']);self.nrc=0
            self.z=np.asarray(record.get('reference',{}).get('soc',[0.,1.]),float)
            self.u=np.asarray(record.get('reference',{}).get('voltage_V',[record['nominal_voltage_V']]*2),float)
            self.r0=float(record['resistance_mohm'])/1000
            if (not math.isfinite(self.capacity) or self.capacity<=0 or not math.isfinite(self.r0) or self.r0<=0
                    or self.z.ndim!=1 or self.z.shape!=self.u.shape or len(self.z)<2 or len(self.z)>2048
                    or not np.isfinite(np.r_[self.z,self.u]).all() or np.any(np.diff(self.z)<=0)
                    or self.z[0]<0 or self.z[-1]>1 or np.any(self.u<=0)):
                raise ValueError('Check the custom cell capacity, DC resistance and voltage-reference coordinates.')
            self.soc_range=(float(self.z[0]),float(self.z[-1]));self.temperature_range=(-40.,100.)
            self.entropy=None
            return
        if self.legacy:
            from .coupling_v2 import VoltageReference
            self.reference = VoltageReference(record)
            self.capacity = float(record['capacity_Ah'])
            self.soc_range = self.reference.bounds
            self.temperature_range = (22., 28.)
            self.nrc = 1
            self.name = 'Original nominal-temperature cell fit'
            return
        self.name = record['name']
        self.capacity = float(record['capacity_Ah'])
        self.z = np.asarray(record['soc'], float)
        self.t = np.asarray(record['temperature_C'], float)
        self.nrc = int(record['nrc'])
        if (not math.isfinite(self.capacity) or self.capacity <= 0 or self.nrc not in (0, 1, 2, 3)
                or self.z.ndim != 1 or self.t.ndim != 1 or len(self.z) < 2 or len(self.t) < 2
                or not np.isfinite(np.r_[self.z, self.t]).all()
                or np.any(np.diff(self.z) <= 0) or np.any(np.diff(self.t) <= 0)
                or self.z[0] < 0 or self.z[-1] > 1 or self.t[0] <= -273.15):
            raise ValueError('Invalid cell-model coordinates or capacity.')
        shape = (len(self.t), len(self.z))
        self.tables = {}
        for key in ('ocv_V', 'r0_ohm', 'r_ohm', 'tau_s'):
            a = np.asarray(record[key], float)
            expected = shape + ((self.nrc,) if key in ('r_ohm', 'tau_s') else ())
            if a.shape != expected or not np.isfinite(a).all() or np.any(a <= 0):
                raise ValueError('Invalid ' + key + ' lookup table.')
            self.tables[key] = a
        # Finite entries can still have an unrepresentable capacitance or decay
        # rate. These are floating-point requirements, not operating limits.
        try:
            with np.errstate(over='raise', divide='raise', invalid='raise', under='ignore'):
                derived = (self.tables['tau_s'] / self.tables['r_ohm'],
                           self.tables['r_ohm'] / self.tables['tau_s'],
                           2. / self.tables['tau_s'])
                if any(not np.isfinite(a).all() or np.any(a <= 0) for a in derived):
                    raise FloatingPointError()
        except FloatingPointError:
            raise ValueError('RC resistance and time constants exceed the numerical range. Check their units and ratios.') from None
        self.soc_range = (float(self.z[0]), float(self.z[-1]))
        self.temperature_range = (float(self.t[0]), float(self.t[-1]))
        domain=record.get('deployment_domain')
        if domain is not None:
            zlo,zhi=map(float,domain['soc']);tlo,thi=map(float,domain['temperature_C'])
            if not self.z[0]<=zlo<zhi<=self.z[-1] or not self.t[0]<=tlo<thi<=self.t[-1]:
                raise ValueError('Deployment domain must stay inside the model coordinates.')
            self.soc_range=(zlo,zhi);self.temperature_range=(tlo,thi)
        entropy = record.get('entropy')
        self.entropy = None
        if entropy is not None:
            ez = np.asarray(entropy['soc'], float); ev = np.asarray(entropy['dOCV_dT_V_K'], float)
            if ez.ndim != 1 or ez.shape != ev.shape or len(ez) < 2 or np.any(np.diff(ez) <= 0) or not np.isfinite(np.r_[ez, ev]).all():
                raise ValueError('Invalid entropy coefficient table.')
            if ez[0] > self.z[0] or ez[-1] < self.z[-1]:
                raise ValueError('Entropy data do not cover the electrical SOC range.')
            self.entropy = (ez, ev)

    def supported(self, soc, temperature):
        return (math.isfinite(soc) and math.isfinite(temperature)
                and self.soc_range[0] <= soc <= self.soc_range[1]
                and self.temperature_range[0] <= temperature <= self.temperature_range[1])

    @staticmethod
    def bracket(axis, value):
        i = min(max(int(np.searchsorted(axis, value, side='right')) - 1, 0), len(axis) - 2)
        return i, (value - axis[i]) / (axis[i + 1] - axis[i])

    def parameters(self, soc, temperature):
        if not self.supported(soc, temperature):
            raise ValueError(self.name + ': state outside the recorded model domain.')
        if self.basic:
            return float(np.interp(soc,self.z,self.u)),self.r0,np.array([]),np.array([])
        if self.legacy:
            r0, r1 = self.record['parameters_ohm']
            return self.reference.value(soc), float(r0), np.array([r1]), np.array([self.record['tau_s']])
        i, wz = self.bracket(self.z, soc); j, wt = self.bracket(self.t, temperature)
        out = []
        for key in ('ocv_V', 'r0_ohm', 'r_ohm', 'tau_s'):
            a = self.tables[key]
            value = (1-wt)*((1-wz)*a[j, i]+wz*a[j, i+1]) + wt*((1-wz)*a[j+1, i]+wz*a[j+1, i+1])
            out.append(value)
        return out

    def reversible_heat(self, soc, temperature, current):
        if self.legacy or self.entropy is None:
            return 0.
        ez, ev = self.entropy
        return float(-current * (temperature + 273.15) * np.interp(soc, ez, ev))

    def current_limits(self, temperature):
        if self.legacy:
            # Historical studies keep their original model; the upgraded engine
            # still applies the sourced M50T operating conditions.
            key = 'LG_M50T_ECN'
        else:
            key = self.record['key']
        if key == 'LG_M50T_ECN':
            # At an overlapping endpoint, take the more restrictive interval.
            discharge = 2.425 if temperature <= 10 else 7.275
            charge = 1.455 if temperature <= 25 else 3.395
            if not 0 <= temperature <= 45: charge = 0.
            return charge, discharge
        limits = self.record['operating_limits']
        def limit(direction):
            value=limits.get('max_'+direction+'_A')
            interval=limits.get(direction+'_temperature_C')
            if interval and not interval[0]<=temperature<=interval[1]:return 0.
            return float(value) if value is not None else None
        return limit('charge'),limit('discharge')

    def operating_error(self, temperature, current, voltage):
        if not self.legacy and self.record['key']=='SAMSUNG_30T' and current>1e-8 and not -20<=temperature<=80:
            return 'discharge_temperature', 'Cell temperature is outside the manufacturer discharge interval.'
        bounds=(2.5, 4.2) if self.legacy else self.record['operating_limits'].get('voltage_V')
        if bounds:
            low,high=bounds
            if voltage < low - 1e-8: return 'voltage_min', f'Cell voltage reached the {low:g} V discharge cutoff.'
            if voltage > high + 1e-8: return 'voltage_max', f'Cell voltage reached the {high:g} V charge cutoff.'
        charge, discharge = self.current_limits(temperature)
        if discharge is not None and current > discharge + 1e-8: return 'current_max', f'Cell current exceeds the {discharge:g} A operating limit at this temperature.'
        if charge is not None and -current > charge + 1e-8: return 'charge_current_max', f'Charging exceeds the {charge:g} A operating limit at this temperature.'
        return None


def lint_tables(record, ratio=1e3):
    """Return jumps between neighbouring SOC nodes too large to be a real cell trend."""
    if record.get('kind') != KIND: return []
    found = []
    for key in ('r_ohm', 'tau_s'):
        table = np.asarray(record[key], float)
        step = np.maximum(table[:, 1:]/table[:, :-1], table[:, :-1]/table[:, 1:])
        for i, j, k in zip(*np.nonzero(step > ratio)):
            found.append(dict(table=key, temperature_C=record['temperature_C'][i], soc=[record['soc'][j], record['soc'][j+1]],
                              branch=int(k), ratio=float(step[i, j, k])))
    return found


def load_additional(root):
    path = Path(root) / 'configs' / 'cell_catalogue_v2.json'
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if data.get('version') != 'voltforge.cell-catalogue/2':
        raise ValueError('Unsupported cell catalogue.')
    models = data['models']
    if not set(ADDITIONAL_KEYS)<=set(models):
        raise ValueError('Cell catalogue entries are incomplete.')
    for key, record in models.items():
        if record.get('key') != key: raise ValueError('Cell-model identity mismatch.')
        if record.get('kind') != KIND: raise ValueError('Unsupported catalogue model kind.')
        CellModel(record)
    # This conservative model-use policy is separate from the historical
    # manufacturer rating and is captured with each numerical experiment.
    if 'SAMSUNG_30T' in models:
        models['SAMSUNG_30T']['operating_limits'].update(charge_temperature_C=[0.,50.],discharge_temperature_C=[-20.,80.])
    return models


def public_model(key, record):
    model = CellModel(record)
    if model.legacy:
        return dict(key=key, name='Original sample '+key, family='LG M50T', capacity_Ah=model.capacity,
                    resistance_mohm=1000*record['parameters_ohm'][0], temperature_range_C=list(model.temperature_range),
                    soc_range_pct=[100*x for x in model.soc_range], source_url='https://data.mendeley.com/datasets/zh58byr53c/2',
                    status='Original nominal-temperature fit', legacy=True)
    temperature=min(max(25.,model.temperature_range[0]),model.temperature_range[1])
    charge=min(max(.7,model.soc_range[0]),model.soc_range[1])
    _, r0, _, _ = model.parameters(charge,temperature)
    return dict(key=key, name=record['name'], family=record['family'], capacity_Ah=model.capacity,
                resistance_mohm=1000*float(r0), temperature_range_C=list(model.temperature_range),
                soc_range_pct=[100*x for x in model.soc_range], source_url=record['source']['url'],
                status=record['evidence_status'], geometry=record.get('geometry'), nrc=model.nrc, legacy=False,
                custom=model.custom,basic=model.basic,thermal_available=model.has_thermal,
                thermal_defaults=record.get('thermal_defaults'),revision=record.get('revision'),
                thermal_provenance=record.get('thermal_provenance'),
                nominal_voltage_V=record.get('nominal_voltage_V'),
                source=record.get('source'),operating_limits=record.get('operating_limits'),
                temperature_dependence='Constant-parameter assumption' if model.basic else 'Recorded lookup model')
