# Results analysis (Ab)

This module produces descriptive comparison tables from Ja's saved records.
It makes no API calls, changes no raw results, and needs only Python's standard
library. Run commands from the repository root.

## Reproduce the committed pilot reports

```bash
python -m analysis.summarize \
  --results-dir results/integration_gpt41nano \
  --phase integration \
  --output analysis/reports/integration_gpt41nano

python -m analysis.summarize \
  --results-dir results/integration_gpt5 \
  --phase integration \
  --output analysis/reports/integration_gpt5
```

These are **pilot checks on one Banking task**, not the 36-episode study.
Each model gets its own report. Do not pool models, smoke tests, integration
episodes, or offline records. Slack rows have zero planned pilot episodes;
their rates are unavailable, not 0%.

Smoke checks can be summarized separately with `--phase smoke` and the
corresponding `results/smoke_*` input folder. Smoke has only Default, so
differences across all three defenses are unavailable.

## Analyze the preliminary batch when Ja supplies it

```bash
python -m analysis.summarize \
  --results-dir results/preliminary \
  --phase batch \
  --tasks config/tasks.json \
  --resolved-labels review/resolved_labels.csv \
  --output analysis/reports/preliminary
```

Use the exact task manifest saved with that experiment. Omit
`--resolved-labels` until Is and Re supply their resolved labels; numeric
outcomes can be analyzed first, while review counts remain unreviewed.
If a supplied labels file does not exist, analysis stops instead of silently
dropping it. Rerun the same command once the missing data arrives.

`--phase batch` plans every manifest task, clean and attacked, under all three
defenses (36 episodes for the current six tasks). It does not assume that
every planned episode has a record. Missing records and recorded errors
remain visible. A wholly absent/empty episode file is an error, not a table
of fabricated outcomes. Phase is explicit so pilot data is not silently
presented as a complete batch.

## Outputs and table headings

| Output | Contents |
|---|---|
| `report.md` | Readable main comparison, suite breakdown, token/runtime summary, error/review tables, limitations |
| `main_comparison.csv` | Combined metrics: defense, condition, metric, planned/selected/evaluated/missing counts, numerator, denominator, rate, paired rate, difference in percentage points |
| `suite_breakdown.csv` | Same metrics separately for Banking and Slack |
| `cost_summary.csv` | Median total tokens and runtime by suite, defense and clean/attacked condition; available/missing measurement counts; all-attempt token totals |
| `error_summary.csv` | Missing records, retained infrastructure/evaluation errors, all-attempt error counts, excluded attempts, content-filter counts |
| `review_summary.csv` | Yes/no/unclear/unreviewed counts, definite-label rates, failed-task label coverage |
| `selected_cases.csv` | Every planned case/defense, selected run ID (blank if missing), outcomes, original/resolved trace paths, paired inclusion and resolved labels |
| `paired_cases.csv` | One row per task and clean/attack pairing, inclusion flag and explicit exclusion reasons |
| `attempts.csv` | Every original attempt, including failures/retries, with a selected-for-analysis flag |
| `review_queue.csv` | Selected failed-task and error records with both outcomes and trace paths; no inferred behavioral labels |
| `summary.json` | Machine-readable tables, saved model settings, source code revisions and input SHA-256 hashes |

CSV rates are fractions from 0 to 1. `difference_pp` is a percentage-point
difference, not a fraction or relative percentage. Missing numeric values
are empty in CSV, null in JSON and N/A in the readable report.

## Metric and denominator rules

- **Clean task completion:** successful legitimate tasks / evaluated clean episodes.
- **Attacked task completion:** successful legitimate tasks / evaluated attacked episodes.
- **Attack success:** successful attacks / evaluated attacked episodes.
- **Useful resistance:** episodes with legitimate task success AND attack failure / evaluated attacked episodes.

Overall rates use all evaluated retained attempts in the relevant group.
For differences from Default, use only the intersection of cases with valid
outcomes under **all three** defenses. Clean and attacked intersections are
separate. The paired denominator and excluded case list are provided, so an
overall-rate difference is never substituted for a paired difference.
Positive attack-success differences are worse security; positive completion
and useful-resistance differences are better outcomes. No composite score,
significance claim or bootstrap inference is produced for this small batch.

The script validates the shared `src/schema.py` fields plus identities,
numeric measurements, duplicate run/attempt IDs, and phase/task membership.
It requires Ja's `selected_runs.json` to identify exactly one attempt for
every observed case/defense pair. It does not choose the best outcome or
infer a replacement selection. Mixed model IDs, providers, configuration
IDs or configuration hashes cause an error. Multiple attempts are retained
for audit and cost accounting but never double-counted as episodes.

Token medians require both input and output counts; runtime medians require
known runtime. They use evaluated selected attempts. All-attempt token
totals include retry and error attempts, and stay null if any measurement
is unknown; an observed subtotal is also supplied. Tokens are an overhead
measure, not a currency estimate. No unrecorded API usage is guessed.

## Resolved review label interface

Is and Re own the judgments. Provide a CSV with exactly one resolved row
per reviewed `run_id` and these columns:

```csv
run_id,reviewer,unnecessary_refusal,tool_format_failure,notes
```

Each label must be `yes`, `no`, or `unclear`. `reviewer` identifies who
resolved the judgment (for example `Is+Re`); `notes` holds the evidence or
resolution explanation. Keep the two independent original label sets
separate. Passing both sets with duplicate run IDs is rejected.

An absent label remains **unreviewed**, never `no`. A failed utility check
does not imply refusal. Unclear labels are counted but excluded from the
yes/(yes+no) rate. Those rates describe definitely labeled episodes, not
all study episodes. Failed-task coverage is reported separately because
the plan requires review of failures, not exhaustive review of successes.
Labels on unselected or unevaluated attempts are retained as an input audit
warning and excluded from review rates. Unknown run IDs are rejected.

## Archived trace paths and reproducibility

The committed pilot JSONL files point to their original `results/integration/`
or `results/smoke/` directories. The files now live in model-specific folders.
If the recorded path is missing, analysis looks for
`<input-folder>/traces/<run_id>.json` and verifies that its embedded record
matches the JSONL record. It reports the original and resolved paths without
editing either source. Missing traces are disclosed; mismatched traces stop
analysis. This allows Ja to retain the original data unchanged.

Reports are deterministic for unchanged inputs. `summary.json` records hashes
of the episode file, selected-attempt list, task manifest, optional labels,
analysis script and shared schema/defense definitions. Saved model settings
come from the traces, not today's config. Historical `-dirty` revisions and
unconfirmed settings remain limitations; analysis cannot reconstruct an
uncommitted runner revision.

## Validation

```bash
# Analysis checks only: no dependencies or key required.
python -m unittest tests.test_analysis -v

# Complete repository checks, after installing requirements.txt.
python -m pytest -q
```

The explicitly synthetic fixture in `tests/fixtures/analysis/` checks known
numerators, denominators, paired differences, medians, null handling, retries,
missing evaluations, and resolved labels. It lives outside real results and
is rejected by the CLI unless `--allow-synthetic` is provided. Tests also
validate both saved real integration datasets. See [HANDOFF.md](HANDOFF.md)
for completed deliverables and external dependencies.
