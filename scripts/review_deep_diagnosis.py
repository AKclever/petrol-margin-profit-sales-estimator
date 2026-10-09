"""Append source-located findings, without altering frozen disclosure taxonomy."""
import json
from pathlib import Path
from musa_nowcast.pit_replay import now, save
from musa_nowcast.prospective import sha

ROOT=Path('data/deep_miss_diagnosis/2026-10-08_v1')
DEEP=Path('data/accounting_miss_audit/2026-10-07_deeper_v2')
CONTROLS=Path('data/deep_miss_diagnosis/2026-10-08_controls_v1')


def located(path, phrase):
    text=json.loads(path.read_text())['text'];offset=text.lower().find(phrase.lower())
    if offset<0: raise ValueError(f'unsupported documentary locator {path}: {phrase}')
    return {'text_source':str(path),'text_sha256':sha(path),'start_offset':offset,
            'page_1_based':text[:offset].count('\f')+1,'locator':phrase,
            'reviewed_at':now(),'exact_error_effect_cpg':None}


def main():
    findings={
        '2021Q2': ('SUPPORTED_MECHANISMS_UNQUANTIFIED',
            'The model recognizes deterioration versus exceptional 2020 but its half-shrunk adjustment is too small. Issuer describes rising-price retail pressure, a higher industry baseline and QuickChek pricing integration. Neither acquisition mix nor accounting is quantified as the cause of the 5.18-cent error.',
            [('2021Q2_call_0_text.json','rising price environment'),('2021Q2_call_0_text.json','fuel pricing playbooks')]),
        '2021Q4': ('SUPPORTED_MECHANISMS_UNQUANTIFIED',
            'A depressed 2020 anchor plus partial market correction underestimates the higher 2021 level. Issuer attributes synergies to pricing tactics and improved supply terms; annual combined synergies cannot be assigned to Q4 retail alone. This is evidence of company-specific mechanisms, not a quantified explanation of the full error.',
            [('2021Q4_call_0_text.json','over $8 million'),('2021Q4_call_0_text.json','renegotiating supply contracts')]),
        '2022Q1': ('CONFIRMED_MODEL_SIGN_BEHAVIOR_ECONOMIC_ATTRIBUTION_UNRESOLVED',
            'Unconstrained calibration gives rising squeeze a strong positive coefficient: its centered contribution is +8.52 cents, despite qualitative rising-price retail pressure. Issuer describes internal transfer pricing and retail/supply timing differences. Supply timing economics are not a permissible retail adjustment.',
            [('2022Q1_call_0_text.json','internal spot-to-rack'),('2022Q1_call_0_text.json','retail margin for us was probably')]),
        '2022Q3': ('SUPPORTED_MECHANISMS_UNQUANTIFIED',
            'The issuer attributes strong retail economics to falling costs plus a higher industry baseline. Production predicts improvement but half-shrinkage leaves a 9.79-cent shortfall. Removing shrinkage still leaves 4.28 cents unexplained. Exact company pump/cost/volume effects are unobserved.',
            [('2022Q3_call_0_text.json','periods of steeply falling'),('2022Q3_call_0_text.json','higher equilibrium')]),
        '2023Q3': ('SUPPORTED_MECHANISMS_UNQUANTIFIED',
            'The prior-year anchor inherits the 2022 falling-price windfall. Production forecasts too little normalization. The call also identifies several Friday price shocks and later recovery, demonstrating timing hidden by smooth quarterly summaries; it does not quantify their contribution to model error.',
            [('2023Q3_call_0_text.json','3 separate price moves'),('2023Q3_call_0_text.json','retail pricing excellence')]),
        '2026Q2': ('CONFIRMED_PROXY_MODEL_CONFLICT_ECONOMIC_ATTRIBUTION_UNRESOLVED',
            'Regional spot spreads weaken while reported MUSA retail margin rises. Spread contributes -4.02 cents and falling capture -0.87 cents in production. Issuer reports higher competitor margin floors and uneven within-quarter price/volume responses. Supply inventory exposure is a loss, not a retail tailwind. The amount attributable to market-based rack costs, local pricing and gallon weights remains unobserved.',
            [('2026Q2_call_0_text.json','marginal retailers'),('2026Q2_call_1_text.json','RBOB declined 16%')])}
    rows=[]
    for q,(status,assessment,locators) in findings.items():
        rows.append({'quarter':q,'assessment_status':status,'assessment':assessment,
                     'evidence':[located(DEEP/file,phrase) for file,phrase in locators],
                     'all_economic_error_cents_explained':False,'supplier_cost_observed':False,
                     'retail_accounting_adjustment_cpg':None,'source_role':'POST_RESULT_DIAGNOSIS'})
    controls=[
        {'quarter':'2022Q2','assessment':'Large upward wholesale movement also occurred in an ordinary-error quarter. Issuer describes faster pump pass-through and deliberate discount/volume tradeoffs; a rising-price indicator alone is insufficient.',
         'evidence':located(CONTROLS/'2022Q2_call_2.json','pricing precision')},
        {'quarter':'2022Q4','assessment':'Large falling prices and company pricing/supply capabilities also appear in an ordinary-error quarter. These mechanisms are not exclusive to the selected large misses.',
         'evidence':located(CONTROLS/'2022Q4_call_2.json','lower our supply cost')},
        {'quarter':'2026Q1','assessment':'Even greater volatility and an upward wholesale move coexist with a nearly exact production estimate. Issuer explains retail floors, prompt competitive pass-through and market-based rack transfer prices; procurement savings and inventory effects also reside in fuel supply.',
         'evidence':located(CONTROLS/'2026Q1_call_5.json','market-based internal transfer price')}]
    save(ROOT/'reviewed_findings.json',{'created_at':now(),'role':'RETROSPECTIVE_DOCUMENTARY_DIAGNOSIS_NOT_VALIDATION',
          'quarters':rows,'ordinary_call_controls':controls,'control_selection':'PURPOSIVE_EXTREME_MARKET_MOVES_NOT_RANDOM',
          'universal_root_cause_confirmed':False,'production_changed':False,
          'quantified_retail_inventory_adjustments_identified_in_checked_scope':0,
          'review_code_sha256':sha(Path(__file__))})
    candidate=located(CONTROLS/'2026Q1_call_1.json','retail margins are around')
    save(ROOT/'new_disclosure_candidates.json',{'created_at':now(),'original_audit_unchanged':True,
          'candidates':[{'target_quarter':'2026Q2','available_at_date':'2026-04-30',
          'date_precision':'DATE_ONLY_NO_INTRADAY_ASSUMPTION','audit_status':'PENDING_SOURCE_AND_PERIOD_ADJUDICATION',
          'disclosed_basis':'RETAIL_APPROXIMATE_COMMENTARY_WITH_SEPARATE_ALL_IN_RANGE',
          'numeric_retail_reference_cpg':30.,'exact_low_high_bounds':None,
          'observed_period':'APRIL_TO_DATE_CONTEXT_BOOKS_NOT_CLOSED_EXACT_END_UNRESOLVED',
          'gallon_share':None,'forecast_assimilated':False,'evidence':candidate,
          'source_url':'https://s22.q4cdn.com/506259022/files/doc_financials/2026/q1/MurphyUSA_Q126_Q-ATranscript.pdf'}],
          'conclusion':'Do not describe Q2 2026 as verified no-disclosure. Do not convert approximate retail commentary or all-in range into an exact quarterly retail anchor.'})
    print('Six targeted assessments and three ordinary-quarter call controls archived; economic cents attribution unresolved.')


if __name__=='__main__':main()
