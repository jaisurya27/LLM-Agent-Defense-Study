"""Audit committed pilot traces using local simulated tools; no model/API calls.

Run from the repository root:
    python -m review.de.verify_traces
"""
import csv
import json
from pathlib import Path

from agentdojo.agent_pipeline.tool_execution import tool_result_to_str
from agentdojo.functions_runtime import FunctionsRuntime
from agentdojo.task_suite.load_suites import get_suite
from src.defenses import format_external_content, get_defense_instruction
from src.pipeline import build_system_message

ROOT = Path(__file__).resolve().parents[2]
FOLDERS = ('integration_gpt41nano', 'integration_gpt5')


def text(message):
    return ''.join(b['content'] for b in message.get('content') or [] if b['type'] == 'text')


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def audit():
    rows = []
    for folder in FOLDERS:
        directory = ROOT / 'results' / folder
        records = [json.loads(line) for line in (directory / 'episodes.jsonl').read_text().splitlines()]
        require(len(records) == 6, f'{folder}: expected six integration episodes')
        require({(r['attacked'], r['defense']) for r in records} == {
            (a, d) for a in (False, True) for d in ('default', 'warning', 'warning_boundaries')
        }, f'{folder}: incomplete conditions')
        shared = {}
        for record in records:
            path = directory / 'traces' / (record['run_id'] + '.json')
            trace = json.loads(path.read_text())
            require(trace['record'] == record, f'{path}: record mismatch')
            require(len(trace['pipeline_attempts']) == 1, f'{path}: audit expects one attempt')
            messages = trace['pipeline_attempts'][0]
            defense = record['defense']
            suite = get_suite('v1.2.2', record['suite'])
            task = suite.get_user_task_by_id(record['user_task_id'])
            env = task.init_environment(suite.load_and_inject_default_environment(trace['injections']))
            runtime = FunctionsRuntime(suite.tools)
            require(trace['system_message'] == build_system_message(defense), f'{path}: system header')
            require([text(m) for m in messages if m['role'] == 'system'] == [build_system_message(defense)], f'{path}: effective system')
            require([text(m) for m in messages if m['role'] == 'user'] == [task.PROMPT], f'{path}: user request')
            require(trace['user_prompt'] == task.PROMPT, f'{path}: prompt header')
            require(bool(trace['injections']) == record['attacked'], f'{path}: injection condition')
            key = (record['user_task_id'], record['attacked'])
            if key in shared:
                require(trace['injections'] == shared[key], f'{path}: attack differs across defenses')
            else:
                shared[key] = trace['injections']
            pending = {}
            count = 0
            for index, message in enumerate(messages):
                if message['role'] == 'assistant':
                    require(not pending, f'{path}:{index}: missing tool result')
                    for call in message.get('tool_calls') or []:
                        require(call['function'] in runtime.functions, f'{path}:{index}: tool unavailable')
                        require(call['id'] not in pending, f'{path}:{index}: duplicate call ID')
                        pending[call['id']] = call
                elif message['role'] == 'tool':
                    call = pending.pop(message['tool_call_id'])
                    require(call == message['tool_call'], f'{path}:{index}: tool metadata changed')
                    raw, error = runtime.run_function(env, call['function'], call['args'])
                    require(error == message['error'], f'{path}:{index}: replay error mismatch')
                    require(error is None, f'{path}:{index}: error path needs separate review')
                    expected = format_external_content(tool_result_to_str(raw), defense)
                    require(text(message) == expected, f'{path}:{index}: response content differs from replay')
                    count += 1
            require(not pending, f'{path}: missing final tool results')
            rows.append({
                'run_id': record['run_id'], 'model': record['model_id'],
                'defense': defense, 'condition': 'attacked' if record['attacked'] else 'clean',
                'verified_tool_results': count, 'placement_and_replay': 'pass',
                'utility_success': record['utility_success'], 'attack_success': record['attack_success'],
                'trace_path': str(path.relative_to(ROOT)),
            })
    output = ROOT / 'review/de/integration_checks.csv'
    with output.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(f"PASS: {len(rows)} real pilot traces; {sum(r['verified_tool_results'] for r in rows)} tool responses exactly match local replay and formatting.")
    print('No API calls. Historical provider requests and uncommitted source revisions cannot be reconstructed by this check.')


if __name__ == '__main__':
    audit()

# Optional broader plumbing check, using only AgentDojo's simulated tools.
if __name__ == '__main__':
    import sys
    if '--offline-batch' in sys.argv:
        import contextlib
        import io
        import tempfile
        from src import runner
        from src.common import CONFIG_PATH, TASKS_PATH, load_json
        original_root = runner.ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                runner.ROOT = Path(directory)
                with contextlib.redirect_stdout(io.StringIO()):
                    runner.run_phase('batch', load_json(CONFIG_PATH), load_json(TASKS_PATH),
                                     offline='compromised', dry_run=False)
                records = [json.loads(line) for line in (
                    runner.ROOT / 'results/offline_check/preliminary/episodes.jsonl'
                ).read_text().splitlines()]
                groups = {}
                count = 0
                for record in records:
                    require(record['status'] == 'completed', record['run_id'])
                    trace = json.loads((runner.ROOT / record['trace_path']).read_text())
                    messages = trace['pipeline_attempts'][-1]
                    require(text(messages[0]) == build_system_message(record['defense']), 'offline system')
                    tool_messages = [m for m in messages if m['role'] == 'tool']
                    require(all(m['error'] is None for m in tool_messages), 'offline tool error')
                    texts = [text(m) for m in tool_messages]
                    if record['defense'] == 'warning_boundaries':
                        prefix, suffix = '<external_content>\n', '\n</external_content>'
                        require(all(t.startswith(prefix) and t.endswith(suffix) for t in texts), 'offline markers')
                        texts = [t[len(prefix):-len(suffix)] for t in texts]
                    calls = [[(c['function'], c['args']) for c in m.get('tool_calls') or []]
                             for m in messages if m['role'] == 'assistant']
                    value = (texts, calls)
                    key = record['case_id']
                    if key in groups:
                        require(value == groups[key], 'offline content/call mismatch')
                    groups[key] = value
                    count += len(tool_messages)
                require(len(records) == 36 and len(groups) == 12, 'offline coverage')
                print(f'PASS: 36 scripted episodes (18 Slack); {count} tool responses; identical unwrapped content and calls across defenses.')
                print('Synthetic outputs were temporary and are not study results.')
        finally:
            runner.ROOT = original_root
