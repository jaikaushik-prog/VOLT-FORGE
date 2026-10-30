"""Bounded, declarative user cell records. Import never executes supplied code."""
from copy import deepcopy
import csv
import io
import json
import math
from urllib.parse import urlsplit

from .cell_catalogue import BASIC_KIND, KIND, CellModel

VERSION = 'voltforge.custom-cell/1'
FIELDS = {'version','kind','name','capacity_Ah','nominal_voltage_V','resistance_mohm',
          'source','thermal_defaults','operating_limits','reference','soc','temperature_C',
          'nrc','ocv_V','r0_ohm','r_ohm','tau_s','geometry','entropy','thermal_preset','deployment_domain'}
THERMAL_PRESET = dict(version='example_cylindrical/1',heat_capacity_J_K=70.,ambient_conductance_W_K=.15,
                      status='Assumed heat model',source='Illustrative cylindrical-cell heat capacity and room-cooling assumptions; not measurements of this custom cell.')


def numeric(value, label, low, high):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label} must be a number from {low:g} to {high:g}.')
    return float(value)


def normalize(data, key, revision=1, parent=None):
    if not isinstance(data,dict) or set(data)-FIELDS:
        raise ValueError('Import a cell definition with supported fields, not code or a complete project.')
    if data.get('version',VERSION)!=VERSION:raise ValueError('This cell-file version is not supported.')
    try:
        encoded=json.dumps(data,allow_nan=False)
    except (TypeError,ValueError):raise ValueError('Cell values must be finite JSON numbers or text.') from None
    if len(encoded.encode())>120000:raise ValueError('Keep a custom cell definition below 120 KB.')
    record=deepcopy(data)
    name=record.get('name')
    if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('Give the cell a name of up to 80 characters.')
    record['name']=name.strip()
    record['capacity_Ah']=numeric(record.get('capacity_Ah'),'Capacity (Ah)',.001,10000)
    kind=record.get('kind',BASIC_KIND)
    if kind not in (BASIC_KIND,KIND):raise ValueError('Choose a basic resistive cell or a temperature-dependent equivalent circuit.')
    record.update(version=VERSION,kind=kind,key=key,origin='user',family=name.strip(),revision=revision,parent=parent,
                  evidence_status='User-provided model; independent assessment pending')
    source=record.get('source','')
    if isinstance(source,str):source={'url':source,'description':'User-provided cell parameters'}
    if not isinstance(source,dict) or set(source)-{'url','description'}:raise ValueError('Use a source link and an optional source description.')
    url=source.get('url','');description=source.get('description','User-provided cell parameters')
    if not isinstance(url,str) or len(url)>2000 or not isinstance(description,str) or len(description)>2000:
        raise ValueError('Keep the source link and description below 2,000 characters each.')
    if url and (urlsplit(url).scheme not in ('http','https') or not urlsplit(url).hostname or urlsplit(url).username):
        raise ValueError('Use an http or https source link without account credentials.')
    record['source']=dict(url=url,description=description)
    preset=record.pop('thermal_preset',None)
    if preset not in (None,'example_cylindrical/1','none'):raise ValueError('Choose the example cylindrical heat model or provide your own thermal values.')
    use_example=preset=='example_cylindrical/1' or (preset is None and kind==BASIC_KIND and 'thermal_defaults' not in data)
    thermal=record.get('thermal_defaults')
    if use_example:
        if thermal is not None:raise ValueError('Choose example thermal properties or your own values, one at a time.')
        thermal={k:THERMAL_PRESET[k] for k in ('heat_capacity_J_K','ambient_conductance_W_K')}
        record['thermal_provenance']=deepcopy(THERMAL_PRESET)
    else:
        record['thermal_provenance']=dict(status='User-provided heat model' if thermal else 'Temperature not modeled',
                                          source=record['source'],version='user_input/1')
    if thermal is not None:
        if not isinstance(thermal,dict) or set(thermal)!={'heat_capacity_J_K','ambient_conductance_W_K'}:
            raise ValueError('Thermal prediction needs both heat capacity (J/K) and cooling conductance (W/K).')
        thermal['heat_capacity_J_K']=numeric(thermal['heat_capacity_J_K'],'Heat capacity (J/K)',.001,1e8)
        thermal['ambient_conductance_W_K']=numeric(thermal['ambient_conductance_W_K'],'Cooling conductance (W/K)',0,1e6)
    record['thermal_defaults']=thermal
    limits=record.get('operating_limits',{})
    allowed={'voltage_V','max_charge_A','max_discharge_A','charge_temperature_C','discharge_temperature_C'}
    if not isinstance(limits,dict) or set(limits)-allowed:raise ValueError('The custom operating limits contain an unsupported field.')
    for direction in ('charge','discharge'):
        k='max_'+direction+'_A'
        if k in limits:limits[k]=numeric(limits[k],direction.title()+' limit (A)',0,100000)
    for k in ('voltage_V','charge_temperature_C','discharge_temperature_C'):
        if k in limits:
            v=limits[k];lo,hi=(.001,1000) if k=='voltage_V' else (-40,100)
            if not isinstance(v,list) or len(v)!=2:raise ValueError('Each operating interval needs a lower and an upper value.')
            v=[numeric(x,k,lo,hi) for x in v]
            if v[0]>=v[1]:raise ValueError('The lower operating bound must be smaller than the upper bound.')
            limits[k]=v
    record['operating_limits']=limits
    geometry=record.get('geometry')
    if geometry is not None:
        if not isinstance(geometry,dict) or set(geometry)!={'diameter_mm','height_mm','mass_kg'}:raise ValueError('Geometry needs diameter, height and mass with their stated units.')
        for k,upper in [('diameter_mm',1000),('height_mm',5000),('mass_kg',10000)]:geometry[k]=numeric(geometry[k],k,.001,upper)
    if kind==BASIC_KIND:
        record['nominal_voltage_V']=numeric(record.get('nominal_voltage_V'),'Nominal voltage (V)',.001,1000)
        record['resistance_mohm']=numeric(record.get('resistance_mohm'),'DC resistance (mΩ)',.000001,1e6)
        if set(record)&{'soc','temperature_C','nrc','ocv_V','r0_ohm','r_ohm','tau_s','entropy'}:
            raise ValueError('Put advanced lookup arrays in a temperature-dependent cell definition.')
        if 'reference' in record and (not isinstance(record['reference'],dict) or set(record['reference'])!={'soc','voltage_V'}):
            raise ValueError('A voltage reference needs soc (0 to 1) and voltage_V arrays.')
    else:
        if 'reference' in record:raise ValueError('Use ocv_V for an advanced lookup model.')
        if isinstance(record.get('nrc'),bool) or record.get('nrc') not in (0,1,2,3):raise ValueError('Use zero to three RC relaxation branches.')
        if len(record.get('soc',[]))>256 or len(record.get('temperature_C',[]))>32:
            raise ValueError('Use at most 256 charge coordinates and 32 temperatures.')
    try:CellModel(record)
    except (KeyError,TypeError,IndexError,ValueError) as exc:
        raise ValueError('Check the cell lookup values, coordinate order and units: '+str(exc)) from None
    return record


def csv_definition(text, metadata):
    """A measured OCV-vs-SOC reference with a separately declared DC resistance."""
    if not isinstance(text,str) or len(text.encode())>100000:raise ValueError('Keep the CSV below 100 KB.')
    reader=csv.DictReader(io.StringIO(text))
    if reader.fieldnames!=['soc_pct','voltage_V']:
        raise ValueError('Use exactly two CSV columns: soc_pct,voltage_V. Supply DC resistance separately.')
    z=[];u=[]
    try:
        for row in reader:
            if len(z)>=2048 or None in row:raise ValueError()
            z.append(float(row['soc_pct'])/100);u.append(float(row['voltage_V']))
    except (ValueError,TypeError):raise ValueError('Use 2 to 2,048 numeric CSV rows with charge in percent and voltage in volts.') from None
    if len(z)<2:raise ValueError('The CSV needs at least two charge and voltage points.')
    if not isinstance(metadata,dict):raise ValueError('Include a name, capacity, nominal voltage and DC resistance with the CSV.')
    data=deepcopy(metadata);data.update(kind=BASIC_KIND,reference=dict(soc=z,voltage_V=u))
    return data
