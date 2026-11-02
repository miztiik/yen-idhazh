# How the local HHEM API owns scoring

**Last Updated**: 2026-11-02

How the standalone service scores supplied source and summary text without
blocking health checks or leaving a second model process behind.
The [API reference](../../reference/hhem-evaluation-api.md) owns its fields,
limits and error codes. This service does not change pipeline evaluation,
publish data, collect resources or retain completed results.

## Admission and deadlines

One HTTP process owns one scoring process. FastAPI's lifespan starts loading
in the background and owns shutdown. Health reports the observed loading,
ready, replacing, stopping or failed state without waiting for prediction.
The listener accepts its configured loopback host only. Browser origins,
duplicate or unexpected Host headers, redirects and raw access logs are not
accepted.

A request reserves waiting capacity before reading input. Reading bodies and
validated waiting requests share that finite capacity; the active evaluation
is separate. Body size and the absolute input-read deadline apply to streamed
input too, including input without Content-Length. Invalid UTF-8, media,
JSON and controls produce only the declared safe errors.

Both window plans are checked before scoring admission. Validated requests
enter in validation-completion order. The waiting deadline starts at the
reservation and is not reset when a model is replaced. Queue-wait timing
includes the reservation's input-read and validation time.

Promotion releases the waiting slot and starts one evaluation deadline for
all primary and full comparisons. A failure waits only for bounded stop and
exit confirmation. Replacement loading runs separately, so a failed caller
does not wait for another model to load. Waiting requests keep their original
identities and deadlines while health reports replacing.

## Windows and completed scores

The service splits words on whitespace. A source no longer than the configured
window is passed unchanged. Longer sources use full-size word ranges joined
with spaces, stepping by size minus overlap. If the last regular range does
not reach the end, one full-size range is anchored at the end. There is no
short tail, truncation or dropped window. The completed score is the largest
valid score across every planned window.

Primary scoring finishes before full scoring starts. Full scoring needs an
explicit full source when enabled. Exactly equal source strings reuse the
completed primary score and logical full plan without another prediction;
different whitespace is not equality.

Each child reply identifies its execution, generation, comparison and word
range. The parent validates that identity against its one outstanding command
and retains each valid completed window. A comparison receives a score only
after all its windows finish. Thus an unfinished primary comparison has no
score, while a failed full comparison preserves the exact completed primary
maximum. Partial responses use an error HTTP status and leave unfinished full
and delta scores null.

## Model loading and identity

The production loader downloads only the named files at the committed full
revision IDs. It supplies the foundation's local tokenizer and configuration
directory through the official model configuration, then calls the official
model loader and `predict` on CPU with the original floating-point weights.
The foundation provides no second set of model weights. Prediction and
replacement loads use local files; a replacement cannot download assets.

Loaded tensor names, dtypes, shapes and bytes are hashed in sorted-name order.
A separate digest covers the actual configuration, effective prompt and named
configuration, tokenizer and model-code assets. Local snapshot paths become
immutable logical identities before hashing. The effective service settings
have their own digest. Replacement must match the initial loaded identity,
not merely its configured label or revision.

The application does not set CPU affinity, quotas, memory limits or fixed
compute thread counts. One active model process limits concurrency, not the
host resources the runtime may use.

## Cancellation and shutdown

Commands and replies use bounded JSON bytes over owned multiprocessing pipes,
not pickled request objects. Blocking pipe and process operations run off the
HTTP event loop. The parent owns startup, read and recovery tasks, including
work interrupted during process creation.

A queued cancellation removes only that reservation. Active cancellation,
deadline expiry or worker failure closes the exact worker's lifetime pipe,
joins its exit, and escalates to killing that owned process if required.
Only confirmed exit permits another model to start. An unconfirmed exit or
changed replacement identity leaves the service unavailable.

The child's independent lifetime watcher exits the process when its parent
disappears, even if prediction never returns. On Linux, a kernel parent-death
signal also stops native prediction that holds Python's execution lock.
Neither mechanism depends on the next command read, a daemon flag or
cancellation of a thread future.

Shutdown closes admission, cancels owned requests and loading, and awaits
owned recovery and stop operations within its declared deadline. A client
disconnect produces one cancellation event and no HTTP status or body.
Connected cleanup failures preserve the first error and any completed primary
score. Request text is released at delivery; no result cache or history exists.

## Private diagnostics and recordings

Only the private scoring command carries text. Public outcomes, health and
events use native closed contracts. Validation projection removes raw input,
unknown property names and exception messages. Child diagnostics and model
progress are discarded rather than forwarded.

The parent writes bounded JSONL events through standard-library logging to
stderr. Event sequence and causal links are parent-owned. Essential events
use the configured severity; failures use at least ERROR. A write, flush or
event-size failure is explicit: an affected response has `LOGGING_FAILED`,
an error status and no claimed terminal-event link.

The capture script runs the production loader and predictor on the named
project-authored inputs. Captured predictions bind exact source/summary hashes
to the actual model identity. Ordinary tests replace only that model-call
boundary with those recordings. They still run the real ASGI lifespan,
controller, reduction, JSON pipes, process termination and parent-loss watcher.
They prove composition and retention, not model accuracy or runner speed.

## Design rationale

An owned process is the cancellation boundary because a blocked native model
call cannot be reliably stopped by cancelling a thread future. Per-window
validated progress keeps a completed primary score outside that process.
Finite reservations bound input memory before validation, rather than only
bounding requests after their bodies have already been read.

## See also

- [../../reference/hhem-evaluation-api.md](../../reference/hhem-evaluation-api.md) - native fields, settings and response policy.
- [../../how-to/run-the-gates.md#independent-python-service-contracts](../../how-to/run-the-gates.md#independent-python-service-contracts) - offline and real-model checks.
- [../contracts/identity.md#6-hhem-execution-and-event-identity](../contracts/identity.md#6-hhem-execution-and-event-identity) - execution and event identities.
