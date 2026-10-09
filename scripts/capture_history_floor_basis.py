"""Capture older issuer releases and alternative EIA retail bases, append-only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse
import subprocess

from musa_nowcast.daily_capture import fetch
from musa_nowcast.pit_replay import now, save
from musa_nowcast.prospective import sha

SPEC = Path('data/history_floor_basis_spec_v1.json')


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output',required=True,type=Path)
    root=p.parse_args().output;root.mkdir(parents=True,exist_ok=False)
    save(root/'input_manifest.json',{'frozen_at':now(),'spec_sha256':sha(SPEC),
         'issuer_index_sha256':sha(Path('data/accounting_miss_audit/2026-10-07_deeper_v2/issuer_report_index.json'))})
    reports=json.loads(Path('data/accounting_miss_audit/2026-10-07_deeper_v2/issuer_report_index.json').read_text())['GetFinancialReportListResult']
    quarter_names={'First Quarter':1,'Second Quarter':2,'Third Quarter':3,'Fourth Quarter':4}
    jobs=[]
    for r in reports:
        year=int(r['ReportYear']);q=quarter_names.get(r['ReportSubType'])
        if not q or not 2013<=year<=2018 or (year==2013 and q<3):continue
        docs=[d for d in r['Documents'] if d['DocumentTitle']=='Press Release']
        for d in docs:
            locator=d['DocumentPath']
            url=urljoin('https://ir.corporate.murphyusa.com',locator)
            if 'murphyusa2017ir.q4web.com' in url:
                url='https://ir.corporate.murphyusa.com'+urlparse(url).path
            jobs.append((f'{year}Q{q}',url,locator,'ISSUER_EARNINGS_RELEASE'))
    for basis,core in [('regular','EMM_EPMR_PTE'),('all_grade','EMM_EPM0_PTE'),('diesel','EMD_EPD2D_PTE')]:
        for padd in [1,2,3]:
            series=f'{core}_R{padd}0_DPG'
            jobs.append((f'{basis}_PADD{padd}',f'https://www.eia.gov/dnav/pet/hist_xls/{series}w.xls',series,'EIA_RETAIL_XLS'))
    for name,series in [('NYH','EER_EPMRU_PF4_Y35NY_DPG'),('USGC','EER_EPMRU_PF4_RGC_DPG')]:
        jobs.append((name,f'https://www.eia.gov/dnav/pet/hist_xls/{series}w.xls',series,'EIA_WHOLESALE_XLS'))
    def capture(job):
        key,url,locator,kind=job
        try:
            raw=fetch(url);suffix='.pdf' if raw.startswith(b'%PDF') else '.xls' if kind.startswith('EIA') else '.html'
            path=root/f'{key}{suffix}'
            with path.open('xb') as f:f.write(raw)
            if suffix=='.pdf':
                txt=subprocess.run(['pdftotext','-layout',str(path),'-'],check=True,capture_output=True).stdout.decode('utf-8')
                save(root/f'{key}_text.json',{'text':txt,'source_sha256':sha(path)})
            check={'key':key,'source_type':kind,'source_url':url,'original_index_locator_or_series':locator,
                   'raw_file':path.name,'sha256':sha(path),'captured_at':now(),'available_at':now(),
                   'availability_basis':'FIRST_CAPTURE_NOT_ORIGINAL_RELEASE','status':'CAPTURED_PENDING_REVIEW'}
        except Exception as exc:
            check={'key':key,'source_type':kind,'source_url':url,'status':'SOURCE_CAPTURE_FAILED','error_type':type(exc).__name__}
        save(root/f'{key}_source_check.json',check)
        print(key,check['status'],flush=True);return check
    with ThreadPoolExecutor(max_workers=3) as pool:checks=list(pool.map(capture,jobs))
    save(root/'source_checks.json',{'checks':checks,'created_at':now(),'spec_sha256':sha(SPEC)})


if __name__=='__main__':main()
