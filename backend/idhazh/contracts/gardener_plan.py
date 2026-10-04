"""Which shard runs which gardener tasks at a wake?

The gardener's plan job writes this and the matrix reads it. It crosses a
process boundary - one job's output, the next job's input - so its shape is
declared once here, and both of its writers are held to it: the typed planner
in `idhazh.gardener.shards` and the standard-library script
`backend/utilities/gardener_shards.py`, which the plan job runs before anything
of ours is installed.

**It names tasks and no folders.** A shard checks out only its code and
config, and lists the files under the folders its tasks own or read from the
commit it checked out, so nothing about folders crosses the boundary.

**An empty wake is a shape, not an absence.** With no task for the matrix,
`shards` is empty, `shard_count` is 0 and the matrix includes nothing, so a
workflow reads the same keys on every wake.
"""

from __future__ import annotations

from typing import Self

from pydantic import Field, field_validator, model_validator

from idhazh.contracts.base import Model, Slug


class ShardPlan(Model):
    """One shard: its place in the matrix and the tasks it runs."""

    index: int = Field(ge=0, description="Which shard, counted from 0.")
    task_names: tuple[Slug, ...] = Field(
        min_length=1, description="The tasks this shard runs, in sorted order. Never none."
    )


class MatrixLeg(Model):
    """One entry of the matrix: the shard a job runs, and the tasks its job's name lists."""

    shard: int = Field(ge=0, description="Which shard this job runs.")
    task_names: tuple[Slug, ...] = Field(
        min_length=1,
        description=(
            "The tasks this shard runs, in sorted order. Never none. The job's name lists "
            "them, so a run's page shows what every shard ran without opening a job."
        ),
    )

    @field_validator("task_names")
    @classmethod
    def _in_sorted_order(cls, names: tuple[str, ...]) -> tuple[str, ...]:
        """One deal always gives one job name, so the names are in sorted order."""
        if list(names) != sorted(names):
            raise ValueError("a leg lists its task_names in sorted order")
        return names


class Matrix(Model):
    """What a workflow's `strategy.matrix` reads: one leg per shard."""

    include: tuple[MatrixLeg, ...] = Field(description="One leg per shard, in shard order.")


class GardenerPlan(Model):
    """One wake's split of the active tasks into shards, and the matrix that runs them."""

    any_active_task: bool = Field(
        description=(
            "Whether the matrix has anything to run: true when at least one active task "
            "is one the matrix runs. The history task runs in a job of its own and is "
            "never counted here."
        )
    )
    shard_count: int = Field(ge=0, description="How many shards this wake runs. 0 is none.")
    shards: tuple[ShardPlan, ...] = Field(description="Every shard, in index order.")
    matrix: Matrix = Field(description="The same shards, in the shape a matrix reads.")

    @model_validator(mode="after")
    def _one_split_said_three_ways(self) -> Self:
        """The count, the shards and the matrix are one answer, so they must agree."""
        if self.shard_count != len(self.shards):
            raise ValueError(
                f"shard_count is {self.shard_count} and {len(self.shards)} shards are listed"
            )
        if self.any_active_task != bool(self.shards):
            raise ValueError(
                "any_active_task says whether the matrix has anything to run, so it is true "
                "exactly when a shard is listed"
            )
        if [shard.index for shard in self.shards] != list(range(len(self.shards))):
            raise ValueError("shards are numbered from 0 in order, with no gap")
        if [leg.shard for leg in self.matrix.include] != [shard.index for shard in self.shards]:
            raise ValueError("the matrix has one leg per shard, in shard order")
        if [leg.task_names for leg in self.matrix.include] != [s.task_names for s in self.shards]:
            raise ValueError(
                "each leg names the tasks its shard runs and no others, so a job's name "
                "says what that job ran"
            )
        named = [name for shard in self.shards for name in shard.task_names]
        if len(named) != len(set(named)):
            raise ValueError("a task runs in one shard of a wake, never two")
        return self
