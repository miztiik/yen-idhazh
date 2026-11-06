# Evaluate the content-similarity judge offline

**Last Updated**: 2026-11-06

Freeze explicit published comparisons, collect independent annotations, capture
the unchanged production judge, then score its saved replies without inference.
This procedure is project-specific because it uses native published-day,
annotation and judge-reader contracts.

## Prepare the named inputs

Use the existing backend development environment with its metric libraries.
From the repository root, select this checkout's code:

```powershell
$env:PYTHONPATH = "backend"
python -m utilities.evaluate_content_similarity_judge --help
```

Choose a private output directory under `backend/var/` or outside the checkout.
Other repository destinations, including production state and published data,
are refused. Keep transcripts private: article and model text remain untrusted
data, not instructions, filenames or addresses.

Create a pair manifest with `EvaluationSelection` from
`backend/idhazh/contracts/content_similarity_judge_evaluation.py`. `sources`
is the exact list of relative native `DigestDay` snapshot paths beneath one
explicit source root. Each pair names its two source paths and item IDs, an
event `group_id`, a `development` or `confirmation` split, and a
`representative` or `challenge` stream. No archive discovery or article fetch
occurs. Set event groups and splits before viewing predictions; articles and
event groups cannot cross splits.

For an instruction challenge, add `mutation` with `side` (`left` or `right`)
and nonempty `append_summary`. Freeze retains the original case and adds a
`planted_instruction` challenge variant in the same event group and split.
The append must survive sanitization and the resulting item must validate.
Repeated parents are retained once; every distinct variant counts toward the
configured case ceiling.

```powershell
python -m utilities.evaluate_content_similarity_judge freeze --selection backend\var\judge-evaluation\selection.json --source-root . --split confirmation --output-root backend\var\judge-evaluation
```

The command prints the content-addressed set and annotation filenames. Retain
the set unchanged. Its sources record exact snapshot-byte hashes and its cases
embed the published summaries; later scoring does not reopen the snapshots.

## Collect labels without showing predictions

Fix the rubric before opening confirmation results. Give each reviewer only
the printed `annotation-<set-hash>-confirmation.txt` file and that rubric.
This view contains opaque case/input identities and the production judge's
exact sanitized summary-pair turn. It omits source metadata, event groups,
selection streams, mutation tags, similarity scores, annotations and model
output. Factual names already present in summary text are not removed.

Collect the primary and independent reviews separately. Do not show the
independent reviewer the primary marks. Record opaque reviewer keys, not names,
and record real marking instants in UTC.

Create an `EvaluationLabels` document with:

- `set_sha256` from `document_sha256(EvaluationSet.read(set_path))`.
- The agreed rubric text and `rubric_sha256` from `derive_text_digest(rubric)`.
- Each annotation's case/input hashes from the blind view, reviewer key,
  primary/independent role, actual human/model/unverified origin, literal
  YES/NO/UNCLEAR verdict and UTC `marked_at`.

Use the native model to validate and serialize the file. Confirmation needs
distinct primary and independent human reviewers in agreement. Development
requires a human primary; a conflicting or non-human additional annotation
still prevents qualification. Model marks remain development references, never
independent human truth. Missing or disputed marks remain unresolved, not NO.
Software validates these declarations; it cannot certify that a person really
worked independently or used only the blinded view.

## Capture the actual model

Start the already configured, operator-controlled model process separately.
This utility never starts a server or downloads weights. Its only destination
is `model_server.base_url` in the selected committed config; there is no
destination or model override argument. Capture uses the production tokenizer
and template checks, reader, request builder, decoder, parser and evidence
policy, including both orders and any configured reasoning spans.

Supply a named native `HostFingerprintRow` JSON file describing the actual
model host, not a guessed machine or another run's caller. The existing
`idhazh.telemetry.silicon.read_row` can collect it locally with
`ask_placement=False`; serialize the returned row without calling a ledger
writer. Keep unavailable hardware fields null. For an off-machine controlled
model, collect the row on that host and supply that file. The
[host reference](../reference/host-metrics.md) owns collection and meanings.

```powershell
python -m utilities.evaluate_content_similarity_judge capture --set backend\var\judge-evaluation\set-<set-hash>.json --split confirmation --host backend\var\judge-evaluation\host.json --output-root backend\var\judge-evaluation
```

Capture records the current Git revision and loaded production configuration, model,
prompt, grammar, interpretation-policy and template-envelope identities.
For each order it retains the actual request JSON and raw response text for
every span, the production verdict or closed refusal reason, token costs and
elapsed time. An invalid completed response still receives its reverse
reading; there is no tie-breaking call.

The initial log names the run file. Each completed reading is saved with
temp-file-plus-rename before the next request. If transport fails, the command
fails and that file remains `incomplete`, with completed evidence intact and
the unfinished reading absent. There is no manufactured refusal, retry or
automatic resume. A new explicit capture is a separate observation; preserve
the incomplete one rather than merging responses from different attempts.

The entrypoint writes shared JSON event lines to stderr with UTC stamps.
Capture progress retains only its safe artifact filename; reading and evidence
refusals retain closed reasons and case identities. Unstructured library
records become fixed evaluator diagnostics with exception type and package
location when available, never raw library, article or model text. The stdout
result fields are unchanged.

## Score saved evidence

Scoring opens only the named set, labels and run, plus the selected config.
It does not initialize a model reader, tokenize, fetch sources or open a socket.
Use the capture's committed model/config/policy inputs; changed instrument
provenance blocks comparison rather than relabelling old replies.

```powershell
python -m utilities.evaluate_content_similarity_judge score --set backend\var\judge-evaluation\set-<set-hash>.json --labels backend\var\judge-evaluation\labels.json --run backend\var\judge-evaluation\run-<capture-hash>.json --output-root backend\var\judge-evaluation
```

Omit `--labels` to record an explicit missing-label result. A measured report
returns exit code 0; a blocked report is still saved and returns exit code 2.
Input validation or transport failures fail the operation, never a successful
empty report.

Reports bind the complete set, label and run documents by canonical SHA-256.
They keep representative and challenge results separate, with case/event-group,
qualified-label and prediction counts and a dense confusion table. Predictions
include YES, NO, UNCLEAR, DISAGREE and REFUSED. Recall includes every case with a
qualified reference verdict, including disagreements and refusals. An absent class or denominator
is unknown, not zero accuracy.

Missing, conflicting or unqualified labels, incomplete capture or mismatched
provenance block all quality metrics. Coverage counts remain visible.
Precision measures how often a predicted class is right; recall measures how
often a reference class is recovered. Both use scikit-learn; SciPy builds
percentile intervals by resampling whole event groups,
not correlated individual pairs. Unsupported intervals remain null with
`insufficient_groups`, `zero_denominator` or `undefined_resamples`; blocked
metrics use `blocked`. Margin diagnostics describe recorded readings, not a
confidence cutoff or a publication decision.

The named `config/judges/content-similarity-evaluation.json` defaults to an
input ceiling of 200 cases, 95% nominal interval coverage, 2,000 group resamples
and repeatable arithmetic seed 0. `load_evaluation(config_dir)` is its only
reader. Any strict integer seed is accepted; negative seeds are SHA-256 mapped
to NumPy's nonnegative seed domain. These settings bound input and reporting
work; none is an accuracy acceptance threshold or an inference-determinism
promise. Record the report settings with any real benchmark.
Each saved report snapshots all actual settings in its required
`report_settings` field. Read interval coverage, resampling count, seed and
input ceiling from that snapshot, not today's configuration. Different settings
produce different report identities even when the interval bounds coincide.

## Design rationale

Independent annotations and actual inference are external evidence, not outputs
that a passing harness can invent. A working evaluator can therefore report
blocked honestly. Schema examples and generated protocol tests verify software
only; they are neither human gold nor model recordings. Two-order agreement
measures consistency, and decoder margins describe recorded readings; neither
substitutes for independent annotations. Without qualified annotations and a
complete actual capture, leave the accuracy measurement explicitly unfinished,
not replaced by a replay score or a placeholder benchmark. A measured result
describes the declared finite set, not population-wide accuracy or permission
to change production behavior.

## See also

- [Contract compatibility](../architecture/contracts/schemas.md#private-judge-evaluation-documents)
- [Similarity judge](../architecture/publishing/autotune-content-similarity.md)
- [Gate commands](run-the-gates.md)
- [Evaluation concepts](../concepts/evaluation.md)
