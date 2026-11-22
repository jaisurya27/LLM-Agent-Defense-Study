"""Regression checks that the batch audit rejects corrupted evidence."""
import copy
import json

import pytest

from review.devin.verify_batch import ROOT, audit_trace


def sample():
    config = json.loads((ROOT / 'config/preliminary_gpt5.json').read_text())
    case = next(c for c in json.loads((ROOT / 'config/tasks_gpt5.json').read_text())['cases']
                if c['suite'] == 'slack' and c['user_task_id'] == 'user_task_12')
    path = next((ROOT / 'results/preliminary_gpt5/traces').glob(
        'slack__user_task_12__injection_task_1__warning_boundaries__*.json'))
    trace = json.loads(path.read_text())
    return trace, copy.deepcopy(trace['record']), case, config


def test_valid_trace_preserves_error_exception():
    row = audit_trace(*sample())
    assert row['successful_tool_results'] == 1
    assert row['tool_errors'] == 2
    assert row['provider_wrapped_successes'] == 1


@pytest.mark.parametrize('corruption', ['warning', 'boundary', 'error', 'call_id', 'payload'])
def test_corrupted_evidence_is_rejected(corruption):
    trace, record, case, config = sample()
    messages = trace['pipeline_attempts'][0]
    if corruption == 'warning':
        messages[0]['content'][0]['content'] += '\nExtra instruction'
    elif corruption == 'boundary':
        messages[3]['content'][0]['content'] = messages[3]['content'][0]['content'].removeprefix('<external_content>\n')
    elif corruption == 'error':
        messages[5]['error'] = 'Different error'
    elif corruption == 'call_id':
        messages[3]['tool_call_id'] = 'wrong-id'
    else:
        trace['injections']['prompt_injection_channel'] += 'Changed attack'
    with pytest.raises(AssertionError):
        audit_trace(trace, record, case, config)
