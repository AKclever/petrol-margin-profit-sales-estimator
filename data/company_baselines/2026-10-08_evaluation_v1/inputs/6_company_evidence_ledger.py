"""Local append-only, hash-chained company evidence. No forecast side effects."""
import fcntl
import hashlib
import json
import math
import os
from datetime import date
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_event(event):
    if event['kind'] not in ['ACTUAL_MARGIN', 'GUIDANCE', 'PERIMETER_CONTEXT']:
        raise ValueError('UNSUPPORTED_EVIDENCE_KIND')
    for field in ['company', 'quarter', 'target_basis', 'source_url', 'source_sha256', 'available_at', 'captured_at']:
        if not event.get(field):
            raise ValueError('MISSING_'+field.upper())
    date.fromisoformat(event['available_at'])
    if event['kind']=='ACTUAL_MARGIN':
        if not math.isfinite(event['actual_cpg']):
            raise ValueError('NONFINITE_MARGIN')
        if not event['start'] <= event['end'] < event['available_at']:
            raise ValueError('INVALID_ACTUAL_PERIOD')
    if event['kind']=='GUIDANCE':
        if not all(math.isfinite(event[k]) for k in ['low_cpg', 'high_cpg']):
            raise ValueError('NONFINITE_GUIDANCE')
        if event['low_cpg'] > event['high_cpg']:
            raise ValueError('REVERSED_GUIDANCE_RANGE')


def event_key(event):
    return '|'.join(event[k] for k in ['company', 'kind', 'quarter', 'target_basis', 'available_at'])


def read_ledger(path):
    rows = []
    previous = '0'*64
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        item = json.loads(line)
        checksum = item.pop('sha256')
        if item['previous_sha256'] != previous or digest(item) != checksum:
            raise ValueError('LEDGER_CHAIN_INVALID')
        validate_event(item['event'])
        rows.append(item['event'])
        previous = checksum
    return rows


def append_event(path, event):
    validate_event(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        existing = read_ledger(path)
        for old in existing:
            if event_key(old)==event_key(event):
                if old != event:
                    raise ValueError('CONFLICTING_EVIDENCE_REQUIRES_NEW_VERSION')
                return 'ALREADY_ARCHIVED'
        handle.seek(0)
        lines = handle.read().splitlines()
        previous = json.loads(lines[-1])['sha256'] if lines else '0'*64
        payload = {'previous_sha256':previous, 'event':event}
        envelope = payload | {'sha256':digest(payload)}
        handle.seek(0, 2)
        handle.write(json.dumps(envelope, sort_keys=True, allow_nan=False)+'\n')
        handle.flush()
        os.fsync(handle.fileno())
    return 'APPENDED'


def eligible_events(events, cutoff, company=None):
    stamp = date.fromisoformat(cutoff)
    return [e for e in events if date.fromisoformat(e['available_at']) < stamp
            and (company is None or e['company']==company)]
