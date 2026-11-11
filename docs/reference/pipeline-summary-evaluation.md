# Pipeline summary evaluation

**Last Updated**: 2026-11-11

How `Yen-Summarizers` and `Yen-AI-Pipeline` score their saved summaries and
report native results without changing generation or either evaluator API.

## Saved inputs

`tools/summary-eval/export-saved-summaries.ts` reads the existing capture with
its own validator and writes native HHEM request JSONL. The Python caller
validates every line with the existing `EvaluateRequest` before starting
either evaluator. It passes the same unchanged source and summary to UniEval.
An empty, malformed, oversized or duplicate-request handoff fails explicitly.

Table A - Generation producers and scoring inputs

| Id | Producer and saved file | Source | Summary |
| --- | --- | --- | --- |
| A1 | `.github/scripts/ai-pipeline.ts`; `pipeline-events.jsonl` | `OUTPUT_STRUCTURED.data.result.input_text` | `analytic_synthesis` |
| A2 | `tools/summary-generator-caller/run-summary-api.ts`; `summary-events.jsonl` | `data.request.input_text` | `data.result.data.executive_summary` |

The source is the prepared text actually sent to generation, not the original
extraction audit. The summary-only score covers `executive_summary`, not its
separate headline or key points. Failed inference results and saved experiment
results from a different workflow run are refused. Original captures are not
rewritten.

## Pipeline orchestration

Both workflows install the evaluator's existing frozen model extra. It supplies
the native scoring runtime; its cost is dependency installation, model downloads
and local CPU inference. No new dependency or external model service is added.

`tools/summary-eval/score-saved.py` dispatches generation shutdown and evaluation.
Shutdown reads only the PID files named by the workflow, pins each existing
process with a Linux process descriptor, and confirms exit before scoring.
Its graceful and forced waits follow the existing workflow settings. Invalid
PID metadata or unconfirmed exit fails the step and prevents evaluation.

Evaluation prepares the native UniEval resources, then uses independent HHEM
and UniEval FastAPI processes. The existing owned-service controller, native
health validation and HTTP callers retain their process identities, finite
waits, response bounds and confirmed shutdown. A failed scorer does not erase
its sibling's completed response. No generation, host measurement or legacy
coverage service runs in this phase.

Transport, handoff size, process waits and the output-directory root come from
`config/summary-evals/workflow.json`. Each evaluator retains its own committed
listener and scoring configuration. HHEM evaluates the supplied pair without
the optional second full-source comparison. UniEval follows its configured
consistency mode without truncation or automatic fallback. These workflows
supply no independent reference; the native relevance skip reason is retained.

## Actions output

The caller groups saved scores by item in `GITHUB_STEP_SUMMARY`, with separate
HHEM and UniEval tables. Metrics are rows and each evaluator has its own score
column and native overall status. UniEval's consistency row includes its
effective consistency mode; relevance retains its explicit skip reason.
It reports HHEM faithfulness and the applicable UniEval dimensions directly,
without a custom aggregate, threshold, coverage score or publication gate.
Missing values remain unavailable; measured zeroes remain numeric zeroes.
Native errors retain their codes and any measured input-token allowance.

The configured output root contains `saved-summaries/report.md` and separate
native JSON responses named from the validated request's recomputed digest.
Each completed response is atomically saved before sibling completion or
service cleanup. Partial responses and error HTTP responses remain available.
Failed input, scoring or cleanup fails the evaluation step; artifact upload
still retains available generation captures, request JSONL, native responses,
the report and native diagnostics.

## Design rationale

Scoring saved text avoids a second generation and preserves which answer was
measured. Confirmed generator exit separates its memory use from evaluation.
The APIs own score calculation and validation; the pipeline owns only input
selection, process orchestration and presentation.

## See also

- [workflow-pipeline-events.md](workflow-pipeline-events.md) - inference captures.
- [summary-generator-caller.md](summary-generator-caller.md) - summary API captures.
- [hhem-evaluation-api.md](hhem-evaluation-api.md) - native HHEM fields.
- [unieval-api.md](unieval-api.md) - native UniEval dimensions and failures.
- [summary-evaluation-workflow.md](summary-evaluation-workflow.md) - the separate manual generation/evaluation workflow.
