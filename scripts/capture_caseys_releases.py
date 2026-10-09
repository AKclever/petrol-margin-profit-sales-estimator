"""Capture original Casey earnings exhibits referenced by verified SEC covers."""
import argparse
import json
from pathlib import Path
from urllib.parse import urljoin

from lxml import html

from musa_nowcast.daily_capture import fetch
from musa_nowcast.pit_replay import now, save
from musa_nowcast.prospective import sha


def capture(out):
    out.mkdir(parents=True, exist_ok=False)
    source = Path('data/peer_surprise/2026-10-07_v2/sources')
    manifest = json.loads((source/'CASY_source_checks.json').read_text())
    checks = []
    for q, r in sorted(manifest['verified'].items()):
        record = {'quarter':q,'available_at':r['available_at'],'cover_url':r['url'],
                  'cover_sha256':r['sha256'],'search_performed_at':now()}
        try:
            accession = r['url'].split('/')[-2]
            cover = source/f'CASY_{accession}.html'
            if sha(cover) != r['sha256']:
                raise ValueError('cover hash changed')
            tree = html.fromstring(cover.read_bytes())
            links = [urljoin(r['url'], a.get('href')) for a in tree.xpath('//a[@href]')
                     if any(term in a.text_content().lower() for term in ['press release','transcript of conference call'])]
            links = list(dict.fromkeys(links))
            if len(links) != 1:
                raise ValueError('no unique press release link')
            record['source_url'] = links[0]
            raw = fetch(links[0]); path = out/f'{q}.html'
            with path.open('xb') as handle: handle.write(raw)
            record.update(status='RAW_CAPTURED',raw_file=path.name,sha256=sha(path),captured_at=now())
        except Exception as exc:
            record.update(status='UNRESOLVED_NOT_NO_DISCLOSURE',error=str(exc))
        checks.append(record); save(out/f'{q}_capture.json',record)
        print(q,record['status'],flush=True)
    save(out/'source_checks.json',{'checks':checks,'captured_at':now()})


def capture_policies(out):
    out.mkdir(parents=True,exist_ok=False)
    checks=[]
    for name,url in {
        'policy_2024':'https://www.sec.gov/Archives/edgar/data/726958/000072695824000046/casy-20240430.htm',
        'policy_2027q1':'https://www.sec.gov/Archives/edgar/data/726958/000072695826000085/casy-20260731.htm',
    }.items():
        raw=fetch(url); path=out/f'{name}.html'
        with path.open('xb') as handle:handle.write(raw)
        checks.append({'id':name,'source_url':url,'raw_file':path.name,'sha256':sha(path),'captured_at':now()})
    save(out/'source_checks.json',{'checks':checks})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out',required=True,type=Path);parser.add_argument('--policies',action='store_true')
    args=parser.parse_args();(capture_policies if args.policies else capture)(args.out)
