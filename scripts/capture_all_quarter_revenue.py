"""Capture original-period SEC filings and earnings exhibits, append-only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse

from lxml import html

from musa_nowcast.daily_capture import fetch
from musa_nowcast.data import load_actuals
from musa_nowcast.pit_replay import now, save
from musa_nowcast.prospective import sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    root = parser.parse_args().output
    root.mkdir(parents=True, exist_ok=False)
    sources = root/'sources'; sources.mkdir()
    ledger = json.loads(Path('data/accounting_miss_audit/2026-10-07_deeper_v2/sec_submissions.json').read_text())['filings']['recent']
    verified = json.loads(Path('data/peer_surprise/2026-10-07_v2/sources/MUSA_source_checks.json').read_text())['verified']
    save(root/'input_manifest.json', {'frozen_at': now(), 'spec_sha256': sha(Path('data/revenue_gap_all_quarters_spec_v1.json')),
         'actuals_sha256': sha(Path('data/actuals.csv')),
         'submissions_sha256': sha(Path('data/accounting_miss_audit/2026-10-07_deeper_v2/sec_submissions.json')),
         'availability_sha256': sha(Path('data/peer_surprise/2026-10-07_v2/sources/MUSA_source_checks.json'))})
    def archive(url, path, kind, quarter, published):
        if urlparse(url).hostname != 'www.sec.gov':
            raise ValueError('Evidence source outside SEC')
        raw = fetch(url)
        with path.open('xb') as f: f.write(raw)
        return raw, {'quarter': quarter, 'source_type': kind, 'source_url': url,
                     'publication_date': published, 'date_precision': 'DATE_ONLY',
                     'captured_at': now(), 'sha256': sha(path),
                     'raw_file': str(path.relative_to(root)), 'audit_result': 'CAPTURED_PENDING_VALUE_REVIEW'}
    def quarter_capture(a):
        checks = []
        try:
            i = next(i for i, f in enumerate(ledger['form']) if f in ['10-Q','10-K'] and ledger['reportDate'][i] == str(a.end))
            acc = ledger['accessionNumber'][i].replace('-', '')
            url = f'https://www.sec.gov/Archives/edgar/data/1573516/{acc}/{ledger["primaryDocument"][i]}'
            _, check = archive(url, sources/f'{a.quarter}_filing.html', ledger['form'][i], a.quarter, ledger['filingDate'][i]); checks.append(check)
        except Exception as exc:
            checks.append({'quarter': a.quarter, 'source_type': 'SEC_PERIOD_FILING', 'audit_result': 'SOURCE_CAPTURE_FAILED', 'error_type': type(exc).__name__})
        try:
            cover = verified.get(a.quarter)
            if not cover:
                # Candidate earnings 8Ks are verified from cover text, not reportDate.
                candidates = [i for i,f in enumerate(ledger['form']) if f == '8-K' and
                              any(item in ledger['items'][i] for item in ['2.02','7.01']) and str(a.end) < ledger['filingDate'][i] < f'{a.end.year}-09-01']
                for i in candidates:
                    acc = ledger['accessionNumber'][i].replace('-', '')
                    url = f'https://www.sec.gov/Archives/edgar/data/1573516/{acc}/{ledger["primaryDocument"][i]}'
                    raw = fetch(url)
                    text = ' '.join(html.fromstring(raw).text_content().split())
                    if re.search(r'(financial results|earnings).*?June 30,\s*2022', text, re.I):
                        cover = {'url': url, 'available_at': ledger['filingDate'][i]}
                        break
            if not cover:
                raise ValueError('Original earnings cover not verified')
            raw, check = archive(cover['url'], sources/f'{a.quarter}_cover.html', 'SEC_EARNINGS_8K', a.quarter, cover['available_at']); checks.append(check)
            tree = html.fromstring(raw)
            # Earnings sometimes are Exhibit99.2; distinguish from dividends,
            # buybacks and management changes by the exhibit-description row.
            earnings_rows = [tr for tr in tree.xpath('//tr') if re.search(
                r'announcing\s+(its\s+)?(earnings|financial results)',
                ' '.join(tr.text_content().split()), re.I)]
            links = [urljoin(cover['url'], anchor.get('href')) for tr in earnings_rows
                     for anchor in tr.xpath('.//a[@href]')
                     if anchor.get('href').lower().endswith(('.htm','.html'))]
            links = list(dict.fromkeys(links))
            if len(links) != 1:
                raise ValueError('Ambiguous original earnings exhibit link')
            _, check = archive(links[0], sources/f'{a.quarter}_release.html', 'SEC_EARNINGS_EXHIBIT', a.quarter, cover['available_at']); checks.append(check)
        except Exception as exc:
            checks.append({'quarter': a.quarter, 'source_type': 'SEC_EARNINGS_EXHIBIT', 'audit_result': 'SOURCE_CAPTURE_FAILED', 'error_type': type(exc).__name__})
        save(root/f'{a.quarter}_source_checks.json', {'checks': checks})
        print(a.quarter, [(c['source_type'], c['audit_result']) for c in checks], flush=True)
        return checks
    with ThreadPoolExecutor(max_workers=3) as pool:
        checks = [c for rows in pool.map(quarter_capture, load_actuals('data/actuals.csv')) for c in rows]
    save(root/'source_checks.json', {'captured_at': now(), 'checks': checks,
         'original_disclosure_taxonomy_changed': False, 'role': 'POST_RESULTS_REVENUE_AUDIT'})


if __name__ == '__main__':
    main()
