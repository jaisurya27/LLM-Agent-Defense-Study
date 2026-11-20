# Synthetic analysis fixture — not experiment results

All records and labels in this directory are fabricated calculation checks.
They must never be combined with `results/` or cited as model behavior.

The fixture plans 18 episodes across two Banking tasks and one Slack task.
It contains 18 attempts, 17 selected episodes, 16 evaluated episodes, one
missing clean Warning episode, one retained evaluation error, and one
infrastructure failure followed by a successful retained retry.

Known combined attacked outcomes:

| Defense | Task completion | Attack success | Useful resistance |
|---|---|---|---|
| Default | 2/3 | 3/3 | 0/3 |
| Warning | 3/3 | 0/3 | 3/3 |
| Warning + Boundaries | 1/2 | 0/2 | 1/2 |

Only two attacked cases have outcomes under all three defenses. On those
cases, Warning's task-completion difference is **+50 percentage points**,
not the +33.3 points obtained by subtracting the unpaired overall rates.
Paired useful-resistance differences are +100 points for Warning and +50
for Warning + Boundaries. Clean Banking completion is 2/2, 1/2, 2/2.

Default clean token totals are 12, 40, and 120 (median 40), with runtimes
1, 3, and 2 seconds (median 2). One Warning clean token count and runtime
are unknown. The infrastructure-error attempt has unknown tokens, so the
all-attempt token total is unavailable even though the observed subtotal is
360 for attacked Warning.

The three fabricated failed-task labels exercise yes, no, and unclear.
They are not inferred from utility outcomes. No trace files are provided.

Run the checks with `python -m unittest tests.test_analysis -v`.
