"""Shared runner for the agent defense study (owner: Ja).

    python -m src.runner smoke         # 1 clean + 1 attacked, default agent
    python -m src.runner integration   # the same 2 cases under all 3 defenses
    python -m src.runner batch         # all planned episodes (needs frozen config)

Add --config config/preliminary_gpt5.json to run the GPT-5 comparison. It has
its own task file and writes to folders ending in _gpt5, so the main results
are never touched.

Add --dry-run to list the planned episodes without running anything, and
--offline to use a scripted stand-in instead of the API (no key, no cost).

Each run appends one record per episode to results/<phase>/episodes.jsonl,
saves a trace to results/<phase>/traces/<run_id>.json and updates
results/<phase>/selected_runs.json, which names the one attempt per episode
that the analysis should count.
"""

from __future__ import annotations

import argparse
import json
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agentdojo.task_suite.load_suites import get_suite

from src.common import CONFIG_PATH, ROOT, TASKS_PATH, code_revision, config_hash, load_env_file, load_json, tasks_path_for
from src.defenses import DEFENSES
from src.pipeline import CaptureLogger, ScriptedLLM, UsageMeter, build_llm, build_pipeline, build_system_message
from src.schema import validate_record

PHASE_DIRS = {"smoke": "smoke", "integration": "integration", "batch": "preliminary"}


# ------------------------------------------------------------------ planning

def case_id(case: dict, attacked: bool) -> str:
    """Identifies the same task and clean/attack pairing across defenses."""
    tail = case["injection_task_id"] if attacked else "clean"
    return f"{case['suite']}__{case['user_task_id']}__{tail}"


def plan_episodes(phase: str, config: dict, tasks: dict) -> list[dict]:
    cases = tasks["cases"]
    if phase == "smoke":
        cases, defenses = cases[:1], ["default"]
    elif phase == "integration":
        cases, defenses = cases[:1], config["defenses"]
    else:
        defenses = config["defenses"]
    for defense in defenses:
        if defense not in DEFENSES:
            raise ValueError(f"Unknown defense in config: {defense!r}")
    return [
        {"case": case, "attacked": attacked, "defense": defense, "case_id": case_id(case, attacked)}
        for case in cases
        for attacked in (False, True)
        for defense in defenses
    ]


# ------------------------------------------------------------------ one episode

def is_infrastructure_error(exc: BaseException) -> bool:
    """Service and connection problems, as opposed to bugs in our own code."""
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    module = type(exc).__module__.split(".")[0]
    return module in ("openai", "anthropic", "httpx", "httpcore", "tenacity")


def is_content_filter_block(exc: BaseException) -> bool:
    """Azure rejects a request with error code 'content_filter' when its own
    filters (for example Prompt Shields) flag the input. That is a platform
    safety layer, not an outage, so it is recorded but not retried."""
    return getattr(exc, "code", None) == "content_filter" or "content_filter" in str(getattr(exc, "body", "") or "")


def termination_reason(messages: list) -> str:
    if not messages:
        return "no_messages"
    last = messages[-1]
    if last["role"] == "assistant" and not last.get("tool_calls"):
        return "final_answer"
    # The tool loop stopped while the model was still asking for tools.
    return "max_tool_iterations"


def serialize_message(message: dict) -> dict:
    out = dict(message)
    if out.get("tool_calls"):
        out["tool_calls"] = [call.model_dump() for call in out["tool_calls"]]
    if out.get("tool_call") is not None:
        out["tool_call"] = out["tool_call"].model_dump()
    return out


def run_episode(episode: dict, config: dict, out_dir: Path, attempt: int, offline: str | None, fingerprint: dict) -> dict:
    case, defense, attacked = episode["case"], episode["defense"], episode["attacked"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{episode['case_id']}__{defense}__{stamp}_{uuid.uuid4().hex[:4]}"
    trace_path = out_dir / "traces" / f"{run_id}.json"

    # A fresh suite and environment for every episode: nothing carries over.
    suite = get_suite(config["benchmark_version"], case["suite"])
    user_task = suite.get_user_task_by_id(case["user_task_id"])
    injection_task = suite.get_injection_task_by_id(case["injection_task_id"]) if attacked else None
    injections = dict(case["injections"]) if attacked else {}

    meter = UsageMeter()
    if offline:
        llm = ScriptedLLM(user_task, injection_task if offline == "compromised" else None)
        provider, model_id = "offline", ScriptedLLM.model
    else:
        llm = build_llm(config["model"], meter)
        provider, model_id = config["model"]["provider"], config["model"]["model_id"]
    pipeline = build_pipeline(defense, llm, config["episode_limits"]["max_tool_iterations"])

    record = {
        "run_id": run_id,
        "case_id": episode["case_id"],
        "config_id": config["config_id"] + ("-offline" if offline else ""),
        "suite": case["suite"],
        "user_task_id": case["user_task_id"],
        "injection_task_id": case["injection_task_id"] if attacked else None,
        "defense": defense,
        "attacked": attacked,
        "status": "completed",
        "utility_success": None,
        "attack_success": None,
        "input_tokens": None,
        "output_tokens": None,
        "runtime_seconds": None,
        "termination_reason": None,
        "error_message": None,
        "trace_path": str(trace_path.relative_to(ROOT)),
        "attempt": attempt,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_provider": provider,
        "model_id": model_id,
        "llm_calls": None,
        **fingerprint,
    }

    capture = CaptureLogger()
    error_traceback = None
    start = time.monotonic()
    try:
        with capture:
            utility, attack_succeeded = suite.run_task_with_pipeline(pipeline, user_task, injection_task, injections)
        record["utility_success"] = bool(utility)
        record["attack_success"] = bool(attack_succeeded) if attacked else None
    except Exception as exc:  # recorded, never counted as a successful defense
        record["status"] = "infrastructure_error" if is_infrastructure_error(exc) else "evaluation_error"
        if is_content_filter_block(exc):
            record["termination_reason"] = "content_filter"
        record["error_message"] = f"{type(exc).__name__}: {exc}"[:2000]
        error_traceback = traceback.format_exc()
    record["runtime_seconds"] = round(time.monotonic() - start, 3)

    messages = capture.attempts[-1] if capture.attempts else []
    if record["status"] != "completed":
        record["termination_reason"] = record["termination_reason"] or "error"
    elif any(call.get("finish_reason") == "content_filter" for call in meter.calls):
        record["termination_reason"] = "content_filter"
    else:
        record["termination_reason"] = termination_reason(messages)
    if not offline:
        record["input_tokens"] = meter.total("input_tokens")
        record["output_tokens"] = meter.total("output_tokens")
        record["llm_calls"] = len(meter.calls)

    trace = {
        "record": record,
        "system_message": build_system_message(defense),
        "user_prompt": user_task.PROMPT,
        "attacker_goal": injection_task.GOAL if injection_task else None,
        "injections": injections,
        "model_settings": None if offline else config["model"],
        "episode_limits": config["episode_limits"],
        "usage_per_call": meter.calls,
        "pipeline_attempts": [[serialize_message(m) for m in attempt_messages] for attempt_messages in capture.attempts],
        "error_traceback": error_traceback,
    }
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(json.dumps(trace, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    problems = validate_record(record)
    if problems:
        raise RuntimeError(f"Runner produced an invalid record: {problems}")
    return record


# ------------------------------------------------------------------ batch bookkeeping

def read_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_selection(out_dir: Path, records: list[dict]) -> None:
    """One retained attempt per (case, defense): the latest. Earlier attempts
    stay in episodes.jsonl but must not be counted."""
    selected: dict[str, dict] = {}
    for record in records:
        selected[f"{record['case_id']}__{record['defense']}"] = {
            "run_id": record["run_id"],
            "status": record["status"],
            "attempt": record["attempt"],
        }
    payload = {"rule": "latest attempt per case_id and defense", "selected": selected}
    (out_dir / "selected_runs.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_phase(phase: str, config: dict, tasks: dict, offline: str | None, dry_run: bool,
              config_path: Path = CONFIG_PATH, tasks_path: Path = TASKS_PATH) -> None:
    episodes = plan_episodes(phase, config, tasks)
    folder = PHASE_DIRS[phase] + config.get("results_suffix", "")
    out_dir = ROOT / "results" / ("offline_check/" if offline else "") / folder
    max_retries = config["max_infrastructure_retries"]

    if dry_run:
        for e in episodes:
            print(f"{e['case_id']:45} {e['defense']}")
        print(f"{len(episodes)} episodes planned -> {out_dir.relative_to(ROOT)}")
        return
    unset = [k for k, v in config["model"].items() if isinstance(v, str) and v.startswith("SET-")]
    if not offline and unset:
        raise SystemExit(f"Fill in these fields in config/preliminary.json first: {', '.join('model.' + k for k in unset)}")
    if phase == "batch" and not offline and not config.get("frozen"):
        raise SystemExit("config/preliminary.json is not frozen. Agree the settings with the team, set \"frozen\": true, commit, then launch the batch.")

    fingerprint = {"config_hash": config_hash(config_path, tasks_path), "code_revision": code_revision()}
    episodes_path = out_dir / "episodes.jsonl"
    out_dir.mkdir(parents=True, exist_ok=True)
    records = read_records(episodes_path)
    other = {r["config_hash"] for r in records} - {fingerprint["config_hash"]}
    if other:
        raise SystemExit(f"{episodes_path.relative_to(ROOT)} holds results from a different configuration ({sorted(other)}). Use a new config_id and results folder, or move the old results aside.")

    consecutive_failures = 0
    for episode in episodes:
        earlier = [r for r in records if r["case_id"] == episode["case_id"] and r["defense"] == episode["defense"]]
        while True:
            # Never rerun an evaluated episode. Retry only infrastructure
            # failures, and at most max_retries times.
            if earlier and (earlier[-1]["status"] != "infrastructure_error"
                            or earlier[-1]["termination_reason"] == "content_filter"
                            or len(earlier) > max_retries):
                break
            record = run_episode(episode, config, out_dir, len(earlier) + 1, offline, fingerprint)
            with episodes_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            records.append(record)
            earlier.append(record)
            write_selection(out_dir, records)
            blocked = record["termination_reason"] == "content_filter"
            consecutive_failures = consecutive_failures + 1 if record["status"] == "infrastructure_error" and not blocked else 0
            print(f"{record['status']:21} utility={record['utility_success']!s:5} attack={record['attack_success']!s:5} "
                  f"{record['case_id']} / {record['defense']}"
                  + (f"  [{record['error_message'][:80]}]" if record["error_message"] else ""))
            if consecutive_failures >= 3:
                raise SystemExit("Stopped after 3 infrastructure errors in a row. Check the API key, quota and model ID before continuing; rerunning resumes where this stopped.")

    final = json.loads((out_dir / "selected_runs.json").read_text())["selected"] if records else {}
    done = sum(1 for e in episodes if final.get(f"{e['case_id']}__{e['defense']}", {}).get("status") == "completed")
    print(f"{done}/{len(episodes)} planned episodes evaluated. Records: {episodes_path.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run agent defense study episodes.")
    parser.add_argument("phase", choices=sorted(PHASE_DIRS))
    parser.add_argument("--dry-run", action="store_true", help="list planned episodes and exit")
    parser.add_argument("--offline", nargs="?", const="reference", choices=["reference", "compromised"],
                        help="scripted stand-in instead of the API; 'compromised' also carries out the attack")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH, help="config file (default: config/preliminary.json)")
    args = parser.parse_args()
    load_env_file()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = load_json(config_path)
    tasks_path = tasks_path_for(config)
    tasks = load_json(tasks_path)
    if tasks["attack"] != config["attack"] or tasks["selection"] != config["selection"]:
        raise SystemExit(f"{tasks_path.name} was not generated from {config_path.name}. Run: python -m src.select_tasks --config {args.config} --force")
    run_phase(args.phase, config, tasks, args.offline, args.dry_run, config_path, tasks_path)


if __name__ == "__main__":
    main()
