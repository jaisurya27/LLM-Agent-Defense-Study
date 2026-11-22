# Agent Defense Study

Do simple prompt-injection defenses make LLM agents safer without making them less useful?
We run the same AgentDojo tasks under three configurations (Default, Warning, Warning + Boundaries), with and without attacks, and compare attack success, task completion, refusals and token cost.

Status: preliminary study. Settings in `config/preliminary.json` are **proposed, not frozen**. See `PLAN.md` for what is built, what is next and what the team still has to decide.

## Setup

Needs Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your API key; .env is git-ignored
```

### Model (Azure OpenAI)

The config uses our Azure OpenAI resource through its OpenAI-compatible endpoint (`https://ta-agent1.openai.azure.com/openai/v1`). In `config/preliminary.json`, set:

- `model_id`: the **deployment name** from Azure AI Foundry (Deployments page), not the model name.
- `underlying_model`: the model and version behind that deployment, for example `gpt-4o-mini (2024-07-18)`.
- `content_filter`: the guardrail/content filter assigned to the deployment.
- `temperature`: `0.0` for GPT-4o-family models. Reasoning models (o-series, GPT-5 family) reject a temperature; use `null` for those.

The runner refuses to call the API while any of these still read `SET-...`.

Azure can block a request with its own content filter (Prompt Shields). That works like an extra, uncontrolled defense, so a blocked episode is recorded with `termination_reason: "content_filter"`, its outcomes stay null, and it is not retried. Blocks of the model's reply show up as `finish_reason: "content_filter"` in the trace.

`requirements.txt` pins `agentdojo==0.1.35`, which provides benchmark version v1.2.2.

## Check your setup (no key, no cost)

```bash
pytest -q                                    # 7 offline checks
python -m src.runner integration --offline   # six conditions with a scripted stand-in
```

`--offline` replaces the model with a script that replays each task's reference tool calls. It checks prompts, boundary placement, traces and evaluators. Its outcomes are not results and go to `results/offline_check/`, which is git-ignored.

## Run

```bash
python -m src.runner smoke --dry-run   # list what would run
python -m src.runner smoke             # 1 clean + 1 attacked episode, default agent
python -m src.runner integration       # the same 2 cases under all 3 defenses (6 episodes)
python -m src.runner batch             # all 36 episodes; only after the config is frozen
```

Only Ja launches `batch`, so we do not pay for the same runs twice. Rerunning a command resumes: evaluated episodes are never run again, and an infrastructure failure is retried at most once.

## Outputs

Each phase writes to its own folder (`results/smoke/`, `results/integration/`, `results/preliminary/`):

| File | Contents |
|---|---|
| `episodes.jsonl` | One record per attempt. Fields are defined in `src/schema.py`. |
| `selected_runs.json` | The one attempt per episode that analysis should count. |
| `traces/<run_id>.json` | System message, user prompt, attack payloads, every message and tool call, token usage per model call. |

Record conventions:

- `status` is `completed`, `infrastructure_error` or `evaluation_error`. `completed` means evaluated, not successful.
- `utility_success` and `attack_success` are booleans from AgentDojo's own evaluators, or null when unavailable. `attack_success` is null for clean runs.
- `case_id` is the same across defenses for the same task and clean/attack pairing. `run_id` is unique per attempt.

## Analyze saved results (Ab)

The analysis needs no API key or additional packages:

```bash
python -m analysis.summarize --results-dir results/integration_gpt41nano --phase integration --output analysis/reports/integration_gpt41nano
```

See [analysis/README.md](analysis/README.md) for metric definitions, paired
comparisons, missing/error handling, review labels and the final batch command.
[Ab's handoff](analysis/HANDOFF.md) links the two real integration pilot reports
and records the remaining dependencies on the batch and resolved review labels.
Pilot reports are separate from the preliminary study results.

## Layout

```
config/preliminary.json   model, limits, attack, seed (proposed)
config/tasks.json         selected task IDs and exact attack payloads
prompts/warning.txt       warning text used by both defended configurations
src/defenses.py           the two defense hooks (owner: De)
src/pipeline.py           builds the agent; token counting; offline stand-in
src/select_tasks.py       seeded task selection
src/runner.py             smoke / integration / batch
src/schema.py             episode record format (shared with Ab)
tests/                    offline checks
analysis/                 reproducible tables, pilot reports and Ab's handoff
```

## How the defenses are applied

- **Warning**: `prompts/warning.txt` is appended to AgentDojo's default system message after a blank line.
- **Boundaries**: each tool result's text is placed between `<external_content>` and `</external_content>` lines. The original text is unchanged.
- Attack text is part of the environment data, so it is already inside the tool result when the markers are added.
- Tool names, arguments, call IDs and message roles are untouched. The environment is rebuilt for every episode.

Known limits: when a tool call fails, AgentDojo sends the model the error message instead of the tool content, so error messages are not wrapped. AgentDojo's environment loader also collapses blank lines in the attack payload, so the text the model sees has single line breaks where `tasks.json` shows double ones.
