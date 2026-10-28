"""Partitioned electro-thermal integration for temperature-dependent cell models.

Electrical parameters are evaluated at the current cell state. Charge and RC
states use held branch current within a step. The linear heat-transfer network
receives the exact constant-parameter RC resistor heat, including its exponential
transients. Temperature feeds back into the following electrical solve.
Convergence is assessed separately from the accounting residuals.
"""
import numpy as np

from voltforge.models.cell_catalogue import CellModel
from voltforge.models.coupling_v2 import rc_interval


def phi1(x):
    x = np.asarray(x, float)
    small = abs(x) < 1e-5
    out = np.empty_like(x)
    out[small] = 1+x[small]/2+x[small]**2/6+x[small]**3/24
    out[~small] = np.expm1(x[~small])/x[~small]
    return out


def phi1_prime(x):
    x = np.asarray(x, float); small = abs(x) < 1e-4
    out = np.empty_like(x)
    out[small] = .5+x[small]/3+x[small]**2/8+x[small]**3/30
    out[~small] = (x[~small]*np.exp(x[~small])-np.expm1(x[~small]))/x[~small]**2
    return out


def convolution(a, b, h):
    """Integral exp(a*(h-s))*exp(b*s) ds for nonpositive a,b."""
    return h*np.exp(np.maximum(a, b)*h)*phi1(-abs(a-b)*h)


def integrated_convolution(a, b, h):
    a, b = np.broadcast_arrays(a, b)
    close = abs((a-b)*h) < 1e-5
    out = np.empty_like(a)
    out[close] = h*h*phi1_prime((a[close]+b[close])*h/2)
    out[~close] = h*(phi1(a[~close]*h)-phi1(b[~close]*h))/(a[~close]-b[~close])
    return out


class ThermalResponse:
    def __init__(self, capacity, conductance):
        self.sqrt = np.sqrt(capacity)
        symmetric = -conductance/self.sqrt[:, None]/self.sqrt[None, :]
        self.rates, self.vectors = np.linalg.eigh(symmetric)
        if np.max(self.rates) > 1e-10:
            raise ValueError('Heat-transfer network is not passive.')
        self.rates = np.minimum(self.rates, 0.)

    def step(self, temperature, constant_heat, coefficients, decay, h):
        modes = self.vectors.T@(self.sqrt*temperature)
        constant = self.vectors.T@(constant_heat/self.sqrt)
        forcing = self.vectors.T@(coefficients/self.sqrt[:, None])
        a = self.rates[:, None]; b = decay[None, :]
        first = h*phi1(self.rates*h)
        second = integrated_convolution(self.rates, np.zeros_like(self.rates), h)
        end = np.exp(self.rates*h)*modes+first*constant+np.sum(forcing*convolution(a, b, h), axis=1)
        integral = first*modes+second*constant+np.sum(forcing*integrated_convolution(a, b, h), axis=1)
        return (self.vectors@end)/self.sqrt, (self.vectors@integral)/self.sqrt


def simulate(graph, settings, bank):
    from .network import Circuit, Result, summarize, validate_settings, integration_grid
    from .protection import VirtualProtection
    circuit = Circuit(graph,bank); duration = validate_settings(settings)
    cells = graph['cells']; n = len(cells)
    models = [CellModel(bank[c['model']]) for c in cells]
    thermal_available=all(m.has_thermal for m in models)
    protection=VirtualProtection(settings.get('protection'),duration)
    if protection.config and protection.config['temperature_max_C'] is not None and not thermal_available:
        raise ValueError('Temperature-based protection needs a thermal model for every cell. Add thermal properties or disable that threshold.')
    q = np.array([m.capacity for m in models]); nrc = max(m.nrc for m in models)
    active = np.array([[j < m.nrc for j in range(nrc)] for m in models])
    soc = np.array([c['charge_pct']/100 for c in cells]); initial_soc = soc.copy()
    temperature = np.array([c['temperature_C'] for c in cells]); initial_temperature = temperature.copy()
    for i, m in enumerate(models):
        if not m.supported(soc[i], temperature[i]):
            lo, hi = m.temperature_range
            raise ValueError(f'{cells[i]["name"]}: {m.name} needs a cell temperature within {lo:g} to {hi:g} °C and charge within {100*m.soc_range[0]:g} to {100*m.soc_range[1]:g}%. Room temperature is a separate boundary condition.')

    def parameters(z, t):
        u = np.empty(n); r0 = np.empty(n)
        r = np.ones((n, nrc)); tau = np.ones((n, nrc))
        for i, m in enumerate(models):
            ui, ri, branches, times = m.parameters(float(z[i]), float(t[i]))
            u[i], r0[i] = ui, ri
            r[i, :m.nrc], tau[i, :m.nrc] = branches, times
        return u, r0, r, tau

    u, r0, resistance, tau = parameters(soc, temperature)
    vp = np.zeros((n, nrc))
    for i, c in enumerate(cells):
        weights = resistance[i]*active[i]
        if models[i].nrc:
            vp[i] = c['polarization_V']*weights/weights.sum()
        elif c['polarization_V']:
            raise ValueError(c['name']+': a basic resistive estimate has no initial relaxation voltage.')
    th = graph['thermal']; overrides = th.get('cell_parameters', {})
    def thermal_value(i,key):
        return overrides.get(cells[i]['id'],{}).get(key,(models[i].record.get('thermal_defaults') or th).get(key,th[key]))
    C = np.array([thermal_value(i,'heat_capacity_J_K') for i in range(n)])
    G = np.array([thermal_value(i,'ambient_conductance_W_K') for i in range(n)])
    K = np.diag(G); ids = {c['id']: i for i, c in enumerate(cells)}
    for contact in th['contacts']:
        a, b, g = ids[contact['a']], ids[contact['b']], contact['conductance_W_K']
        K[a, a] += g; K[b, b] += g; K[a, b] -= g; K[b, a] -= g
    heat = ThermalResponse(C, K)
    share = np.zeros((n, len(graph['connections'])))
    for j, w in enumerate(graph['connections']):
        for end in ('a', 'b'): share[ids[w[end].split(':')[0]], j] += th['wire_heat_fraction']/2
    profile = settings['profile']; starts = np.array([p['start_s'] for p in profile])
    grid = integration_grid(settings)
    charges = np.zeros(n); energy = np.zeros(6); parameter_exchange = 0.; generated = exchanged = 0.
    initial_storage = float(.5*np.sum(active*tau/resistance*vp**2))
    rows = []; stop = None

    def operating_error(state_t, solution):
        for i, m in enumerate(models):
            error = m.operating_error(float(state_t[i]), float(solution['current'][i]), float(solution['voltage'][i]))
            if error: return dict(reason=error[0], cell=cells[i]['id'], message=cells[i]['name']+': '+error[1])
        return None

    def solution_at(z, t, polarization, load):
        uu, rr, rj, tj = parameters(z, t)
        solution = circuit.solve(uu-np.sum(polarization, axis=1), rr, load)
        return uu, rr, rj, tj, solution

    def row_at(time, load, z, t, polarization, pp, event_side='sample'):
        uu, rr, rj, tj, s = pp; current = s['current']
        storage = float(.5*np.sum(active*tj/rj*polarization**2))
        resistor_power = float(np.sum(active*polarization**2/rj))
        storage_power = float(np.sum(active*polarization*(current[:, None]-polarization/rj)))
        p = float(s['terminal']*load)
        return dict(time_s=float(time), event_side=event_side, current_A=float(load), requested_current_A=requested_load,
                    external_disconnected=interval_external_open,voltage_V=s['terminal'], power_W=p,
                    cell_side_voltage_V=s['cell_side_voltage_V'],output_route_loss_W=s['output_loss_W'],
                    cell_current_A=current.tolist(), cell_voltage_V=s['voltage'].tolist(), charge_pct=(100*z).tolist(), temperature_C=t.tolist() if thermal_available else [None]*n,
                    parameter_temperature_C=t.tolist(),
                    wire_current_A=[float(v) if w['resistance_mohm'] > 0 else None for v, w in zip(s['wire_current'], graph['connections'])],
                    wire_loss_W=s['wire_loss'].tolist(), kcl_residual_A=s['kcl'], kvl_residual_V=s['kvl'],
                    power_residual_W=float(uu@current-p-rr@(current**2)-s['wire_loss'].sum()-s['output_loss_W']-resistor_power-storage_power),
                    cell_charge_residual_As=(3600*q*(initial_soc-z)-charges).tolist(), source_energy_Wh=float(energy[0]/3600),
                    delivered_energy_Wh=float(energy[1]/3600), delivered_positive_Wh=float(energy[4]/3600), received_energy_Wh=float(energy[5]/3600),
                    loss_energy_Wh=float((energy[2]+energy[3])/3600), parameter_storage_exchange_Wh=float(parameter_exchange/3600),
                    energy_residual_Wh=float((energy[0]-energy[1]-energy[2]-energy[3]-(storage-initial_storage)+parameter_exchange)/3600),
                    thermal_residual_J=float(C@(t-initial_temperature)-(generated-exchanged)) if thermal_available else None)

    t = 0.
    for j, target in enumerate(grid):
        requested_load = float(profile[min(np.searchsorted(starts, t, side='right')-1, len(profile)-1)]['current_A'])
        interval_external_open=protection.is_open(t)
        load=0. if interval_external_open else requested_load
        pp = solution_at(soc, temperature, vp, load); u, r0, resistance, tau, solution = pp
        switching = bool(rows and rows[-1]['time_s'] == t and (rows[-1]['current_A'] != load or rows[-1]['external_disconnected']!=interval_external_open or rows[-1]['requested_current_A']!=requested_load))
        if switching:
            event_kind='protective_disconnect' if not rows[-1]['external_disconnected'] and interval_external_open else 'requested_load_change'
            rows[-1]['event_side'] = 'before'
            rows[-1]['event_kind']=event_kind
            rows.append(row_at(t, load, soc, temperature, vp, pp, 'after'))
            rows[-1]['event_kind']=event_kind
        error = operating_error(temperature, solution)
        if error:
            if not rows: raise ValueError(error['message']+' Reduce the load, change starting charge or check the circuit.')
            stop = dict(**error, time_s=float(t)); break
        protection.observe(t,cells,solution,temperature)
        if protection.is_open(t) and not interval_external_open:
            if not rows or rows[-1]['time_s']!=t or rows[-1]['current_A']!=load:
                rows.append(row_at(t,load,soc,temperature,vp,pp,'before'))
            rows[-1]['event_side']='before';rows[-1]['event_kind']='protective_disconnect'
            interval_external_open=True
            load=0.;pp=solution_at(soc,temperature,vp,load);u,r0,resistance,tau,solution=pp
            rows.append(row_at(t,load,soc,temperature,vp,pp,'after'));rows[-1]['event_kind']='protective_disconnect'
            error=operating_error(temperature,solution)
            if error:
                stop=dict(**error,time_s=float(t));break
        if not rows or rows[-1]['time_s'] != t or rows[-1]['current_A'] != load:
            rows.append(row_at(t, load, soc, temperature, vp, pp))
        if j == len(grid)-1: break
        h = float(grid[j+1]-t); current = solution['current']
        b = active*resistance*current[:, None]; d = vp-b
        qrev = np.array([m.reversible_heat(float(soc[i]), float(temperature[i]), float(current[i])) for i, m in enumerate(models)])
        constant = r0*current**2+share@solution['wire_loss']+np.sum(active*b*b/resistance, axis=1)+G*settings['ambient_C']+qrev
        coefficients = np.zeros((n, 2*n*nrc)); decay = np.empty(2*n*nrc)
        for i in range(n):
            for k in range(nrc):
                index = 2*(i*nrc+k)
                coefficients[i, index] = active[i, k]*2*b[i, k]*d[i, k]/resistance[i, k]
                coefficients[i, index+1] = active[i, k]*d[i, k]**2/resistance[i, k]
                decay[index:index+2] = [-1/tau[i, k], -2/tau[i, k]]

        def trial(step):
            zz = soc-current*step/(3600*q)
            tt, integral_t = heat.step(temperature, constant, coefficients, decay, step) if thermal_available else (temperature.copy(),temperature*step)
            for i, m in enumerate(models):
                if not m.supported(float(zz[i]), float(tt[i])):
                    reason = 'charge_domain' if not m.soc_range[0] <= zz[i] <= m.soc_range[1] else 'temperature_domain'
                    return None, dict(reason=reason, cell=cells[i]['id'], message=cells[i]['name']+' reached the edge of its recorded '+('charge' if reason=='charge_domain' else 'cell-temperature')+' data.')
            vv, losses, _ = rc_interval(vp, active*current[:, None], resistance, tau, step)
            end = solution_at(zz, tt, vv, load)
            error = operating_error(tt, end[-1])
            return (zz, tt, vv, losses, integral_t, end), error

        # Examine the held-forcing trajectory inside the proposed interval too.
        # Bracket the first observed domain/operating violation, rather than
        # assuming a valid final point proves every earlier point was valid.
        candidate = error = None
        lower = 0.
        for fraction in (.25, .5, .75, 1.):
            check_h = h*fraction
            candidate, error = trial(check_h)
            if error:
                h = check_h
                break
            lower = check_h
        if error:
            lo, hi = lower, h
            for _ in range(38):
                mid = (lo+hi)/2
                _, bad = trial(mid)
                if bad: hi = mid
                else: lo = mid
            if lo < 1e-9:
                stop = dict(**error, time_s=float(t)); break
            h = lo; candidate, _ = trial(h)
            stop = dict(**error, time_s=float(t+h))
        zz, tt, vv, losses, integral_t, end = candidate
        end_u, end_r0, end_r, end_tau, end_s = end
        # Simpson integration along the state path. The energy residual remains
        # visible; it is not assigned to an invented physical loss term.
        mid_u = parameters((soc+zz)/2, (temperature+tt)/2)[0]
        energy[0] += float(current@(u+4*mid_u+end_u))*h/6
        p0, p1 = solution['terminal']*load, end_s['terminal']*load
        energy[1] += .5*(p0+p1)*h
        energy[4] += .5*(max(p0, 0)+max(p1, 0))*h
        energy[5] += .5*(max(-p0, 0)+max(-p1, 0))*h
        energy[2] += float(r0@(current**2)+solution['wire_loss'].sum()+solution['output_loss_W'])*h
        energy[3] += float(np.sum(active*losses))
        parameter_exchange += float(.5*np.sum(active*(end_tau/end_r-tau/resistance)*vv**2))
        generated += float(r0@(current**2)+(share@solution['wire_loss']).sum()+qrev.sum())*h+float(np.sum(active*losses))
        exchanged += float(G@(integral_t-settings['ambient_C']*h))
        charges += current*h
        soc, temperature, vp = zz, tt, vv
        t = float(t+h) if stop else float(grid[j+1])
        rows.append(row_at(t, load, soc, temperature, vp, end))
        if stop: break
    service=protection.service(profile,rows[-1]['time_s'])
    summary = summarize(rows, graph, settings, completed=stop is None,service_met=service['requested_demand_met'])
    if protection.config:
        summary['protection']=protection.summary(rows[-1]['time_s']);summary['service']=service
        if service['unserved_demand_s']>0:
            summary['insights'].insert(0,f'Virtual protection disconnected the external load. {service["unserved_demand_s"]:g} s of requested demand was not served.')
    summary.update(model=('Temperature-dependent equivalent circuits with cell-temperature feedback' if thermal_available else 'Isothermal temperature-dependent equivalent circuits') if any(not m.legacy and not m.basic for m in models) else ('Constant-parameter equivalent circuits with declared heat transfer' if thermal_available else 'Isothermal constant-parameter equivalent circuits'),
                   temperature_range_C=[max(m.temperature_range[0] for m in models), min(m.temperature_range[1] for m in models)],
                   cell_models=[dict(cell=c['id'], model=c['model'], temperature_range_C=list(m.temperature_range),
                                     source=bank[c['model']].get('source'), evidence=bank[c['model']].get('evidence_status', 'Original nominal fit')) for c, m in zip(cells, models)],
                   numerical_method='Held-current RC steps; exact within-step linear thermal response; state-dependent parameters updated each step',
                   reversible_heat='Included only for models with an attributed entropy coefficient',
                   experimental_validation=False)
    summary['thermal_mode']='Coupled declared heat-transfer model' if thermal_available else 'Isothermal electrical estimate; cell temperatures held at their starting values'
    summary['thermal_assumptions']=[dict(cell=c['id'],**m.record['thermal_provenance']) for c,m in zip(cells,models) if m.record.get('thermal_provenance')]
    from .conductors import physical_summary
    summary['physical_components']=physical_summary(graph,bank)
    summary['metrics']['conductor_mass_g']=summary['physical_components']['conductor_mass_g']
    summary['assessment']['interval_boundary_checks'] = 'Quarter-step domain/operating probes with localized first observed crossing; timestep refinement remains required for continuous claims.'
    return Result(rows, summary, 'stopped' if stop else 'completed', stop)
