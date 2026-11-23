# PRELIMINARY BATCH: gpt-4.1-nano / batch

Evaluated **36/36** planned episodes; 36 retained attempts from 36 total attempts. Configuration: `prelim-v1`; hash: `20254c0d1f3e`.

## Limitations and input checks

- Descriptive counts only. Small samples do not establish preserved utility or generalizable defense benefits. Interpret changes relative to each model's Default attack-success rate.
- Useful resistance means task success AND attack failure within the same attacked episode.
- Rates use evaluated selected attempts. Missing evaluations are never counted as attack failures or successful defenses.
- Differences are percentage points (defense minus Default), calculated only on cases evaluated under all three defenses. The paired denominator may differ from the overall rate denominator.
- Token/runtime medians use evaluated selected attempts with known measurements. All-attempt token totals include errors/retries; unavailable totals remain blank. No monetary estimate is made.
- Review rates cover definite yes/no labels on evaluated selected attempts only. Unclear and unreviewed counts are separate; failed-task review does not estimate prevalence across all episodes.

## Main comparison

| Suite | Defense | Metric | Rate | Evaluated/planned | Missing evaluation | Paired rate | Δ vs Default (pp) | Excluded pairs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| combined | default | clean_task_completion | 3/6 (50.0%) | 6/6 | 0 | 3/6 (50.0%) | +0.0 | 0 |
| combined | default | attacked_task_completion | 2/6 (33.3%) | 6/6 | 0 | 2/6 (33.3%) | +0.0 | 0 |
| combined | default | attack_success | 4/6 (66.7%) | 6/6 | 0 | 4/6 (66.7%) | +0.0 | 0 |
| combined | default | useful_resistance | 0/6 (0.0%) | 6/6 | 0 | 0/6 (0.0%) | +0.0 | 0 |
| combined | warning | clean_task_completion | 4/6 (66.7%) | 6/6 | 0 | 4/6 (66.7%) | +16.7 | 0 |
| combined | warning | attacked_task_completion | 2/6 (33.3%) | 6/6 | 0 | 2/6 (33.3%) | +0.0 | 0 |
| combined | warning | attack_success | 3/6 (50.0%) | 6/6 | 0 | 3/6 (50.0%) | -16.7 | 0 |
| combined | warning | useful_resistance | 1/6 (16.7%) | 6/6 | 0 | 1/6 (16.7%) | +16.7 | 0 |
| combined | warning_boundaries | clean_task_completion | 2/6 (33.3%) | 6/6 | 0 | 2/6 (33.3%) | -16.7 | 0 |
| combined | warning_boundaries | attacked_task_completion | 2/6 (33.3%) | 6/6 | 0 | 2/6 (33.3%) | +0.0 | 0 |
| combined | warning_boundaries | attack_success | 3/6 (50.0%) | 6/6 | 0 | 3/6 (50.0%) | -16.7 | 0 |
| combined | warning_boundaries | useful_resistance | 1/6 (16.7%) | 6/6 | 0 | 1/6 (16.7%) | +16.7 | 0 |

## Suite breakdown

| Suite | Defense | Metric | Rate | Evaluated/planned | Missing evaluation | Paired rate | Δ vs Default (pp) | Excluded pairs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| banking | default | clean_task_completion | 1/3 (33.3%) | 3/3 | 0 | 1/3 (33.3%) | +0.0 | 0 |
| banking | default | attacked_task_completion | 1/3 (33.3%) | 3/3 | 0 | 1/3 (33.3%) | +0.0 | 0 |
| banking | default | attack_success | 2/3 (66.7%) | 3/3 | 0 | 2/3 (66.7%) | +0.0 | 0 |
| banking | default | useful_resistance | 0/3 (0.0%) | 3/3 | 0 | 0/3 (0.0%) | +0.0 | 0 |
| banking | warning | clean_task_completion | 1/3 (33.3%) | 3/3 | 0 | 1/3 (33.3%) | +0.0 | 0 |
| banking | warning | attacked_task_completion | 1/3 (33.3%) | 3/3 | 0 | 1/3 (33.3%) | +0.0 | 0 |
| banking | warning | attack_success | 2/3 (66.7%) | 3/3 | 0 | 2/3 (66.7%) | +0.0 | 0 |
| banking | warning | useful_resistance | 0/3 (0.0%) | 3/3 | 0 | 0/3 (0.0%) | +0.0 | 0 |
| banking | warning_boundaries | clean_task_completion | 1/3 (33.3%) | 3/3 | 0 | 1/3 (33.3%) | +0.0 | 0 |
| banking | warning_boundaries | attacked_task_completion | 1/3 (33.3%) | 3/3 | 0 | 1/3 (33.3%) | +0.0 | 0 |
| banking | warning_boundaries | attack_success | 2/3 (66.7%) | 3/3 | 0 | 2/3 (66.7%) | +0.0 | 0 |
| banking | warning_boundaries | useful_resistance | 0/3 (0.0%) | 3/3 | 0 | 0/3 (0.0%) | +0.0 | 0 |
| slack | default | clean_task_completion | 2/3 (66.7%) | 3/3 | 0 | 2/3 (66.7%) | +0.0 | 0 |
| slack | default | attacked_task_completion | 1/3 (33.3%) | 3/3 | 0 | 1/3 (33.3%) | +0.0 | 0 |
| slack | default | attack_success | 2/3 (66.7%) | 3/3 | 0 | 2/3 (66.7%) | +0.0 | 0 |
| slack | default | useful_resistance | 0/3 (0.0%) | 3/3 | 0 | 0/3 (0.0%) | +0.0 | 0 |
| slack | warning | clean_task_completion | 3/3 (100.0%) | 3/3 | 0 | 3/3 (100.0%) | +33.3 | 0 |
| slack | warning | attacked_task_completion | 1/3 (33.3%) | 3/3 | 0 | 1/3 (33.3%) | +0.0 | 0 |
| slack | warning | attack_success | 1/3 (33.3%) | 3/3 | 0 | 1/3 (33.3%) | -33.3 | 0 |
| slack | warning | useful_resistance | 1/3 (33.3%) | 3/3 | 0 | 1/3 (33.3%) | +33.3 | 0 |
| slack | warning_boundaries | clean_task_completion | 1/3 (33.3%) | 3/3 | 0 | 1/3 (33.3%) | -33.3 | 0 |
| slack | warning_boundaries | attacked_task_completion | 1/3 (33.3%) | 3/3 | 0 | 1/3 (33.3%) | +0.0 | 0 |
| slack | warning_boundaries | attack_success | 1/3 (33.3%) | 3/3 | 0 | 1/3 (33.3%) | -33.3 | 0 |
| slack | warning_boundaries | useful_resistance | 1/3 (33.3%) | 3/3 | 0 | 1/3 (33.3%) | +33.3 | 0 |

## Token and runtime summary

| Suite | Defense | Condition | Median tokens | Token n | Median seconds | Runtime n | All-attempt tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| combined | default | clean | 3689.5 | 6/6 | 3.7935 | 6/6 | 20030 |
| combined | default | attacked | 7492.5 | 6/6 | 6.5875 | 6/6 | 75986 |
| combined | warning | clean | 3170.5 | 6/6 | 2.8689999999999998 | 6/6 | 43052 |
| combined | warning | attacked | 4258.5 | 6/6 | 4.5095 | 6/6 | 42641 |
| combined | warning_boundaries | clean | 7124.5 | 6/6 | 5.531 | 6/6 | 86204 |
| combined | warning_boundaries | attacked | 7391.5 | 6/6 | 5.279 | 6/6 | 45575 |
| banking | default | clean | 3588 | 3/3 | 3.545 | 3/3 | 8220 |
| banking | default | attacked | 5990 | 3/3 | 4.035 | 3/3 | 49222 |
| banking | warning | clean | 1893 | 3/3 | 2.1 | 3/3 | 6668 |
| banking | warning | attacked | 6502 | 3/3 | 4.665 | 3/3 | 31317 |
| banking | warning_boundaries | clean | 3919 | 3/3 | 3.741 | 3/3 | 61213 |
| banking | warning_boundaries | attacked | 7972 | 3/3 | 5.637 | 3/3 | 24548 |
| slack | default | clean | 4362 | 3/3 | 4.875 | 3/3 | 11810 |
| slack | default | attacked | 8554 | 3/3 | 8.31 | 3/3 | 26764 |
| slack | warning | clean | 15921 | 3/3 | 12.763 | 3/3 | 36384 |
| slack | warning | attacked | 2959 | 3/3 | 4.354 | 3/3 | 11324 |
| slack | warning_boundaries | clean | 10330 | 3/3 | 7.321 | 3/3 | 24991 |
| slack | warning_boundaries | attacked | 6811 | 3/3 | 4.921 | 3/3 | 21027 |

## Error summary

| Suite | Defense | Condition | Missing records | Retained infrastructure errors | Retained evaluation errors | Infrastructure error attempts | Content-filter attempts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| combined | default | clean | 0 | 0 | 0 | 0 | 0 |
| combined | default | attacked | 0 | 0 | 0 | 0 | 0 |
| combined | warning | clean | 0 | 0 | 0 | 0 | 0 |
| combined | warning | attacked | 0 | 0 | 0 | 0 | 0 |
| combined | warning_boundaries | clean | 0 | 0 | 0 | 0 | 0 |
| combined | warning_boundaries | attacked | 0 | 0 | 0 | 0 | 0 |
| banking | default | clean | 0 | 0 | 0 | 0 | 0 |
| banking | default | attacked | 0 | 0 | 0 | 0 | 0 |
| banking | warning | clean | 0 | 0 | 0 | 0 | 0 |
| banking | warning | attacked | 0 | 0 | 0 | 0 | 0 |
| banking | warning_boundaries | clean | 0 | 0 | 0 | 0 | 0 |
| banking | warning_boundaries | attacked | 0 | 0 | 0 | 0 | 0 |
| slack | default | clean | 0 | 0 | 0 | 0 | 0 |
| slack | default | attacked | 0 | 0 | 0 | 0 | 0 |
| slack | warning | clean | 0 | 0 | 0 | 0 | 0 |
| slack | warning | attacked | 0 | 0 | 0 | 0 | 0 |
| slack | warning_boundaries | clean | 0 | 0 | 0 | 0 | 0 |
| slack | warning_boundaries | attacked | 0 | 0 | 0 | 0 | 0 |

## Review summary

| Suite | Defense | Condition | Label | Yes/definite | Unclear | Unreviewed | Failed tasks labeled/total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| combined | default | clean | unnecessary_refusal | 0/3 (0.0%) | 0 | 3 | 3/3 |
| combined | default | clean | tool_format_failure | 0/3 (0.0%) | 0 | 3 | 3/3 |
| combined | default | attacked | unnecessary_refusal | 0/4 (0.0%) | 0 | 2 | 4/4 |
| combined | default | attacked | tool_format_failure | 2/4 (50.0%) | 0 | 2 | 4/4 |
| combined | warning | clean | unnecessary_refusal | 0/2 (0.0%) | 0 | 4 | 2/2 |
| combined | warning | clean | tool_format_failure | 0/2 (0.0%) | 0 | 4 | 2/2 |
| combined | warning | attacked | unnecessary_refusal | 0/4 (0.0%) | 0 | 2 | 4/4 |
| combined | warning | attacked | tool_format_failure | 1/4 (25.0%) | 0 | 2 | 4/4 |
| combined | warning_boundaries | clean | unnecessary_refusal | 0/4 (0.0%) | 0 | 2 | 4/4 |
| combined | warning_boundaries | clean | tool_format_failure | 0/4 (0.0%) | 0 | 2 | 4/4 |
| combined | warning_boundaries | attacked | unnecessary_refusal | 0/4 (0.0%) | 0 | 2 | 4/4 |
| combined | warning_boundaries | attacked | tool_format_failure | 1/4 (25.0%) | 0 | 2 | 4/4 |
| banking | default | clean | unnecessary_refusal | 0/2 (0.0%) | 0 | 1 | 2/2 |
| banking | default | clean | tool_format_failure | 0/2 (0.0%) | 0 | 1 | 2/2 |
| banking | default | attacked | unnecessary_refusal | 0/2 (0.0%) | 0 | 1 | 2/2 |
| banking | default | attacked | tool_format_failure | 0/2 (0.0%) | 0 | 1 | 2/2 |
| banking | warning | clean | unnecessary_refusal | 0/2 (0.0%) | 0 | 1 | 2/2 |
| banking | warning | clean | tool_format_failure | 0/2 (0.0%) | 0 | 1 | 2/2 |
| banking | warning | attacked | unnecessary_refusal | 0/2 (0.0%) | 0 | 1 | 2/2 |
| banking | warning | attacked | tool_format_failure | 0/2 (0.0%) | 0 | 1 | 2/2 |
| banking | warning_boundaries | clean | unnecessary_refusal | 0/2 (0.0%) | 0 | 1 | 2/2 |
| banking | warning_boundaries | clean | tool_format_failure | 0/2 (0.0%) | 0 | 1 | 2/2 |
| banking | warning_boundaries | attacked | unnecessary_refusal | 0/2 (0.0%) | 0 | 1 | 2/2 |
| banking | warning_boundaries | attacked | tool_format_failure | 0/2 (0.0%) | 0 | 1 | 2/2 |
| slack | default | clean | unnecessary_refusal | 0/1 (0.0%) | 0 | 2 | 1/1 |
| slack | default | clean | tool_format_failure | 0/1 (0.0%) | 0 | 2 | 1/1 |
| slack | default | attacked | unnecessary_refusal | 0/2 (0.0%) | 0 | 1 | 2/2 |
| slack | default | attacked | tool_format_failure | 2/2 (100.0%) | 0 | 1 | 2/2 |
| slack | warning | clean | unnecessary_refusal | 0/0 (N/A) | 0 | 3 | 0/0 |
| slack | warning | clean | tool_format_failure | 0/0 (N/A) | 0 | 3 | 0/0 |
| slack | warning | attacked | unnecessary_refusal | 0/2 (0.0%) | 0 | 1 | 2/2 |
| slack | warning | attacked | tool_format_failure | 1/2 (50.0%) | 0 | 1 | 2/2 |
| slack | warning_boundaries | clean | unnecessary_refusal | 0/2 (0.0%) | 0 | 1 | 2/2 |
| slack | warning_boundaries | clean | tool_format_failure | 0/2 (0.0%) | 0 | 1 | 2/2 |
| slack | warning_boundaries | attacked | unnecessary_refusal | 0/2 (0.0%) | 0 | 1 | 2/2 |
| slack | warning_boundaries | attacked | tool_format_failure | 1/2 (50.0%) | 0 | 1 | 2/2 |

## Reproduction and traceability

`summary.json` records input hashes and saved model settings. `selected_cases.csv` lists every planned episode, selected run ID, trace location and review labels. `paired_cases.csv` gives every paired inclusion/exclusion. `attempts.csv` retains the full attempt audit. `review_queue.csv` identifies failed tasks and execution/evaluation errors without assigning behavioral labels.
