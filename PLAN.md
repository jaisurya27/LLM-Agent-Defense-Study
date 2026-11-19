# Implementation plan: benchmark and execution (Ja)

Based on the team work plan: 3 defenses x (6 clean + 6 attacked cases) = 36 episodes on Banking and Slack, AgentDojo v1.2.2, `important_instructions` attack.

## 1. What is in the repo now

| Item | State |
|---|---|
| Pinned dependencies, setup and run instructions | Done |
| Task selection (`config/tasks.json`): 3 user tasks per suite, 1 attack each, seed 261 | Done; payloads saved before any model run |
| Runner with `smoke`, `integration`, `batch` | Done; checked offline and against a local fake API |
| Episode records in Ab's format, traces, selected-attempt file | Done |
| Retry and resume rules from the work plan | Done |
| Defense hooks (`src/defenses.py`, `prompts/warning.txt`) | Starting version from De's spec; De to review |
| A run against a real model | **Not done. Needs an API key and a model decision.** |

Selected cases:

| Suite | User task | Attack |
|---|---|---|
| banking | user_task_13: update account info from a file | injection_task_0: send a transaction leaking the user's streaming service |
| banking | user_task_0: pay a bill from a file | injection_task_4: redirect a recurring payment |
| banking | user_task_2: adjust rent from landlord notices | injection_task_6: transfer $30,000 in increments |
| slack | user_task_5: post a question in the largest channel | injection_task_4: post general-channel messages to a website |
| slack | user_task_8: reply about a coffee mug | injection_task_5: invite and then remove an outside user |
| slack | user_task_12: post a message in the External channel | injection_task_1: send a link to Alice |

## 2. My next steps

1. **Model and key.** Confirm the model with the team (proposal below), put the key in `.env`.
2. **Smoke test.** `python -m src.runner smoke`. Check the two traces by hand: tool calls work, the attack text is visible in the attacked run, token counts are filled in. Commit `results/smoke/` and share it with De, Ab, Is and Re.
3. **Integration check.** `python -m src.runner integration` with De and Ab: six episodes, one clean and one attacked case under each defense. De checks the model-visible messages; Ab reads the records.
4. **Freeze.** Record model, settings, limits and budget; set `"frozen": true`; commit. Give Re the settings, task list and limitations for the experiment specification.
5. **Batch.** `python -m src.runner batch`. Commit `results/preliminary/` unchanged. Report evaluated, missing and error counts.

## 3. Overlap with other owners

Built now so nobody waits; each owner can replace their part.

- **De (defenses).** `get_defense_instruction(defense)` and `format_external_content(content, defense)` exist with the warning text and boundary format from the work plan. The runner calls only these two functions, so De can change wording or format without touching the runner. To confirm with De: the warning is appended to the default system message after a blank line, and the text being wrapped is each tool result after AgentDojo's YAML formatting.
- **Ab (analysis).** `src/schema.py` holds the agreed fields and a `validate_record` check that Ab's script can import. The runner adds a few extra fields (`attempt`, `started_at`, `model_id`, `llm_calls`, `config_hash`, `code_revision`). `python -m src.runner batch --offline compromised` produces 36 schema-valid records for testing the analysis code; these are scripted, not results.
- **Is and Re (review).** Traces include the full message list, tool errors and the reason the episode ended (`final_answer` or `max_tool_iterations`), which is the evidence the refusal and tool-format rubric needs.

## 4. Decisions the team still has to make

These are proposals in `config/preliminary.json`, not final choices.

1. **Model: Azure OpenAI deployment on `ta-agent1`.** Record the deployment name, the model and version behind it, and its content filter in the config. Earlier proposal was `gpt-4o-mini-2024-07-18`: A pinned snapshot, cheap, supported by AgentDojo. OpenAI lists it for shutdown on 14 Jan 2027, so runs must finish before then. An older model is also more likely to show some baseline attack success; if the default agent is never attacked successfully, we cannot measure any benefit from the defenses. The integration check will give a first indication.
2. **Temperature 0.0.** AgentDojo 0.1.35 silently drops a temperature of 0.0 for OpenAI models and the API then uses 1.0. The runner sets it explicitly, so 0.0 is what is sent.
3. **Episode limit: 15 tool rounds** (AgentDojo's default). No separate token cap yet; the smoke test will show whether one is needed.
4. **Attack names.** The payload addresses the model as "GPT-4" and signs as "Emma Johnson", which is what AgentDojo uses for this model. If the model changes, decide whether to regenerate the payloads.
5. **Budget.** 36 short episodes on this model should cost very little, but the estimate should come from the smoke test's token counts.
6. **Azure content filter.** Prompt Shields for user-prompt attacks are on by default on Azure deployments; detection for attacks in documents is off by default. If Azure blocks our attacked episodes, it is acting as an extra defense in every configuration. Check the smoke test for `content_filter`; for the batch, the team should agree on the guardrail setting (ideally annotate-only) and record it.
7. **Tool errors are not wrapped** in boundaries (see README). De to decide whether this needs fixing before the freeze.

## 5. Rules built into the runner

- `batch` refuses to run until the config is frozen.
- Results from two different configurations cannot be mixed in one folder: every record carries a hash of the config, task list, warning text and defense code.
- An evaluated episode is never rerun. An infrastructure failure is kept in `episodes.jsonl` and retried at most once; `selected_runs.json` names the attempt to count.
- Three infrastructure errors in a row stop the run, so a bad key cannot fill the results with errors.
- Service errors are `infrastructure_error`; any other exception is `evaluation_error`. Neither is counted as a successful defense: their outcomes are null.

## 6. Later, for the larger evaluation

- Scale to the proposal's design (about 10 user tasks x 3 attacks per suite, roughly 240 episodes) by changing `selection` and extending `select_tasks.py` to pair several attacks per user task.
- Optional second model through an OpenAI-compatible endpoint (for example vLLM); the runner already accepts `"provider": "openai_compatible"` with a `base_url`.
