"""Archive public footprint context, not inferred company margin weights."""
import argparse
from pathlib import Path

from musa_nowcast.daily_capture import fetch
from musa_nowcast.pit_replay import now, save
from musa_nowcast.prospective import sha


def capture(out):
    out.mkdir(parents=True,exist_ok=False)
    checks=[]
    for name,url in {
        'footprint':'https://corporate.couche-tard.com/where-we-operate',
        'annual_index_2025':'https://corporate.couche-tard.com/financial-reporting?cat=29',
    }.items():
        record={'id':name,'source_url':url,'search_performed_at':now()}
        try:
            raw=fetch(url);path=out/f'{name}.html'
            with path.open('xb') as h:h.write(raw)
            record.update(status='RAW_CAPTURED',raw_file=path.name,sha256=sha(path),captured_at=now())
        except Exception as exc:
            record.update(status='UNRESOLVED_FETCH_FAILED',error=str(exc))
        checks.append(record);save(out/f'{name}_capture.json',record)
        print(name,record['status'],flush=True)
    save(out/'source_checks.json',{'checks':checks})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path)
    capture(p.parse_args().out)
