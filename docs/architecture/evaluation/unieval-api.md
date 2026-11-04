# How the UniEval API checks a complete source

**Last Updated**: 2026-11-04

How the local evaluator produces four distinct scores without silently
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

The service preserves the selected model's native question formats,
sentence rules and normalized Yes/No probability calculation. It does not
produce an overall grade. Relevance is not a measure of source coverage,
and consistent claims do not prove that the summary includes every important
fact.

## Complete source processing

The default consistency mode splits the summary into its native sentence
units and the source into overlapping tokenizer-sized spans. Each source span
is a slice of the unchanged original string. The plan reserves room for the
question, the longest summary sentence and special tokens, then verifies
every complete prompt again with the actual tokenizer. It never uses the
tokenizer's truncation option.

When normalization maps several tokens to one original character, windows
end and restart only at complete character boundaries. Overlap rounds
outward, never below its configured target. If that prevents forward
progress within the prompt allowance, consistency receives a declared
planning error; other admissible dimensions still run.

Every summary sentence is compared with every source window. A sentence's
score is the highest completed window score; consistency is the mean of
these sentence scores. Taking one best window against the whole summary
would miss support spread across different sections, so that is not the
calculation. Source offsets and completed counts let the caller verify
coverage of the supplied article, including its end.

The alternative full-source mode compares each sentence with the complete
source and retains the native sentence mean. An oversized complete prompt
fails explicitly; the service does not silently select another mode.

Neither mode proves global factual correctness. A segmented comparison
cannot join evidence split across distant windows, and choosing a best
match can overlook contradictory passages elsewhere. The result names the
actual mode so it cannot be confused with a native whole-source score.

## Native dimensions and incomplete work

Fluency keeps its native sentence mean and needs no article windows.
Coherence uses one full-source/full-summary prompt. Relevance uses one
full-reference/full-summary prompt. Averaging either score over source
windows would define a different measure, so the service does not do it.

If a complete prompt exceeds its allowance, that dimension has a safe error
and no numeric score. Other admissible dimensions can finish. Missing
reference text is invalid input, not a request for three scores.

The parent validates each private reply against its request, process
generation, dimension, sentence and source-window identity. It retains
completed predictions outside the model process. A final dimension requires
all of its planned comparisons; a maximum from an unfinished matrix is not a
score. Computed zero is valid, while uncomputed values remain null.
All four dimensions and no errors are required for a complete result.

## Independent ownership

The [shared application](local-model-api.md) explicitly registers the
UniEval router. Its queue and owned process are independent of HHEM and
native generation. Model loading, tokenization and inference run in the
worker, not on the HTTP event loop. Body reservations and deadlines still
apply before reading a request.

Requests and progress use bounded JSON bytes over owned pipes. A lifetime
watcher stops the child when its parent disappears; Linux also uses the
kernel parent-death mechanism shared with HHEM. Cancellation and request
deadlines close the exact child's lifetime pipe and confirm its joined
exit, escalating to a kill of that owned process if needed. A failed worker
does not start an automatic restart loop.

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

## Design rationale

One mode control describes source handling without creating interacting
flags or changing the saved summary. All-window consistency trades more
comparisons for direct source-span coverage, rather than a retrieval promise
that selected passages represent the entire article.

A larger configured input allowance permits complete native coherence and
reference prompts when execution supports them. It is not evidence that
judging accuracy is unchanged at longer lengths. Recorded real predictions
prove composition and reduction; they are not live workflow proof or an
accuracy certificate. Workflow delivery remains a separate integration.

## See also

- [../../reference/unieval-api.md](../../reference/unieval-api.md) - native fields, preparation and errors.
- [local-model-api.md](local-model-api.md) - shared app composition and logging.
- [hhem-evaluation-api.md](hhem-evaluation-api.md) - independent HHEM process ownership.
- [../../concepts/evaluation.md](../../concepts/evaluation.md) - published evaluation semantics.
