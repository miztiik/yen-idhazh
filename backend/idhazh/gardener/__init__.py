"""Which module answers which of the gardener's questions?

The gardener is the one program that deletes and rewrites what this repository
keeps. It runs tasks, each declared by one file under `config/gardener/`, splits
a wake's tasks into shards, and lands one record per shard on main.

- `cli` routes `idhazh gardener <subcommand>` and holds nothing else.
- `registry` finds which module runs each task, by name, in `tasks/`.
- `shards` splits a wake's active tasks into shards, the same way the plan job does.
- `schedule` says whether a UTC day is old enough to act on at an instant.
- `runner` runs one shard or one task, checks what each task touched, and writes the record.
- `outcome` is what a shard comes to: its exit code and what that code means, the
  paths it hands on to land, and how each of its tasks ended.
- `context` is what a task is handed; `report` turns what a pass did into its row
  and its `task-finished` event.
- `event_log` writes each event a task or the runner logs as one line of JSON.
- `workflow_commands` names the commands GitHub reads beside an event: a group
  around each task's lines, an error for a task that failed, and a warning when
  nothing landed because main moved on.
- `run_summary` says what one shard did, as Markdown for its job's summary page.
- `one_at_a_time` deletes a collection's members one at a time, under a ceiling.
- `github_collections` lists and deletes what GitHub holds for this repository.
- `error_cause` says what an error a pass meets means: a member gone, one GitHub
  will not delete, an API that is down, a download budget spent, or a code defect.

Landing a shard's commit on main runs git, and nothing in this package starts a
process, so the commit loop is `backend/utilities/gardener_publish.py`.

A second driver of `one_at_a_time` lives in `idhazh.telemetry.prune`, because its
question is an operator's ("which ledger, and which days?") and it belongs beside
the command an operator types.
"""
