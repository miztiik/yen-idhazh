# Verify the shared text-analysis APIs

**Last Updated**: 2026-11-09

How to verify both independent native APIs through one application in the
existing API-functional job. This procedure is project-specific because it
uses the native provider packages, their committed listener settings and the
registered `ner-tests.yml` workflow.

## Dispatch the exact candidate

Follow [the native spaCy dispatch procedure](run-spacy-tests.md) for the exact
ref, selected language/profile, source-text disclosure and retained evidence.
Run the final candidate once for English and once for Chinese, both using
`md`, and require both recorded `headSha` values to equal that candidate.
Ordinary pull-request CI is also required; a running or skipped check is not a
pass.

Each dispatch retains spaCy's Unicode evidence check, native in-memory tests,
live HTTP verification, cleanup and evidence upload. The same job additionally
runs the existing neutral-host regressions and the focused native/shared API
file. No new workflow or pipeline test is involved.

## Prepare one provider environment

These are Linux workflow commands, not developer-host instructions. Follow the
[local execution boundary](run-the-gates.md#independent-text-analysis-service).
Verify the named native locks, then use the existing GLiNER development group,
which already resolves the sibling text-analysis package:

```bash
uv lock --locked --project services/local_api_host
uv lock --locked --project services/text_analysis/spacy
uv lock --locked --project services/text_analysis/gliner
uv sync --project services/text_analysis/gliner --frozen --extra model --group dev
```

The workflow checks Ruff and strict mypy over GLiNER, the neutral host and
`services/text_analysis/hosting/`. `MYPYPATH=../hosting` from the GLiNER project
directory resolves the thin assembly during those checks.
The native and repository lint profiles are selected explicitly for their
respective source roots; strict mypy uses the native project configuration.
The existing host registration, lifecycle and trace tests use the evaluator's
own frozen verification environment; they prepare no evaluator model.

After the existing native spaCy tests, prepare its selected configured wheel
using the dispatch's `TEXT_ANALYSIS_LANGUAGE` and `TEXT_ANALYSIS_PROFILE`.
Prepare the configured GLiNER snapshot before the focused test:

```bash
uv run --project services/text_analysis/gliner --no-sync python services/text_analysis/spacy/scripts/prepare-selected-model.py
uv run --project services/text_analysis/gliner --no-sync python services/text_analysis/gliner/scripts/prepare_model.py --root .
uv pip check --python services/text_analysis/gliner/.venv/bin/python
PYTHONPATH=services/text_analysis/hosting uv run --project services/text_analysis/gliner --no-sync pytest services/text_analysis/gliner/tests/test_api.py
```

`--no-sync` preserves the selected spaCy wheel installed after frozen
preparation. It does not substitute an unlocked dependency set: the preceding
sync and compatibility check remain required. Provider production manifests
remain independent, and there is no additional model download for comparison.
Tests disable external sockets and use real prepared inference, not model
mocks.

## Inspect the shared result

The focused file constructs the actual
`services/text_analysis/hosting/serve_apis.py` application and uses one
prepared-model ASGI lifespan for both providers. It requires actual spaCy
analysis plus native GLiNER NER/classification results, separate ready health
responses, unchanged customized schemas, native refusal behavior and one
receiving trace operation per request. Classification definitions come from
the current active entries in `config/taxonomy.json`, not a copied label list.

The installed HTTPX async client enters the native application lifespan
directly on the provider's asyncio event loop. It does not use the deprecated
synchronous test-client bridge or another listener.

The SDK import also loads its HTTP library, which probes local IPv6 support.
`pytest-socket` blocks that socket creation and emits a warning even when the
probe catches the exception. That specific import-time alert is not an
outbound inference request. Keep socket blocking enabled and investigate any
other blocked call rather than ignoring socket warnings.

The existing GLiNER cancellation check still requires accepted work and
terminal diagnostics to retain model ownership after the HTTP waiter
disappears. Its own shutdown must not stop spaCy. Construction also refuses
duplicate applications, colliding paths and mismatched transport bounds.

Preserve the exact candidate commit, both run URLs and conclusions, the
`gliner-api-results-<run-id>-<run-attempt>` JUnit artifacts and the original
spaCy evidence artifacts. A successful shared result proves native
request/readiness/schema/lifecycle retention on one application, not
recognition quality, faster elapsed time or news-pipeline integration.

## Start the same application

After preparing that Linux environment and its configured model assets:

```bash
uv run --project services/text_analysis/gliner --no-sync python services/text_analysis/hosting/serve_apis.py --root .
```

The command binds only the existing listener from
`config/text-analysis/settings.json`. The complete native API families remain
independent; no second host/port setting or hosting distribution is needed.

## See also

- [Native dispatch and spaCy evidence](run-spacy-tests.md)
- [Gate ownership and local execution boundary](run-the-gates.md)
- [Complete-application hosting](../architecture/local-api-host.md)
- [Native GLiNER lifecycle](../architecture/text-analysis/gliner-api.md)
- [Exact GLiNER API contract](../reference/gliner-api.md)
