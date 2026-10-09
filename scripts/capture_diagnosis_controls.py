"""Archive issuer-linked ordinary-quarter calls; read-only source acquisition."""
import json
from pathlib import Path
import subprocess

from musa_nowcast.daily_capture import fetch
from musa_nowcast.pit_replay import now, save
from musa_nowcast.prospective import sha

ROOT = Path('data/deep_miss_diagnosis/2026-10-08_controls_v1')
INDEX = Path('data/accounting_miss_audit/2026-10-07_deeper_v2/issuer_report_index.json')
WANTED = {'Second Quarter 2022':'2022Q2', 'Fourth Quarter 2022':'2022Q4', 'First Quarter 2026':'2026Q1'}


def main():
    ROOT.mkdir(parents=True,exist_ok=False)
    checks=[]
    reports=json.loads(INDEX.read_text())['GetFinancialReportListResult']
    for report in reports:
        q=WANTED.get(report['ReportTitle'])
        if not q: continue
        for i,doc in enumerate(report['Documents']):
            if 'transcript' not in doc['DocumentTitle'].lower(): continue
            url=doc['DocumentPath']; path=ROOT/f'{q}_call_{i}.pdf'
            row={'quarter':q,'source_url':url,'document_title':doc['DocumentTitle'],
                 'captured_at':now(),'index_path':str(INDEX),'index_sha256':sha(INDEX),
                 'role':'POST_RESULT_DIAGNOSTIC_NOT_FORECAST_INPUT'}
            try:
                raw=fetch(url)
                if not raw.startswith(b'%PDF'): raise ValueError('not a PDF')
                with path.open('xb') as handle: handle.write(raw)
                text=subprocess.run(['pdftotext','-layout',str(path),'-'],check=True,capture_output=True).stdout.decode()
                save(path.with_suffix('.json'),{'text':text,'raw_sha256':sha(path)})
                row.update(status='CAPTURED_REQUIRES_REVIEW',raw_file=str(path),sha256=sha(path),text_file=str(path.with_suffix('.json')))
            except Exception as exc:
                row.update(status='CAPTURE_FAILED_NOT_NO_DISCLOSURE',error=str(exc))
            checks.append(row)
    save(ROOT/'source_checks.json',{'created_at':now(),'checks':checks,'production_changed':False})
    print(json.dumps(checks,indent=2))


if __name__=='__main__': main()
