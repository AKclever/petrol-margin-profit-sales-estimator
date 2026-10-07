"""Free primary-source capture for six misses; not the 22-quarter disclosure audit."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import json
import re

from lxml import html

from musa_nowcast.daily_capture import fetch
from musa_nowcast.geo import SEC_FILINGS
from musa_nowcast.pit_replay import now, save
from musa_nowcast.prospective import sha

BASE = 'https://ir.corporate.murphyusa.com/investor-relations/news-releases/press-release-details/'
RELEASES = {
 '2021Q2':('2021-07-28','2021/Murphy-USA-Inc.-Reports-Second-Quarter-2021-Results/default.aspx'),
 '2021Q4':('2022-02-02','2022/Murphy-USA-Inc.-Reports-Fourth-Quarter-2021-Results/default.aspx'),
 '2022Q1':('2022-05-03','2022/Murphy-USA-Inc.-Reports-First-Quarter-2022-Results/default.aspx'),
 '2022Q3':('2022-10-26','2022/Murphy-USA-Inc.-Reports-Third-Quarter-2022-Results/default.aspx'),
 '2023Q3':('2023-11-01','2023/Murphy-USA-Inc.-Reports-Third-Quarter-2023-Results/default.aspx'),
 '2026Q2':('2026-08-05','2026/Murphy-USA-Inc--Reports-Second-Quarter-2026-Results/default.aspx')
}
PEERS = {
 'caseys_f2027q1':('2026-09-08','https://www.sec.gov/Archives/edgar/data/726958/000072695826000084/q1fy2027earningspressrelea.htm'),
 'couchetard_f2027q1':('2026-09-01','https://corporate.couche-tard.com/2026-09-01-ALIMENTATION-COUCHE-TARD-ANNOUNCES-ITS-RESULTS-FOR-ITS-FIRST-QUARTER-OF-FISCAL-YEAR-2027'),
 'arko_2026q2':('2026-08-07','https://www.arkocorp.com/news-events/press-releases/detail/213/arko-corp-reports-second-quarter-2026-results')
}


def normalized(raw):
    tree = html.fromstring(raw.decode('utf-8'))
    for element in tree.xpath('//script|//style'):
        element.drop_tree()
    return tree, ' '.join(' '.join(tree.itertext()).split())


def capture(root, source):
    key, published, url, category = source
    checked = now()
    try:
        raw = fetch(url)
        path = root/f'{key}.html'
        with path.open('xb') as handle:
            handle.write(raw)
        tree, text = normalized(raw)
        rows = []
        for tr in tree.xpath('//tr'):
            cells = [' '.join(' '.join(c.itertext()).split()) for c in tr.xpath('./th|./td')]
            if cells and any(token in cells[0].lower() for token in
                            ['fuel','petroleum','ps&w','rins','excise','lifo','inventory']):
                rows.append(cells)
        # Raw evidence preserved; candidate paragraphs require human review.
        paragraphs = list(dict.fromkeys(' '.join(' '.join(e.itertext()).split()) for e in tree.xpath('//p')))
        candidates = [p for p in paragraphs if re.search(r'fuel|petroleum|inventory|lifo|spot.to.rack',p,re.I)
                      and len(p) < 5000]
        save(root/f'{key}.extraction.json',{'table_rows':rows,'candidate_paragraphs':candidates})
        return {'source_id':key,'source_type':category,'source_url':url,'publication_date':published,
                'publication_date_precision':'DATE_ONLY' if published else 'PENDING_VERIFICATION',
                'search_performed_at':checked,'captured_at':now(),'sha256':sha(path),
                'raw_file':str(path),'result':'CAPTURED_REQUIRES_REVIEW',
                'historical_byte_identity_verified':False}
    except Exception as exc:
        return {'source_id':key,'source_type':category,'source_url':url,'publication_date':published,
                'search_performed_at':checked,'result':'CAPTURE_FAILED_NOT_NO_DISCLOSURE',
                'error_type':type(exc).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    sources = [(q,p,BASE+u,'MUSA_QUARTER_RESULTS') for q,(p,u) in RELEASES.items()]
    sources += [(q,p,u,'PEER_RESULTS') for q,(p,u) in PEERS.items()]
    with ThreadPoolExecutor(max_workers=6) as pool:
        checks = list(pool.map(lambda s:capture(args.output,s),sources))
    for filing in SEC_FILINGS:
        if filing.report_year not in (2021,2022,2023,2025):
            continue
        path = Path('data/raw/geo/2026-09-27T202037Z/sec')/f'{filing.report_year}-{filing.document}'
        if not path.exists():
            continue
        with (args.output/path.name).open('xb') as handle:
            handle.write(path.read_bytes())
        tree,text = normalized(path.read_bytes())
        # Keep concise search contexts, not entire one-line SEC HTML output.
        contexts = []
        for term in ['SHIPPING AND HANDLING','LIFO liquidation','replacement cost','excise taxes','Petroleum product sales (at retail)']:
            for match in list(re.finditer(re.escape(term),text,re.I))[:6]:
                contexts.append({'search_term':term,'context':text[max(0,match.start()-80):match.end()+600]})
        save(args.output/f'annual_{filing.report_year}.extraction.json',{'contexts':contexts})
        checks.append({'source_id':f'annual_{filing.report_year}','source_type':'ARCHIVED_MUSA_10K',
                       'source_url':filing.url,'publication_date':str(filing.filed_at),'sha256':sha(path),
                       'search_performed_at':now(),'raw_file':str(args.output/path.name),
                       'result':'ARCHIVED_BYTES_REVIEWED','scope':'annual accounting policy, not isolated quarterly retail acquisition costs'})
    save(args.output/'source_checks.json',{'captured_at':now(),'checks':checks,
      'scope':'six largest production misses, earnings releases plus four annual accounting-policy filings; three peer releases',
      'original_22_quarter_disclosure_audit_changed':False,'production_changed':False,
      'pit_claim':'No historical byte identity proof; outcome explanations are post-quarter evidence'})
    print(json.dumps([{'source_id':x['source_id'],'result':x['result']} for x in checks],indent=2))


if __name__ == '__main__':
    main()
