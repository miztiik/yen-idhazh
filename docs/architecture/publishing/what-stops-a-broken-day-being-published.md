# What stops a broken day being published

**Last Updated**: 2026-09-27

One verb decides whether a day may be committed: `python -m idhazh
check-publication`. It is a framework rather than a function - every rule is a
plugin found on disk, so adding a rule is adding a file. This page holds what a
rule is, what the runner guarantees before any rule sees a day, the four ways
the wiring can be wrong and what each one says, and what it costs to run.

Which workflow runs it and when is
[github-actions.md](../../reference/github-actions.md). How to run it yourself
is [run-the-gates.md](../../how-to/run-the-gates.md). Why the gate exists at all
- the reading routes split and the build stopped opening every story - is
[frontend.md](frontend.md).

## A check is a name, a scope, and a function

A check is one `Check` declared at the top level of its own module under
`backend/idhazh/publication_checks/checks/`:

```python
CHECK = Check(name="pictures", scope=CheckScope.DAY, run=_run)
```

Four fields, and only the first three are ever set today.

| Field | What it says |
| --- | --- |
| `name` | What the check is called. Two modules claiming one name is refused. |
| `scope` | Which of the two contexts `run` is handed. |
| `run` | A function taking that context and returning a `CheckResult`. |
| `ledger` | Where to file rows, when a check measures rather than only judges. `None` on every rule shipped today. |

`scope` is what pairs a check with its context, so `run` is typed on whichever
one it wants and nothing has to narrow a type at runtime.

- **`CheckScope.DAY`** is handed a `DayContext`: the digest root, the public
  root above it, and every committed day in scope. Each day arrives as a
  `CommittedDay` carrying its date, its path, its bytes, the JSON object and
  the validated `DigestDay` - or `None` for that last one when the object
  failed the contract, which the runner has already reported.
- **`CheckScope.TREE`** is handed a `TreeContext`: the digest root and the set
  of months this run touched, or `None` meaning every month on disk. It is for
  a payload that is not a day - the console's own month shards are the only one
  today.

A `CheckResult` carries `faults` and `rows`. A fault is a sentence an operator
reads in the workflow log; one fault anywhere makes the verb exit 1 and the
commit does not happen. **A DAY check writes the date into its own fault**,
because the runner logs every fault the same way and a sentence naming no day
says nothing on a tree of four hundred.

## The runner reads each day once, and that read is the guarantee

Before any check runs, `run_publication_checks` opens every day in scope
exactly once and parses it through `DigestDay`. That parse is not a
convenience. It is the one guarantee no producer can give itself: the day is
read back by the gate rather than by the stage that wrote it, so a producer
that quietly stopped matching its own contract is caught by a different reader.
Two stages write a committed day and only one of them checks what it wrote:
`assemble.py` builds the day through the model, and `backfill_vectors.py`
rewrites it with `model_copy(update=...)`, which copies the fields across
without re-checking them. That second writer is why the guarantee has to be a
read.

Four things can go wrong before a rule looks at a day, and each names which:
the file will not read, the bytes are not JSON, the JSON is not an object, or
the object fails `digest-day.schema.json`. The first three end that day; the
fourth does not, because the JSON object is still there and the projection
check can still say whether a reader's browser would refuse it too. Reporting
both in one run is the difference between one fix and two.

## The four checks shipped today

| Check | Scope | What it refuses |
| --- | --- | --- |
| `projection` | day | A day the served contract refuses, or one that cannot be projected at all. The build never opens the stories past a document's seed; a reader's browser does. |
| `pictures` | day | A payload and its picture directory that disagree - two stories on one file, a named file that is not there, a file no story claims. |
| `planned-items-reconciliation` | day | A day that planned stories, published none and failed none. Nothing can write that day honestly, and it looks exactly like a quiet day. |
| `console` | tree | A console month shard, or the band file, that its own reader refuses. |

Each module's own docstring carries the defect it exists for. None of them
declares a ledger: what a day planned against what it published is already a
column of `day_metrics`, and a second record of the same arithmetic is a second
number to keep in step.

## Adding a check

Write a module under `checks/` that declares `CHECK`. There is no list to join
and no import to add - `discover()` walks the package. Give the module's first
sentence the question it answers, date every fault if the scope is `DAY`, and
add the check to the tuple in
`backend/tests/pipeline/test_publication_registry.py`, which is what makes an
accidental file or a deleted rule fail loudly.

## The four ways the wiring can be wrong

A mis-wired gate is worse than a failing one: it passes. So discovery refuses
rather than logs, and the verb exits **2** - a code an operator can tell from
the **1** that means a day is broken.

| The fault | What it says |
| --- | --- |
| A check module raises on import | The import error itself, unchanged. A rule that will not load must not be skipped. |
| A module declares no `CHECK`/`CHECKS` | `<module> declares no CHECK/CHECKS of type Check`. A file that looks like a rule and declares none is a typo. |
| Two modules declare one name | `two modules declare check 'x': <a> and <b>`. Silently, the second would replace the first and run alone. |
| A check names a ledger with no tree shape | `<check> names ledger <name> with no tree-shape entry`. The write would otherwise fail after the gate had already passed the day. |

## Filing rows, and when a check does not

A check that declares a ledger has its rows written through `write_segment`
into that ledger's day tree - but only when the run names the days it is
checking and has a state directory to write into. **A sweep over the whole
archive files nothing.** A sweep is a re-reading of days already measured, so
filing its rows would add a row per day per contract change: the same run that
finds nothing wrong would grow the ledger it writes into.

A run that would file rows and has no `--run-id` refuses, because a row nothing
can attribute is worse than no row at all.

## What it costs

`digest.yml` names the one day the run wrote and parses one day. `ci.yml` and
`backfill.yml` sweep the whole committed tree, and that sweep grows one day a
day: no prune deletes a `digest.json`, and a contract change can invalidate any
frozen day, so a bounded input would answer the question for only some of them.

Measured 2026-09-08 on a developer machine: 18 committed days, 19.87 MB, 0.45 s
- about 44 MB/s. At the 727-day horizon the 1 GB Pages cap sets, that is roughly
645 MB, which reads in about 15 s on a laptop and 30-60 s on the 4-vCPU runner,
against a 6 h job. The read violates the fixed-size input rule in
[../../../CLAUDE.md](../../../CLAUDE.md) Guardrail #12.

## Design rationale

**2026-09-27: one stage became a discovered package.** The four rules lived in
one 300-line module, three of them as private functions two test files reached
into. Splitting them made each rule a file with its own first sentence, and
made the registry the thing that can be tested - a rule silently not running
was previously unobservable.

**The standalone day-shape check was dropped rather than moved.** The runner
parses every day through `DigestDay` before any check sees it, so a separate
check asking the same question would have asked it twice.

**Discovery follows `idhazh.council.registry`.** The council finds judges the
same way and for the same reason, so there is one pattern in this repository
for "a plugin the code does not name".

**The `ledger` hook ships live with no production consumer.** It is four lines
in the runner and one integration test. A hook declared and never exercised is
a hook that stops working silently; shipping it live means the first check that
needs to persist a measurement adds a field rather than a subsystem.

## See also

- [frontend.md](frontend.md) - why a broken day can no longer be caught by building.
- [../../../CLAUDE.md](../../../CLAUDE.md) Guardrail #12 - every read must have a fixed-size input.
- [run-the-gates.md](../../how-to/run-the-gates.md) - running the verb yourself.
- [github-actions.md](../../reference/github-actions.md) - which job runs it, and where in the order.
