"""Engineering screen over saved simulated trajectories: sampled metrics and optional upper limits. Margins are simulated screens, never acceptance or safety claims."""

import math

import numpy as np
import pandas as pd

ACTIVE_CURRENT_FLOOR_A = 0.5
LIMITS = {'peak_branch_current_A': 'A', 'current_imbalance_pct': '%', 'peak_cell_temperature_C': 'degC'}


def _to_py_float(val):
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    # Convert numpy types to Python types
    if hasattr(val, 'item'):
        val = val.item()
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return float(val)


def _to_py_int(val):
    if val is None:
        return None
    if hasattr(val, 'item'):
        val = val.item()
    return int(val)


def _finite_number(val):
    """True only for a real, finite, non-boolean number; NaN, +/-inf, strings and booleans are not limits."""
    if isinstance(val, (bool, np.bool_)) or not isinstance(val, (int, float, np.integer, np.floating)):
        return False
    try:
        return math.isfinite(val)
    except OverflowError:  # an integer too large to be a float is not a usable limit either
        return False


def per_sample(frame, thermal=None, active_floor_A=ACTIVE_CURRENT_FLOOR_A):
    if frame is None or len(frame) == 0:
        return pd.DataFrame(columns=[
            'time_s', 'step_s', 'peak_branch_current_A', 'peak_branch_cell',
            'current_imbalance_pct', 'peak_cell_temperature_C', 'peak_temperature_cell',
            'temperature_spread_K'
        ])
    
    df = pd.DataFrame()
    df['time_s'] = frame['time_s']
    df['step_s'] = frame['step_s']
    
    # Compute peak branch current
    i_cols = ['I1_A', 'I2_A', 'I3_A', 'I4_A']
    i_stack = frame[i_cols]
    peak_vals = i_stack.max(axis=1)
    peak_idx = i_stack.values.argmax(axis=1)  # 0-based index
    df['peak_branch_current_A'] = peak_vals
    df['peak_branch_cell'] = [f'cell_{idx + 1}' for idx in peak_idx]
    
    # Compute current imbalance
    imbalance = []
    for idx, row in frame.iterrows():
        module_current = row['module_current_A']
        i_vals = [row[c] for c in i_cols]
        i_mean = sum(i_vals) / len(i_vals)
        if abs(module_current) >= active_floor_A and abs(i_mean) >= active_floor_A / 4:
            i_max = max(i_vals)
            i_min = min(i_vals)
            if abs(i_mean) < 1e-18:  # avoid division issues
                imbalance.append(float('nan'))
            else:
                imb = 100.0 * (i_max - i_min) / abs(i_mean)
                imbalance.append(imb)
        else:
            imbalance.append(float('nan'))
    df['current_imbalance_pct'] = imbalance
    
    # Handle thermal
    if thermal is not None and len(thermal) > 0:
        # Check time_s match
        if len(thermal) != len(frame):
            raise ValueError('Thermal and electrical samples differ')
        # Absolute tolerance only: numpy's default relative tolerance would admit offsets of 0.1 s at t = 10000 s.
        if not np.allclose(frame['time_s'].values, thermal['time_s'].values, rtol=0, atol=1e-9):
            raise ValueError('Thermal and electrical samples differ')
        t_cols = ['T1_C', 'T2_C', 'T3_C', 'T4_C']
        t_stack = thermal[t_cols]
        t_peak_vals = t_stack.max(axis=1)
        t_peak_idx = t_stack.values.argmax(axis=1)
        # The samples are aligned by position (checked above), never by index label.
        df['peak_cell_temperature_C'] = t_peak_vals.to_numpy()
        df['peak_temperature_cell'] = [f'cell_{idx + 1}' for idx in t_peak_idx]
        df['temperature_spread_K'] = (t_stack.max(axis=1) - t_stack.min(axis=1)).to_numpy()
    else:
        df['peak_cell_temperature_C'] = float('nan')
        df['peak_temperature_cell'] = None
        df['temperature_spread_K'] = float('nan')
    
    return df


def metrics(frame, thermal=None, active_floor_A=ACTIVE_CURRENT_FLOOR_A):
    if frame is None or len(frame) == 0:
        reason = 'no samples'
        return {
            'peak_branch_current_A': {'value': None, 'unit': 'A', 'time_s': None, 'component': None, 'reason': reason},
            'current_imbalance_pct': {'value': None, 'unit': '%', 'time_s': None, 'component': None, 'reason': reason, 'active_samples': 0, 'active_current_floor_A': active_floor_A},
            'peak_cell_temperature_C': {'value': None, 'unit': 'degC', 'time_s': None, 'component': None, 'reason': reason},
            'maximum_temperature_spread_K': {'value': None, 'unit': 'K', 'time_s': None, 'component': None, 'reason': reason},
            'minimum_terminal_voltage_V': {'value': None, 'unit': 'V', 'time_s': None, 'component': None, 'reason': reason},
        }
    
    ps = per_sample(frame, thermal=thermal, active_floor_A=active_floor_A)
    
    result = {}
    
    # peak_branch_current_A
    peak_branch_max_idx = ps['peak_branch_current_A'].idxmax()
    peak_branch_val = ps.at[peak_branch_max_idx, 'peak_branch_current_A']
    result['peak_branch_current_A'] = {
        'value': _to_py_float(peak_branch_val),
        'unit': 'A',
        'time_s': _to_py_float(ps.at[peak_branch_max_idx, 'time_s']),
        'component': str(ps.at[peak_branch_max_idx, 'peak_branch_cell']),
    }
    
    # current_imbalance_pct
    imb_series = ps['current_imbalance_pct']
    # Count active samples
    active_mask = imb_series.notna()
    active_samples = int(active_mask.sum())
    if active_samples == 0:
        result['current_imbalance_pct'] = {
            'value': None,
            'unit': '%',
            'time_s': None,
            'component': None,
            'reason': 'no active samples above the active-current floor',
            'active_samples': 0,
            'active_current_floor_A': active_floor_A,
        }
    else:
        imb_valid = imb_series[active_mask]
        imb_max_idx = imb_valid.idxmax()
        imb_val = ps.at[imb_max_idx, 'current_imbalance_pct']
        result['current_imbalance_pct'] = {
            'value': _to_py_float(imb_val),
            'unit': '%',
            'time_s': _to_py_float(ps.at[imb_max_idx, 'time_s']),
            'component': None,
            'active_samples': active_samples,
            'active_current_floor_A': active_floor_A,
        }
    
    # peak_cell_temperature_C
    if thermal is not None and len(thermal) > 0:
        t_peak_max_idx = ps['peak_cell_temperature_C'].idxmax()
        t_peak_val = ps.at[t_peak_max_idx, 'peak_cell_temperature_C']
        result['peak_cell_temperature_C'] = {
            'value': _to_py_float(t_peak_val),
            'unit': 'degC',
            'time_s': _to_py_float(ps.at[t_peak_max_idx, 'time_s']),
            'component': str(ps.at[t_peak_max_idx, 'peak_temperature_cell']) if ps.at[t_peak_max_idx, 'peak_temperature_cell'] is not None else None,
        }
        # maximum_temperature_spread_K
        t_spread_max_idx = ps['temperature_spread_K'].idxmax()
        t_spread_val = ps.at[t_spread_max_idx, 'temperature_spread_K']
        result['maximum_temperature_spread_K'] = {
            'value': _to_py_float(t_spread_val),
            'unit': 'K',
            'time_s': _to_py_float(ps.at[t_spread_max_idx, 'time_s']),
            'component': 'module',
        }
    else:
        result['peak_cell_temperature_C'] = {
            'value': None,
            'unit': 'degC',
            'time_s': None,
            'component': None,
            'reason': 'thermal output unavailable',
        }
        result['maximum_temperature_spread_K'] = {
            'value': None,
            'unit': 'K',
            'time_s': None,
            'component': None,
            'reason': 'thermal output unavailable',
        }
    
    # minimum_terminal_voltage_V
    v_min_idx = frame['terminal_V'].idxmin()
    v_min_val = frame.at[v_min_idx, 'terminal_V']
    result['minimum_terminal_voltage_V'] = {
        'value': _to_py_float(v_min_val),
        'unit': 'V',
        'time_s': _to_py_float(frame.at[v_min_idx, 'time_s']),
        'component': 'module',
    }
    
    return result


def screen(frame, thermal, requirements, completed=True, active_floor_A=ACTIVE_CURRENT_FLOOR_A):
    mets = metrics(frame, thermal=thermal, active_floor_A=active_floor_A)
    
    # Determine requirements processing
    req_results = {}
    req_map = requirements if requirements is not None else {}
    
    for name in LIMITS:
        req_cfg = req_map.get(name)
        if req_cfg is None:
            req_results[name] = {'status': 'requirement not configured', 'reason': 'An upper limit and a documented source are both required'}
            continue
        limit = req_cfg.get('limit')
        doc_source = req_cfg.get('documented_source')
        # A documented source is text; any other type (including False, 0 or an empty container) is no source.
        if limit is None or not isinstance(doc_source, str) or doc_source.strip() == '':
            req_results[name] = {'status': 'requirement not configured', 'reason': 'An upper limit and a documented source are both required'}
            continue
        if not _finite_number(limit):
            req_results[name] = {'status': 'requirement not configured', 'reason': 'Limit must be a finite number'}
            continue
        metric = mets.get(name)
        if metric is None:
            req_results[name] = {'status': 'requirement not configured', 'reason': 'An upper limit and a documented source are both required'}
            continue
        if metric.get('value') is None:
            req_results[name] = {'status': 'not evaluable', 'reason': metric.get('reason', 'no samples')}
            continue
        # Check for violations
        ps = per_sample(frame, thermal=thermal, active_floor_A=active_floor_A)
        # Find worst value according to metric type
        if name == 'peak_branch_current_A':
            worst_val = metric['value']
            worst_time = metric['time_s']
            worst_comp = metric['component']
            # Find first crossing
            violations = ps[ps['peak_branch_current_A'] > limit]
        elif name == 'current_imbalance_pct':
            worst_val = metric['value']
            worst_time = metric['time_s']
            worst_comp = metric['component']
            violations = ps[ps['current_imbalance_pct'].notna() & (ps['current_imbalance_pct'] > limit)]
        elif name == 'peak_cell_temperature_C':
            if thermal is None or len(thermal) == 0:
                req_results[name] = {'status': 'not evaluable', 'reason': metric.get('reason', 'thermal output unavailable')}
                continue
            worst_val = metric['value']
            worst_time = metric['time_s']
            worst_comp = metric['component']
            violations = ps[ps['peak_cell_temperature_C'].notna() & (ps['peak_cell_temperature_C'] > limit)]
        else:
            violations = pd.DataFrame()
        
        if len(violations) > 0:
            # Some per-sample value > limit
            first_crossing_time_s = _to_py_float(violations.iloc[0]['time_s']) if len(violations) > 0 else None
            time_above_limit_s = float(violations['step_s'].sum()) if len(violations) > 0 else 0.0
            req_results[name] = {
                'status': 'simulated violation of configured limit',
                'value': _to_py_float(worst_val),
                'limit': _to_py_float(limit),
                'unit': metric['unit'],
                'margin': _to_py_float(limit) - _to_py_float(worst_val) if limit is not None and worst_val is not None else None,
                'time_s': _to_py_float(worst_time),
                'component': worst_comp,
                'first_crossing_time_s': first_crossing_time_s,
                'time_above_limit_s': _to_py_float(time_above_limit_s),
                'documented_source': doc_source,
                'note': 'Sampled at saved solver samples; does not resolve behaviour between samples or model error'
            }
            continue
        if completed is False:
            req_results[name] = {
                'status': 'insufficient simulation',
                'value': _to_py_float(worst_val),
                'limit': _to_py_float(limit),
                'unit': metric['unit'],
                'margin': _to_py_float(limit) - _to_py_float(worst_val) if limit is not None and worst_val is not None else None,
                'time_s': _to_py_float(worst_time),
                'component': worst_comp,
                'first_crossing_time_s': None,
                'time_above_limit_s': 0.0,
                'documented_source': doc_source,
                'note': 'Sampled at saved solver samples; does not resolve behaviour between samples or model error'
            }
            continue
        else:
            req_results[name] = {
                'status': 'no sampled exceedance; insufficient evidence for a pass',
                'value': _to_py_float(worst_val),
                'limit': _to_py_float(limit),
                'unit': metric['unit'],
                'margin': _to_py_float(limit) - _to_py_float(worst_val) if limit is not None and worst_val is not None else None,
                'time_s': _to_py_float(worst_time),
                'component': worst_comp,
                'first_crossing_time_s': None,
                'time_above_limit_s': 0.0,
                'documented_source': doc_source,
                'note': 'Sampled at saved solver samples; does not resolve behaviour between samples or model error'
            }
            continue
    
    return {
        'classification': 'simulated engineering screen; not experimental acceptance',
        'active_current_floor_A': float(active_floor_A),
        'metrics': mets,
        'requirements': req_results,
    }
