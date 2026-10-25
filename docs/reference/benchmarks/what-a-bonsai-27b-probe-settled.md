# What the Bonsai 27B ternary probe settled

**Last Updated**: 2026-10-24

This page records the result and limits of the experimental Ternary Bonsai 27B
probe. It records runtime behavior only; it does not establish summary quality
or model suitability.

## Status

**Ternary-Bonsai-2-27B-PTQ1_0 is parked for future investigation.** The one run
that reached inference did not return a usable reply before cancellation after
about 188 minutes on four AMD EPYC 7763 cores. It is not performant enough for
this repository at this time.

This is a finding about the probe on this runtime and runner. It is not an
evaluation of summary quality, and it does not reject every ternary packing or
every future runtime. The model is not configured for the daily pipeline.

## Conditions

| Reading | Value |
| --- | --- |
| Model | Ternary-Bonsai-2-27B-PTQ1_0 |
| Repository | `prism-ml/Ternary-Bonsai-2-27B-gguf` |
| GGUF | `Ternary-Bonsai-2-27B-PTQ1_0.gguf` |
| Packing | PTQ1_0 |
| Runtime | PrismML llama.cpp, release `prism-b10685-7dffb15` |
| Date | 2026-10-14 UTC |
| Runner | GitHub-hosted `ubuntu-latest`, AMD EPYC 7763 64-Core Processor |
| Visible cores | 4 |
| Memory reported by the script | 15.61 GiB |
| Server context | 65,536 tokens |
| Request shape | One system prompt and one article sent to `/v1/chat/completions` |

The probe used the experimental `bonsai-ternary-model-test` workflow and a
separate Node inference script. It did not use the repository's current
production summarization path or a fixed article corpus, and it did not produce
a model dossier.

## The run that reached inference

Run [38616024322](https://github.com/miztiik/yen-idhazh/actions/runs/38616024322)
started the PrismML server and reported the server healthy at 9931 at
18:33:50 UTC. Inference started at 18:33:51 UTC and produced no summary.

The pipeline reported heartbeats every 15 seconds while waiting for the server
response. The last logged heartbeat reported 11,283 seconds elapsed. The run
ended cancelled about three minutes later. No completion tokens, decode rate, or
usable output were recorded.

Server startup was healthy in this run. Runtime compatibility was not the
question left open; the open question was whether inference would return within
an acceptable runner window.

## Earlier attempts

The workflow had earlier setup failures. These failures are why the full result
must not be described from the final run alone, and why none of them is a
summary-quality reading.

| Run | Outcome |
| --- | --- |
| [38607619554](https://github.com/miztiik/yen-idhazh/actions/runs/38607619554) | The first `node-llama-cpp` script path failed before a model response because the package used unsupported CommonJS top-level-await output. |
| [38609395389](https://github.com/miztiik/yen-idhazh/actions/runs/38609395389) | The runtime rejected the GGUF weight type or block size as invalid. |
| [38610739398](https://github.com/miztiik/yen-idhazh/actions/runs/38610739398) | The server accepted a 1,024-token context, then rejected the 1,561-token request. |
| [38612339326](https://github.com/miztiik/yen-idhazh/actions/runs/38612339326) | The inference process could not connect because the server stopped listening. |
| [38613775096](https://github.com/miztiik/yen-idhazh/actions/runs/38613775096) | The server became healthy, then the HTTP client timed out after about five minutes without a model response. |
| [38616024322](https://github.com/miztiik/yen-idhazh/actions/runs/38616024322) | The server became healthy and inference began, then the run was cancelled after about 188 minutes with no reply. |

## What this page settles

- The PTQ1_0 packing loaded on a GitHub runner with the PrismML runtime.
- One inference request did not return a usable reply before the run ended.
- The model is not suitable for the repository's current nightly summarization
  workflow without further runtime work and a matched throughput measurement.
- The model remains parked instead of being configured or adopted.

## What this page does not settle

- Summary faithfulness, length, reasoning leakage, schema validity or human
  preference.
- Throughput relative to the incumbent or any other model.
- Memory peaks or a complete runner budget.
- Whether another packing, runtime or hardware class performs differently.
- Whether this model family should be adopted in the future.

Future investigation can reopen the question, but it needs a bounded production
shape and a paired or fixed corpus before a summary-quality decision is meaningful.

## Records behind this page

| Record | Use |
| --- | --- |
| GitHub run [38616024322](https://github.com/miztiik/yen-idhazh/actions/runs/38616024322) | The run that loaded the server and waited for inference. |
| GitHub artifact `llama-server-log` from run 38616024322 | The server log artifact for the run. |

## See also

- [../pipeline-cost.md](../pipeline-cost.md) - the runner and throughput readings that this probe does not replace.
