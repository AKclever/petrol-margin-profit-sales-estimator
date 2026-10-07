"""Append reviewed, basis-separated accounting findings to the raw capture."""
import argparse
import json
from pathlib import Path

from musa_nowcast.pit_replay import now,save
from musa_nowcast.prospective import sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    root=parser.parse_args().root
    sources=json.loads((root/'source_checks.json').read_text())['source_checks']
    reserve={'2021Q2':222.4,'2021Q4':227.5,'2022Q1':373.2,'2022Q3':303.2,'2023Q3':311.6,'2026Q2':337.0}
    assessments={
      '2021Q2':'Call separates rising-price retail pressure from favorable uncontrollable PS&W and offsetting supply/RIN economics. Inventory note calls QuickChek gasoline FIFO; do not silently replace that with the later annual policy.',
      '2021Q4':'Call reports over $8m of 2021 synergies, mostly in total fuel contribution, including retail pricing tactics and renegotiated supply terms. Annual total is not an isolated Q4 retail adjustment. Annual QuickChek petroleum policy is weighted average, unlike June note wording.',
      '2022Q1':'Management reports 10.7c supply/RIN contribution and about 2.7c after stripping uncontrollable timing/inventory effects; discusses internal spot-to-rack transfer pricing. Qualitative remark that retail is understated is not a numeric retail restatement.',
      '2022Q3':'Call explains falling prices strengthen retail while inventory timing depresses PS&W. No numeric retail inventory adjustment identified in the checked inventory note and fuel-cost call passages.',
      '2023Q3':'Call attributes supply fluctuation to inventory variances; separate retail commentary describes repeated Friday price moves and subsequent recovery. Supply gains cannot be assigned to retail.',
      '2026Q2':'Prepared commentary explicitly separates supply controllable +7.2c, uncontrollable -2.0c, terminal/wholesale +0.3c = +5.5c. This corrects any inference that inventory exposure was a supply tailwind. Retail benefit remains a separate 35.1c target.'}
    rows=[]
    for q in reserve:
        checked=[s for s in sources if s.get('quarter')==q and s['audit_result']=='CAPTURED_PENDING_REVIEW']
        if len(checked)<2:raise ValueError('missing filing or call evidence')
        for s in checked:
            if sha(root/s['raw_file'])!=s['sha256']:raise ValueError('raw source hash mismatch')
        rows.append({'quarter':q,'audit_status':'COMPLETED_TARGETED_ACCOUNTING_REVIEW',
          'review_scope':'inventory notes/accounting policies and relevant fuel-margin, supply and synergy call passages',
          'reviewed_sources':[{'source_url':s['source_url'],'source_type':s['source_type'],
                             'sha256':s['sha256'],'raw_file':s['raw_file']} for s in checked],
          'petroleum_lifo_reserve_snapshot_million':reserve[q],
          'reserve_is_quarterly_expense':False,'reserve_usable_as_retail_margin_adjustment':False,
          'numeric_retail_inventory_adjustment':'NOT_IDENTIFIED_IN_REVIEWED_SCOPE',
          'retail_adjustment_cpg':None,'supply_adjustment_applied_to_retail':False,
          'weekly_acquisition_cost_recovered':False,'assessment':assessments[q]})
    commentary=json.loads((root/'2026Q2_call_0_text.json').read_text())['text']
    if not all(x in commentary for x in ('7.2 cents','negative 2 cent','30 basis points','5.5 cents')):
        raise ValueError('reported supply decomposition unsupported')
    result={'created_at':now(),'evaluation_role':'RETROSPECTIVE_DOCUMENTARY_DIAGNOSIS_NOT_PIT_FORECAST_INPUT',
      'reviewed_quarters':rows,'quantified_retail_inventory_adjustments_identified':0,
      'q2_2026_supply_components_cpg':{'controllable_including_rins':7.2,'uncontrollable_inventory_exposure':-2.0,
                                    'terminal_and_wholesale':.3,'total_supply':5.5},
      'quickchek_policy_wording':'2021Q2 note: FIFO gasoline; 2021 annual policy: weighted-average petroleum. Difference retained unresolved; not assumed to be a policy change or quantified forecast correction.',
      'production_changed':False,'original_22_quarter_disclosure_audit_changed':False,
      'source_checks_sha256':sha(root/'source_checks.json'),'review_script_sha256':sha(Path(__file__))}
    save(root/'reviewed_findings.json',result)
    print(json.dumps({'reviewed_quarters':len(rows),'quantified_retail_inventory_adjustments_identified':0,
                      'supply_bridge_cpg':7.2-2+.3},indent=2))


if __name__=='__main__':main()
