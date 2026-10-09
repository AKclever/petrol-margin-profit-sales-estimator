"""Descriptive all-quarter revenue audit, with no fitted forecasting adjustment."""
from datetime import date
import math
import re
from statistics import mean

from lxml import html

LARGE_MISS_QUARTERS = {'2021Q2','2021Q4','2022Q1','2022Q3','2023Q3','2026Q2'}


def rows_from_html(raw):
    tree = html.fromstring(raw, parser=html.HTMLParser(encoding='utf-8'))
    rows = [[' '.join(c.text_content().split()) for c in tr.xpath('./td|./th')]
            for tr in tree.xpath('//tr')]
    return tree, rows


def decimal_values(cells):
    return [float(s.replace(',', '')) for c in cells
            for s in re.findall(r'(?<![\w.])\d[\d,]*\.\d+(?![\w.])', c)]


def reported_volume_and_margin(raw):
    _, rows = rows_from_html(raw)
    result = {}
    for cells in rows:
        if not cells:
            continue
        label = cells[0].lower()
        for key, pattern in [('gallons_million', r'^retail fuel volume\s*-\s*chain'),
                             ('retail_margin_cpg', r'^retail fuel margin')]:
            if key not in result and re.search(pattern, label):
                values = decimal_values(cells[1:])
                if values:
                    result[key] = {'value': values[0], 'evidence': cells}
    if set(result) != {'gallons_million','retail_margin_cpg'}:
        raise ValueError('Quarterly retail gallons/margin not verified in earnings table')
    return result


def reported_sss(raw):
    tree, rows = rows_from_html(raw)
    text = ' '.join(tree.text_content().split())
    match = re.search(r'volumes on a same[ -]store sales.{0,60}?basis\s+(increased|improved|declined|decreased)\s+([\d.]+)%', text, re.I)
    if not match:
        return {'value': None, 'status': 'UNRESOLVED_DIRECT_SSS_STATEMENT', 'evidence': None}
    value = float(match[2]) * (-1 if match[1].lower() in ['declined','decreased'] else 1)
    # Corroborate against the SSS/APSM variance table, never against changing
    # same-store volume levels. The first percentage is the quarterly SSS rate.
    table_value = None; table_evidence = None
    for cells in rows:
        if not cells or cells[0] != 'Fuel gallons per month':
            continue
        numbers = decimal_values(cells[1:])
        if numbers:
            remainder = ' '.join(cells[1:])
            first = re.search(r'\(?\s*-?\s*\d[\d,]*\.\d+\s*\)?', remainder)
            table_value = numbers[0] * (-1 if first and ('(' in first[0] or '-' in first[0]) else 1)
            table_evidence = cells
            break
    if table_value is not None and abs(table_value-value) > .001:
        raise ValueError('Quarterly same-store growth statement/table disagree')
    return {'value': value, 'status': 'VERIFIED_DIRECT_STATEMENT', 'evidence': match[0],
            'table_value': table_value, 'table_evidence': table_evidence}


def pearson(x, y):
    if len(x) != len(y):
        raise ValueError('Correlation observations must be paired')
    if len(x) < 3:
        return None
    mx, my = mean(x), mean(y)
    vx = sum((v-mx)**2 for v in x); vy = sum((v-my)**2 for v in y)
    if vx == 0 or vy == 0:
        return None
    return sum((a-mx)*(b-my) for a,b in zip(x,y)) / math.sqrt(vx*vy)


def ranks(values):
    result = [0.0]*len(values)
    for value in set(values):
        positions = [i+1 for i,v in enumerate(sorted(values)) if v == value]
        rank = mean(positions)
        for i,v in enumerate(values):
            if v == value:
                result[i] = rank
    return result


def association(rows, x_key, y_key):
    valid = [r for r in rows if r.get(x_key) is not None and r.get(y_key) is not None]
    x = [r[x_key] for r in valid]; y = [r[y_key] for r in valid]
    return {'n': len(valid), 'quarters': [r['quarter'] for r in valid],
            'pearson_r': pearson(x,y), 'spearman_r': pearson(ranks(x), ranks(y))}


def lagged_rows(rows):
    indexed = {r['quarter']: r for r in rows}
    result = []
    for target in rows:
        year, q = int(target['quarter'][:4]), int(target['quarter'][-1])
        previous = f'{year if q>1 else year-1}Q{q-1 if q>1 else 4}'
        prior = indexed.get(previous)
        if not prior or prior.get('revenue_proxy_error_cpg') is None or target.get('actual_minus_production_cpg') is None:
            continue
        available = prior.get('revenue_gap_available_at')
        if not available or date.fromisoformat(available) >= date.fromisoformat(target['quarter_end']):
            continue
        result.append({'quarter': target['quarter'], 'prior_quarter': previous,
                       'prior_gap_available_at': available, 'target_quarter_end_cutoff': target['quarter_end'],
                       'previous_revenue_gap_cpg': prior['revenue_proxy_error_cpg'],
                       'actual_minus_production_cpg': target['actual_minus_production_cpg']})
    return result


def summarize(rows):
    lagged = lagged_rows(rows)
    groups = {}
    for label, group in [('previous_six_large_misses', [r for r in rows if r['quarter'] in LARGE_MISS_QUARTERS]),
                         ('other_oof_quarters', [r for r in rows if r['quarter'] not in LARGE_MISS_QUARTERS and r.get('actual_minus_production_cpg') is not None])]:
        available = [r for r in group if r.get('revenue_proxy_error_cpg') is not None]
        groups[label] = {'n': len(available),
                        'mean_abs_revenue_gap_cpg': mean(abs(r['revenue_proxy_error_cpg']) for r in available) if available else None,
                        'mean_abs_margin_error_cpg': mean(abs(r['actual_minus_production_cpg']) for r in available) if available else None,
                        'gap_vs_error': association(available,'revenue_proxy_error_cpg','actual_minus_production_cpg'),
                        'gap_vs_volume': association(available,'revenue_proxy_error_cpg','reported_same_store_gallon_growth_percent')}
    return {'coverage': {'total_quarters': len(rows),
                         'retail_revenue_quarters': sum(r.get('reported_revenue_per_gallon_cpg') is not None for r in rows),
                         'direct_sss_quarters': sum(r.get('reported_same_store_gallon_growth_percent') is not None for r in rows),
                         'yoy_gap_quarters': sum(r.get('revenue_proxy_error_cpg') is not None for r in rows),
                         'production_oof_quarters': sum(r.get('actual_minus_production_cpg') is not None for r in rows)},
            'gap_vs_same_quarter_volume': association(rows,'revenue_proxy_error_cpg','reported_same_store_gallon_growth_percent'),
            'gap_vs_same_quarter_margin_error': association(rows,'revenue_proxy_error_cpg','actual_minus_production_cpg'),
            'lagged_gap_vs_next_margin_error': association(lagged,'previous_revenue_gap_cpg','actual_minus_production_cpg'),
            'lagged_rows': lagged, 'groups': groups,
            'production_changed': False, 'new_coefficients_fitted': False,
            'causal_interpretation_authorized': False,
            'current_quarter_gap_is_available_before_results': False}
