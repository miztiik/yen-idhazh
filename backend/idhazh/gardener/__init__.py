"""Which module answers which of the gardener's questions?

The gardener is the one program that deletes and rewrites what this repository
keeps. It runs tasks, each declared by one file under `config/gardener/`, splits
a wake's tasks into shards, and lands one record per shard on main.

- `cli` routes `idhazh gardener <subcommand>` and holds nothing else.
- `registry` finds which module runs each task, by name, in `tasks/`.
- `shards` splits a wake's active tasks into shards, the same way the plan job does.
- `schedule` says whether a UTC day is old enough to act on at an instant.
- `runner` runs one shard or one task, checks what each task touched, and writes the record.
- `publish` lands a shard's one commit on main, however many shards race it.
- `context` is what a task is handed; `report` turns what a pass did into its row.
- `one_at_a_time` deletes a collection's members one at a time, under a ceiling.
- `github_collections` lists and deletes what GitHub holds for this repository.

A second driver of `one_at_a_time` lives in `idhazh.telemetry.prune`, because its
question is an operator's ("which ledger, and which days?") and it belongs beside
the command an operator types.
"""
