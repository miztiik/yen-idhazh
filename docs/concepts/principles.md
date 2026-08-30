# Principles

**Last Updated**: 2026-08-30

The small set of beliefs that shape every yen-idhazh decision, stated once as vocabulary. These operationalize the engineering contract for a build-time digest pipeline; the authoritative rules live in [../../CLAUDE.md](../../CLAUDE.md) and the rules-only digest in [../agents/guardrails.md](../agents/guardrails.md). This page explains the *why* a reader needs before those rules make sense - it does not restate them.

## 1. Static-first, or there is no project

What reaches a reader is a file that was committed hours earlier. No backend, no runtime inference, no accounts, no telemetry, no calls home. This is not asceticism: it is the only shape in which a one-person project keeps running for years without a bill, an on-call rota, or a breach. Every design question starts by asking what can be decided at build time, because build time is the only time there is.

## 2. The runner is the architecture

A stock 4 vCPU runner with no GPU, a 6 h job cap and a 10 GB cache is the machine. Which model can be used, how long an article may be, how work is divided and when a job is killed all fall out of that. When a feature does not fit, the feature is simplified - the budget is not raised. Treating the constraint as the platform rather than as an inconvenience is what keeps the design honest.

## 3. Measured, not estimated

An unmeasured number may not justify a design. Every throughput, cost, size and quality claim carries the hardware it came from, the date and the spread; a laptop figure is labelled a laptop figure. When a measurement contradicts the design, the design changes. This has already happened here, which is the point of measuring at all. The one exception is a counterfactual: the operator console prices a run at a rate the operator sets, to answer whether the self-hosted design is worth its wall clock, and it is labelled a counterfactual rather than a bill ([../../CLAUDE.md](../../CLAUDE.md) Rule #10).

## 4. Contracts before logic

Every persisted shape is a typed model before anything reads or writes it, and the schemas and frontend types are generated from those models rather than written twice. Stages then talk in validated payloads rather than function calls, so a boundary can be logged, replayed and tested from a real fixture. The shape of the data is the design; the code is an implementation detail of it.

## 5. Fetched text is data, never instruction

Every article is a stranger's web page. It crosses the trust boundary exactly once, at extraction, where it is sanitized - and after that it is content the system reasons *about*, never a message the system obeys. It does not enter a system prompt, and nothing derived from it becomes a shell argument, a file path, or a URL to fetch. The schema and the sanitizer are the control. A prompt politely asking a model to ignore instructions is a request, not a control, and the canary suite exists to prove the difference. The crossing itself is [../architecture/sources/trust-boundary.md](../architecture/sources/trust-boundary.md).

## 6. The evaluation is the product, not the report

A summarizer nobody measures produces confident, plausible, wrong text indefinitely and nobody notices, because every summary reads equally authoritative. So quality is measured on every item, the measurement is committed rather than recomputed, and it is designed knowing that a single faithfulness score rewards copying and cannot see what was omitted. The corollary is a rule that is easy to break by accident: **a metric used to choose an output can no longer detect that outputs are getting worse.** The selector and the alarm stay separate.

## 7. Degrade, do not fail

One unreachable source, one failed extraction, one visual that would not render - each degrades its own item, records why, and lets the run finish. Work items are independent by construction: one item is one file written temp-then-rename under a predictable path, so a failure never damages a sibling and a re-run costs only what did not finish. The digest ships even at zero successes, because a failure count that nobody sees is a failure nobody fixes.

## 8. Config-driven, with sane defaults

Source lists, caps, thresholds, model references and retry budgets live in `config/`, schema-validated, never in code. A fresh clone runs on the defaults. Tuning the system should never require reading it.

## 9. Logging is local by construction

There is no log sink, because there is nothing to send logs to. On a developer machine the backend writes structured records to stderr; in CI the same stream is what the Actions run retains, and that IS the log store; on the published page the browser console is the whole of it. A stage logs the same structured payload it emits, so a log line and a persisted file never disagree about what happened.

## 10. Publish the link, not the article

The pipeline stores and serves a URL and our own summary. The source text is fetched, used, and never committed. This is a copyright rule and a scope rule at once, and it is also why the link to the original is a first-class element of every item rather than a footnote.

## 11. Delete before you build, and build before you settle

One developer, weekends. Every kept line is rent paid forever. Before asking how to build something well, ask whether it should exist: name the consumer and name what concretely breaks without it. If neither is concrete, the honest answer is not to build it.

The second clause is not a softening, it is the other failure. **A surface nobody would choose to look at has not been simplified, it has been abandoned.** Deleting is free and building is not, so a project that only rewards the first ratchets one way until what is left is correct and unloved. When the answer is that the thing should exist, it is then owed the craft that makes it worth someone's attention - and "it works" is not that.

## Design rationale

These eleven are not new law - they are the concept-tier restatement of the Rules in the vocabulary a digest pipeline needs, so a contributor learns the *why* from the concept tier and the *rule* from the contract. The rejected alternative was to let each concept doc re-derive the ethos in passing; that duplicates the contract and drifts (Rule #4, one definition). Authority: Fowler ([../../.github/agents/fowler.agent.md](../../.github/agents/fowler.agent.md)).

## See also

- [vision.md](vision.md) - what the project is and is not.
- [pipeline-loop.md](pipeline-loop.md) - the stages these principles govern.
- [evaluation.md](evaluation.md) - principle 6 in concrete form.
- [config.md](config.md) - principle 8 in concrete form.
- [telemetry.md](telemetry.md) - principle 9 in concrete form.
- [../agents/guardrails.md](../agents/guardrails.md) - the rules-only digest.
- [../../CLAUDE.md](../../CLAUDE.md) - the authoritative contract.
