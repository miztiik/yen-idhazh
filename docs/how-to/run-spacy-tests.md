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
selection is refused. It has no separate dispatch source or label input.

GLiNER also classifies the unchanged source in one separate request containing
all article tasks. `desk` is single-label and offers active taxonomy verticals;
`lenses` and `events` are multi-label and offer their active entries.
`config/taxonomy.json` supplies each ID and its committed definition, in
taxonomy order. Draft and retired entries are excluded. The native `Taxonomy`
model validates this file; undefined definitions and empty offered
vocabularies fail classification explicitly without preventing NER.
The workflow exposes the backend source root only to reuse that schema;
it does not install the backend runtime or copy a taxonomy schema.

Send the JSON form through standard input so text is not a shell argument:

```powershell
$inputs = @{
  profile = 'md'
  feature_mode = 'default'
  custom_features = ''
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

The job is named `Text analysis`. Its Summary shows source text once, then
spaCy configuration/results, then GLiNER configuration/results. Escaped inline
code uses GitHub's native soft wrapping, including long words, while retaining
leading/repeated spaces, Unicode and displayed line breaks. GitHub normalizes
CR/LF line endings when rendering; saved native request text remains exact.

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
Entities have no explicit result-count cap.

Configuration tables distinguish saved request values from effective response
features/model metadata and saved native settings. An omitted spaCy `features`
field remains omitted, rather than becoming an explicit list; explicit lists
retain their order. The tables include native entity mapping/case rules and
Important Terms settings. GLiNER shows both attempted operations, exact entity
labels, classification task modes and offered ID-to-definition mappings.
Its model identity comes from saved native settings, not response metadata;
classification uses the same loaded model and its native SDK configuration,
with no caller threshold or model override. Selected optional raw spaCy
features retain their native fields and response order.

The separate expandable Article classification table shows row ID, task,
selected label ID, display name and native score. Tasks keep request order;
selections keep returned order, without sorting or discarding labels.
Display names come from the saved taxonomy, not later configuration.
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
source and the same provider section used in the Summary. The GLiNER root
request/response remain NER; its only additional files are
`classification/request.json`, `classification/response.json` and
`taxonomy.json`, the exact bytes validated for this request. Each upload runs
independently even after failure. The existing retention policy is unchanged.
Files are written atomically under a run-owned runner-temporary directory.
The summary and files can contain source text and extracted data. Diagnostic
stderr stays in the workflow logs, not the result tables.

Successful empty collections say no results were returned; unselected features
say not requested. Failed features show native errors without hiding completed
siblings, and partial status remains partial. Provider, startup, transport and
invalid-response failures are explicit rather than empty successes; each
independently available operation is attempted once. Classification failure
does not hide successful spaCy or GLiNER NER work, and NER failure does not hide
successful classification. Missing native output stays missing.
Available reports/files are uploaded after failure and execution exits nonzero.
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

## Regenerate reports without inference

Download each artifact into its matching `spacy` or `gliner` directory under
one results directory, then run:

```powershell
python tools\text-analysis-caller\write_reports.py <results-directory>
```

This standard-library-only command reads named saved native files and rewrites
each provider's `report.md`. It does not import provider runtimes, access the
network or load current repository configurations. Classification reuses its
saved request, response and taxonomy, retaining historical definitions and
display names. Source comes from any available saved native request, so
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
These checks exercise rendering, independent outcomes and in-memory caller
scheduling, not workflow declarations or provider execution.

## Design rationale

Preformatted blocks disable native wrapping, while inline CSS can be removed
by GitHub's sanitizer. Inline code uses the supported native wrapping rules;
escaped character references keep source line breaks out of Markdown parsing.
Separate provider artifacts preserve independent delivery and keep oversized
summaries recoverable without introducing a second JSON contract. Classification
keeps its existing native request/result contracts and the validated taxonomy
copy so replay needs neither inference nor a later vocabulary.

## See also

- [GitHub Actions workflows](../reference/github-actions.md)
- [Dispatch input rules](../reference/ci-dispatch-inputs.md)
- [Gate commands](run-the-gates.md)
