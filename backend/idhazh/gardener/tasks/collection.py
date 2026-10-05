"""Which members of a collection GitHub holds for this repository has the window aged out?

One module serves every `collection` declaration. The declaration names its
collection in `collection`, a closed word, and the loader refuses a declaration
not named for it, so one collection has one task and one window. What a member
is, and how one is listed or deleted, is `idhazh.gardener.github_collections`;
the window, the ceiling and the resume point are `one_at_a_time.take`'s; where
the task's last walk stopped is `idhazh.gardener.collection_mark`'s. This
module only joins them.

**Both collections are walked from the task's own mark.** The mark is the day
its last pass with the same `dry_run` handled through. With no such pass in
reach, GitHub's own answers say where a first walk starts. The runs are walked
a UTC day at a time; the artifacts from the oldest end, a page at a time.

**Nothing a pass takes is in the repository.** It takes GitHub ids, so the
runner holds a collection task to what it wrote, and it writes nothing: the
record row is all a pass leaves in the tree, on a dry run and a live one alike.

The transport is built from the run's environment - the repository Actions
names and the token it hands the step - inside `github_collections`, so this
module reads no environment, and a test hands in a recorded one instead. The
HTTP client is imported inside `run`, because discovery imports every task
module in every shard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

if TYPE_CHECKING:
    from idhazh.gardener.github_collections import Api

KIND = TaskKind.COLLECTION


def run(context: TaskContext, *, api: Api | None = None) -> Pass:
    """Take up to the ceiling of members older than the window, from the task's own mark."""
    from idhazh.contracts.knobs.gardener import CollectionTaskPolicy, PrunableCollection
    from idhazh.gardener import collection_mark, github_collections
    from idhazh.gardener.one_at_a_time import Window, take

    policy = context.policy
    if not isinstance(policy, CollectionTaskPolicy):
        raise ValueError(f"the collection task was handed a {policy.kind} declaration")
    transport = api if api is not None else github_collections.api_of_this_repository()
    window = Window.older_than(today=context.today.isoformat(), days=policy.window.value)
    line = window.until
    if line is None:
        raise ValueError("an age window ends on a day, and this one names none")
    kept = collection_mark.last_mark(context, policy)
    match policy.collection:
        case PrunableCollection.WORKFLOW_ARTIFACTS:
            mark = kept or github_collections.first_artifacts_mark(transport, line=line)
            collection = github_collections.artifacts(transport, through=line)
        case PrunableCollection.WORKFLOW_RUNS:
            mark = kept or github_collections.first_runs_mark(transport, line=line)
            collection = github_collections.runs(transport, after=mark, through=line)
        case _:
            assert_never(policy.collection)
    return take(
        collection,
        window=window,
        ceiling=policy.max_deletes_per_run,
        dry_run=policy.dry_run,
        mark=mark,
    )
