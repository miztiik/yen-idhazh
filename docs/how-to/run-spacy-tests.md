# Run the text-analysis verification

**Last Updated**: 2026-11-08

How to dispatch `spacy-tests.yml` against one selected implementation ref
and inspect its live multilingual API evidence. This procedure is
project-specific because it uses the committed text-analysis service and shared
TypeScript event contracts.

## Register before dispatch

The workflow definition must exist on the default branch before GitHub accepts
a dispatch by filename. Select the implementation branch or tag when
dispatching. GitHub resolves that ref to `github.sha`; the workflow checks out
and verifies that exact immutable commit.

Do not treat registration or ordinary pull-request checks as live
text-analysis evidence. The checked commit must contain the complete
`services/text_analysis/` implementation and scripts.

## Select the exact ref and inputs

The dispatch ref selects both the workflow revision and implementation. The
workflow disables checkout credentials, checks out `github.sha` and confirms
that the resulting `HEAD` is the same 40-character commit.

Always supply `language` as `en` or `zh` and `feature_mode` as `default`, `all`
or `custom`. `profile` defaults to `md`; `sm` and `lg` remain optional manual
profiles. `text` is required. `default` selects `relations`, `entities`,
`sentences`, `document_metrics`; `all` selects every feature supported by the
selected language.

For `custom` mode, set `custom_features` to a nonempty comma-separated list
drawn from `entities`, `sentences`, `relations`, `noun_phrases`,
`linguistic_tokens` and `document_metrics`. Names are case-sensitive, duplicate
names are refused, surrounding CSV whitespace is ignored and supplied order is
preserved. Leave `custom_features` blank for the other modes.

Send the JSON form through standard input so text never becomes a shell
argument:

```powershell
$inputs = @{
  language = 'en'
  profile = 'md'
  feature_mode = 'default'
  custom_features = ''
  text = Get-Content -Raw .\text-analysis-input.txt
} | ConvertTo-Json -Compress

$inputs | gh workflow run spacy-tests.yml --ref '<implementation-branch-or-tag>' --json
```

Before the implementation pull request merges, select its final branch head
once with `language = 'en'` and once with `language = 'zh'`, both using
`profile = 'md'`. Confirm both runs record the same final `github.sha`. Any
later implementation edit invalidates both results.

The platform retains dispatch inputs, and completed evidence may contain
returned source spans. Do not submit private material or credentials.

## Inspect the run and evidence

```powershell
gh run list --workflow spacy-tests.yml --limit 5 --json databaseId,headSha,status,conclusion,url
gh run view <run-id> --log
gh run download <run-id> --dir <evidence-directory>
```

The run's `headSha`, recorded selected SHA and tested commit must agree.
Preserve the run URL, workflow SHA, tested commit, inputs, artifact ID,
conclusion and `report.json`.

The single artifact is named
`spacy-tests-<run-id>-<run-attempt>` and is retained for 90 days. It includes
the workflow context, `selected-ref.txt`, selected SHA and tested commit, the runner's
machine-readable report, captured `events.jsonl` and escaped
`job-summary.md`. The artifact uploads after ordinary failure. Cleanup or
upload failure leaves the job red.

The job has a 60-minute bound. It prepares only the selected model, runs the
service through its owned process group and uses the shared TypeScript
CloudEvents contract. It never writes evidence paths into API configuration.

## Local execution boundary

Do not install, import, start or load the text-analysis service locally for
this verification. Existing CI checks workflow structure; this manual workflow
is the live functional check.

## See also

- [GitHub Actions workflows](../reference/github-actions.md)
- [Dispatch input rules](../reference/ci-dispatch-inputs.md)
- [Gate commands](run-the-gates.md)
