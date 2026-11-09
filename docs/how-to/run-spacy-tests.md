# Run text analysis and inspect results

**Last Updated**: 2026-11-09

How to dispatch `ner-tests.yml` for one source and inspect the native spaCy
and GLiNER results. This procedure is project-specific because it uses the
committed text-analysis providers and their shared listener.

## Select the ref and inputs

The workflow definition must exist on the default branch before GitHub accepts
a dispatch by filename. Select the implementation branch or tag; GitHub
resolves it to `github.sha`, and the workflow checks out and verifies that
commit without retaining checkout credentials.

The required `text` input is the source for both providers. Its editable
default is in the workflow dispatch definition. The platform retains dispatch
inputs, and the source is visible in the summary and saved requests to anyone
who can view the run. Do not submit secrets or private material.

spaCy runs in English. `profile` defaults to `md`, with `sm` and `lg` also
available. `feature_mode` defaults to `default`; `all` selects all supported
English features, and `custom` uses `custom_features`. Default mode omits
`features` from the request so the API selects its configured defaults.
Custom mode requires a nonempty comma-separated list from `entities`,
`sentences`, `relations`, `noun_phrases`, `linguistic_tokens`,
`document_metrics`, `named_entities` and `important_terms`. Names are
case-sensitive; duplicates are refused, surrounding whitespace is ignored,
and order is preserved. Leave `custom_features` blank for other modes.

GLiNER uses distinct presentation types from `named_entities.label_map` in
`config/text-analysis/settings.json`, in configuration order. An empty label
selection is refused. NER has no separate dispatch source or entity-label input.

GLiNER also classifies the unchanged source in one separate request. Optional
`classification_tasks` accepts the API's native tasks JSON object: one or any
number of arbitrary named tasks, each with an ID-to-label-text `labels` mapping
and a `multi_label` boolean. Names and IDs must be nonblank strings, not members
of a caller-maintained list. Label text can be a plain display name; no extra
definition field or taxonomy membership is required. For example:

```json
{"tone":{"labels":{"neutral":"Neutral","opinion":"Opinion"},"multi_label":false}}
```

Leave `classification_tasks` blank to build the convenience request from
`config/taxonomy.json`: single-label `vertical` and `desk` use active vertical
definitions, multi-label `lenses` uses active lens definitions, and single-label
`source_kind` uses active source-kind display names without new definitions.
Draft and retired entries are excluded. Only this default construction loads
the native `Taxonomy` model; custom tasks do not read taxonomy. Invalid custom
JSON or invalid defaults fail classification explicitly without preventing NER.
The workflow exposes the backend source root for default validation without
installing the backend runtime or copying a taxonomy schema.

These are model selections for the requested tasks only. Text alone supplies
no feed provenance, so `vertical` is not a factual source vertical and
`source_kind` is not the feed-declared source kind. Nothing changes production
article identity, desk placement or publication policy. `events` is not in the
default request but remains a valid caller-supplied task like any other name.

Send the JSON form through standard input so text is not a shell argument:

```powershell
$inputs = @{
  profile = 'md'
  feature_mode = 'default'
  custom_features = ''
  classification_tasks = ''
  text = Get-Content -Raw .\text-analysis-input.txt
} | ConvertTo-Json -Compress

$inputs | gh workflow run ner-tests.yml --ref '<implementation-branch-or-tag>' --json
```

## Inspect the results

```powershell
gh run list --workflow ner-tests.yml --limit 5 --json databaseId,headSha,status,conclusion,url
gh run view <run-id> --log
gh run download <run-id> --dir <results-directory>
```

The job is named `Text analysis`. Its Summary shows a collapsed `Source text`
disclosure, then spaCy configuration/results, then GLiNER configuration/results.
The source is escaped ordinary prose, with native wrapping and explicit source
line breaks, not code styling. Native prose collapses repeated spaces and tabs
and normalizes CR/LF while displaying breaks. Saved native request text remains
exact, including whitespace and Unicode.

Each provider has expandable tables for every configured/requested entity
type. The current types display as Organizations, Locations and People; extra
types get their own table rather than being filtered out. Each row has a stable
identifier, original entity text, returned occurrence count and source
positions. Groups sort by occurrence count descending, then earliest source
position, then original group order. Row identifiers retain that original
order. Occurrences sort by source position; native JSON order is unchanged.

spaCy retains its existing groups, first spelling, configured case rule and
every native span/sentence index. GLiNER groups only exact text with the same
requested label, retaining each occurrence's native confidence beside its
position. No aliases are merged or labels rewritten. Offsets are zero-based,
half-open Unicode code points; GLiNER supplies no sentence indexes.

Important Terms shows rank, phrase, occurrence count, native YAKE score and
positions in native term order. Lower scores rank higher within the same
article/settings; scores are not percentages, confidence probabilities or
editorial quality grades. Counts are frequency, not weights. Existing native
term limits appear in the configuration table, not as another report cap.
Neither NER request accepts a per-category entity maximum; all returned
entities are kept.

Configuration tables contain row ID, Setting and one Effective value column.
spaCy features/model metadata come from its response; entity mapping/case rules
and Important Terms settings come from saved native settings. An omitted spaCy
`features` field remains omitted in the request; returned feature order is
preserved. GLiNER shows actual saved values for both operations, exact entity
labels, classification task modes and offered ID-to-label-text mappings.
Its model identity comes from saved native settings, not response metadata;
classification uses the same loaded model and its native SDK configuration,
with no caller threshold or model override. Selected optional raw spaCy
features retain their native fields and response order.

The separate expandable Article classification table shows row ID, task,
selected label ID, request label text and native score. Tasks keep request order;
selections keep returned order, without sorting or discarding labels.
Label text comes directly from the saved request, not taxonomy or later
configuration. Rendering never reconstructs an expected task list.
GLiNER native NER and classification scores range from zero to one:
higher means stronger model confidence, not calibrated correctness
percentages. Long-text classifier scores can aggregate chunks. A valid empty
selection is shown as no label selected, not replaced with an invented choice.
Native multi-label selection can keep its strongest label when none meets
its internal selection threshold; it does not guarantee abstention.

Only these provider artifacts are uploaded:

- `spacy-results-YYYYMMDD-<run_id>-<attempt>`
- `gliner-results-YYYYMMDD-<run_id>-<attempt>`

The UTC date is captured once near job start and reused across midnight.
Each artifact contains available exact native `request.json`, `response.json`
and validated `settings.json`, plus a complete standalone `report.md` with
source and the same provider section used in the Summary. Each also contains
`events.jsonl`; see [console and saved events](#console-and-saved-events).
The GLiNER root request/response remain NER; its other files are
`classification/request.json` and `classification/response.json`. Each upload runs
independently even after failure. The existing retention policy is unchanged.
Files are written atomically under a run-owned runner-temporary directory.
The summary and native request/response files can contain source text and
extracted data. Diagnostic events are separate from result tables.

Successful empty collections say no results were returned; unselected features
say not requested. Failed features show native errors without hiding completed
siblings, and partial status remains partial. Provider, startup, transport and
invalid-response failures are explicit rather than empty successes; each
independently available operation is attempted once. Classification failure
does not hide successful spaCy or GLiNER NER work, and NER failure does not hide
successful classification. Missing native output stays missing.
Available reports/files are uploaded after failure and execution exits nonzero.
A partial spaCy response also makes the reporting step fail even when both
GLiNER operations complete.
If the combined UTF-8 report exceeds GitHub's 1 MiB per-step summary limit,
the Summary points to both complete provider reports rather than truncating or
referring to an unuploaded combined file.

The manual workflow reports results, not recognition quality, performance or
API correctness. It makes one spaCy analysis POST and dispatches one GLiNER
NER POST and one classification POST concurrently for the same source.
Both GLiNER calls finish before the shared API process stops. This is
concurrent client dispatch, not parallel native model inference: the existing
provider serializes operations on one loaded model. No second server, model,
download, live-check suite or inference retry is added. Ordinary required CI
is separate. See the [shared API procedure](run-ner-api-tests.md) for preparation
and process ownership.

## Console and saved events

The APIs emit validated native CloudEvents to stderr, not HTTP response bodies.
The caller mirrors every emitted event immediately to the workflow console
and to the matching artifact's `events.jsonl`. spaCy source
`/services/text-analysis` goes only to the spaCy file; GLiNER source
`/services/text-analysis/gliner` goes only to the GLiNER file, including both
NER and classification. Records retain their exact bytes, UTC times, event
identities, traces and diagnostic data.

Capture begins before readiness and continues through process cleanup and
confirmed stderr EOF, retaining startup, readiness, operation, failure and
shutdown records whenever the native services emit them. Logging levels and
event byte limits come from each saved, native-validated provider setting.
Malformed, unknown, oversized or incomplete records fail capture without
printing their raw contents. Capture, console, file and cleanup failures are
explicit process errors and make the job fail, while retaining available
validated events and successful processing artifacts.

Full response bodies remain in `response.json` and GLiNER's
`classification/response.json`; they are not dumped to the console or event
files. Neither API gains a file sink, and report regeneration does not read
or rewrite diagnostics.

Capture covers emitted native diagnostics, not every internal model action.
A `FEATURE_FAILED` outcome identifies the failing feature but omits the
underlying exception and traceback. Preparation steps run before API startup
and therefore have no API events.

## Regenerate reports without inference

Download each artifact into its matching `spacy` or `gliner` directory under
one results directory, then run:

```powershell
python tools\text-analysis-caller\write_reports.py <results-directory>
```

This standard-library-only command reads named saved native files and rewrites
each provider's `report.md`. It does not import provider runtimes, access the
network or load current repository configurations. Classification reuses only
its saved native request and response, retaining exact task names, label text,
selections and scores. Historical requests including `events` remain replayable
unchanged; a historical `taxonomy.json` is not read or required.
Source comes from any available saved native request, so
regeneration cannot recover source when no request was saved. Artifacts
without classification evidence retain their original not-requested state.
Saved failures or missing responses remain failures, with a nonzero exit.

The bounded caller checks do not install or import either provider:

```powershell
python tools\text-analysis-caller\test_reports.py
python -m ruff check --config services\text_analysis\gliner\pyproject.toml tools\text-analysis-caller
python -m mypy --ignore-missing-imports --follow-imports=skip --platform linux --python-version 3.12 --strict tools\text-analysis-caller
npm --prefix frontend run test:changed -- --list
```

Ordinary CI also runs the pure report assertions without starting a provider.
These checks exercise rendering, independent outcomes, in-memory caller
scheduling and bounded stream delivery, not workflow declarations or provider
execution. Native event validation and console/file routing are observed on
the Linux reporting run.

## Design rationale

Native disclosure and ordinary prose provide wrapping without code styling.
Escaped character references keep source markup literal; explicit breaks retain
source paragraphs. Exact whitespace stays in saved requests rather than relying
on preformatted text or styles that GitHub's sanitizer can remove.
Separate provider artifacts preserve independent delivery and keep oversized
summaries recoverable without introducing a second JSON contract. Classification
keeps its existing native request/result contracts. The request itself owns
the offered tasks and label text, so replay needs neither inference nor a
taxonomy snapshot, and adding a task requires request data rather than code.

## See also

- [GitHub Actions workflows](../reference/github-actions.md)
- [Dispatch input rules](../reference/ci-dispatch-inputs.md)
- [Gate commands](run-the-gates.md)
