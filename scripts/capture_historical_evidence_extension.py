"""Small original-source acquisition, no price scraping or paid sources."""
import argparse
import json
from pathlib import Path

from musa_nowcast.daily_capture import fetch
from musa_nowcast.pit_replay import now, save
from musa_nowcast.prospective import sha

SOURCES = {
 'quickchek_close': 'https://www.sec.gov/Archives/edgar/data/1573516/000095010321001416/dp145149_ex9901.htm',
 'musa_2022q2_filing': 'https://www.sec.gov/Archives/edgar/data/1573516/000157351622000035/musa-20220630.htm',
 'caseys_buchanan_filing': 'https://www.sec.gov/Archives/edgar/data/726958/000072695821000136/casy-20211031.htm',
 'atd_f2018q2': 'https://corporate.couche-tard.com/2017-11-28-Alimentation-Couche-Tard-announces-record-earnings-for-its-second-quarter-of-fiscal-year-2018-with-the-contribution-from-CST',
 'atd_f2019q2': 'https://corporate.couche-tard.com/2018-11-27-Alimentation-Couche-Tard-maintains-its-momentum-into-the-second-quarter-of-fiscal-year-2019',
 'atd_f2019q3': 'https://corporate.couche-tard.com/2019-03-19-Alimentation-Couche-Tard-announces-record-earnings-in-third-quarter-of-fiscal-year-2019',
 'eia_rack_table': 'https://www.eia.gov/dnav/pet/pet_pri_allmg_a_epmr_pra_dpgal_m.htm',
 'eia_resale_table': 'https://www.eia.gov/dnav/pet/PET_PRI_REFMG_A_EPMR_PWG_DPGAL_M.htm',
 'cec_wholesale': 'https://www.energy.ca.gov/data-reports/energy-almanac/californias-petroleum-market/california-oil-refinery-cost-disclosure',
 'opis_history': 'https://www.opis.com/product/pricing/',
 'usda_ethanol': 'https://mymarketnews.ams.usda.gov/viewReport/3198',
}
for area in ['R10','R20','R30','STX']:
    for kind in ['PRA','PWG']:
        key = f'EMA_EPMR_{kind}_{area}_DPG'
        SOURCES[key] = f'https://www.eia.gov/dnav/pet/hist_xls/{key}m.xls'


def main(out, only=None):
    out.mkdir(parents=True, exist_ok=False)
    checks = []
    for name, url in SOURCES.items():
        if only and name not in only: continue
        record = {'id': name, 'source_url': url, 'search_performed_at': now()}
        try:
            raw = fetch(url)
            path = out/(name+('.xls' if url.endswith('.xls') else '.html'))
            with path.open('xb') as handle: handle.write(raw)
            record.update(status='RAW_CAPTURED', raw_file=path.name, sha256=sha(path), captured_at=now())
        except Exception as exc:
            record.update(status='UNRESOLVED_FETCH_FAILED', error=str(exc))
        checks.append(record)
        save(out/f'{name}_capture.json', record)
        print(name, record['status'], flush=True)
    save(out/'source_checks.json', {'checks': checks, 'historical_available_at_not_inferred_from_capture': True})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, required=True); parser.add_argument('--only',nargs='+',choices=list(SOURCES))
    args=parser.parse_args();main(args.out,args.only)
