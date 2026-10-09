"""Frozen accounting-proxy diagnostics and publication-filtered forward benchmarks.

These are not new production forecasts or independent acquisition-cost estimates.
"""
from datetime import date, timedelta
import math
import re
from statistics import mean, median

from lxml import html


def cutoff_two_quarters_ahead(target_start):
    index = target_start.year * 4 + (target_start.month - 1) // 3 - 2
    year, quarter = divmod(index, 4)
    next_start = date(year + (quarter == 3), ((quarter + 1) % 4) * 3 + 1, 1)
    return next_start - timedelta(days=1)


def forward_rows(actuals, verified):
    rows = []
    for target in actuals:
        cutoff = cutoff_two_quarters_ahead(target.start)
        known = [a for a in actuals if a.end < cutoff and
                 a.quarter in verified and date.fromisoformat(verified[a.quarter]['available_at']) < cutoff]
        known.sort(key=lambda a: a.end)
        seasons = [a.retail_margin_cpg for a in known if a.start.month == target.start.month]
        prior = next((a for a in known if a.start.year == target.start.year - 1 and
                      a.start.month == target.start.month), None)
        if len(known) < 8 or not seasons or prior is None:
            continue
        rows.append({'quarter': target.quarter, 'information_cutoff': str(cutoff),
                     'latest_published_quarter': known[-1].quarter,
                     'known_quarters': [a.quarter for a in known],
                     'actual_cpg': target.retail_margin_cpg,
                     'prior_year_same_quarter': prior.retail_margin_cpg,
                     'median_previous_same_quarters': median(seasons),
                     'mean_last_four_published_quarters': mean(a.retail_margin_cpg for a in known[-4:])})
    return rows


def metrics(rows, key):
    if not rows:
        return {'n': 0, 'mae_cpg': None, 'rmse_cpg': None}
    errors = [r[key] - r['actual_cpg'] for r in rows]
    return {'n': len(rows), 'mae_cpg': mean(abs(e) for e in errors),
            'rmse_cpg': math.sqrt(mean(e*e for e in errors)),
            'max_abs_error_cpg': max(abs(e) for e in errors)}


def revenue_pairs(raw, annual=False):
    """Retail-only revenue rows; duplicate consolidated columns are validated."""
    tree = html.fromstring(raw, parser=html.HTMLParser(encoding='utf-8'))
    pairs = []
    for tr in tree.xpath('//tr'):
        cells = [' '.join(c.text_content().split()) for c in tr.xpath('./td|./th')]
        if not cells or not re.search(r'Petroleum product sales\s*\(at retail\)', cells[0]):
            continue
        values = [float(x.replace(',', '')) for c in cells[1:]
                  for x in re.findall(r'(?<![\w.])\d[\d,]*\.\d+(?![\w.])', c)]
        if annual:
            if len(values) < 2:
                raise ValueError('Annual retail revenues missing comparative')
            pairs.append((values[0], values[1], cells))
        else:
            if len(values) != 4 or values[0] != values[1] or values[2] != values[3]:
                raise ValueError('Retail revenue columns do not reconcile')
            pairs.append((values[0], values[2], cells))
    if not pairs:
        raise ValueError('No retail-only petroleum revenue row')
    return pairs


def decompose(current_revenue, prior_revenue, current_gallons, prior_gallons,
              eia_change, actual_margin, production):
    if min(current_gallons, prior_gallons) <= 0:
        raise ValueError('Positive reported gallons required')
    revenue = 100 * current_revenue / current_gallons
    prior = 100 * prior_revenue / prior_gallons
    proxy = prior + eia_change
    gap = revenue - proxy
    residual = gap - (actual_margin - production)
    return {'reported_revenue_per_gallon_cpg': revenue,
            'prior_reported_revenue_per_gallon_cpg': prior,
            'eia_yoy_retail_change_cpg': eia_change,
            'revenue_proxy_cpg': proxy, 'revenue_proxy_error_cpg': gap,
            'implied_cost_residual_cpg': residual,
            'actual_minus_production_cpg': actual_margin - production,
            'identity_reconciliation_cpg': gap - residual - (actual_margin - production)}
