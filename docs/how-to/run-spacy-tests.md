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

The GitHub Summary shows the unchanged source first, then spaCy results, then
GLiNER results. Source text is escaped preformatted text; result tables are
inside expandable disclosures. spaCy's default Named Entities and Important
Terms have separate tables; selected optional features appear in response
order. YAKE scores are native rankings: lower is better, not a confidence
probability. GLiNER shows the requested labels and each returned mention,
label, native score and offsets in response order. Provider scores are not
calibrated against each other. Offsets are zero-based, half-open Unicode code
points.

Named Entities lists text, type and occurrences; Important Terms lists phrase,
native YAKE score and occurrences. Selected raw entities, sentences, relations,
noun phrases, tokens and metrics each retain their native fields, including
source spans where supplied. Every table has row identifiers.

The run uploads available exact native `request.json` and `response.json`
files in fixed provider subdirectories, together with the complete `report.md`.
Files are written atomically in a run-owned runner-temporary directory and
retained under the workflow's existing artifact retention policy. The summary
and files can contain source text and extracted data. Diagnostic stderr stays
in the workflow logs, not the result tables.

Successful empty collections say no results were returned. A feature failure
shows its API error code and message without hiding completed siblings, and
partial status remains partial. Provider, startup, transport and invalid
response failures are explicit rather than empty successes; the other provider
is attempted when available. Available results are written and uploaded even
after failure, and execution exits nonzero. If the full UTF-8 report exceeds
GitHub's 1 MiB per-step summary limit, the complete report remains in the
artifact and the summary shows a size notice rather than truncating results.

The manual workflow reports results, not recognition quality, performance or
API correctness. It makes one spaCy analysis POST and one GLiNER NER POST for
the same source; it does not run a live-check suite or classification. Ordinary
required CI is separate. See the [shared API procedure](run-ner-api-tests.md)
for preparation and process ownership.

## See also

- [GitHub Actions workflows](../reference/github-actions.md)
- [Dispatch input rules](../reference/ci-dispatch-inputs.md)
- [Gate commands](run-the-gates.md)
