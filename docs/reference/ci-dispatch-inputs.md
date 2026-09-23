# Dispatch inputs

**Last Updated**: 2026-09-22

What shape a `workflow_dispatch` input has to have, which shapes exist, and what
checks each one. One of them decides a published address, which is why the list
is closed rather than open. The workflows that take these inputs are in
[github-actions.md](github-actions.md).

## Every dispatch input has a shape, and one of them decides a published address

A `workflow_dispatch` form is free text unless somebody constrained it. Seven
workflows declare 23 inputs between them. Until 2026-08-27 one of those was
constrained by nothing at all, and it was the one that decides where a day is
published.

**`digest.yml`'s `date` is the expensive one.** It becomes the day's directory,
five artifact paths, two commit messages and six `--date` arguments.
`2026-8-27`, `2026/08/27`, `2026-13-45` and a trailing space all read as a date
to a person, and none of them fails anywhere in the run: every stage takes the
string, the commit lands, and the day is published to an address the site never
looks at. A run takes 164-184 minutes, so one keystroke costs a digest nobody
sees for about three hours.

**This is a correctness boundary, not a privilege boundary.** `digest.yml`
carries `permissions: contents: write`, and only a dispatch reaches the form, so
whoever fills it in can already commit to `main` by hand. The pattern is worth
having because the mistake is silent, not because the person is untrusted.

The check runs where the value first becomes a fact - the `decide` step of the
`plan` job - and it runs **after** the empty-string default resolves. That is
what makes the scheduled path the case the pattern is proved against rather than
the case nobody ever ran it on: a schedule passes no inputs, `date -u +%F`
writes `2026-08-27`, and the same pattern accepts it. The month and the day are
bounded as well as counted, because `2026-13-45` publishes exactly as well as a
real day does.

The value arrives as `DISPATCH_DATE` in the step's `env` rather than pasted into
the script. A pasted value is text before it is a value, so a pattern written
under the paste is reading a script the input has already edited.

### Three shapes, and a closed list

Every one of the 23 inputs is one of three things, and a contract test finds
them by reading the workflow files rather than by consulting a list - so a new
input fails the test until somebody says which one it is and the test finds the
evidence in the file.

| Shape | What it means | Count |
| --- | --- | --- |
| Enumerated | `type: choice` with an option list, or `type: boolean`. GitHub renders a menu or a checkbox and no other value can be submitted. | 7 |
| Read by name | The value never lands in a script. It reaches a step as an environment variable, and the program that reads it decides what it means. | 8 |
| Matched | The workflow matches the value against an anchored pattern before anything acts on it. | 10 |

The named inputs:

- **Enumerated** - `backfill.commit`, `digest.faithfulness`, `digest.shards`,
 `measure.target`, `measure.runtime_candidate`, `measure.model_speed_case`,
 `prune.force`.
- **Read by name** - `measure.runtime_repeats`, `measure.runtime_threads`,
 `measure.runtime_threads_batch`, `measure.runtime_corpus_items`,
 `measure.runtime_corpus_offset`, and
 `candidate_models_file` on
 `measure.yml`, `validate.yml` and `idhazh-pipeline-tests.yaml`. That one
 becomes a file path, so the step resolves it and proves it sits inside
 `config/` rather than matching its spelling, then asserts every field it
 republishes is one bare word.
- **Matched** - `digest.date`, `drift.recent_days`, `drift.baseline_days`,
 `measure.corpus_links`, `measure.threads`, `measure.budget_samples`,
 `validate.shards`, `validate.corpus_per_shard`,
 `validate.job_budget_minutes`.

**`candidate_models_file` is the same field on all three, and that is the point.**
Every fact about a candidate - the repository, the commit, the filename, the
digest, the byte count, the alias, the quantisation - is already written in
`config/models/<name>.json`. A form that asked for them again would let one
workflow measure one set of bytes while another pointed at a different set, with
every gate green. Empty means the configured model on all three, so a dispatch
that types nothing runs what the committed config already names.

`validate.yml` shapes its four numbers in one step of the `plan` job, which is
the job every other job needs, so "before its first use" is anywhere after that
step - the qualify matrix, the job bound and the gate all read them later. The
byte check reads the size the candidate's own entry declares, not a number the
form carried.

`drift.yml` was the other one worth fixing. Its two window sizes were pasted
into a Python program inside the step, so a value that is not a number was a
value the program was built from. They now arrive through `env` and the program
reads them with `os.environ`. That step also gained the `set -euo pipefail`
every other step in the repository starts with, so a crash inside the comparison
now turns the step red instead of passing through `tee` as a success and
skipping the issue step on `if: success`.

### Nothing lints a `run:` body

`ruff` and `mypy` stop at Python, and no linter reads the shell a workflow
writes inline: a `run:` body is a string inside YAML, not a file. The tool that
can read one is `actionlint`, a Go binary this repository does not fetch. The
inline shell is held by the contract tests in `backend/tests/workflows/`
instead, which execute the real steps rather than grep them.

CI ran `shellcheck` over `.github/scripts/*.sh` in the gates job until
2026-09-23. That directory is gone, and the linter, the `shellcheck-py` dev
dependency and a glob with nothing left to read went with it
([repository-layout.md](repository-layout.md)).

## See also

- [github-actions.md](github-actions.md) - which workflows take these inputs, and when each runs.
- [ci-model-runtime.md](ci-model-runtime.md) - the model ref a dispatch input may name, and where the production one is written.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - the linter and the contract tests that hold these shapes.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #11 on why an input that reaches a URL is a closed list.
