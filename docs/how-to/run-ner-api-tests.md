# Run the shared text-analysis APIs

**Last Updated**: 2026-11-09

How the manual reporting workflow collects results from both independent
providers on their existing shared listener. This procedure is project-specific
because it uses their committed settings and registered `ner-tests.yml`.

## Dispatch and inspect

Follow [the text-analysis dispatch procedure](run-spacy-tests.md) for the
selected ref, profile, source disclosure and report. For a candidate
observation, inspect one Linux run at the intended commit and compare its
saved requests and responses with the summary. Both requests use the same
source. This observation is not a test suite or a quality assessment.
Ordinary required pull-request CI remains separate.

## Prepare and collect on Linux

Follow the [local execution boundary](run-the-gates.md#independent-text-analysis-service).
The workflow verifies the named native locks, syncs the frozen GLiNER
development environment, prepares the selected spaCy wheel and configured
GLiNER snapshot, and checks installation compatibility. The providers retain
independent production manifests.

The caller under `tools/text-analysis-caller/` starts the existing
`services/text_analysis/hosting/serve_apis.py` assembly as a child. It uses
bounded readiness checks and the existing listener settings, sends one spaCy
analysis POST and one GLiNER NER POST, and stops its owned process group in a
`finally` path. Readiness and cleanup are operational steps, not inference
tests. There are no synthetic probes, classification calls, warm repeats or
automatic inference retries. The caller uses HTTP rather than provider
extraction internals; neither API writes report files.

The caller renders available results and uploads the exact native requests,
responses and complete Markdown report even after failure. The
[dispatch guide](run-spacy-tests.md#inspect-the-results) describes partial,
empty, failed and oversized results. The report does not establish recognition
quality, concurrency, throughput or news-pipeline integration.

## Start the same application

After preparing the Linux environment and its configured model assets:

```bash
uv run --project services/text_analysis/gliner --no-sync python services/text_analysis/hosting/serve_apis.py --root .
```

The command binds the existing listener from
`config/text-analysis/settings.json`. The native API families remain independent;
no second host or port setting is needed.

## See also

- [Dispatch and results](run-spacy-tests.md)
- [Gate ownership and local execution boundary](run-the-gates.md)
- [Complete-application hosting](../architecture/local-api-host.md)
- [Native GLiNER lifecycle](../architecture/text-analysis/gliner-api.md)
- [Exact GLiNER API contract](../reference/gliner-api.md)
