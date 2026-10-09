"""Dated RBOB scenarios, explicitly not a MUSA retail-margin estimator."""
import argparse
from datetime import date, datetime
import json
from pathlib import Path
import re
from statistics import mean
import subprocess

from .alternative_experiments import SPEC
from .pit_replay import now, save
from .prospective import sha

MONTHS = {name:i+1 for i,name in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])}


def parse_report(text):
    printed = re.search(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})',text)
    quote = re.search(r'Closing Settlement Prices as of\s+(\d{1,2}/\d{1,2}/\d{4})',text,re.I)
    row = next((line for line in text.splitlines() if 'RBOB Gasoline' in line), None)
    if not printed or not quote or not row or '$/gal' not in row:
        raise ValueError('Dated RBOB settlement row and USD/gallon units required')
    published = datetime.strptime(' '.join(printed.groups()),'%B %d %Y').date()
    observed = datetime.strptime(quote[1],'%m/%d/%Y').date()
    if observed > published:
        raise ValueError('Settlement observation after report date')
    contracts = []
    for price, month, year in re.findall(r'(\d+\.\d+)\s*\(([A-Za-z]{3})\s+(\d{2})\)',row):
        if month not in MONTHS or float(price)<=0:
            raise ValueError('Invalid contract month or price')
        contract_month = date(2000+int(year),MONTHS[month],1)
        if contract_month < date(published.year,published.month,1):
            raise ValueError('Expired contract in dated forward scenario')
        contracts.append({'contract_month':contract_month.strftime('%Y-%m'),
                          'settlement_usd_per_gallon':float(price),
                          'settlement_cpg':100*float(price)})
    if len(contracts)<3 or len({c['contract_month'] for c in contracts})!=len(contracts):
        raise ValueError('Incomplete or duplicate RBOB settlement row')
    return {'report_publication_date':str(published),'settlement_observation_date':str(observed),
            'contracts':contracts,'raw_evidence_row':row.strip(),
            'market_basis':'NYMEX_RBOB_NOT_DELIVERED_MUSA_FUEL'}


def quarterly_scenario(curve, quarter, shifts=(-20,0,20)):
    year, q = int(quarter[:4]),int(quarter[-1])
    if q not in [1,2,3,4]: raise ValueError('Invalid quarter')
    months = [f'{year}-{m:02d}' for m in range(3*q-2,3*q+1)]
    indexed = {c['contract_month']:c['settlement_cpg'] for c in curve['contracts']}
    missing = [m for m in months if m not in indexed]
    if missing:
        return {'quarter':quarter,'status':'BLOCKED_INCOMPLETE_CONTRACT_COVERAGE',
                'required_months':months,'missing_months':missing,'rbob_scenario_cpg':None,
                'musa_retail_margin_cpg':None}
    point = mean(indexed[m] for m in months)
    return {'quarter':quarter,'status':'CONDITIONAL_WHOLESALE_SCENARIO_ONLY',
            'contract_months':months,'month_weights':[1/3]*3,
            'weight_basis':'EQUAL_MONTH_SCENARIO_NOT_GALLON_SHARE',
            'rbob_scenario_cpg':point,
            'parallel_shift_scenarios':[{'shift_cpg':s,'rbob_scenario_cpg':point+s} for s in shifts],
            'scenarios_are_probabilistic':False, 'musa_retail_margin_cpg':None,
            'musa_margin_status':'BLOCKED_RETAIL_RESPONSE_AND_REGIONAL_BASIS_METHODOLOGY'}


def replay(pdf, manifest_path, output):
    output.mkdir(parents=True,exist_ok=False)
    manifest = json.loads(manifest_path.read_text())
    if sha(pdf) != manifest['sha256']:
        raise ValueError('Futures PDF raw evidence hash mismatch')
    spec = json.loads(SPEC.read_text())
    for name, path in [('report.pdf',pdf),('source_manifest.json',manifest_path),
                       ('spec.json',SPEC),('futures_scenarios.py',Path(__file__))]:
        with (output/name).open('xb') as f:f.write(path.read_bytes())
    save(output/'input_manifest.json',{'frozen_at':now(),'raw_sha256':sha(pdf),
         'source_manifest_sha256':sha(manifest_path),'spec_sha256':sha(SPEC),'code_sha256':sha(Path(__file__))})
    text = subprocess.run(['pdftotext','-layout',str(pdf),'-'],check=True,capture_output=True).stdout.decode('utf-8')
    curve = parse_report(text)
    available = manifest['available_at_conservative']
    if date.fromisoformat(curve['report_publication_date']) > datetime.fromisoformat(available.replace('Z','+00:00')).date():
        raise ValueError('Report date after conservative source availability')
    curve.update({'available_at':available,'captured_at_precision':'VERIFIED_AT_CONSERVATIVE_NOT_ORIGINAL_RELEASE',
                  'raw_sha256':sha(pdf),'source_url':manifest['source_url']})
    save(output/'curve.json',curve)
    scenarios = [quarterly_scenario(curve,q,spec['futures']['scenario_shifts_cpg']) for q in ['2026Q4','2027Q1','2027Q2']]
    result = {'created_at':now(),'role':'CONDITIONAL_WHOLESALE_SCENARIO_NOT_MUSA_MARGIN_FORECAST',
              'curve':curve,'quarter_scenarios':scenarios,'production_changed':False,
              'historical_two_quarter_accuracy':'BLOCKED_ARCHIVED_CURVE_VINTAGES_UNVERIFIED',
              'current_calendar_quarter':'2026Q4','two_quarter_ahead_target':'2027Q2',
              'prospective_validation':False,'bulk_acquisition_or_redistribution_terms_verified':False}
    save(output/'scenarios.json',result)
    print(json.dumps(result,indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf',required=True,type=Path)
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args(); replay(args.pdf,args.manifest,args.output)


if __name__=='__main__':main()
