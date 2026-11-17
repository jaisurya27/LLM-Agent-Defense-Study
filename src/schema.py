"""Episode record format shared by the runner (Ja) and the analysis (Ab).

One JSON object per line in episodes.jsonl. Unavailable values are null,
never a guessed false or zero.
"""

STATUSES = ("completed", "infrastructure_error", "evaluation_error")

# Fields agreed in the team work plan.
REQUIRED_FIELDS = (
    "run_id", "case_id", "config_id", "suite", "user_task_id", "injection_task_id",
    "defense", "attacked",
    "status", "utility_success", "attack_success",
    "input_tokens", "output_tokens", "runtime_seconds", "termination_reason",
    "error_message", "trace_path",
)

# Extra fields the runner adds for reproducibility. Analysis may ignore them.
EXTRA_FIELDS = (
    "attempt", "started_at", "model_provider", "model_id", "llm_calls",
    "config_hash", "code_revision",
)


def validate_record(record: dict) -> list[str]:
    """Return a list of problems. An empty list means the record is valid."""
    problems = [f"missing field: {f}" for f in REQUIRED_FIELDS if f not in record]
    if problems:
        return problems
    if record["status"] not in STATUSES:
        problems.append(f"bad status: {record['status']!r}")
    if not isinstance(record["attacked"], bool):
        problems.append("attacked must be a boolean")
    if record["attacked"] and record["injection_task_id"] is None:
        problems.append("attacked episode needs injection_task_id")
    if not record["attacked"]:
        if record["injection_task_id"] is not None:
            problems.append("clean episode must have injection_task_id null")
        if record["attack_success"] is not None:
            problems.append("clean episode must have attack_success null")
    if record["status"] == "completed":
        if not isinstance(record["utility_success"], bool):
            problems.append("completed episode needs boolean utility_success")
        if record["attacked"] and not isinstance(record["attack_success"], bool):
            problems.append("completed attacked episode needs boolean attack_success")
    else:
        if record["utility_success"] is not None or record["attack_success"] is not None:
            problems.append("outcomes must be null unless status is completed")
        if not record["error_message"]:
            problems.append("error status needs error_message")
    return problems
