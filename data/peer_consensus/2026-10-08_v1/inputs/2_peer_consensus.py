"""Frozen, abstaining peer consensus experiments; no production adjustment."""
import argparse
from datetime import date
import json
from pathlib import Path

from .earnings_event_replay import overlap, select
from .error_direction import DATA, predictions, score, sign
from .prospective import sha

SPEC = Path('data/peer_consensus_spec_v1.json')
VARIANTS = ('consensus', 'overlap_only', 'strength_only', 'overlap_and_strength')


def consensus_call(signals, require_overlap=False, require_strength=False):
    peers = [signals[c] for c in ('CASY', 'ATD')]
    if any(p['call'] == 'ABSTAIN' for p in peers):
        return 'ABSTAIN'
    if peers[0]['call'] != peers[1]['call']:
        return 'ABSTAIN'
    if require_overlap and any(p['overlap_fraction'] < .5 for p in peers):
        return 'ABSTAIN'
    if require_strength and any(abs(p['surprise_cpg']) < 2 for p in peers):
        return 'ABSTAIN'
    return peers[0]['call']


def forecast(target, records):
    row = predictions(target, records)
    days = (date.fromisoformat(target['end']) - date.fromisoformat(target['start'])).days + 1
    for company in ('CASY', 'ATD'):
        donor = select(target, company, records, target['end'])
        if donor:
            row['signals'][company]['overlap_fraction'] = overlap(target, donor) / days
            row['signals'][company]['target_basis'] = donor['target_basis']
    for variant in VARIANTS:
        row['signals'][variant] = {'call': consensus_call(
            row['signals'], variant in ('overlap_only', 'overlap_and_strength'),
            variant in ('strength_only', 'overlap_and_strength'))}
    return row


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    paths = [DATA, SPEC, Path(__file__), Path('musa_nowcast/error_direction.py'),
             Path('musa_nowcast/earnings_event_replay.py')]
    (output/'inputs').mkdir()
    for i, p in enumerate(paths):
        (output/'inputs'/f'{i}_{p.name}').write_bytes(p.read_bytes())
    (output/'manifest.json').write_text(json.dumps(
        [{'path': str(p), 'sha256': sha(p)} for p in paths], indent=2)+'\n')
    records = json.loads(DATA.read_text())['records']
    targets = [r for r in records if r['company'] == 'MUSA']
    frozen = [forecast(r, records) for r in targets]
    (output/'frozen_predictions.json').write_text(json.dumps(frozen, indent=2)+'\n')
    outcomes = {r['quarter']: r['actual_cpg'] for r in targets}
    scored = [r | {'actual_direction': sign(outcomes[r['quarter']]-r['production_forecast_cpg']),
                   'absolute_production_error_cpg': abs(outcomes[r['quarter']]-r['production_forecast_cpg'])}
              for r in frozen]
    groups = {}
    for group in ('all', 'modern', 'modern_large', 'modern_ordinary'):
        rows = [r for r in scored if (group == 'all' or r['era'] == 'modern') and
                (group != 'modern_large' or r['absolute_production_error_cpg'] >= 5) and
                (group != 'modern_ordinary' or r['absolute_production_error_cpg'] < 5)]
        groups[group] = {}
        for variant in VARIANTS:
            called = [r for r in rows if r['signals'][variant]['call'] != 'ABSTAIN']
            abstained = [r for r in rows if r['signals'][variant]['call'] == 'ABSTAIN']
            groups[group][variant] = {'consensus': score(rows, variant),
                'individuals_same_rows': {c: score(called, c) for c in ('CASY', 'ATD')},
                'individuals_abstained_rows': {c: score(abstained, c) for c in ('CASY', 'ATD')}}
    result = {'role': json.loads(SPEC.read_text())['role'], 'groups': groups,
              'scored_rows': scored, 'production_changed': False,
              'probability_calibrated': False, 'variant_promoted': None}
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    for g, variants in groups.items():
        print(g, {v: (x['consensus']['calls'], x['consensus'].get('correct'),
                       x['consensus'].get('accuracy')) for v, x in variants.items()})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
