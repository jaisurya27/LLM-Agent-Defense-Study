# Defense integration review and handoff

## Completion status

The committed Banking pilots and the newly committed Banking/Slack preliminary
batches have been technically reviewed. The batch review covers 72 episodes,
75 internal attempts, 347 successful tool results, and 21 tool errors. All recorded
tool content and errors match local replay and the intended formatting policy.

Reviewed batch source: `a8bfad309ce57f5df95889280917c73f8a64e84b`.
See [batch findings and limitations](BATCH_REVIEW.md) before using these results.
This is technical placement evidence. Independent behavioral labeling and
collaborator acknowledgment remain separate handoff tasks.

## Deliverables

- [Batch per-run checklist](batch_checks.csv): 72 real episodes, including retries,
  errors and whether the boundary was actually exercised.
- [Batch audit](verify_batch.py): exact local replay and pinned provider conversion.
- [Batch audit regression checks](test_verify_batch.py).
- [Actual Slack excerpts](BATCH_EXCERPTS.md): clean/attacked boundaries and errors.
- [Pilot checklist](integration_checks.csv): the original 12 integration runs.
- [Original pilot excerpts](ANNOTATED_EXCERPTS.md).
- [Original pilot audit](verify_traces.py): pilot-only checks and optional offline
  scripted coverage; synthetic outputs are not experimental results.

```bash
python -m review.devin.verify_batch
python -m review.devin.verify_traces --offline-batch
python -m pytest -q tests review/devin/test_verify_batch.py
```

No command above calls a model API. Batch and pilot checklists are separate.

## Placement policy

| Configuration | Added instruction | Successful tool-result text |
| --- | --- | --- |
| Default | None | Unchanged after standard benchmark serialization |
| Warning | Shared warning from prompts/warning.txt | Unchanged |
| Warning + Boundaries | Identical warning | Original serialized text between marker lines |

The warning is appended to the existing base instructions after two newlines.
Default's existing newline stripping is preserved. Attack content is inserted into
the simulated environment before serialization and wrapping; the same policy is
used in clean and attacked cases. Tool availability, names, arguments and IDs are
not changed by the defense. The pinned provider adapter converts internal system
messages to developer messages consistently across configurations.

Markers are text cues, not enforced security boundaries. The provider adapter sends
error strings instead of formatted tool content on errors. These strings remain
unwrapped. Unlike the pilots, the batch includes tool errors and two errors echoing
attack text (under Default/Warning). The full review records these observations.

## Handoff and remaining dependencies

The batch placement review supports retaining the existing frozen defenses.
The experiment owner should acknowledge the policy and complete the GPT-5 deployment/source provenance
notes. No defense change or experiment rerun is requested by the review. After
freeze, any prompt or placement change requires a new config ID and separate results.

Independent behavioral labeling, analysis, and presenting findings and limitations
remain with their respective owners. Placement correctness and defense effectiveness are
separate questions. Seven batch episodes have no tool calls and therefore do not
exercise content formatting.

The historical pilot records identify `87c5d5e-dirty`; GPT-5 batch records identify
`5c4a39a-dirty`. Exact historical HTTP requests, full tool schemas and uncommitted
source cannot be certified from saved message traces alone. Batch fingerprints do
match current frozen inputs. Model attack wording/decoding differ, so keep model
results separate. See the batch report for exact provenance limits and retry behavior.

All changes in this handoff are under `review/devin/`. Production code, prompts,
configs and raw results are unchanged.
