"""Where do the gardener's task modules live, and what does each one hold?

One module a task, or one a kind: `idhazh.gardener.registry` finds them here by
their file names and imports each in turn. A module holds exactly two names,
`KIND` - the `TaskKind` it serves - and `run`, which takes a `TaskContext` and
returns the `Pass` it made. It carries no task name of its own: a declaration
under `config/gardener/` names its module, and no module names itself.

**Nothing heavy loads at module scope.** A module here imports no columnar
engine, no database and no HTTP client until `run` is called, so finding every
task costs the same whatever the tasks go on to do.

This file imports none of them, so importing the package runs no task's code.
"""
