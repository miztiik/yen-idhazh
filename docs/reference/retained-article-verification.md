# Retained article verification

**Last Updated**: 2026-11-11

Which inputs and native artifacts establish a fixed-input production-call
observation without publishing or fetching an article again.

## Dispatch inputs

The existing `idhazh-pipeline-tests.yaml` workflow accepts an optional retained
mode. Leaving both retained inputs empty preserves the random draw, enabled
experimental cases, report and isolated ledger commit.

Table A - Retained mode inputs

| ID | Input | Rule |
| --- | --- | --- |
| A1 | `retained_source_run` | Positive Content refresh run ID; latest attempt complete with success or failure, as required by native recovery |
| A2 | `retained_item_ids` | Explicit comma-separated, unique native item IDs; at least one and no more than `config/pipeline-tests.json`'s `articles_a_dispatch` |
| A3 | `candidate_models_file` | Must be empty in retained mode; the committed production pointer, model, settings and destination are used unchanged |

Supplying either retained input selects retained mode. A missing companion,
invalid ID, duplicate, overlarge selection or candidate-model override fails
before model startup. Selection order is execution order. Each article's label
call and summary/plan call stay adjacent; a decline never triggers another call.
No expected visual kind or quality assertion enters either request.

Dispatch a reviewed branch or tag, then verify the run's `headSha` against the
intended commit before interpreting it:

```text
gh workflow run idhazh-pipeline-tests.yaml --ref <reviewed-ref> -f retained_source_run=<source-run> -f retained_item_ids=<first-id>,<second-id>
gh run view <verification-run> --json headSha,jobs,status,conclusion
```

This workflow's existing model-server action starts and checks the committed
runtime and weights. The replay job takes its timeout from the existing
`budget_minutes` setting, not a separate verification budget.

## Source validation

The plan job uses the assembly-recovery downloader for the selected run only.
It checks completed source-attempt metadata, the successful planning job,
platform artifact digests and artifact ownership. Native recovery readers select
the matching plan envelope rather than the first file, check shard membership
and validate worker payload identities.

Only the selected eligible `Article` bytes and their original native plan are
copied into the replay input tree. Old summaries, decisions, captures and
worker provenance are not imported as new results. There is no source-page
fetch, re-extraction, history scan, saved case manifest or replay result format.
Expired or incomplete retained inputs are errors, not an invitation to refetch.

The source plan retains the source execution, attempt and producer commit.
Preparation logs the validated platform source metadata. Fresh calls separately
log their native `WriterIdentity`, naming the replay execution, attempt and
checked-out commit. The old producer commit need not equal the replay commit.

## Native outputs and failures

The plan job uploads `pipeline-tests-retained-inputs-<verification-run>`.
The replay job uploads `pipeline-tests-retained-<verification-run>`, including
partial native products when generation fails. Both use the existing artifact
retention window. All replay files stay below the private directory
`backend/var/retained-article-verification/`:

- `source/<native-plan-file>`: unchanged source plan, including its envelope.
- `inputs/<item-id>.article.json`: exact selected source Article bytes.
- `outputs/<item-id>/items/pipeline-inputs.json`: native current model, runtime,
  prompt, schema and runner provenance; extraction/sanitization versions describe
  the retained Article, not an extraction that did not happen.
- `outputs/<item-id>/items/<item-id>.summary.json`, `<item-id>.visual.json` and
  `<item-id>.health.json`: fresh native products, including truthful failures.
- `outputs/<item-id>/captures/`: the actual native label and summary captures,
  with requests, replies and available call costs.
- `outputs/<item-id>/assets/`: compiled chart or Who/What data at the native
  relative asset path. This directory is not a publication tree.
- `llama-server.log`: the owned runtime's log.

The adapter supplies a configured `ItemRecorder` and explicit capture/render
roots to the real `two_calls_one_item()`. Configured prompt and reply capture
must both be enabled. Existing source and output paths reject traversal,
symlinks and junctions. A pre-existing output directory refuses a replay rather
than mixing an older result into fresh proof.

A failed summary fails verification and remains a failed native summary.
A missing call, missing decision or failed asset write is not a legitimate
no-visual result. A successful native decline remains visible and does not
become an error merely because the operator hoped for a visual. Additional
quality postconditions are observations over these saved outputs; they cannot
force the producer to draw or weaken native validation.
Native reachability may instead record `not_reachable` while both calls ran.
Preserve native `asked_the_model`: it stays true for the shared summary request
even when visual fields were omitted. Use `run_visual_decision` and the actual
second request to distinguish visual admission, and captures to establish which
calls occurred.

Only the read-only plan and replay jobs run in retained mode. Experimental
cases, their report and the ledger-commit job are skipped. No production ledger,
reader-facing file, deploy or publication is written.

## Design rationale

Fixed retained inputs isolate a producer change from mutable source pages.
Native artifact recovery preserves source integrity, while a separate fresh
output tree prevents historical success from looking like new generation.
Passing a render root through the existing producer keeps its ordinary
production default unchanged without replacing inference or patching globals.

These artifacts prove execution and expose the model's actual choice.
Source-backed usefulness still requires inspecting the named positive and
negative examples. Publication additionally requires ordinary assembly,
inventory references and the served reader on the delivered revision.

## See also

- [github-actions.md#pipeline-tests](github-actions.md#pipeline-tests) - random and retained workflow modes.
- [../architecture/summarize/model-boundary.md](../architecture/summarize/model-boundary.md) - committed model and destination ownership.
- [../architecture/publishing/visuals.md](../architecture/publishing/visuals.md) - visual validation and publication evidence.
