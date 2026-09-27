"""Which day files does a task take when it also lists a folder it was never given?

A real defect, written down: the task walks its own folder and a neighbour's,
which is what the runner's ownership check exists to stop before anything is
staged.
"""

from fixture_day_files import day_files

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION

#: The neighbour's folder this task has no business listing.
NEIGHBOUR = "state/neighbour"


def run(context: TaskContext) -> Pass:
    return day_files(context, (*(context.policy.owns or ()), NEIGHBOUR))
