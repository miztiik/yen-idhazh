# Run the text-analysis verification

**Last Updated**: 2026-11-08

How to dispatch `spacy-tests.yml` against one immutable implementation commit
and inspect its live multilingual API evidence. This procedure is
project-specific because it uses the committed text-analysis service and shared
TypeScript event contracts.

## Register before dispatch

The workflow definition must exist on the default branch before GitHub accepts
a dispatch by filename. The workflow still tests the commit supplied through
`code_ref`; the default-branch workflow revision and the tested implementation
revision are separate identities.

Do not treat registration or ordinary pull-request checks as live
text-analysis evidence. The checked commit must contain the complete
`services/text_analysis/` implementation and scripts.

## Supply the exact commit and inputs

`code_ref` is required and must be a lowercase 40-character commit SHA. The
workflow validates it before checkout, disables checkout credentials and
confirms that the resulting `HEAD` is the same SHA.

Always supply `language` as `en` or `zh` and `feature_mode` as `default`, `all`
or `custom`. `profile` defaults to `md`; `sm` and `lg` remain optional manual
profiles. `text` is required.

For `custom` mode, set `custom_features` to a nonempty comma-separated list
drawn from `entities`, `sentences`, `relations`, `noun_phrases`,
`linguistic_tokens` and `document_metrics`. Names are case-sensitive, duplicate
names are refused and supplied order is preserved. Leave `custom_features`
blank for the other modes.

Send the JSON form through standard input so text never becomes a shell
argument:

```powershell
$inputs = @{
  code_ref = '<immutable-40-character-sha>'
  language = 'en'
  profile = 'md'
  feature_mode = 'default'
  custom_features = ''
  text = Get-Content -Raw .\text-analysis-input.txt
} | ConvertTo-Json -Compress

$inputs | gh workflow run spacy-tests.yml --ref main --json
```

Before the implementation pull request merges, run the same final `code_ref`
once with `language = 'en'` and once with `language = 'zh'`, both using
`profile = 'md'`. Any later implementation edit invalidates both results.

The platform retains dispatch inputs, and completed evidence may contain
returned source spans. Do not submit private material or credentials.

## Inspect the run and evidence

```powershell
gh run list --workflow spacy-tests.yml --limit 5 --json databaseId,headSha,status,conclusion,url
gh run view <run-id> --log
gh run download <run-id> --dir <evidence-directory>
```

The run's `headSha` identifies the default-branch workflow definition, not the
tested implementation. Preserve the run URL, workflow SHA, tested commit,
inputs, artifact ID, conclusion and `report.json`.

The single artifact is named
`spacy-tests-<run-id>-<run-attempt>` and is retained for 90 days. It includes
the workflow context, requested and tested commits, the runner's
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
