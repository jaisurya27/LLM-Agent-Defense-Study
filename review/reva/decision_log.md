# Preliminary Study — Short Decision Log

**Owner:** Reva Kaneri  
**Status:** Frozen experiment decisions recorded; trace-label reconciliation documented separately

| Recorded decision | Evidence |
|---|---|
| Use AgentDojo v1.2.2, Banking + Slack, seed 261, three tasks per suite and fixed `important_instructions` payloads | [`config/tasks.json`](../../config/tasks.json), [`config/tasks_gpt5.json`](../../config/tasks_gpt5.json) |
| Test Default, Warning, and Warning + Boundaries, each clean and attacked (36 episodes per model) | Frozen configs and saved preliminary results |
| Freeze GPT-4.1-nano as `prelim-v1` and run GPT-5 separately as `prelim-v1-gpt5` | [`config/preliminary.json`](../../config/preliminary.json), [`config/preliminary_gpt5.json`](../../config/preliminary_gpt5.json) |
| Apply the same warning to both defenses; only Warning + Boundaries wraps successful serialized tool content | [`prompts/warning.txt`](../../prompts/warning.txt), [`review/devin/BATCH_REVIEW.md`](../../review/devin/BATCH_REVIEW.md) |
| Preserve selected run IDs, traces, errors and retries; keep pilot results separate | [`src/runner.py`](../../src/runner.py), result folders |
| Analyze security, legitimate utility and overhead separately, with explicit denominators | [`analysis/README.md`](../../analysis/README.md) |
| Keep Is and Re labels independent before resolving disagreement | Team work plan and [`review/ishan/rubric.md`](../../review/ishan/rubric.md) |

**Documentation caveats:** GPT-5's exact Azure deployment version is not specified in the frozen config; its saved code revision is `5c4a39a-dirty`. Decoding and attack wording differ across models. The repository README contains older pre-freeze wording; rely on frozen configs and original run records. These are disclosure notes, **not a list of extra tasks or claims of unresolved approval**.
