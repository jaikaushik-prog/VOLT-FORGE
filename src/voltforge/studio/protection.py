"""Declared virtual sensing and a latched ideal external disconnect.

This is a bounded control experiment, not a model of a certified protection IC.
Opening the external circuit does not isolate parallel cells from each other.
"""
from copy import deepcopy
import math

import numpy as np

VERSION='voltforge.virtual-protection/1'


def defaults():
    return dict(version=VERSION,sample_period_s=.5,response_delay_s=.5,current_max_A=4.5,
                voltage_min_V=None,temperature_max_C=None,
                sensor_bias=dict(current_A=0.,voltage_V=0.,temperature_C=0.),
                source='Declared virtual sensing and ideal external-disconnect assumptions; not verified hardware settings.')


def validate(config,duration):
    from .network import number
    if config is None:return
    if not isinstance(config,dict) or set(config)!=set(defaults()) or config['version']!=VERSION:
        raise ValueError('Use a supported virtual monitoring and protection definition.')
    number(config['sample_period_s'],'Sensor sample interval',.05,60)
    number(config['response_delay_s'],'Protection response delay',0,30)
    if duration/config['sample_period_s']>50000:raise ValueError('Increase the sensor sample interval for this mission.')
    if all(config[k] is None for k in ('current_max_A','voltage_min_V','temperature_max_C')):
        raise ValueError('Set at least one threshold for the virtual protection experiment.')
    for key,lo,hi in [('current_max_A',.001,200),('voltage_min_V',.001,1000),('temperature_max_C',-40,100)]:
        if config[key] is not None:number(config[key],key,lo,hi)
    bias=config['sensor_bias']
    if not isinstance(bias,dict) or set(bias)!={'current_A','voltage_V','temperature_C'}:
        raise ValueError('Declare current, voltage and temperature sensor offsets.')
    for k,v in bias.items():number(v,k+' sensor offset',-10,10)
    if not isinstance(config['source'],str) or not 1<=len(config['source'].strip())<=2000:
        raise ValueError('Record the source or assumptions for the virtual protection settings.')


class VirtualProtection:
    def __init__(self,config,duration):
        validate(config,duration);self.config=deepcopy(config);self.duration=duration
        self.event=None;self.samples=0
        self.sample_times=set()
        if config:
            self.sample_times={round(float(t),10) for t in np.arange(0,duration+1e-10,config['sample_period_s'])}

    def grid_times(self):
        if not self.config:return []
        delay=self.config['response_delay_s']
        return sorted(self.sample_times|{round(t+delay,10) for t in self.sample_times if t+delay<=self.duration})

    def is_open(self,time):
        return bool(self.event and time>=self.event['disconnect_time_s']-1e-10)

    def observe(self,time,cells,solution,temperature):
        if not self.config or self.event or round(time,10) not in self.sample_times:return
        self.samples+=1;c=self.config
        quantities=[('voltage_V','voltage_min_V',solution['voltage'],'V',False),
                    ('current_A','current_max_A',solution['current'],'A',True),
                    ('temperature_C','temperature_max_C',temperature,'°C',True)]
        for quantity,threshold,values,unit,upper in quantities:
            target=c[threshold]
            if target is None:continue
            for i,true in enumerate(values):
                measured=float(true)+c['sensor_bias'][quantity]
                value=abs(measured) if quantity=='current_A' else measured
                crossed=value>=target if upper else value<=target
                if crossed:
                    self.event=dict(kind='virtual_protection',cell=cells[i]['id'],quantity=quantity,unit=unit,
                        detected_time_s=float(time),disconnect_time_s=round(float(time+c['response_delay_s']),10),
                        true_value=float(true),measured_value=measured,threshold=float(target),
                        source=c['source'],action='Latched ideal external disconnect; parallel-cell connections remain intact')
                    return

    def service(self,profile,final_time=None):
        final_time=self.duration if final_time is None else final_time
        unserved_time=unserved_charge=0.
        trip=self.event['disconnect_time_s'] if self.event and self.event['disconnect_time_s']<=final_time+1e-10 else math.inf
        unconfirmed_time=0.
        for p in profile:
            if abs(p['current_A'])<1e-12:continue
            h=max(0.,p['end_s']-max(p['start_s'],trip))
            unserved_time+=h;unserved_charge+=abs(p['current_A'])*h
            if not math.isfinite(trip):unconfirmed_time+=max(0.,p['end_s']-max(p['start_s'],final_time))
        return dict(requested_demand_met=unserved_time<1e-10 and unconfirmed_time<1e-10,unserved_demand_s=unserved_time,
                    unserved_requested_charge_As=unserved_charge,
                    unconfirmed_requested_demand_s=unconfirmed_time,
                    note='Requested current and duration are compared with the external demand actually served. No counterfactual energy estimate is invented.')

    def summary(self,final_time=None):
        final_time=self.duration if final_time is None else final_time
        return dict(config=self.config,sample_count=self.samples,event=deepcopy(self.event),
                    actuated=bool(self.event and self.event['disconnect_time_s']<=final_time+1e-10),
                    sensing='Simulated state plus the declared constant sensor offset, not measured hardware data',
                    actuator='Ideal latched external disconnect; no fuse, contactor or protection-IC certification is implied')
