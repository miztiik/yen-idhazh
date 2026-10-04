"""Which members of a collection GitHub holds for this repository has the window aged out?

One module serves every `collection` declaration. The declaration names its
collection in `collection`, a closed word, and the loader refuses a declaration
not named for it, so one collection has one task and one window. What a member
is, and how one is listed or deleted, is `idhazh.gardener.github_collections`;
the window, the ceiling and the resume point are `one_at_a_time.take`'s. This
module only joins the two.

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
    """Take up to the ceiling of members older than the window, in the order GitHub lists them."""
    from idhazh.contracts.knobs.gardener import CollectionTaskPolicy, PrunableCollection
    from idhazh.gardener import github_collections
    from idhazh.gardener.one_at_a_time import Window, take

    policy = context.policy
    if not isinstance(policy, CollectionTaskPolicy):
        raise ValueError(f"the collection task was handed a {policy.kind} declaration")
    transport = api if api is not None else github_collections.api_of_this_repository()
    match policy.collection:
        case PrunableCollection.WORKFLOW_ARTIFACTS:
            collection = github_collections.artifacts(transport)
        case PrunableCollection.WORKFLOW_RUNS:
            collection = github_collections.runs(transport)
        case _:
            assert_never(policy.collection)
    return take(
        collection,
        window=Window.older_than(today=context.today.isoformat(), days=policy.window.value),
        ceiling=policy.max_deletes_per_run,
        dry_run=policy.dry_run,
    )
