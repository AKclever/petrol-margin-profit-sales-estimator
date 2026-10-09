"""Original SEC earnings exhibits for post-spin 2013Q3-2018Q4 targets."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urljoin

from lxml import html

from musa_nowcast.daily_capture import fetch
from musa_nowcast.pit_replay import now,save
from musa_nowcast.prospective import sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    root=parser.parse_args().output;root.mkdir(parents=True,exist_ok=False)
    raw=fetch('https://data.sec.gov/submissions/CIK0001573516-submissions-001.json')
    with (root/'older_submissions.json').open('xb') as f:f.write(raw)
    older=json.loads(raw)
    recent=json.loads(Path('data/accounting_miss_audit/2026-10-07_deeper_v2/sec_submissions.json').read_text())['filings']['recent']
    candidates=[]
    for ledger in [older,recent]:
        for i,form in enumerate(ledger['form']):
            if form=='8-K' and any(item in ledger['items'][i] for item in ['2.02','7.01']) and '2013-08-01' <= ledger['filingDate'][i] <= '2019-03-15':
                candidates.append({k:ledger[k][i] for k in ['accessionNumber','primaryDocument','filingDate']})
    def capture(c):
        acc=c['accessionNumber'].replace('-','')
        url=f'https://www.sec.gov/Archives/edgar/data/1573516/{acc}/{c["primaryDocument"]}'
        checks=[]
        try:
            raw=fetch(url);path=root/f'{acc}_cover.html'
            with path.open('xb') as f:f.write(raw)
            tree=html.fromstring(raw);text=' '.join(tree.text_content().split())
            match=re.search(r'Item\s*2\.02\.?(.*?)(?=Item\s*\d\.\d\d|Signature|$)',text,re.I)
            evidence=match[1] if match else text
            quarters=[]
            for year in range(2013,2019):
                for q,month,day in [(1,'March',31),(2,'June',30),(3,'September',30),(4,'December',31)]:
                    key=f'{year}Q{q}'
                    if key<'2013Q3':continue
                    stamp=f'{month} {day}, {year}'
                    if stamp in evidence and re.search(r'financial results|earnings',evidence,re.I):quarters.append(key)
            # Covers sometimes mention prior comparatives: only the latest ended
            # quarter near filing is an original-period candidate.
            quarters=[q for q in quarters if 0<(date.fromisoformat(c['filingDate'])-date(int(q[:4]),3*int(q[-1]),[31,30,30,31][int(q[-1])-1])).days<100]
            if len(quarters)!=1:
                return [{'source_url':url,'raw_file':path.name,'sha256':sha(path),'status':'COVER_NOT_UNAMBIGUOUS_PERIOD_RESULT'}]
            q=quarters[0]
            check={'quarter':q,'source_url':url,'raw_file':path.name,'sha256':sha(path),
                   'available_at':c['filingDate'],'availability_basis':'SEC_FILING_DATE_CONSERVATIVE_DATE_ONLY',
                   'captured_at':now(),'evidence':evidence[:1600],'source_type':'SEC_EARNINGS_COVER','status':'PERIOD_VERIFIED'}
            checks.append(check)
            rows=[tr for tr in tree.xpath('//tr') if re.search(r'announcing\s+(its\s+)?(earnings|financial results)', ' '.join(tr.text_content().split()),re.I)]
            links=[urljoin(url,a.get('href')) for tr in rows for a in tr.xpath('.//a[@href]') if a.get('href').lower().endswith(('.htm','.html'))]
            if not links:
                links=[urljoin(url,a.get('href')) for a in tree.xpath('//a[@href]') if re.search(r'99[._-]?1',a.text_content()+' '+a.get('href'),re.I) and a.get('href').lower().endswith(('.htm','.html'))]
            links=list(dict.fromkeys(links))
            if not links:
                # Older covers have an exhibit description but no hyperlink.
                # Resolve the exact EX-99.1 document from the official filing index.
                index_url=urljoin(url,c['accessionNumber']+'-index.htm')
                index_raw=fetch(index_url);index_path=root/f'{acc}_index.html'
                with index_path.open('xb') as f:f.write(index_raw)
                index_tree=html.fromstring(index_raw)
                exhibit_rows=[tr for tr in index_tree.xpath('//tr') if 'EX-99.1' in tr.text_content()]
                links=[urljoin(index_url,a.get('href')) for tr in exhibit_rows for a in tr.xpath('.//a[@href]')
                       if a.get('href').lower().endswith(('.htm','.html'))]
                links=list(dict.fromkeys(links))
                checks.append({'quarter':q,'source_url':index_url,'raw_file':index_path.name,
                    'sha256':sha(index_path),'source_type':'SEC_EXHIBIT_INDEX','status':'CHECKED_EXHIBIT_LINK'})
            if len(links)!=1:raise ValueError('Ambiguous exhibit')
            raw=fetch(links[0]);path=root/f'{q}_release.html'
            with path.open('xb') as f:f.write(raw)
            checks.append({'quarter':q,'source_url':links[0],'raw_file':path.name,'sha256':sha(path),
                   'available_at':c['filingDate'],'captured_at':now(),'source_type':'SEC_EARNINGS_EXHIBIT',
                   'status':'CAPTURED_PENDING_TARGET_RECONCILIATION'})
            print(q,'SEC_EXHIBIT_CAPTURED',flush=True)
        except Exception as exc:checks.append({'source_url':url,'status':'SOURCE_FAILED','error_type':type(exc).__name__})
        return checks
    with ThreadPoolExecutor(max_workers=3) as pool:checks=[c for rows in pool.map(capture,candidates) for c in rows]
    save(root/'source_checks.json',{'checks':checks,'created_at':now(),'metadata_sha256':sha(root/'older_submissions.json')})


if __name__=='__main__':main()
