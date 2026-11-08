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
`services/text_analysis/spacy/` implementation and scripts.

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

The platform retains dispatch inputs. The selected source text is also visible
in the run summary and `analysis-request.json` to anyone who can view the run.
Do not submit secrets or private material.

## Inspect the run and evidence

```powershell
gh run list --workflow spacy-tests.yml --limit 5 --json databaseId,headSha,status,conclusion,url
gh run view <run-id> --log
gh run download <run-id> --dir <evidence-directory>
```

The run's `headSha` and `report.json` `commit_sha` must agree. Preserve the run
URL, commit, inputs, artifact ID, conclusion and `report.json`.

The single artifact is named
`text-analysis-spacy-evidence-<run-id>-<run-attempt>` and is retained for 90
days. A successful artifact contains exactly:

- `report.json` - the strict workflow receipt;
- `analysis-request.json` - the exact validated selected request, including
  source text and resolved feature order;
- `health-response.json` - the exact validated ready health response;
- `analysis-response.json` - the exact validated selected analysis response;
- `events.jsonl` - the canonical validated CloudEvents; and
- `report.md` - the same escaped bytes appended to the GitHub step summary.

The successful receipt has only version `2026-11-08`, conclusion `success`,
the lowercase 40-hex `commit_sha`, positive run ID and attempt, and cleanup
`confirmed`. A failed receipt adds one declared safe `failure_code`. The
contract changelog says: `Split native API evidence from the verification
outcome and make cleanup semantic.` Old retained artifacts keep their original
shape; new runs write only this version.

The summary leads with PASS or FAIL, links the run and commit, then
shows selected model identity, ordered feature outcomes, the capacity/BUSY/warm
reuse checks, semantic cleanup and the escaped source text. It never includes
raw analysis data, trace values, process details, paths, exceptions or the
generated concurrency input. GitHub limits one step summary to 1 MiB. The
runner checks the complete UTF-8 bytes and fails with a safe code instead of
truncating them. Its failed `report.md` keeps the complete escaped source; it
never substitutes an omission message.

The artifact uploads after ordinary failure. Cleanup or upload failure leaves
the job red.

The job has a 60-minute bound. It prepares only the selected model, runs the
service through its owned process group and uses the shared TypeScript
CloudEvents contract. It never writes evidence paths into API configuration.
The verification step pipes the GitHub event payload to the runner on stdin,
so dispatch text is not copied into the step environment or command line.
Keeping supervision inside that one step is deliberate:
`run-spacy-test.py` owns server startup, readiness, HTTP evidence, exact
process-group cleanup and final validation in one `try/finally`.
`probe-text-analysis.ts` receives only `base_url` for live calls and verifies
the service independently over HTTP. The runner reads `events.jsonl` as bounded
records, using the configured `logging.max_event_bytes` and the exact expected
request plus lifecycle count. It mirrors only events that pass the native
strict CloudEvents contract to the live workflow stderr log.

Cleanup evidence is semantic: `not_started` means no child was created,
`confirmed` means an owner-sent SIGTERM or a clean exit was confirmed,
`forced` means SIGKILL was required and confirmed, and `unconfirmed` means exit
could not be proved. Successful runs require `confirmed`. Historical report
value `-15` was the POSIX SIGTERM exit code and represented expected owner
cleanup, not a service failure. New receipts expose no raw exit code.

## Local execution boundary

Do not install, import, start or load the text-analysis service locally for
this verification. Existing CI checks workflow structure; this manual workflow
is the live functional check.

Production pipelines use their own process supervisor and call the health and
analyze routes directly. They do not reuse this verification runner.

## See also

- [GitHub Actions workflows](../reference/github-actions.md)
- [Dispatch input rules](../reference/ci-dispatch-inputs.md)
- [Gate commands](run-the-gates.md)
