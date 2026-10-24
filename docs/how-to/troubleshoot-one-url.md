# Troubleshoot a Pipeline Item

**Last Updated**: 2026-10-04

Use CI records to inspect an item that the pipeline already processed; the
project does not support local model inference or arbitrary-URL runs.

## Inspect a production run

1. Find the run that processed the item:

   ```powershell
   gh run list --repo miztiik/yen-idhazh --workflow digest.yml
   ```

2. Use the run's `captures-<shard>` artifacts to inspect model prompts, replies
   and timings. Follow
   [How to analyze a pipeline artifact](analyze-a-pipeline-artifact.md).

3. If the run has no captures, inspect its workflow logs and the capture
   settings for that run. Captures are not guaranteed when both prompt and reply
   capture settings are off.

The item-health ledger records the stage, outcome, failure code and timings for
each planned item. See
[item health](../architecture/sources/item-health.md) for its fields and
[pipeline artifacts](analyze-a-pipeline-artifact.md) for the detailed model
request record.

## Test the production path

The [Pipeline tests workflow](../reference/github-actions.md#pipeline-tests)
runs the real production stages against the article cases in
`config/pipeline-tests.json`. Its configured articles are the test inputs; it
does not accept an arbitrary URL.

There is no `work --url` command or supported way to create a scratch plan for a
URL. Do not invent source metadata or create a local model server to work around
that boundary. Add a first-class CI capability only through a separate,
reviewed change with its own contract and tests.

## Read a summary failure code

The item-health ledger records the stage, outcome and failure code. Use that
code to focus review of the run's workflow logs and captured artifact:

| Summary `model_unreachable` | The configured model service did not answer. Check its startup and workflow logs. |
| Summary `model_refused` | The model service returned an error. Check the request and service logs. |
| Summary `model_timed_out` | The model service did not finish before its configured request limit. |
| Summary `shard_out_of_time` | The worker reached its configured time limit before starting this item. |
| Summary `context_exceeded` | The prompt and reply allowance did not fit the model context limit. |
| Summary `output_truncated` | The model reply ended before it formed a complete summary. |
| Summary `labels_truncated` | The labelling reply ended early, so the summary call did not run. |
| Summary `bad_shape` | The model reply did not match the required summary shape. |
| Summary `length_out_of_range` | The reply was below the minimum length for this source. |
| Summary `copied_source` | The reply repeated too much text from the article. |
| Summary `leaked_address` | The reply contained an address; the item uses its source headline instead. |

## See also

- [run-the-pipeline.md](run-the-pipeline.md) - what the production stages do and where they run.
- [../reference/github-actions.md](../reference/github-actions.md) - workflow roles and triggers.
- [../../CLAUDE.md](../../CLAUDE.md) - fetched text and operator-controlled model destinations.
