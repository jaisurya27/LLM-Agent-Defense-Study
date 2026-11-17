"""Choose the user tasks and attacks for the preliminary batch (owner: Ja).

Writes config/tasks.json with task IDs and the exact attack payloads. Run this
once, before any defense results exist, so the selection cannot be influenced
by outcomes. Tasks are sampled with a fixed seed and are not screened on
whether the default agent can solve them.

    python -m src.select_tasks            # refuses to overwrite
    python -m src.select_tasks --force
"""

from __future__ import annotations

import argparse
import json
import random

from agentdojo.attacks.base_attacks import FixedJailbreakAttack
from agentdojo.attacks.important_instructions_attacks import ImportantInstructionsAttack
from agentdojo.task_suite.load_suites import get_suite

from src.common import CONFIG_PATH, TASKS_PATH, load_json


def task_number(task_id: str) -> int:
    return int(task_id.rsplit("_", 1)[1])


def build_attack(suite, attack_cfg: dict) -> FixedJailbreakAttack:
    """AgentDojo's important_instructions template with the names from the
    config, so the payload does not depend on which model is being run."""
    if attack_cfg["name"] != "important_instructions":
        raise ValueError("Only important_instructions is set up for this study.")
    attack = FixedJailbreakAttack(ImportantInstructionsAttack._JB_STRING, suite, target_pipeline=None)
    attack.user_name = attack_cfg["user_name"]
    attack.model_name = attack_cfg["model_name"]
    return attack


def select(config: dict) -> dict:
    sel = config["selection"]
    rng = random.Random(sel["seed"])
    cases = []
    for suite_name in sel["suites"]:
        suite = get_suite(config["benchmark_version"], suite_name)
        attack = build_attack(suite, config["attack"])
        n = sel["user_tasks_per_suite"]
        user_ids = rng.sample(sorted(suite.user_tasks, key=task_number), n)
        injection_ids = rng.sample(sorted(suite.injection_tasks, key=task_number), n)
        for user_id, injection_id in zip(user_ids, injection_ids):
            user_task = suite.get_user_task_by_id(user_id)
            injection_task = suite.get_injection_task_by_id(injection_id)
            # Raises if the user task never reads attacker-controllable content.
            payloads = attack.attack(user_task, injection_task)
            cases.append({
                "suite": suite_name,
                "user_task_id": user_id,
                "injection_task_id": injection_id,
                "user_prompt": user_task.PROMPT,
                "attacker_goal": injection_task.GOAL,
                "injections": payloads,
            })
    return {
        "benchmark_version": config["benchmark_version"],
        "selection": sel,
        "attack": config["attack"],
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--force", action="store_true", help="overwrite an existing tasks.json")
    args = parser.parse_args()
    if TASKS_PATH.exists() and not args.force:
        raise SystemExit(f"{TASKS_PATH} already exists. Re-selecting changes the experiment; use --force only before any results exist.")
    tasks = select(load_json(CONFIG_PATH))
    TASKS_PATH.write_text(json.dumps(tasks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for case in tasks["cases"]:
        print(f"{case['suite']:8} {case['user_task_id']:13} + {case['injection_task_id']}")
    print(f"Wrote {len(tasks['cases'])} cases to {TASKS_PATH}")


if __name__ == "__main__":
    main()
