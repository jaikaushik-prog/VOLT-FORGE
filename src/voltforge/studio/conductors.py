"""Declared rectangular conductors: bulk/contact resistance and material mass.

Dimensions are independent of canvas pixels. This is a DC calculation at the
declared material reference temperature, not a conductor-temperature model.
"""
from copy import deepcopy
import math

VERSION='voltforge.rectangular-conductor/1'
COPPER_SOURCE='https://copper.org/resource-library/characteristics-and-properties-of-copper-and-copper-alloy-p-m-materials/'


def copper_reference():
    return dict(version=VERSION,material='Fully dense copper reference',length_mm=30.,width_mm=8.,thickness_mm=.2,
                contact_mohm=.2,resistivity_ohm_m=1.71e-8,density_kg_m3=8940.,reference_temperature_C=20.,
                material_source=COPPER_SOURCE+' Table 3: 1.71 microohm-cm and 8.94 g/cm³ at 20 °C.',
                assumption_source='Declared rectangular link dimensions and total resistance of both end contacts; not a measured joint.')


def calculate(c):
    """SI conversion: R=rho*L/A; m=density*L*A, plus both end contacts."""
    from .network import number
    if not isinstance(c,dict) or set(c)!=set(copper_reference()) or c['version']!=VERSION:
        raise ValueError('Use a supported rectangular-conductor definition.')
    for key,low,high in [('length_mm',.001,100000.),('width_mm',.001,10000.),('thickness_mm',.001,1000.),
                         ('contact_mohm',0.,1000.),('resistivity_ohm_m',1e-12,1.),('density_kg_m3',1.,100000.),
                         ('reference_temperature_C',-273.,2000.)]:
        number(c[key],key,low,high)
    for key,limit in [('material',120),('material_source',2000),('assumption_source',2000)]:
        if not isinstance(c[key],str) or not 1<=len(c[key].strip())<=limit:
            raise ValueError('Record the conductor material and the source of its dimensions, contacts and properties.')
    length=c['length_mm']*.001;area=c['width_mm']*c['thickness_mm']*1e-6
    bulk=1000*c['resistivity_ohm_m']*length/area
    total=bulk+c['contact_mohm']
    number(total,'Calculated connection resistance',0.,1000.)
    return dict(resistance_mohm=total,bulk_resistance_mohm=bulk,contact_mohm=c['contact_mohm'],
                area_mm2=area*1e6,volume_mm3=length*area*1e9,mass_g=1000*c['density_kg_m3']*length*area,
                reference_temperature_C=c['reference_temperature_C'])


def apply(wire,definition):
    values=calculate(definition)
    wire['conductor']=deepcopy(definition);wire['resistance_mohm']=values['resistance_mohm']
    wire['source']='Calculated from rectangular-conductor dimensions and total end-contact resistance; full sources saved with this connection.'
    return wire


def validate_wire(wire):
    if 'conductor' not in wire:return
    expected=calculate(wire['conductor'])['resistance_mohm']
    if not math.isclose(wire['resistance_mohm'],expected,rel_tol=1e-10,abs_tol=1e-10):
        raise ValueError('Connection resistance does not match its conductor dimensions. Recalculate it or use a direct resistance assumption.')


def add_contact_resistance(wire,extra,source):
    if 'conductor' in wire:
        c=deepcopy(wire['conductor']);c['contact_mohm']+=extra;c['assumption_source']=source
        apply(wire,c)
    else:wire['resistance_mohm']+=extra
    wire['source']=source


def physical_summary(graph,models):
    links=[dict(connection=w['id'],**calculate(w['conductor']),definition=deepcopy(w['conductor']))
           for w in graph['connections'] if 'conductor' in w]
    cell_specs=[]
    for c in graph['cells']:
        record=models[c['model']];geometry=record.get('geometry')
        if geometry:
            cell_specs.append(dict(cell=c['id'],geometry=deepcopy(geometry),
                                   source=record.get('operating_limits',{}).get('source_url',record.get('source',{}).get('url'))))
    all_cells=len(cell_specs)==len(graph['cells']) and all(s['geometry'].get('mass_kg') is not None for s in cell_specs)
    cell_mass=1000*sum(s['geometry']['mass_kg'] for s in cell_specs) if all_cells else None
    routes=[dict(output=pole,connection=pole+' output route',**calculate(c),definition=deepcopy(c)) for pole,c in graph.get('output_leads',{}).items()]
    conductor_mass=sum(link['mass_g'] for link in links+routes)
    return dict(conductors=links,output_routes=routes,conductor_mass_g=conductor_mass if links or routes else None,
                dimensioned_connections=len(links),undimensioned_connections=len(graph['connections'])-len(links),
                cells=cell_specs,cell_mass_g=cell_mass,
                listed_component_mass_g=cell_mass+conductor_mass if all_cells else None,
                complete_assembly_mass=False,
                scope='Listed cell and specified-conductor mass only. Unspecified external routing, terminals, insulation, enclosure, cooling hardware and fabrication are not included. Material volume is not an assembly bounding box. Resistance uses the declared material reference temperature; conductor self-heating and ampacity are not modeled. Specified output-route losses go to the surroundings rather than into the cells.')
