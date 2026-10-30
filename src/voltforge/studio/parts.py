"""Live parts list and listed-price estimate for a design.

Each part is one exact item, priced by averaging its own seller listings. Currencies
are never added together, and an unpriced part stays visibly unpriced, never zero.
"""
from pathlib import Path
import json

VERSION = 'voltforge.parts-prices/1'
SCOPE = 'Listed parts only. Shipping, fabrication, enclosure and assembly are not included.'


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


def estimate(graph, bank, prices):
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
    for slot in ('converter', 'protection'):
        lines.append(line(items.get(f'{slot}:{len(graph["cells"])}') or items[slot], 1, 'part'))
    subtotals = {}
    for row in lines:
        if row['priced']: subtotals[row['currency']] = subtotals.get(row['currency'], 0.)+row['cost']
    return dict(version=VERSION, lines=lines, subtotals=subtotals, unpriced=[r['part'] for r in lines if not r['priced'] and not r.get('included')],
                cell_mass_g=physical['cell_mass_g'], listed_mass_g=physical['listed_component_mass_g'], scope=SCOPE, checked=prices.get('checked'))
