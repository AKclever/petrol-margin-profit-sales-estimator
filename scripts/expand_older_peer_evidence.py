"""Append-only original older peer exhibits; unresolved rows stay unresolved."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
import json
from pathlib import Path
import re
from urllib.parse import urljoin

from lxml import html

from musa_nowcast.daily_capture import fetch
from musa_nowcast.couchetard_peer import parse_release
from musa_nowcast.pit_replay import now, save
from musa_nowcast.prospective import sha


def caseys_target(raw):
    tree=html.fromstring(raw,parser=html.HTMLParser(encoding='utf-8'))
    text=' '.join(tree.text_content().split())
    section=re.search(r'Fuel\s*[-–—]\s*(.*?)(?:Grocery and Other Merchandise|Grocery & Other)',text,re.I)
    if section:
        match=re.search(r'For the (?:first |second |third |fourth )?quarter.{0,160}?average margin of ([\d.]+) cents per gallon',section[1],re.I)
        if match:
            return {'status':'VERIFIED_DIRECT_QUARTERLY_REPORTED_BASIS',
                    'reported_margin_cpg':float(match[1]),'evidence':match[0],
                    'rin_context':section[1],
                    'target_basis':'CASEYS_REPORTED_FUEL_MARGIN_INCLUDES_RIN_WHERE_DISCLOSED_NOT_MUSA_RETAIL',
                    'usable_for_new_forecast_model':False}
    paragraphs=[' '.join(p.text_content().split()) for p in tree.xpath('//p')]
    matches=[]
    for text in paragraphs:
        # Explicit quarterly achieved margin, never annual goal or YTD margin.
        for m in re.finditer(r'(?:for (?:the |its )?(?:first|second|third|fourth) quarter|(?:during |for )the quarter|this quarter|quarterly).{0,180}?(?:fuel margin|average margin|margin).{0,35}?([\d.]+)\s*cents per gallon',text,re.I):
            if re.search(r'goal|guidance|expect|year.to.date',m[0],re.I):continue
            matches.append({'value_cpg':float(m[1]),'evidence':m[0]})
    if len({r['value_cpg'] for r in matches}) != 1:
        return {'status':'PENDING_NUMERIC_BASIS_REVIEW','candidates':matches}
    return {'status':'DIRECT_QUARTERLY_NUMBER_PENDING_RIN_BASIS_RECONCILIATION',
            'reported_margin_cpg':matches[0]['value_cpg'],'evidence':matches,
            'target_basis':'CASEYS_REPORTED_FUEL_MARGIN_POTENTIALLY_INCLUDES_RIN_NOT_MUSA_RETAIL',
            'usable_for_new_forecast_model':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    root=p.parse_args().out;root.mkdir(parents=True,exist_ok=False)
    jobs=[]
    # SEC recent submissions cover Casey's back to 2011 in this archived listing.
    source=Path('data/peer_surprise/2026-10-07_v2/sources/CASY_submissions.json')
    ledger=json.loads(source.read_text())['filings']['recent']
    save(root/'discovery_manifest.json',{'created_at':now(),'caseys_submissions_sha256':sha(source),
         'scope':'2013-2019 original peer releases; no correction fitting'})
    for i,form in enumerate(ledger['form']):
        if form=='8-K' and '2.02' in ledger['items'][i] and '2013-01-01' <= ledger['filingDate'][i] < '2019-01-01':
            jobs.append(('CASY',{k:ledger[k][i] for k in ['accessionNumber','primaryDocument','filingDate']}))
    links=set()
    for path in Path('data/couchetard_peer/2026-10-07_v3/sources').glob('index*'):
        for a in html.fromstring(path.read_bytes()).xpath('//a[@href]'):
            url=a.get('href')
            if re.search(r'announces.*results.*quarter.*20\d{2}$',url,re.I) and '2013-01-01' <= url.split('/')[-1][:10] < '2019-01-01':links.add(url)
    jobs += [('ATD',url) for url in sorted(links)]
    def capture(job):
        peer,item=job;checks=[]
        locator=item if peer=='ATD' else item['accessionNumber']
        try:
            if peer=='CASY':
                acc=item['accessionNumber'].replace('-','');base=f'https://www.sec.gov/Archives/edgar/data/726958/{acc}/'
                cover_url=base+item['primaryDocument'];cover=fetch(cover_url)
                path=root/f'CASY_{acc}_cover.html'
                with path.open('xb') as f:f.write(cover)
                tree=html.fromstring(cover);text=' '.join(tree.text_content().split())
                section=re.search(r'Item\s*2\.02\.?(.*?)(?=Item\s*\d\.\d\d|Signature|$)',text,re.I)
                evidence=section[1] if section else ''
                checks.append({'peer':peer,'source_url':cover_url,'raw_file':path.name,'sha256':sha(path),'available_at':item['filingDate'],'status':'COVER_CHECKED','evidence':evidence[:1500]})
                index_url=base+item['accessionNumber']+'-index.htm';raw_index=fetch(index_url)
                path=root/f'CASY_{acc}_index.html'
                with path.open('xb') as f:f.write(raw_index)
                index=html.fromstring(raw_index)
                urls=[urljoin(index_url,a.get('href')) for tr in index.xpath('//tr') if 'EX-99.1' in tr.text_content() for a in tr.xpath('.//a[@href]') if a.get('href').lower().endswith(('.htm','.html'))]
                if len(set(urls))!=1:raise ValueError('Ambiguous original earnings exhibit')
                url=urls[0];raw=fetch(url);path=root/f'CASY_{acc}_release.html'
                with path.open('xb') as f:f.write(raw)
                stamp=re.search(r'(January|April|July|October)\s+(\d{1,2}),?\s+(20\d{2})',evidence,re.I)
                period=None
                if stamp:
                    end=datetime.strptime(' '.join(stamp.groups()),'%B %d %Y').date()
                    if 0<(date.fromisoformat(item['filingDate'])-end).days<100:
                        q={1:3,4:4,7:1,10:2}[end.month];year=end.year+(end.month>4)
                        period={'quarter':f'F{year}Q{q}','end':str(end)}
                target=caseys_target(raw) if period else {'status':'PENDING_PERIOD_VERIFICATION'}
                available=item['filingDate']
            else:
                url=item;raw=fetch(url);path=root/('ATD_'+url.split('/')[-1]+'.html')
                with path.open('xb') as f:f.write(raw)
                try:
                    target=parse_release(raw,url);target['status']='PARSED_FEE_RECONCILED_PENDING_REVIEW';period={'quarter':target['quarter'],'end':target['end']}
                except ValueError as exc:
                    target={'status':'PENDING_NUMERIC_OR_FISCAL_BASIS_REVIEW','reason':str(exc)};period=None
                available=url.split('/')[-1][:10]
            record={'peer':peer,'source_url':url,'raw_file':path.name,'sha256':sha(path),
                    'available_at':available,'captured_at':now(),'period':period,'target':target,
                    'status':'ORIGINAL_RELEASE_CAPTURED','absence_conclusion_authorized':False}
            checks.append(record);print(peer,record['period'],target['status'],flush=True)
        except Exception as exc:
            checks.append({'peer':peer,'locator':locator,'status':'SOURCE_AUDIT_UNRESOLVED','reason':str(exc)})
        return checks
    with ThreadPoolExecutor(max_workers=2) as pool:checks=[r for records in pool.map(capture,jobs) for r in records]
    save(root/'source_checks.json',{'created_at':now(),'checks':checks,'forecast_model_changed':False})


if __name__=='__main__':main()
