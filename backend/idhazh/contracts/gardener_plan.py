"""Which shard runs which gardener tasks at a wake, and which folders does each check out?

The gardener's plan job writes this and the matrix reads it. It crosses a
process boundary - one job's output, the next job's input - so its shape is
declared once here, and both of its writers are held to it: the typed planner
in `idhazh.gardener.shards` and the standard-library script
`backend/utilities/gardener_shards.py`, which the plan job runs before anything
of ours is installed.

**A cone is one string where it crosses the boundary.** `actions/checkout`
takes its sparse folders as a newline-separated input, so a shard's cone
travels as one string, joined and split by the two functions below and by no
other code. In Python it is a tuple of folders.

**An empty wake is a shape, not an absence.** With no task for the matrix,
`shards` is empty, `shard_count` is 0 and the matrix includes nothing, so a
workflow reads the same keys on every wake.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Final, Self

from pydantic import Field, field_serializer, field_validator, model_validator

from idhazh.contracts.base import Model, RelPath, Slug

#: What separates two folders in a cone as it crosses the process boundary.
CONE_SEPARATOR: Final = "\n"


def join_cone(folders: Iterable[str]) -> str:
    """A shard's folders as the one string a checkout step reads."""
    return CONE_SEPARATOR.join(folders)


def split_cone(text: str) -> tuple[str, ...]:
    """The string a checkout step reads, back into its folders. Empty is no folders."""
    return tuple(folder for folder in text.split(CONE_SEPARATOR) if folder)


class ShardPlan(Model):
    """One shard: its place in the matrix, the tasks it runs, and the folders it needs."""

    index: int = Field(ge=0, description="Which shard, counted from 0.")
    task_names: tuple[Slug, ...] = Field(
        min_length=1, description="The tasks this shard runs, in sorted order. Never none."
    )
    cone: tuple[RelPath, ...] = Field(
        description=(
            "The folders this shard checks out beside the code, sorted. A task that owns "
            "everything else under a root adds none: it reads what it needs from git."
        )
    )

    @field_validator("cone", mode="before")
    @classmethod
    def _split(cls, value: Any) -> Any:
        return split_cone(value) if isinstance(value, str) else value

    @field_serializer("cone")
    def _joined(self, cone: tuple[str, ...]) -> str:
        return join_cone(cone)


class MatrixLeg(Model):
    """One entry of the matrix: the shard a job runs and the cone it checks out."""

    shard: int = Field(ge=0, description="Which shard this job runs.")
    cone: tuple[RelPath, ...] = Field(description="The same folders as that shard's plan.")

    @field_validator("cone", mode="before")
    @classmethod
    def _split(cls, value: Any) -> Any:
        return split_cone(value) if isinstance(value, str) else value

    @field_serializer("cone")
    def _joined(self, cone: tuple[str, ...]) -> str:
        return join_cone(cone)


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
        legs = [(leg.shard, leg.cone) for leg in self.matrix.include]
        if legs != [(shard.index, shard.cone) for shard in self.shards]:
            raise ValueError("the matrix has one leg per shard, carrying that shard's cone")
        named = [name for shard in self.shards for name in shard.task_names]
        if len(named) != len(set(named)):
            raise ValueError("a task runs in one shard of a wake, never two")
        return self
