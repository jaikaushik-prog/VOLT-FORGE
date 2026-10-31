"""Live parts list and listed-price estimate for a design.

Each part is one exact item, priced by averaging its own seller listings. Currencies
are never added together, and an unpriced part stays visibly unpriced, never zero.
"""
from pathlib import Path
import json

VERSION = 'voltforge.parts-prices/1'
SCOPE = 'Listed cells and candidate parts only; a price does not establish compatibility or protection. Shipping, fabrication, enclosure and assembly are not included.'


def load_prices(root):
    path = Path(root)/'configs'/'parts_prices_v1.json'
    data = json.loads(path.read_text())
    if data.get('version') != VERSION: raise ValueError('Unsupported price list.')
    return data


def unit_price(item):
    listings = item.get('listings') or []
    if not listings: return None
    currency = {x['currency'] for x in listings}
    if len(currency) != 1: raise ValueError(f'{item["name"]}: average listings in one currency only.')
    return dict(value=sum(x['price'] for x in listings)/len(listings), currency=currency.pop(), listing_count=len(listings))


def line(item, quantity, unit, multiplier=1.):
    price = unit_price(item)
    row = dict(specification=item.get('specification'), limits=item.get('limits'), part=item['name'], slot=item['slot'], quantity=quantity, unit=unit, listings=item.get('listings', []), exclusions=item.get('exclusions', ''), checked=item.get('checked'))
    if item.get('included_in'): return dict(row, priced=False, included=True, note=item['note'])
    if price is None: return dict(row, priced=False, note=item.get('note', 'Not priced yet'))
    return dict(row, priced=True, unit_price=price['value'], currency=price['currency'], listing_count=price['listing_count'], cost=price['value']*quantity*multiplier)


def board_compatibility(graph, bank, item, settings=None):
    """Bounded screening of a priced candidate, never a hardware approval.

    A supported holder count is only one condition. Unpublished input-current,
    charge/protection and efficiency behavior remains unassessed even when the
    elementary topology and output-power checks are consistent.
    """
    from .design_rules import groups
    name=item['name']; count=len(graph['cells'])
    slots=2 if 'X1205' in name else 4 if 'X1206' in name else None
    incompatible=[]; unknown=[]
    if slots is None:
        unknown.append('No electrical compatibility specification is recorded for this candidate.')
    elif count!=slots:
        if count>slots:incompatible.append(f'The {slots}-slot candidate cannot hold {count} cells.')
        else:unknown.append(f'Operation with {count} cells in this {slots}-slot board is not established.')
    if count:
        root=groups(graph)
        positive={root(c['id']+':p') for c in graph['cells']}
        negative={root(c['id']+':n') for c in graph['cells']}
        parallel=(len(positive)==len(negative)==1 and positive!=negative
                  and graph['output']['positive'] is not None and graph['output']['negative'] is not None
                  and root(graph['output']['positive']) in positive and root(graph['output']['negative']) in negative)
        if slots and not parallel:
            incompatible.append('This candidate is for a single-voltage parallel battery, not the drawn series, mixed, disconnected or reversed-output arrangement.')
        records=[bank[c['model']] for c in graph['cells']]
        families={r.get('key',c['model']) for c,r in zip(graph['cells'],records)}
        if slots and len(families)>1:
            incompatible.append('The board maker does not support mixing different cell types in its holder.')
        if slots and any(r.get('key') not in ('LG_M50T_ECN','SAMSUNG_30T') or r.get('origin')=='user' for r in records):
            unknown.append('Cell chemistry, voltage range and 21700 holder fit have not been established for every supplied cell model.')
    else:
        unknown.append('Add a battery arrangement before assessing the candidate.')
    from .loads import power_proxy_assessment
    demand=power_proxy_assessment(settings)
    power=demand['power_W']
    if slots and power is not None and power>5.1*6:
        incompatible.append('The declared load exceeds the candidate board\'s 5.1 V, 6 A output envelope (30.6 W).')
    elif power is None:
        unknown.append(demand['reason'])
    status='incompatible' if incompatible else 'not_assessed' if unknown else 'conditional'
    conditions=['Battery-side current limits, contact/trace losses, backup efficiency and actual charger/protection settings remain unassessed.',
                'The drawn wiring and cell temperature sensing must match the assembled board; an ideal virtual switch is not its protection circuit.']
    if slots==2:
        conditions += ['The advertised 95% belongs to the external-input step-down converter, not a measured battery-to-Pi efficiency curve.',
                       'The advertised charger maximum is 3 A total. Check each cell\'s charge limit and unequal sharing; two LG M50T cells at 23 C have a deployed equal-share ceiling of 2.91 A before margin.',
                       'The documented v1.1 2.4 V hardware cutoff does not implement the mission\'s 3.3 V floor or the LG cell model\'s 2.5 V cutoff.']
    return dict(status=status,reasons=incompatible+unknown,conditions=conditions,demand=demand,
                source_url='https://wiki.geekworm.com/'+('X1205' if slots==2 else 'X1206') if slots else None,
                note='Candidate screening only; no board has been validated for this design.')


def estimate(graph, bank, prices, settings=None):
    from .conductors import physical_summary
    items = prices['items']; lines = []
    counts = {}
    for c in graph['cells']: counts[c['model']] = counts.get(c['model'], 0)+1
    for key, quantity in counts.items():
        item = items.get('cell:'+key) or dict(name=bank[key].get('name', key), slot='cell')
        lines.append(line(item, quantity, 'cells'))
    physical = physical_summary(graph, bank)
    if physical['conductor_mass_g']:
        lines.append(line(items['copper'], physical['conductor_mass_g'], 'g of copper', .001))
    elif graph['connections']:
        lines.append(dict(part='Connections', slot='conductor', quantity=len(graph['connections']), unit='links', priced=False, listings=[], note='Give the links dimensions to price them.'))
    converter=items.get(f'converter:{len(graph["cells"])}') or items['converter']
    compatibility=board_compatibility(graph,bank,converter,settings)
    board=line(converter,1,'candidate part')
    board.update(selection='candidate',compatibility=compatibility)
    if 'X1205' in converter['name']:
        board['listed_limits']=board.get('limits')
        board['limits']='Battery-to-Pi efficiency and battery overcurrent threshold are unmeasured. The advertised 95% refers to the external-input step-down path. The documented v1.1 cutoff is 2.4 V; charge-path compatibility remains unassessed.'
    lines.append(board)
    protection=line(items.get(f'protection:{len(graph["cells"])}') or items['protection'],1,'candidate part')
    protection.update(selection='candidate',included=False,included_in_candidate=bool(protection.get('included')),
                      compatibility=dict(status='not_assessed',reasons=['Protection listed on a candidate board does not establish protection of this drawn battery.'],
                                         conditions=compatibility['conditions']),
                      note='Listed on candidate board; compatibility and cell protection remain unassessed.')
    lines.append(protection)
    subtotals = {}; cell_subtotals = {}
    for row in lines:
        if row['priced']:
            subtotals[row['currency']] = subtotals.get(row['currency'], 0.)+row['cost']
            if row['slot']=='cell':cell_subtotals[row['currency']]=cell_subtotals.get(row['currency'],0.)+row['cost']
    return dict(version=VERSION, lines=lines, subtotals=subtotals, unpriced=[r['part'] for r in lines if not r['priced'] and not r.get('included')],
                cell_subtotals=cell_subtotals,cell_cost_complete=bool(counts) and all(r['priced'] for r in lines if r['slot']=='cell'),
                cell_mass_g=physical['cell_mass_g'], listed_mass_g=physical['listed_component_mass_g'], scope=SCOPE, checked=prices.get('checked'))
