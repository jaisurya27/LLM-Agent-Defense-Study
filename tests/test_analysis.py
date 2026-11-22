"""Numerical and data-integrity checks; no API access or third-party packages."""

import csv
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from analysis.summarize import AnalysisError, summarize, write_outputs

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/analysis"


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "synthetic"
        shutil.copytree(FIXTURE, self.data)

    def analyze(self, labels=True, phase="batch"):
        return summarize(self.data, phase, self.data / "tasks.json",
                         self.data / "resolved_labels.csv" if labels else None,
                         root=self.root, allow_synthetic=True)

    def records(self):
        return [json.loads(line) for line in (self.data / "episodes.jsonl").read_text().splitlines()]

    def save_records(self, records):
        (self.data / "episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))

    def selection(self):
        return json.loads((self.data / "selected_runs.json").read_text())

    def save_selection(self, selection):
        (self.data / "selected_runs.json").write_text(json.dumps(selection))

    @staticmethod
    def row(summary, table, **values):
        return next(r for r in summary[table] if all(r[k] == v for k, v in values.items()))

    def test_known_metrics_use_paired_cases_for_differences(self):
        result = self.analyze()
        self.assertEqual(result["metadata"]["planned_episodes"], 18)
        self.assertEqual(result["metadata"]["selected_episodes"], 17)
        self.assertEqual(result["metadata"]["evaluated_episodes"], 16)
        self.assertEqual(result["metadata"]["all_attempts"], 18)
        row = self.row(result, "metrics", scope="combined", defense="warning", metric="attacked_task_completion")
        self.assertEqual((row["numerator"], row["denominator"]), (3, 3))
        self.assertEqual((row["paired_numerator"], row["paired_denominator"]), (2, 2))
        # Overall differences would be +33.3 pp; the matched cases give +50 pp.
        self.assertEqual(row["difference_pp"], 50)
        self.assertEqual(row["paired_excluded"], 1)
        for defense, numerator, denominator, delta in [("default", 0, 3, 0), ("warning", 3, 3, 100), ("warning_boundaries", 1, 2, 50)]:
            row = self.row(result, "metrics", scope="combined", defense=defense, metric="useful_resistance")
            self.assertEqual((row["numerator"], row["denominator"], row["difference_pp"]), (numerator, denominator, delta))
        exclusions = [r for r in result["paired_cases"] if not r["included"]]
        self.assertEqual(len(exclusions), 2)
        self.assertTrue(any("evaluation_error" in r["exclusion_reason"] for r in exclusions))
        self.assertTrue(any("missing_record" in r["exclusion_reason"] for r in exclusions))

    def test_suite_breakdown_and_empty_denominators(self):
        result = self.analyze()
        banking = self.row(result, "metrics", scope="banking", defense="warning", metric="clean_task_completion")
        self.assertEqual((banking["numerator"], banking["denominator"], banking["difference_pp"]), (1, 2, -50))
        slack = self.row(result, "metrics", scope="slack", defense="warning", metric="clean_task_completion")
        self.assertEqual(slack["missing_record"], 1)
        self.assertIsNone(slack["rate"])
        self.assertIsNone(slack["difference_pp"])

    def test_retry_is_not_double_counted_but_error_attempt_is_retained(self):
        result = self.analyze()
        row = self.row(result, "errors", scope="combined", defense="warning", condition="attacked")
        self.assertEqual((row["evaluated"], row["all_attempts"], row["unselected_attempts"]), (3, 4, 1))
        self.assertEqual(row["infrastructure_error_attempts"], 1)
        self.assertEqual(row["infrastructure_errors"], 0)
        self.assertEqual(sum(r["selected_for_analysis"] for r in result["attempts"]), 17)
        error = self.row(result, "errors", scope="combined", defense="warning_boundaries", condition="attacked")
        self.assertEqual((error["evaluation_errors"], error["missing_evaluation"]), (1, 1))

    def test_tokens_runtime_and_unknown_values(self):
        result = self.analyze()
        row = self.row(result, "costs", scope="combined", defense="default", condition="clean")
        self.assertEqual(row["median_total_tokens"], 40)
        self.assertEqual(row["median_runtime_seconds"], 2)
        row = self.row(result, "costs", scope="combined", defense="warning", condition="clean")
        self.assertEqual((row["median_total_tokens"], row["tokens_available"], row["tokens_missing"]), (120, 1, 1))
        self.assertEqual((row["runtimes_available"], row["runtimes_missing"]), (1, 1))
        retry = self.row(result, "costs", scope="combined", defense="warning", condition="attacked")
        self.assertEqual(retry["observed_attempt_tokens"], 360)
        self.assertIsNone(retry["all_attempts_total_tokens"])

    def test_review_labels_are_not_inferred_from_task_failure(self):
        result = self.analyze(labels=False)
        row = self.row(result, "reviews", scope="combined", defense="warning", condition="clean", label="unnecessary_refusal")
        self.assertEqual((row["yes"], row["no"], row["unreviewed"], row["failed_tasks"]), (0, 0, 2, 1))
        self.assertIsNone(row["rate"])
        labeled = self.analyze()
        row = self.row(labeled, "reviews", scope="combined", defense="warning_boundaries", condition="attacked", label="unnecessary_refusal")
        self.assertEqual((row["yes"], row["no"], row["unclear"], row["unreviewed"]), (0, 0, 1, 1))
        self.assertIsNone(row["rate"])
        self.assertEqual(len(labeled["review_queue"]), 4)
        self.assertEqual(sum(r["action"] == "clarify_error_with_Ja" for r in labeled["review_queue"]), 1)

    def test_mock_data_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(AnalysisError, "Synthetic/offline"):
            summarize(self.data, "batch", self.data / "tasks.json", root=self.root)
        self.assertTrue(self.analyze()["metadata"]["synthetic"])

    def test_rejects_duplicate_run_or_attempt(self):
        records = self.records()
        records.append(dict(records[0]))
        self.save_records(records)
        with self.assertRaisesRegex(AnalysisError, "duplicate"):
            self.analyze()

    def test_rejects_missing_fields_and_invalid_numbers(self):
        original = self.records()
        for field, value in [("input_tokens", -1), ("runtime_seconds", float("nan")), ("output_tokens", True)]:
            records = [dict(r) for r in original]
            records[0][field] = value
            self.save_records(records)
            with self.subTest(field=field), self.assertRaisesRegex(AnalysisError, field):
                self.analyze()
        del original[0]["utility_success"]
        self.save_records(original)
        with self.assertRaisesRegex(AnalysisError, "missing field"):
            self.analyze()

    def test_rejects_mixed_models_and_configurations(self):
        original = self.records()
        for field in ("model_id", "config_id", "config_hash", "model_provider"):
            records = [dict(r) for r in original]
            records[0][field] = "different"
            self.save_records(records)
            with self.subTest(field=field), self.assertRaisesRegex(AnalysisError, f"Mixed {field}"):
                self.analyze()

    def test_rejects_incomplete_unknown_and_stale_selection(self):
        original = self.selection()
        key = next(iter(original["selected"]))
        for change in ("missing", "unknown", "stale", "wrong_case"):
            selection = json.loads(json.dumps(original))
            if change == "missing":
                del selection["selected"][key]
            elif change == "unknown":
                selection["selected"][key]["run_id"] = "not-a-run"
            elif change == "stale":
                selection["selected"][key]["status"] = "infrastructure_error"
            else:
                selection["selected"][key]["run_id"] = self.records()[1]["run_id"]
            self.save_selection(selection)
            with self.subTest(change=change), self.assertRaises(AnalysisError):
                self.analyze()

    def test_rejects_wrong_phase_or_task_identity(self):
        with self.assertRaisesRegex(AnalysisError, "phase/task manifest"):
            self.analyze(phase="integration")
        records = self.records()
        records[0]["suite"] = "different-suite"
        self.save_records(records)
        with self.assertRaisesRegex(AnalysisError, "phase/task manifest"):
            self.analyze()

    def test_rejects_duplicate_json_selection_keys(self):
        selection = self.selection()
        key, entry = next(iter(selection["selected"].items()))
        repeated = json.dumps(key) + ":" + json.dumps(entry)
        (self.data / "selected_runs.json").write_text('{"selected":{' + repeated + ',' + repeated + '}}')
        with self.assertRaisesRegex(AnalysisError, "Duplicate JSON key"):
            self.analyze()

    def test_partial_labels_keep_failed_task_coverage_explicit(self):
        path = self.data / "resolved_labels.csv"
        path.write_text("\n".join(path.read_text().splitlines()[:2]) + "\n")
        result = self.analyze()
        row = self.row(result, "reviews", scope="combined", defense="warning_boundaries", condition="attacked", label="unnecessary_refusal")
        self.assertEqual(row["failed_tasks_unreviewed"], 1)
        self.assertTrue(any("failed-task episodes still lack" in w for w in result["warnings"]))

    def test_content_filter_errors_never_become_successful_resistance(self):
        records = self.records()
        blocked = next(r for r in records if r["status"] == "evaluation_error")
        blocked.update(status="infrastructure_error", termination_reason="content_filter")
        self.save_records(records)
        selection = self.selection()
        selection["selected"][f"{blocked['case_id']}__{blocked['defense']}"]["status"] = blocked["status"]
        self.save_selection(selection)
        result = self.analyze()
        row = self.row(result, "errors", scope="combined", defense="warning_boundaries", condition="attacked")
        self.assertEqual((row["content_filter_attempts"], row["selected_content_filter"], row["infrastructure_errors"]), (1, 1, 1))
        metric = self.row(result, "metrics", scope="combined", defense="warning_boundaries", metric="useful_resistance")
        self.assertEqual((metric["numerator"], metric["denominator"]), (1, 2))

    def test_rejects_unresolved_duplicate_or_unknown_review_rows(self):
        path = self.data / "resolved_labels.csv"
        original = path.read_text()
        path.write_text(original + original.splitlines()[1] + "\n")
        with self.assertRaisesRegex(AnalysisError, "Duplicate review"):
            self.analyze()
        path.write_text(original.replace("SYNTHETIC Is+Re,yes", "SYNTHETIC Is+Re,maybe"))
        with self.assertRaisesRegex(AnalysisError, "yes, no, or unclear"):
            self.analyze()
        first_id = original.splitlines()[1].split(",")[0]
        path.write_text(original.replace(first_id, "unknown-run"))
        with self.assertRaisesRegex(AnalysisError, "unknown run_id"):
            self.analyze()

    def test_archived_trace_paths_are_resolved_without_mutating_input(self):
        record = self.records()[0]
        trace_dir = self.data / "traces"
        trace_dir.mkdir()
        trace_path = trace_dir / f"{record['run_id']}.json"
        trace_path.write_text(json.dumps({"record": record, "model_settings": {"model_id": "mock-model"}}))
        before = (self.data / "episodes.jsonl").read_bytes()
        row = self.row(self.analyze(), "selected_cases", run_id=record["run_id"])
        self.assertTrue(row["trace_relocated"])
        self.assertEqual(row["resolved_trace_path"], trace_path.relative_to(self.root).as_posix())
        self.assertEqual((self.data / "episodes.jsonl").read_bytes(), before)
        trace_path.write_text(json.dumps({"record": {**record, "utility_success": False}}))
        with self.assertRaisesRegex(AnalysisError, "Trace record differs"):
            self.analyze()

    def test_outputs_are_deterministic_and_include_missing_cases(self):
        summary = self.analyze()
        output = self.root / "report"
        write_outputs(summary, output, self.data)
        first = {p.name: p.read_bytes() for p in output.iterdir()}
        write_outputs(self.analyze(), output, self.data)
        self.assertEqual(first, {p.name: p.read_bytes() for p in output.iterdir()})
        with (output / "selected_cases.csv").open(newline="") as stream:
            cases = list(csv.DictReader(stream))
        self.assertEqual(len(cases), 18)
        self.assertEqual(sum(c["status"] == "missing_record" for c in cases), 1)
        self.assertIn("SYNTHETIC CHECK", (output / "report.md").read_text())
        with self.assertRaisesRegex(AnalysisError, "separate directory"):
            write_outputs(summary, self.data / "analysis", self.data)

    def test_real_pilot_records_and_defense_differences(self):
        for model, useful, delta in [("gpt41nano", 0, 0), ("gpt5", 1, -100)]:
            result = summarize(ROOT / f"results/integration_{model}", "integration", ROOT / "config/tasks.json")
            self.assertEqual(result["metadata"]["evaluated_episodes"], 6)
            self.assertEqual(sum(r["trace_relocated"] for r in result["selected_cases"]), 6)
            default = self.row(result, "metrics", scope="combined", defense="default", metric="useful_resistance")
            self.assertEqual(default["numerator"], useful)
            boundaries = self.row(result, "metrics", scope="combined", defense="warning_boundaries", metric="attacked_task_completion")
            self.assertEqual(boundaries["difference_pp"], delta)
            self.assertFalse(result["metadata"]["resolved_labels_supplied"])

    def test_smoke_stays_separate_and_has_no_paired_comparisons(self):
        for model in ("gpt41nano", "gpt5"):
            result = summarize(ROOT / f"results/smoke_{model}", "smoke", ROOT / "config/tasks.json")
            self.assertEqual(result["metadata"]["planned_episodes"], 2)
            self.assertEqual(result["metadata"]["evaluated_episodes"], 2)
            self.assertTrue(all(r["defense"] == "default" and r["difference_pp"] is None for r in result["metrics"]))
            self.assertTrue(all(not r["included"] for r in result["paired_cases"]))


if __name__ == "__main__":
    unittest.main()
