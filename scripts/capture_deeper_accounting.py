"""Targeted six-miss filing and issuer-hosted transcript evidence, append-only."""
import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urljoin

import requests
from lxml import html

from musa_nowcast.daily_capture import fetch
from musa_nowcast.pit_replay import now, save
from musa_nowcast.prospective import sha

PERIODS={'2021Q2':'2021-06-30','2021Q4':'2021-12-31','2022Q1':'2022-03-31',
         '2022Q3':'2022-09-30','2023Q3':'2023-09-30','2026Q2':'2026-06-30'}
SUBTYPES={'First Quarter':'1','Second Quarter':'2','Third Quarter':'3','Fourth Quarter':'4'}
HOST='https://ir.corporate.murphyusa.com'


def candidates(text):
    words=r'LIFO|FIFO|weighted.average|inventory|inventories|replacement cost|acquisition cost|spot.to.rack|timing|pricing adjustment'
    spans=[]
    for m in re.finditer(words,text,re.I):
        start,end=max(0,m.start()-400),min(len(text),m.end()+700)
        if spans and start<=spans[-1][1]:spans[-1]=(spans[-1][0],max(end,spans[-1][1]))
        else:spans.append((start,end))
    return [{'start_offset':s,'end_offset':e,'text':text[s:e]} for s,e in spans]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();root=args.output
    root.mkdir(parents=True,exist_ok=False)
    raw=fetch('https://data.sec.gov/submissions/CIK0001573516.json')
    with (root/'sec_submissions.json').open('xb') as f:f.write(raw)
    recent=json.loads(raw)['filings']['recent'];checks=[]
    for quarter,period in PERIODS.items():
        index=next(i for i,form in enumerate(recent['form']) if form in ('10-Q','10-K') and recent['reportDate'][i]==period)
        accession=recent['accessionNumber'][index].replace('-','')
        url=f'https://www.sec.gov/Archives/edgar/data/1573516/{accession}/{recent["primaryDocument"][index]}'
        raw=fetch(url);path=root/f'{quarter}_filing.html'
        with path.open('xb') as f:f.write(raw)
        tree=html.fromstring(raw,parser=html.HTMLParser(encoding='utf-8'))
        for e in tree.xpath('//script|//style'):e.drop_tree()
        text=' '.join(tree.text_content().split())
        save(root/f'{quarter}_filing_candidates.json',{'candidates':candidates(text),'status':'PENDING_MANUAL_BASIS_REVIEW'})
        checks.append({'quarter':quarter,'source_type':recent['form'][index],'source_url':url,
          'publication_date':recent['filingDate'][index],'available_at_precision':'DATE_ONLY',
          'captured_at':now(),'sha256':sha(path),'raw_file':path.name,'audit_result':'CAPTURED_PENDING_REVIEW',
          'source_usable_at_quarter_end':False})
    # Public read-only service and parameters used by the issuer's quarterly-results page.
    endpoint=HOST+'/Services/FinancialReportService.svc/GetFinancialReportList'
    page_url=HOST+'/investor-relations/financial-information/quarterly-results/default.aspx'
    page=fetch(page_url)
    with (root/'issuer_quarterly_results.html').open('xb') as f:f.write(page)
    payload={'serviceDto':{'ViewType':'2','ViewDate':'','RevisionNumber':'1','LanguageId':'1','Signature':'',
      'ItemCount':-1,'StartIndex':0,'TagList':[],'IncludeTags':True},'excludeSelection':1,'year':-1,
      'reportTypes':'|'.join(SUBTYPES),'reportSubType':list(SUBTYPES),'reportSubTypeList':list(SUBTYPES)}
    try:
        response=requests.post(endpoint,json=payload,timeout=30)
        response.raise_for_status()
        raw=response.content
        with (root/'issuer_report_index.json').open('xb') as f:f.write(raw)
        items=response.json()['GetFinancialReportListResult']
        save(root/'issuer_report_index_request.json',{'endpoint':endpoint,'request':payload,
          'source_page':page_url,'sha256':sha(root/'issuer_report_index.json'),'captured_at':now()})
        for quarter in PERIODS:
            reports=[r for r in items if str(r['ReportYear'])==quarter[:4] and SUBTYPES.get(r['ReportSubType'])==quarter[-1]]
            docs=[d for r in reports for d in r['Documents'] if re.search(r'transcript|commentary|prepared remarks',d['DocumentTitle'],re.I)]
            if not docs:
                checks.append({'quarter':quarter,'source_type':'ISSUER_CALL_INDEX','source_url':page_url,
                  'captured_at':now(),'audit_result':'NO_LINK_IN_CHECKED_INDEX_NOT_NO_DISCLOSURE'})
            for n,doc in enumerate(docs):
                url=urljoin(HOST,doc['DocumentPath'])
                try:
                    raw=fetch(url);path=root/f'{quarter}_call_{n}.pdf'
                    if not raw.startswith(b'%PDF'):raise ValueError('linked call is not PDF')
                    with path.open('xb') as f:f.write(raw)
                    converted=subprocess.run(['pdftotext','-layout',str(path),'-'],check=True,capture_output=True).stdout.decode('utf-8')
                    save(root/f'{quarter}_call_{n}_text.json',{'title':doc['DocumentTitle'],
                        'text':converted,'candidates':candidates(' '.join(converted.split())),'status':'PENDING_MANUAL_REVIEW'})
                    checks.append({'quarter':quarter,'source_type':'ISSUER_HOSTED_CALL_PDF','source_url':url,
                      'document_title':doc['DocumentTitle'],'captured_at':now(),'sha256':sha(path),
                      'raw_file':path.name,'audit_result':'CAPTURED_PENDING_REVIEW','source_usable_at_quarter_end':False})
                except Exception as exc:
                    checks.append({'quarter':quarter,'source_type':'ISSUER_HOSTED_CALL_PDF','source_url':url,
                      'captured_at':now(),'audit_result':'CAPTURE_FAILED_NOT_NO_DISCLOSURE','error':str(exc)})
    except Exception as exc:
        checks.append({'source_type':'ISSUER_CALL_INDEX','source_url':endpoint,'captured_at':now(),
          'audit_result':'CAPTURE_FAILED_NOT_NO_DISCLOSURE','error':str(exc)})
    save(root/'source_checks.json',{'scope':'SIX_LARGEST_PRODUCTION_MISSES_FILINGS_AND_ISSUER_CALL_LINKS',
      'source_checks':checks,'production_changed':False,'original_disclosure_audit_changed':False,
      'script_sha256':sha(Path(__file__)),'created_at':now()})
    print(json.dumps({'captured_sources':sum(c['audit_result']=='CAPTURED_PENDING_REVIEW' for c in checks),
                      'other_checks':[c for c in checks if c['audit_result']!='CAPTURED_PENDING_REVIEW']},indent=2))


if __name__=='__main__':main()
