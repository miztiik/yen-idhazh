"""Which day files does a task take when it also takes from a folder it only reads?

A real defect, written down: the task walks its own folder and a neighbour's
that its declaration names under `reads`, which lists the neighbour's files for
it and lets it open them, and never lets it delete there. The runner's
ownership check exists to stop that before anything is staged.
"""

from fixture_day_files import day_files

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION

#: The neighbour's folder this task may read and has no business taking from.
NEIGHBOUR = "state/neighbour"


def run(context: TaskContext) -> Pass:
    return day_files(context, (*(context.owned_folders), NEIGHBOUR))
