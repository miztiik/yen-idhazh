# How the UniEval API checks a complete source

**Last Updated**: 2026-11-09

How the local evaluator produces applicable distinct scores without silently
cutting the article or replacing an unfinished result. The
[API reference](../../reference/unieval-api.md) owns fields and settings.
This service neither generates a summary nor publishes a quality judgement.

## Four different questions

Fluency measures natural wording. Coherence measures the complete summary
with its complete source. Consistency measures source support for the claims
that the summary makes. Relevance compares the generated summary with an
independently supplied reference summary. The selected summarization
checkpoint can answer all four questions; the separate factuality-only
checkpoint cannot replace it.

The first three questions always apply. Relevance requires the resolved strict
boolean selection and an independent reference. It is disabled by default;
supplying a reference never enables it. No source-only replacement or generated
reference is used.

The service preserves the selected model's native question formats,
sentence rules and normalized Yes/No probability calculation. It does not
produce an overall grade. Relevance is not a measure of source coverage,
and consistent claims do not prove that the summary includes every important
fact.

## Complete source processing

The default `full_source_prompt` consistency mode compares each native summary
sentence with the complete unchanged source. Consistency is the arithmetic
mean of all completed sentence scores, not one question over the whole summary.
Its one original-character span covers the source from start through end.
Every complete question/text input, including special tokens, is counted with
the actual pinned tokenizer against the configured resource allowance.
An oversized input fails explicitly; there is no truncation, window retry or
automatic mode fallback.

Explicit `all_source_windows`, selected by request or committed configuration,
splits the source into overlapping tokenizer-sized spans. Each span is a slice
of the unchanged original string. The plan reserves room for the question,
the longest summary sentence and special tokens, then verifies every complete
input again with the actual tokenizer. It never uses tokenizer truncation.

When normalization maps several tokens to one original character, windows
end and restart only at complete character boundaries. Overlap rounds
outward, never below its configured target. If that prevents forward
progress within the input allowance, consistency receives
`WINDOW_BUDGET_INSUFFICIENT`; other admissible dimensions still run.
This is a geometry refusal, not an invented measurement of an oversized article.
An actually oversized summary-sentence question is checked first and retains
its measured `SUMMARY_SENTENCE_TOO_LONG` refusal.

In this explicit mode, every summary sentence is compared with every source window. A sentence's
score is the highest completed window score; consistency is the mean of
these sentence scores. Taking one best window against the whole summary
would miss support spread across different sections, so that is not the
calculation. Source offsets and completed counts let the caller verify
coverage of the supplied article, including its end.

Neither mode proves global factual correctness. A segmented comparison
cannot join evidence split across distant windows, and choosing a best
match can overlook contradictory passages elsewhere. The result names the
actual mode so it cannot be confused with a native whole-source score.

## Native dimensions and incomplete work

Fluency keeps its native sentence mean and needs no article windows.
Coherence uses one full-source/full-summary prompt, even when consistency
explicitly uses windows; those windows do not make oversized coherence fit.
Relevance uses one
full-reference/full-summary prompt. Averaging either score over source
windows would define a different measure, so the service does not do it.

If a complete prompt exceeds its allowance, that dimension has a safe error
and no numeric score. Its actual assembled token count, configured allowance
and zero-based comparison index survive planning, predictor defense, bounded
worker packets, parent reduction and reporting. The predictor's neutral size
refusal is projected to the actual comparison dimension, never assumed to be
consistency. Other admissible dimensions can finish. Missing
reference text does not block the other scores. Disabled relevance has reason
`disabled`, even without a reference; enabled relevance without one has reason
`reference_not_supplied`. A supplied blank or null reference is invalid input.
A valid unused reference still retains its exact byte hash.

The parent validates each private reply against its request, process
generation, dimension, sentence, source-window and exact issued operation
identity. It retains
completed predictions outside the model process. A final dimension requires
all of its planned comparisons; a maximum from an unfinished matrix is not a
score. Computed zero is valid, while uncomputed values remain null.
Every applicable dimension and no errors are required for a complete result.
A skipped relevance dimension has no score, plan, completed comparisons or
failure. An attempted relevance failure has no skip reason. The parent derives
this authorization from the original request and validated controls, not from
the worker's claim.

## Independent ownership

The [reusable application](summary-evaluator.md) explicitly registers the
UniEval router in its own API process. Its listener, queue and owned model process are independent of HHEM and
native generation. Model loading, tokenization and inference run in the
worker, not on the HTTP event loop. Body reservations and deadlines still
apply before reading a request.

Requests and progress use bounded JSON bytes over owned pipes. A lifetime
watcher stops the child when its parent disappears; Linux also uses the
kernel parent-death mechanism shared with HHEM. Cancellation and request
deadlines close the exact child's lifetime pipe and confirm its joined
exit, escalating to a kill of that owned process if needed. A failed worker
does not start an automatic restart loop.
An enabled request consumes the host's one receiving operation. Request
outcomes and connected response headers retain it. The real worker evaluation
is a child of that request; its planning, prediction and final packets all
retain the issued operation. Native sentence/window indexing and reduction
remain unchanged, without fake per-item work or another calculation.

Shared health retains separate component states. An unavailable UniEval
worker does not erase HHEM's readiness or completed result. Disabled UniEval
does not read its configuration or load its optional model dependencies.
Health and admission check the actual owned process, not only its cached
loaded identity. An observed idle exit closes UniEval admission and joins
that child before reporting `WORKER_EXITED`. Concurrent observers share the
same owned stop operation and wait for its confirmed outcome, including
cleanup errors, before returning failed health or refusing admission.

## Assets and diagnostics

Preparation downloads only named files from the declared immutable model
revision. The sentence-resource archive has an immutable URL, a SHA-256
digest and a finite named file inventory. Preparation checks that digest
before writing the required files. Execution uses local resources only.
No article, summary, model output or HTTP request can select a destination,
path, program or model.

The existing T5 runtime supplies the real model implementation. NLTK supplies
the native sentence rules; its added cost is the package plus the named
sentence-resource archive. Tokenizer/resource preparation needs no Torch or
weight download. Model preparation additionally downloads the declared
weights; neither kind of resource is committed.

Lifecycle and request outcomes use the shared CloudEvents stderr/file
writer. Only codes, identities and measured facts are logged. Source,
reference, summary, prompts, model output and raw exceptions are not
diagnostic fields. Failure of the optional file mirror warns without
changing a score.
Startup/load/shutdown diagnostics stay on the service branch. File-mirror
warnings use the causing operation, and startup/open/close warnings use the
service operation. Current private packets have a separate version from
native scoring and recordings; incompatible owned workers are retired before
new packets are issued.

## Design rationale

One mode control describes source handling without creating interacting
flags or changing the saved summary. Complete-source sentence comparisons
retain the native summarization calculation by default. Explicit all-window consistency trades more
comparisons for direct source-span coverage, rather than a retrieval promise
that selected passages represent the entire article.
Exact operation equality is part of native progress validation, alongside
execution and generation. Complete command metadata is included in derived
byte bounds; replies keep the configured byte allowance and fail explicitly
when the serialized packet does not fit.

An independent relevance boolean separates a scoring decision from input
provenance. A nullable skip reason distinguishes intentional absence of work
from failure while retaining the four numeric fields. Frozen four-score readers
keep earlier results and recordings meaningful; current saved handoffs bind
selection and nullable reference identity before generation and through reporting.
Frozen applicable-score readers also retain unmeasured errors without creating
counts or rewriting original receipt bytes.

A short question is only the fixed template. The complete model input also
contains its substituted summary sentence or full summary, source or reference
where applicable, and special tokens. Only that assembled input's actual
tokenizer count is compared with the configured allowance; separately counted
components are not assumed to add up. A fitting sentence/question can still
leave too little room for source progress and overlap, so geometry has its own
body-free error rather than a misleading size claim.

The scorer at the committed `assets.reference_code_revision` has a configurable
`max_length` constructor default of 1024 tokens and requests tokenizer
truncation in `metric/scorer.py`. Its `metric/evaluator.py` averages sentence
scores for consistency and fluency, while coherence and relevance use the
complete summary. The model configuration at `assets.model.revision` uses
relative attention and declares no fixed input-position ceiling.
Its pinned `tokenizer_config.json` advertises 512 tokens; this is advisory
metadata, not a second input cap.

The native `max_input_tokens` resource allowance is currently 4096 tokens,
above that upstream constructor default, and remains operator-configurable.
It counts the complete assembled input without clipping. Neither the
allowance, the constructor default nor tokenizer metadata establishes a fixed
model context maximum or arbitrary-length capacity. Recorded real predictions
prove composition and reduction, not judging accuracy or live workflow
execution. Workflow delivery remains a separate integration.

## See also

- [../../reference/unieval-api.md](../../reference/unieval-api.md) - native fields, preparation and errors.
- [summary-evaluator.md](summary-evaluator.md) - shared app composition and logging.
- [hhem-evaluation-api.md](hhem-evaluation-api.md) - independent HHEM process ownership.
- [../../concepts/evaluation.md](../../concepts/evaluation.md) - published evaluation semantics.
