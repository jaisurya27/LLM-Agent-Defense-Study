"""Audit the two frozen preliminary batches locally; never calls a model API.

Run: python -m review.devin.verify_batch
Replays saved calls against AgentDojo's simulated environments, including errors
and state carried between internal attempts. Writes only review/devin/batch_checks.csv.
"""
import copy
import csv
import json
from importlib.metadata import version
from pathlib import Path

from agentdojo.agent_pipeline.agent_pipeline import load_system_message
from agentdojo.agent_pipeline.llms.openai_llm import _message_to_openai
from agentdojo.agent_pipeline.tool_execution import tool_result_to_str
from agentdojo.functions_runtime import FunctionCall, FunctionsRuntime
from agentdojo.task_suite.load_suites import get_suite

from src.common import config_hash
from src.defenses import get_defense_instruction
from review.devin.verify_traces import require, text

ROOT = Path(__file__).resolve().parents[2]
DATASETS = (
    ('preliminary', 'preliminary.json', 'tasks.json'),
    ('preliminary_gpt5', 'preliminary_gpt5.json', 'tasks_gpt5.json'),
)
DEFENSES = ('default', 'warning', 'warning_boundaries')


def provider_message(message, model):
    """Reconstruct pinned adapter output; this is not a saved HTTP request."""
    converted = copy.deepcopy(message)
    if converted['role'] == 'assistant' and converted.get('tool_calls'):
        converted['tool_calls'] = [FunctionCall(**c) for c in converted['tool_calls']]
    if converted['role'] == 'tool':
        converted['tool_call'] = FunctionCall(**converted['tool_call'])
    return _message_to_openai(converted, model)


def provider_text(message):
    content = message.get('content')
    return content if isinstance(content, str) else ''.join(b['text'] for b in content or [])


def audit_trace(trace, record, case, config):
    label = record['run_id']
    require(trace['record'] == record, f'{label}: record mismatch')
    require(record['status'] == 'completed', f'{label}: incomplete episode')
    require(record['config_id'] == config['config_id'], f'{label}: config ID')
    require(record['model_id'] == config['model']['model_id'], f'{label}: model ID')
    require(trace['model_settings'] == config['model'], f'{label}: model settings')
    require(trace['episode_limits'] == config['episode_limits'], f'{label}: limits')
    require(record['injection_task_id'] == (case['injection_task_id'] if record['attacked'] else None), f'{label}: injection task')
    require(trace['injections'] == (case['injections'] if record['attacked'] else {}), f'{label}: injection payload')
    suite = get_suite(config['benchmark_version'], record['suite'])
    task = suite.get_user_task_by_id(record['user_task_id'])
    require(trace['user_prompt'] == case['user_prompt'] == task.PROMPT, f'{label}: user prompt')
    defense = record['defense']
    base = load_system_message(None).rstrip('\n')  # preserve existing convention
    warning = (ROOT / 'prompts/warning.txt').read_bytes().decode().removesuffix('\n').removesuffix('\r')
    require(get_defense_instruction('warning') == get_defense_instruction('warning_boundaries') == warning, 'shared warning')
    expected_system = base if defense == 'default' else base + '\n\n' + warning
    require(trace['system_message'] == expected_system, f'{label}: system header')
    # AgentDojo run_task_with_pipeline retains the environment across attempts.
    env = task.init_environment(suite.load_and_inject_default_environment(trace['injections']))
    runtime = FunctionsRuntime(suite.tools)
    attempts = trace['pipeline_attempts']
    require(bool(attempts), f'{label}: no captured attempt')
    successes = errors = reflected = wrapped = unexecuted = 0
    for attempt_index, messages in enumerate(attempts):
        prefix = f'{label}:attempt {attempt_index + 1}'
        require([m['role'] for m in messages[:2]] == ['system', 'user'], f'{prefix}: initial roles')
        require([text(m) for m in messages if m['role'] == 'system'] == [expected_system], f'{prefix}: system text')
        require([text(m) for m in messages if m['role'] == 'user'] == [task.PROMPT], f'{prefix}: user text')
        pending = {}
        for index, message in enumerate(messages):
            where = f'{prefix}:message {index}'
            wire = provider_message(message, record['model_id'])
            require(wire['role'] == ('developer' if message['role'] == 'system' else message['role']), f'{where}: adapter role')
            if message['role'] in ('system', 'user'):
                require(provider_text(wire) == text(message), f'{where}: adapter instruction text')
            elif message['role'] == 'assistant':
                require(not pending, f'{where}: missing tool results')
                calls = message.get('tool_calls') or []
                for call, wire_call in zip(calls, wire.get('tool_calls') or []):
                    require(call['function'] in runtime.functions, f'{where}: unavailable tool')
                    require(call['id'] not in pending, f'{where}: duplicate ID')
                    require(wire_call['id'] == call['id'] and wire_call['function']['name'] == call['function'], f'{where}: adapter call metadata')
                    require(json.loads(wire_call['function']['arguments']) == call['args'], f'{where}: adapter arguments')
                    pending[call['id']] = call
                require(len(calls) == len(wire.get('tool_calls') or []), f'{where}: adapter call count')
            elif message['role'] == 'tool':
                require(message['tool_call_id'] in pending, f'{where}: orphan tool result')
                call = pending.pop(message['tool_call_id'])
                require(call == message['tool_call'], f'{where}: changed call metadata')
                raw, error = runtime.run_function(env, call['function'], copy.deepcopy(call['args']))
                require(error == message['error'], f'{where}: replay error')
                original = tool_result_to_str(raw)
                expected = '<external_content>\n' + original + '\n</external_content>' if defense == 'warning_boundaries' else original
                require(text(message) == expected, f'{where}: full replayed content/format')
                require(wire['tool_call_id'] == call['id'] and wire['name'] == call['function'], f'{where}: adapter tool metadata')
                require(provider_text(wire) == (error or expected), f'{where}: provider-visible text')
                if error:
                    errors += 1
                    reflected += int('<INFORMATION>' in error)
                else:
                    successes += 1
                    wrapped += int(defense == 'warning_boundaries')
            else:
                raise AssertionError(f'{where}: unexpected role')
        if pending:
            # The last model turn can request another call after the loop limit.
            # Those calls were never executed; retain state from actual results only.
            rounds = sum(bool(m.get('tool_calls')) for m in messages if m['role'] == 'assistant') - 1
            require(messages[-1]['role'] == 'assistant' and rounds == config['episode_limits']['max_tool_iterations'], f'{prefix}: unexplained missing final results')
            unexecuted += len(pending)
    return {
        'run_id': label, 'model': record['model_id'], 'suite': record['suite'],
        'defense': defense, 'condition': 'attacked' if record['attacked'] else 'clean',
        'pipeline_attempts': len(attempts), 'successful_tool_results': successes,
        'tool_errors': errors, 'errors_with_attack_marker': reflected,
        'unexecuted_calls_at_limit': unexecuted,
        'provider_wrapped_successes': wrapped,
        'placement_and_replay': 'pass',
        'boundary_exercised': defense == 'warning_boundaries' and successes > 0,
        'utility_success': record['utility_success'], 'attack_success': record['attack_success'],
        'config_hash': record['config_hash'], 'code_revision': record['code_revision'],
        'trace_path': record['trace_path'],
    }


def audit():
    root = ROOT
    require(version('agentdojo') == '0.1.35', 'requires AgentDojo 0.1.35')
    rows = []
    for folder, config_name, tasks_name in DATASETS:
        config_path, tasks_path = root / 'config' / config_name, root / 'config' / tasks_name
        config, tasks = json.loads(config_path.read_text()), json.loads(tasks_path.read_text())
        require(config['frozen'] is True, f'{folder}: config not frozen')
        cases = {(c['suite'], c['user_task_id']): c for c in tasks['cases']}
        records = [json.loads(line) for line in (root / 'results' / folder / 'episodes.jsonl').read_text().splitlines()]
        expected = {(s, t, a, d) for s, t in cases for a in (False, True) for d in DEFENSES}
        observed = {(r['suite'], r['user_task_id'], r['attacked'], r['defense']) for r in records}
        require(len(records) == len(expected) == 36 and observed == expected, f'{folder}: coverage')
        selected = json.loads((root / 'results' / folder / 'selected_runs.json').read_text())['selected']
        require({s['run_id'] for s in selected.values()} == {r['run_id'] for r in records}, f'{folder}: selected runs')
        fingerprint = config_hash(config_path, tasks_path)
        for record in records:
            require(record['config_hash'] == fingerprint, f'{record["run_id"]}: frozen input hash mismatch')
            path = root / 'results' / folder / 'traces' / (record['run_id'] + '.json')
            require(record['trace_path'] == str(path.relative_to(root)), f'{path}: trace path')
            trace = json.loads(path.read_text())
            rows.append(audit_trace(trace, record, cases[record['suite'], record['user_task_id']], config))
    output = root / 'review/devin/batch_checks.csv'
    with output.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f'PASS: {len(rows)} episodes; {sum(r["pipeline_attempts"] for r in rows)} internal attempts; '
          f'{sum(r["successful_tool_results"] for r in rows)} successful tool results; '
          f'{sum(r["tool_errors"] for r in rows)} tool errors.')
    print('All recorded tool content and errors match local replay. Provider conversion reconstructed with pinned adapter; no API calls.')
    return rows


if __name__ == '__main__':
    audit()
