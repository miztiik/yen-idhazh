# Dispatch inputs

**Last Updated**: 2026-10-14

What shape a `workflow_dispatch` input has to have, which shapes exist, and what
checks each one. One of them decides a published address, which is why the list
is closed rather than open. The workflows that take these inputs are in
[github-actions.md](github-actions.md).

## Every dispatch input has a shape, and one of them decides a published address

A `workflow_dispatch` form is free text unless somebody constrained it. Eight
workflows declare 27 inputs between them. Until 2026-08-27 one of those was
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

The workflow checks the value where it first becomes a fact - the `decide`
step of the `plan` job - and **after** the empty-string default resolves. A
schedule passes no inputs, `date -u +%F` writes `2026-08-27`, and the same
pattern accepts it. The month and the day are bounded as well as counted,
because `2026-13-45` publishes exactly as well as a real day does.

The value arrives as `DISPATCH_DATE` in the step's `env` rather than pasted into
the script. A pasted value is text before it is a value, so a pattern written
under the paste is reading a script the input has already edited.

### Three shapes, and a closed list

Every one of the 27 inputs is one of three things. This is a maintained
documentation inventory; tests do not read workflow files to discover or verify
these declarations.

| Shape | What it means | Count |
| --- | --- | --- |
| Enumerated | `type: choice` with an option list, or `type: boolean`. GitHub renders a menu or a checkbox and no other value can be submitted. | 7 |
| Read by name | The value never lands in a script. It reaches a step as an environment variable, and the program that reads it decides what it means. | 9 |
| Matched | The workflow matches the value against an anchored pattern before anything acts on it. | 11 |

The named inputs:

- **Enumerated** - `backfill.commit`,
 `digest.faithfulness`, `digest.shards`,
 `idhazh-gardener.force`.
- **Read by name** - `backfill.days`, `candidate_models_file` on
 `idhazh-pipeline-tests.yaml`. That value becomes a
 file path, so the step resolves it and proves it sits inside `config/` rather
 than matching its spelling, then asserts every field it republishes is one
 bare word.
- **Matched** - `digest.date`, `digest.article_limit`, `llm-council.date`,
 `drift.recent_days`, `drift.baseline_days`.

**`digest.article_limit` makes a short test run of the full pipeline.** Blank,
which is what every scheduled run passes, plans the full day exactly as before.
A whole number of at least 1 lowers the run's crash guard,
`run.safety_ceiling_per_run`, to that number, so the planner keeps the
highest-ranked stories across every vertical and never more than the guard
allows. It does not choose the number of work shards: `digest.shards` still
does. The `Plan the day` step matches the value against `^[1-9][0-9]*$` and
passes it to `idhazh plan --article-limit`. The stories it does plan are
published like any other run's, so a test run on today's date adds to today's
digest.

**`candidate_models_file` selects a model configuration for pipeline tests.**
The repository, commit, filename, digest, byte count, alias and quantisation
come from that file under `config/models/`; the workflow validates its path and
does not accept copied model fields.

`drift.yml` was the other one worth fixing. Its two window sizes were pasted
into a Python program inside the step, so a value that is not a number was a
value the program was built from. They now arrive through `env` and the program
reads them with `os.environ`. That step also gained the `set -euo pipefail`
every other step in the repository starts with, so a crash inside the comparison
now turns the step red instead of passing through `tee` as a success and
skipping the issue step on `if: success`.

### Inline shell is not linted

`ruff` and `mypy` stop at Python, and no linter reads the shell a workflow
writes inline: a `run:` body is a string inside YAML, not a file. This
repository does not lint workflow files or execute their `run:` bodies in
tests. Hosted runs remain the place where GitHub executes those declarations.

CI ran `shellcheck` over `.github/scripts/*.sh` in the gates job until
2026-09-23. Removing the last shell file also removed `shellcheck`, its
`shellcheck-py` dev dependency and the empty glob. The directory now holds a
TypeScript helper, which is outside that shell check
([repository-layout.md](repository-layout.md)).

## See also

- [github-actions.md](github-actions.md) - which workflows take these inputs, and when each runs.
- [ci-model-runtime.md](ci-model-runtime.md) - the model ref a dispatch input may name, and where the production one is written.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - the checks that still run in CI.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #11 on why an input that reaches a URL is a closed list.
