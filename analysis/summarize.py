"""Summarize one model/configuration without calling a model or modifying results.

Run from the repository root with ``python -m analysis.summarize --help``.
Only Python's standard library and the shared record/defense definitions are used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

from src.defenses import DEFENSES
from src.schema import validate_record

ROOT = Path(__file__).resolve().parents[1]
LABELS = ("unnecessary_refusal", "tool_format_failure")
METRICS = ("clean_task_completion", "attacked_task_completion", "attack_success", "useful_resistance")


class AnalysisError(ValueError):
    """An input cannot be analyzed without guessing or mixing experiments."""


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise AnalysisError(f"Duplicate JSON key: {key}")
        obj[key] = value
    return obj


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except (OSError, ValueError) as exc:
        raise AnalysisError(f"Cannot read JSON from {path}: {exc}") from exc


def read_records(path):
    if not path.is_file():
        raise AnalysisError(f"Missing episode file: {path}")
    records, run_ids, attempts = [], set(), set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line, object_pairs_hook=unique_object)
            if not isinstance(record, dict):
                raise ValueError("record must be a JSON object")
            problems = validate_record(record)
            if problems:
                raise ValueError("; ".join(problems))
            for key in ("run_id", "case_id", "config_id", "suite", "user_task_id", "trace_path"):
                if not isinstance(record[key], str) or not record[key].strip():
                    raise ValueError(f"{key} must be a nonempty string")
            if record["defense"] not in DEFENSES:
                raise ValueError("unknown defense")
            if record["attacked"] and not isinstance(record["injection_task_id"], str):
                raise ValueError("injection_task_id must be a string for attacked episodes")
            for key in ("input_tokens", "output_tokens", "runtime_seconds"):
                value = record[key]
                if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                    raise ValueError(f"{key} must be a nonnegative finite number or null")
                if key != "runtime_seconds" and value is not None and type(value) is not int:
                    raise ValueError(f"{key} must be an integer or null")
            if record.get("attempt") is not None:
                attempt = record["attempt"]
                if type(attempt) is not int or attempt < 1:
                    raise ValueError("attempt must be a positive integer")
                key = (record["case_id"], record["defense"], attempt)
                if key in attempts:
                    raise ValueError("duplicate case/defense/attempt")
                attempts.add(key)
            if record["run_id"] in run_ids:
                raise ValueError("duplicate run_id")
            run_ids.add(record["run_id"])
            records.append(record)
        except (ValueError, TypeError) as exc:
            raise AnalysisError(f"{path.name}:{number}: {exc}") from exc
    if not records:
        raise AnalysisError("No episode records; wait for Ja's outputs before generating results.")
    for field in ("config_id", "config_hash", "model_id", "model_provider"):
        values = {json.dumps(r.get(field), sort_keys=True) for r in records}
        if len(values) != 1:
            raise AnalysisError(f"Mixed {field} values: analyze each model/configuration separately")
    return records


def make_plan(tasks, phase):
    cases = tasks.get("cases") if isinstance(tasks, dict) else None
    if not isinstance(cases, list) or not cases:
        raise AnalysisError("Task manifest must contain a nonempty cases list")
    for case in cases:
        if not isinstance(case, dict) or any(not isinstance(case.get(k), str) or not case[k].strip()
                                             for k in ("suite", "user_task_id", "injection_task_id")):
            raise AnalysisError("Every task needs nonempty suite, user_task_id and injection_task_id strings")
    defenses = DEFENSES[:1] if phase == "smoke" else DEFENSES
    selected_cases = cases if phase == "batch" else cases[:1]
    planned = {}
    for case in selected_cases:
        for attacked in (False, True):
            injection = case["injection_task_id"] if attacked else None
            case_id = f"{case['suite']}__{case['user_task_id']}__{injection if attacked else 'clean'}"
            for defense in defenses:
                key = f"{case_id}__{defense}"
                if key in planned:
                    raise AnalysisError(f"Duplicate planned case: {key}")
                planned[key] = dict(case_id=case_id, suite=case["suite"], user_task_id=case["user_task_id"],
                                    injection_task_id=injection, attacked=attacked, defense=defense)
    return planned


def select_records(records, selection, planned):
    entries = selection.get("selected") if isinstance(selection, dict) else None
    if not isinstance(entries, dict):
        raise AnalysisError("selected_runs.json must contain a selected object")
    by_id = {r["run_id"]: r for r in records}
    observed = set()
    for record in records:
        key = f"{record['case_id']}__{record['defense']}"
        if key not in planned or any(record[k] != v for k, v in planned[key].items()):
            raise AnalysisError(f"Record {record['run_id']} does not match the requested phase/task manifest")
        observed.add(key)
    if set(entries) != observed:
        raise AnalysisError("Selected-attempt keys must match all observed case/defense pairs exactly")
    selected = {}
    for key, entry in entries.items():
        if not isinstance(entry, dict) or entry.get("run_id") not in by_id:
            raise AnalysisError(f"Selection {key} refers to an unknown run_id")
        record = by_id[entry["run_id"]]
        if key != f"{record['case_id']}__{record['defense']}":
            raise AnalysisError(f"Selection key does not match its run: {key}")
        for field in ("status", "attempt"):
            if field in entry and entry[field] != record.get(field):
                raise AnalysisError(f"Selection has stale {field}: {key}")
        selected[key] = record
    return selected


def read_labels(path, records):
    if path is None:
        return {}
    known = {r["run_id"] for r in records}
    labels = {}
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {"run_id", "reviewer", "notes", *LABELS}
            if not required.issubset(reader.fieldnames or []):
                raise AnalysisError(f"Resolved labels require columns: {', '.join(sorted(required))}")
            for row in reader:
                run_id = row["run_id"]
                if run_id not in known:
                    raise AnalysisError(f"Review label has unknown run_id: {run_id}")
                if run_id in labels:
                    raise AnalysisError(f"Duplicate review labels for {run_id}; supply one resolved row per run")
                if not row["reviewer"] or not row["reviewer"].strip():
                    raise AnalysisError(f"Review label needs a reviewer: {run_id}")
                if any(row[field] not in ("yes", "no", "unclear") for field in LABELS):
                    raise AnalysisError(f"Review labels must be yes, no, or unclear: {run_id}")
                labels[run_id] = row
    except OSError as exc:
        raise AnalysisError(f"Cannot read resolved labels: {exc}") from exc
    return labels


def resolve_trace(record, results_dir, root):
    """Recognize archived pilot folders without rewriting the original records."""
    recorded = Path(record["trace_path"])
    primary = recorded if recorded.is_absolute() else root / recorded
    sibling = results_dir / "traces" / f"{record['run_id']}.json"
    for candidate, relocated in ((primary, False), (sibling, True)):
        candidate = candidate.resolve()
        if not any(candidate.is_relative_to(base.resolve()) for base in (root, results_dir)):
            continue
        if candidate.is_file():
            trace = read_json(candidate)
            if not isinstance(trace, dict) or trace.get("record") != record:
                raise AnalysisError(f"Trace record differs from episodes.jsonl: {candidate}")
            display = candidate.relative_to(root.resolve()).as_posix() if candidate.is_relative_to(root.resolve()) else candidate.as_posix()
            return display, relocated, trace.get("model_settings")
    return None, False, None


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def median(values):
    return statistics.median(values) if values else None


def success(record, metric):
    if metric.endswith("task_completion"):
        return record["utility_success"]
    if metric == "attack_success":
        return record["attack_success"]
    return record["utility_success"] and not record["attack_success"]


def aggregate(planned, selected, records, labels, suites):
    paired_cases = []
    for case_id in dict.fromkeys(p["case_id"] for p in planned.values()):
        case = next(p for p in planned.values() if p["case_id"] == case_id)
        exclusions = []
        for defense in DEFENSES:
            r = selected.get(f"{case_id}__{defense}")
            if r is None or r["status"] != "completed":
                exclusions.append(f"{defense}:{r['status'] if r else 'missing_record'}")
        paired_cases.append(dict(case_id=case_id, suite=case["suite"], attacked=case["attacked"],
                                 included=not exclusions, exclusion_reason="; ".join(exclusions)))
    paired_ids = {p["case_id"] for p in paired_cases if p["included"]}
    metrics, costs, errors, reviews = [], [], [], []
    for scope in ["combined", *suites]:
        for defense in dict.fromkeys(p["defense"] for p in planned.values()):
            for attacked in (False, True):
                def matches(r):
                    return (scope == "combined" or r["suite"] == scope) and r["defense"] == defense and r["attacked"] == attacked
                expected = [p for p in planned.values() if matches(p)]
                retained = [r for r in selected.values() if matches(r)]
                evaluated = [r for r in retained if r["status"] == "completed"]
                attempts = [r for r in records if matches(r)]
                paired = [r for r in evaluated if r["case_id"] in paired_ids]
                defaults = [selected[f"{r['case_id']}__default"] for r in paired]
                base = dict(scope=scope, defense=defense, condition="attacked" if attacked else "clean")
                counts = dict(planned=len(expected), selected=len(retained), evaluated=len(evaluated),
                              missing_evaluation=len(expected) - len(evaluated), missing_record=len(expected) - len(retained),
                              infrastructure_errors=sum(r["status"] == "infrastructure_error" for r in retained),
                              evaluation_errors=sum(r["status"] == "evaluation_error" for r in retained))
                for metric in METRICS[1:] if attacked else METRICS[:1]:
                    numerator = sum(success(r, metric) for r in evaluated)
                    paired_numerator = sum(success(r, metric) for r in paired)
                    default_numerator = sum(success(r, metric) for r in defaults)
                    metrics.append(dict(**base, metric=metric, **counts, numerator=numerator, denominator=len(evaluated),
                                        rate=ratio(numerator, len(evaluated)), paired_numerator=paired_numerator,
                                        paired_denominator=len(paired), paired_rate=ratio(paired_numerator, len(paired)),
                                        paired_default_rate=ratio(default_numerator, len(defaults)),
                                        difference_pp=100 * (paired_numerator - default_numerator) / len(paired) if paired else None,
                                        paired_excluded=len(expected) - len(paired)))
                totals = [r["input_tokens"] + r["output_tokens"] for r in evaluated
                          if r["input_tokens"] is not None and r["output_tokens"] is not None]
                runtimes = [r["runtime_seconds"] for r in evaluated if r["runtime_seconds"] is not None]
                attempt_totals = [r["input_tokens"] + r["output_tokens"] for r in attempts
                                  if r["input_tokens"] is not None and r["output_tokens"] is not None]
                costs.append(dict(**base, evaluated=len(evaluated), median_total_tokens=median(totals),
                                  tokens_available=len(totals), tokens_missing=len(evaluated) - len(totals),
                                  median_runtime_seconds=median(runtimes), runtimes_available=len(runtimes),
                                  runtimes_missing=len(evaluated) - len(runtimes), all_attempts=len(attempts),
                                  all_attempts_tokens_available=len(attempt_totals),
                                  observed_attempt_tokens=sum(attempt_totals) if attempt_totals else None,
                                  all_attempts_total_tokens=sum(attempt_totals) if attempts and len(attempt_totals) == len(attempts) else None))
                errors.append(dict(**base, **counts, all_attempts=len(attempts), unselected_attempts=len(attempts) - len(retained),
                                   infrastructure_error_attempts=sum(r["status"] == "infrastructure_error" for r in attempts),
                                   evaluation_error_attempts=sum(r["status"] == "evaluation_error" for r in attempts),
                                   content_filter_attempts=sum(r["termination_reason"] == "content_filter" for r in attempts),
                                   selected_content_filter=sum(r["termination_reason"] == "content_filter" for r in retained)))
                failed = [r for r in evaluated if not r["utility_success"]]
                for label in LABELS:
                    values = [labels.get(r["run_id"], {}).get(label, "unreviewed") for r in evaluated]
                    yes, no = values.count("yes"), values.count("no")
                    reviews.append(dict(**base, label=label, evaluated=len(evaluated), yes=yes, no=no,
                                        unclear=values.count("unclear"), unreviewed=values.count("unreviewed"),
                                        numerator=yes, denominator=yes + no, rate=ratio(yes, yes + no),
                                        failed_tasks=len(failed), failed_tasks_labeled=sum(r["run_id"] in labels for r in failed),
                                        failed_tasks_unreviewed=sum(r["run_id"] not in labels for r in failed)))
    return dict(metrics=metrics, costs=costs, errors=errors, reviews=reviews, paired_cases=paired_cases)


def summarize(results_dir, phase, tasks_path, labels_path=None, root=ROOT, allow_synthetic=False):
    if phase not in ("smoke", "integration", "batch"):
        raise AnalysisError("phase must be smoke, integration, or batch")
    results_dir, tasks_path, root = Path(results_dir).resolve(), Path(tasks_path).resolve(), Path(root).resolve()
    labels_path = Path(labels_path).resolve() if labels_path is not None else None
    records = read_records(results_dir / "episodes.jsonl")
    synthetic = any(r.get("model_provider") in ("offline", "mock") or r["config_id"].endswith(("-offline", "-mock")) for r in records)
    if synthetic and not allow_synthetic:
        raise AnalysisError("Synthetic/offline records are not empirical results; use --allow-synthetic only for testing")
    tasks = read_json(tasks_path)
    planned = make_plan(tasks, phase)
    selected = select_records(records, read_json(results_dir / "selected_runs.json"), planned)
    labels = read_labels(labels_path, records)
    tables = aggregate(planned, selected, records, labels, sorted({c["suite"] for c in tasks["cases"]}))
    warnings = []
    if phase != "batch":
        warnings.append("Pilot only: one user task is tested. Do not pool these episodes with the preliminary batch or claim defense effectiveness.")
    if synthetic:
        warnings.append("SYNTHETIC CHECK ONLY: these records do not measure model behavior.")
    if labels_path is None:
        warnings.append("Resolved review labels have not been supplied. Unreviewed is not no; refusal/tool-format rates remain unavailable.")
    selected_cases, model_settings = [], []
    for key, expected in planned.items():
        record = selected.get(key)
        trace, relocated, settings = resolve_trace(record, results_dir, root) if record else (None, False, None)
        if settings is not None and settings not in model_settings:
            model_settings.append(settings)
        row = dict(**expected, run_id=record["run_id"] if record else None,
                   status=record["status"] if record else "missing_record",
                   utility_success=record["utility_success"] if record else None,
                   attack_success=record["attack_success"] if record else None,
                   recorded_trace_path=record["trace_path"] if record else None,
                   resolved_trace_path=trace, trace_relocated=relocated,
                   paired_included=expected["case_id"] in {p["case_id"] for p in tables["paired_cases"] if p["included"]})
        for label in LABELS:
            row[label] = labels.get(row["run_id"], {}).get(label, "unreviewed")
        row["reviewer"] = labels.get(row["run_id"], {}).get("reviewer")
        row["review_notes"] = labels.get(row["run_id"], {}).get("notes")
        selected_cases.append(row)
    if len(model_settings) > 1:
        raise AnalysisError("Selected traces contain different model settings; split the experiment before analysis")
    relocated_count = sum(r["trace_relocated"] for r in selected_cases)
    missing_traces = sum(r["run_id"] is not None and r["resolved_trace_path"] is None for r in selected_cases)
    if relocated_count:
        warnings.append(f"{relocated_count} stale trace paths resolved in the input folder's traces directory. Raw results were not changed; see selected_cases.csv.")
    if missing_traces:
        warnings.append(f"{missing_traces} selected traces are missing. Outcomes remain reported, but trace evidence is unavailable.")
    missing_evaluations = len(planned) - sum(r["status"] == "completed" for r in selected.values())
    if missing_evaluations:
        warnings.append(f"{missing_evaluations}/{len(planned)} planned episodes lack evaluated outcomes; see error_summary.csv and paired_cases.csv.")
    revisions = sorted({r.get("code_revision") or "unknown" for r in records})
    if any(r == "unknown" or r.endswith("-dirty") for r in revisions):
        warnings.append("Run code revision is unknown or marked dirty; the exact executed source is not fully identified by a clean commit.")
    failed = [r for r in selected.values() if r["status"] == "completed" and not r["utility_success"]]
    if labels_path and any(r["run_id"] not in labels for r in failed):
        warnings.append("Some failed-task episodes still lack resolved labels; review counts are incomplete.")
    ignored_labels = sorted(set(labels) - {r["run_id"] for r in selected.values() if r["status"] == "completed"})
    if ignored_labels:
        warnings.append(f"{len(ignored_labels)} label rows refer to unselected or unevaluated attempts and are excluded from review rates.")
    inputs = {"episodes": results_dir / "episodes.jsonl", "selection": results_dir / "selected_runs.json", "tasks": tasks_path,
              "analysis_script": Path(__file__), "schema": ROOT / "src/schema.py", "defenses": ROOT / "src/defenses.py"}
    if labels_path:
        inputs["resolved_labels"] = labels_path
    metadata = dict(phase=phase, synthetic=synthetic, config_id=records[0]["config_id"],
                    config_hash=records[0].get("config_hash"), model_id=records[0].get("model_id"),
                    model_provider=records[0].get("model_provider"), model_settings=model_settings,
                    run_code_revisions=revisions, planned_episodes=len(planned), selected_episodes=len(selected),
                    evaluated_episodes=len(planned) - missing_evaluations, all_attempts=len(records),
                    resolved_labels_supplied=labels_path is not None, ignored_label_run_ids=ignored_labels,
                    input_sha256={key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in inputs.items()})
    tables["selected_cases"] = selected_cases
    tables["review_queue"] = [dict(run_id=r["run_id"], case_id=r["case_id"], defense=r["defense"],
                                   suite=r["suite"], attacked=r["attacked"], status=r["status"],
                                   utility_success=r["utility_success"], attack_success=r["attack_success"],
                                   trace_path=r["resolved_trace_path"],
                                   action="review_failed_task" if r["status"] == "completed" else "clarify_error_with_Ja",
                                   labels_supplied=r["run_id"] in labels)
                              for r in selected_cases if r["run_id"] and (r["status"] != "completed" or r["utility_success"] is False)]
    selected_ids = {r["run_id"] for r in selected.values()}
    tables["attempts"] = [{**r, "selected_for_analysis": r["run_id"] in selected_ids} for r in records]
    return dict(metadata=metadata, warnings=warnings, **tables)


def write_csv(path, rows, fields=None):
    fields = fields or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def rate_text(n, d):
    return f"{n}/{d} ({100 * n / d:.1f}%)" if d else "0/0 (N/A)"


def markdown_table(headers, rows):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ") if value is not None else "N/A"
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |",
                      *["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]])


def render_report(summary):
    m = summary["metadata"]
    stage = "SYNTHETIC CHECK" if m["synthetic"] else "PRELIMINARY BATCH" if m["phase"] == "batch" else "PILOT"
    lines = [f"# {stage}: {m['model_id'] or 'unknown model'} / {m['phase']}", "",
             f"Evaluated **{m['evaluated_episodes']}/{m['planned_episodes']}** planned episodes; "
             f"{m['selected_episodes']} retained attempts from {m['all_attempts']} total attempts. "
             f"Configuration: `{m['config_id']}`; hash: `{m['config_hash']}`.", "",
             "## Limitations and input checks", "",
             *[f"- {warning}" for warning in summary["warnings"]],
             "- Descriptive counts only. Small samples do not establish preserved utility or generalizable defense benefits. Interpret changes relative to each model's Default attack-success rate.",
             "- Useful resistance means task success AND attack failure within the same attacked episode.",
             "- Rates use evaluated selected attempts. Missing evaluations are never counted as attack failures or successful defenses.",
             "- Differences are percentage points (defense minus Default), calculated only on cases evaluated under all three defenses. The paired denominator may differ from the overall rate denominator.",
             "- Token/runtime medians use evaluated selected attempts with known measurements. All-attempt token totals include errors/retries; unavailable totals remain blank. No monetary estimate is made.",
             "- Review rates cover definite yes/no labels on evaluated selected attempts only. Unclear and unreviewed counts are separate; failed-task review does not estimate prevalence across all episodes.", ""]
    for title, combined in (("Main comparison", True), ("Suite breakdown", False)):
        rows = [r for r in summary["metrics"] if (r["scope"] == "combined") == combined]
        lines += [f"## {title}", "", markdown_table(
            ["Suite", "Defense", "Metric", "Rate", "Evaluated/planned", "Missing evaluation", "Paired rate", "Δ vs Default (pp)", "Excluded pairs"],
            [[r["scope"], r["defense"], r["metric"], rate_text(r["numerator"], r["denominator"]),
              f"{r['evaluated']}/{r['planned']}", r["missing_evaluation"], rate_text(r["paired_numerator"], r["paired_denominator"]),
              f"{r['difference_pp']:+.1f}" if r["difference_pp"] is not None else None, r["paired_excluded"]] for r in rows]), ""]
    lines += ["## Token and runtime summary", "", markdown_table(
        ["Suite", "Defense", "Condition", "Median tokens", "Token n", "Median seconds", "Runtime n", "All-attempt tokens"],
        [[r["scope"], r["defense"], r["condition"], r["median_total_tokens"], f"{r['tokens_available']}/{r['evaluated']}",
          r["median_runtime_seconds"], f"{r['runtimes_available']}/{r['evaluated']}", r["all_attempts_total_tokens"]] for r in summary["costs"]]), "",
        "## Error summary", "", markdown_table(
            ["Suite", "Defense", "Condition", "Missing records", "Retained infrastructure errors", "Retained evaluation errors", "Infrastructure error attempts", "Content-filter attempts"],
            [[r["scope"], r["defense"], r["condition"], r["missing_record"], r["infrastructure_errors"], r["evaluation_errors"],
              r["infrastructure_error_attempts"], r["content_filter_attempts"]] for r in summary["errors"]]), "",
        "## Review summary", "", markdown_table(
            ["Suite", "Defense", "Condition", "Label", "Yes/definite", "Unclear", "Unreviewed", "Failed tasks labeled/total"],
            [[r["scope"], r["defense"], r["condition"], r["label"], rate_text(r["numerator"], r["denominator"]), r["unclear"],
              r["unreviewed"], f"{r['failed_tasks_labeled']}/{r['failed_tasks']}"] for r in summary["reviews"]]), "",
        "## Reproduction and traceability", "",
        "`summary.json` records input hashes and saved model settings. `selected_cases.csv` lists every planned episode, selected run ID, trace location and review labels. "
        "`paired_cases.csv` gives every paired inclusion/exclusion. `attempts.csv` retains the full attempt audit. "
        "`review_queue.csv` identifies failed tasks and execution/evaluation errors without assigning behavioral labels.", ""]
    return "\n".join(lines)


def write_outputs(summary, output, results_dir):
    output, results_dir = Path(output).resolve(), Path(results_dir).resolve()
    if output.is_relative_to(results_dir) or results_dir.is_relative_to(output):
        raise AnalysisError("Write analysis to a separate directory, outside the raw result tree")
    output.mkdir(parents=True, exist_ok=True)
    tables = {"main_comparison.csv": [r for r in summary["metrics"] if r["scope"] == "combined"],
              "suite_breakdown.csv": [r for r in summary["metrics"] if r["scope"] != "combined"],
              "cost_summary.csv": summary["costs"], "error_summary.csv": summary["errors"],
              "review_summary.csv": summary["reviews"], "selected_cases.csv": summary["selected_cases"],
              "paired_cases.csv": summary["paired_cases"], "attempts.csv": summary["attempts"]}
    for filename, rows in tables.items():
        fields = list(dict.fromkeys(k for row in rows for k in row))
        write_csv(output / filename, rows, fields)
    queue_fields = ["run_id", "case_id", "defense", "suite", "attacked", "status", "utility_success", "attack_success", "trace_path", "action", "labels_supplied"]
    write_csv(output / "review_queue.csv", summary["review_queue"], queue_fields)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    (output / "report.md").write_text(render_report(summary), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True, help="One model/configuration folder containing episodes.jsonl and selected_runs.json")
    parser.add_argument("--phase", choices=("smoke", "integration", "batch"), required=True, help="Defines planned coverage; pilots use only the first task")
    parser.add_argument("--tasks", type=Path, default=ROOT / "config/tasks.json", help="Exact task manifest used by the run")
    parser.add_argument("--resolved-labels", type=Path, help="One resolved review row per run_id; never pool independent reviewer rows")
    parser.add_argument("--output", type=Path, required=True, help="Separate analysis output directory")
    parser.add_argument("--allow-synthetic", action="store_true", help="Permit clearly labeled mock/offline checks; never treat them as study results")
    args = parser.parse_args()
    try:
        summary = summarize(args.results_dir, args.phase, args.tasks, args.resolved_labels, allow_synthetic=args.allow_synthetic)
        write_outputs(summary, args.output, args.results_dir)
    except (AnalysisError, OSError) as exc:
        parser.exit(2, f"Analysis stopped: {exc}\n")
    m = summary["metadata"]
    print(f"{m['evaluated_episodes']}/{m['planned_episodes']} planned episodes evaluated. Report: {args.output / 'report.md'}")
    for warning in summary["warnings"]:
        print(f"Note: {warning}")


if __name__ == "__main__":
    main()
