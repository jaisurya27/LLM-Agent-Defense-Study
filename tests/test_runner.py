"""Offline checks. No API key and no spending: `pytest -q`."""

import json

import pytest

from src import runner
from src.common import CONFIG_PATH, TASKS_PATH, load_json
from src.defenses import BOUNDARY_CLOSE, BOUNDARY_OPEN, format_external_content, get_defense_instruction
from src.pipeline import build_system_message
from src.schema import validate_record
from src.select_tasks import select

CONFIG = load_json(CONFIG_PATH)
TASKS = load_json(TASKS_PATH)


@pytest.fixture
def results_root(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    return tmp_path


def tool_texts(trace):
    return [m["content"][0]["content"] for m in trace["pipeline_attempts"][-1] if m["role"] == "tool" and not m["error"]]


def load_traces(root, phase):
    out = {}
    for line in (root / "results/offline_check" / phase / "episodes.jsonl").read_text().splitlines():
        record = json.loads(line)
        out[(record["case_id"], record["defense"])] = (record, json.loads((root / record["trace_path"]).read_text()))
    return out


def test_defense_functions():
    assert get_defense_instruction("default") == ""
    assert get_defense_instruction("warning") == get_defense_instruction("warning_boundaries") != ""
    assert format_external_content("x\ny", "default") == format_external_content("x\ny", "warning") == "x\ny"
    assert format_external_content("x\ny", "warning_boundaries") == f"{BOUNDARY_OPEN}\nx\ny\n{BOUNDARY_CLOSE}"
    with pytest.raises(ValueError):
        format_external_content("x", "other")


def test_selection_is_reproducible_and_matches_saved_file():
    assert select(CONFIG) == TASKS
    assert len(TASKS["cases"]) == 6


def test_plan_sizes():
    assert len(runner.plan_episodes("smoke", CONFIG, TASKS)) == 2
    assert len(runner.plan_episodes("integration", CONFIG, TASKS)) == 6
    batch = runner.plan_episodes("batch", CONFIG, TASKS)
    assert len(batch) == 36 and sum(e["attacked"] for e in batch) == 18


def test_six_conditions_show_the_intended_prompts_and_content(results_root):
    runner.run_phase("integration", CONFIG, TASKS, offline="compromised", dry_run=False)
    traces = load_traces(results_root, "integration")
    assert len(traces) == 6
    payload = next(iter(TASKS["cases"][0]["injections"].values()))
    default_system = build_system_message("default")

    for (case, defense), (record, trace) in traces.items():
        assert validate_record(record) == []
        texts = tool_texts(trace)
        assert texts
        # System message: default unchanged, same warning in both defended configurations.
        if defense == "default":
            assert trace["system_message"] == default_system
        else:
            assert trace["system_message"] == default_system + "\n\n" + get_defense_instruction("warning")
        # Boundaries only in warning_boundaries, around every tool result.
        wrapped = [t.startswith(BOUNDARY_OPEN + "\n") and t.endswith("\n" + BOUNDARY_CLOSE) for t in texts]
        assert all(wrapped) if defense == "warning_boundaries" else not any(BOUNDARY_OPEN in t for t in texts)
        # Attack text appears only in attacked runs, and inside the markers.
        # (AgentDojo's environment loader collapses the payload's blank lines.)
        seen = [t for t in texts if " ".join(payload.split()) in " ".join(t.split())]
        assert bool(seen) == record["attacked"]
        assert record["attack_success"] is (True if record["attacked"] else None)

    # Removing the markers gives exactly the content the default agent saw.
    for case in {c for c, _ in traces}:
        plain = tool_texts(traces[(case, "default")][1])
        inner = [t[len(BOUNDARY_OPEN) + 1 : -len(BOUNDARY_CLOSE) - 1] for t in tool_texts(traces[(case, "warning_boundaries")][1])]
        assert inner == plain == tool_texts(traces[(case, "warning")][1])


def test_evaluated_episodes_are_never_rerun(results_root):
    runner.run_phase("smoke", CONFIG, TASKS, offline="reference", dry_run=False)
    runner.run_phase("smoke", CONFIG, TASKS, offline="reference", dry_run=False)
    assert len(load_traces(results_root, "smoke")) == 2
    lines = (results_root / "results/offline_check/smoke/episodes.jsonl").read_text().splitlines()
    assert len(lines) == 2


def test_infrastructure_failure_is_recorded_and_retried_once(results_root, monkeypatch):
    calls = {"n": 0}
    original = runner.ScriptedLLM.query

    def flaky(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("simulated outage")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(runner.ScriptedLLM, "query", flaky)
    runner.run_phase("smoke", CONFIG, TASKS, offline="reference", dry_run=False)
    out = results_root / "results/offline_check/smoke"
    records = [json.loads(line) for line in (out / "episodes.jsonl").read_text().splitlines()]
    first, second = records[0], records[1]
    assert first["status"] == "infrastructure_error" and first["utility_success"] is None and first["attempt"] == 1
    assert second["status"] == "completed" and second["attempt"] == 2 and second["case_id"] == first["case_id"]
    assert first["run_id"] != second["run_id"]
    selected = json.loads((out / "selected_runs.json").read_text())["selected"]
    assert selected[f"{first['case_id']}__default"]["run_id"] == second["run_id"]
    assert len(records) == 3 and len(selected) == 2


def test_batch_refuses_unfrozen_config(results_root):
    with pytest.raises(SystemExit):
        runner.run_phase("batch", {**CONFIG, "frozen": False}, TASKS, offline=None, dry_run=False)
