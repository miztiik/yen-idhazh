"""What one night at the council costs a runner, whatever judges it hosts."""

from __future__ import annotations

import keyword
from enum import UNIQUE, StrEnum, verify
from pathlib import Path

from pydantic import Field, PrivateAttr, field_validator

from idhazh.contracts.base import DateStamp, Model, Slug


@verify(UNIQUE)
class JudgeLifecycleStatus(StrEnum):
    """Whether the council runs a judge; its ledger families have their own status."""

    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class JudgeDeclaration(Model):
    """The two declaration keys the council reads from one judge's own file."""

    lifecycle_status: JudgeLifecycleStatus
    runs_model: bool = Field(strict=True)


def derive_judge_package_name(slug: str) -> str:
    """Derive one importable package name, without accepting a dotted path."""
    package = slug.replace("-", "_")
    if not package.isidentifier() or keyword.iskeyword(package):
        raise ValueError(f"judge name '{slug}' does not derive a valid Python package name")
    return package


class CouncilConfig(Model):
    """`config/llm_council.json`: the clocks, width, nights and judges of one night."""

    _declarations: dict[str, JudgeDeclaration] = PrivateAttr(default_factory=dict)
    _config_dir: Path | None = PrivateAttr(default=None)

    def bind_declarations(
        self, declarations: dict[str, JudgeDeclaration], *, config_dir: Path | None = None
    ) -> None:
        """Attach validated declarations without adding them to the council's file."""
        self._declarations = declarations
        self._config_dir = config_dir

    @property
    def config_dir(self) -> Path | None:
        """The local source directory, never part of a serialized council config."""
        return self._config_dir

    def declaration(self, name: str) -> JudgeDeclaration:
        """One registered judge's explicit declaration, or a refusal by name."""
        if name not in self.judge_names or name not in self._declarations:
            raise ValueError(
                f"judge '{name}' has no loaded declaration in config/judges/{name}.json"
            )
        return self._declarations[name]

    def running(self) -> tuple[str, ...]:
        """The active judges, in registration order, before any code is imported."""
        return tuple(
            name
            for name in self.judge_names
            if self.declaration(name).lifecycle_status is JudgeLifecycleStatus.ACTIVE
        )

    shard_timeout_minutes: int = Field(
        default=200,
        ge=1,
        le=350,
        description=(
            "How long one judging shard may run before GitHub kills it. 200 minutes is "
            "2 hours 9 minutes of model time at the content-similarity judge's cap of 200 "
            "pairs over 4 shards, plus 71 minutes of headroom against a fixed cost of "
            "about 6 minutes for the checkout, the weights cache restore and the server "
            "start. That model time is derived from 9.85 tokens a second measured on a "
            "stock runner on 2026-09-09, not from a judge call. A tenant that draws more "
            "work than fits is refused when its own block is read, never answered by "
            "raising this past GitHub's 6 h job ceiling."
        ),
    )
    shard_preamble_minutes: int = Field(
        default=13,
        ge=0,
        description=(
            "How much of shard_timeout_minutes is gone before the judging process starts. "
            "The job clock starts at provisioning; the process starts after a checkout, a "
            "weights cache restore, a checksum verify and a health poll, and all four are "
            "the venue's own fixed cost. 13 minutes is one minute above the worst case "
            "those four steps have been measured at, which is 12.1 minutes: provisioning "
            "0.41, cache restore up to 1.58, checksum verify 0.12, and a health poll "
            "bounded at 10. Without it the in-process deadline lands AFTER GitHub's own "
            "kill on a slow model load, and the reserve below protects nothing."
        ),
    )
    shard_wrap_up_minutes: int = Field(
        default=12,
        ge=0,
        description=(
            "How much of shard_timeout_minutes a judging shard keeps back for itself, so "
            "it stops on its own clock instead of being killed on the platform's. A shard "
            "killed at the bound uploads nothing, so every verdict it had already produced "
            "dies with the units it had not started. The reserve covers what happens after "
            "the last unit: writing the records and the artifact upload. Its own knob "
            "rather than a copy of run.shard_wrap_up_minutes, because a work shard is a "
            "different stage with a different preamble. Raise it if an upload is ever cut "
            "off, and never lower it to fit one more unit."
        ),
    )
    shards: int = Field(
        default=4,
        ge=1,
        le=8,
        description=(
            "How many shards split one night. The workflow reads it to size its own "
            "matrix, so it is the venue's number rather than a tenant's. 4, because one "
            "llama-server on the configured weights already peaks at 12.57 to 13.16 GiB "
            "and reaches 14.31 GiB with the shard's python - 96.0 percent of the 16 GB "
            "runner, measured 2026-09-08 over four shards of run 2026-08-29-3. A second "
            "server on one runner does not fit at all. The ceiling of 8 is what a GitHub "
            "matrix job costs rather than a measured limit. A tenant may narrow it "
            "downward, so this is the ceiling and the default rather than an instruction."
        ),
    )
    first_night: DateStamp = Field(
        default="2026-09-19",
        description=(
            "The first night this council existed, and the floor under every window it "
            "asks about. Before it a date carries no verdict because nothing was judging, "
            "which is not the same thing as a night that died - and the plan has no way to "
            "tell the two apart without this. The council's ledger holds one day file "
            "against 30 published days, so an unfloored window names every one of those "
            "days on its first run and buys a backfill nobody asked for. A tenant that "
            "moved in later raises the floor for itself, by naming no night from before it "
            "arrived; this is the floor it gets by default."
        ),
    )
    repair_window_nights: int = Field(
        default=7,
        ge=1,
        le=30,
        description=(
            "How many nights back the council asks its tenants about, ending the night "
            "before tonight. This tuple of dates is the whole of what a tenant is handed, "
            "so it bounds the tenant's read as well as the council's own (CLAUDE.md "
            "Guardrail #12). 7, because a night that died on a Friday is still repairable "
            "the following Thursday, and a date still unjudged after a week is one a "
            "person should look at rather than one the next run should keep retrying."
        ),
    )
    repair_dates_a_night: int = Field(
        default=1,
        ge=0,
        le=4,
        description=(
            "How many older dates one night may repair, on top of tonight. Dates are a "
            "parallel axis - one job a date a shard a tenant, each under its own "
            "shard_timeout_minutes - so this buys matrix width rather than wall clock. At "
            "4 shards and 2 tenants, 1 repair is 16 jobs against the platform's 20-job "
            "ceiling and 2 repairs is 24, which runs in two waves. 1, because a cap with no "
            "floor under the window only slows a backfill down instead of stopping it."
        ),
    )
    judge_names: tuple[Slug, ...] = Field(
        default=(),
        description=(
            "Which tenants the council hosts, in the order it runs them. The one place a "
            "tenant is registered: its slug names its package with hyphens replaced by "
            "underscores. The package must be a valid Python identifier, not a keyword. "
            "A missing module or a different declared judge_id is refused by name. Empty is a "
            "legal night - every step still runs and the venue judges nothing - because "
            "a list in source would make adding a judge a code change and would put a "
            "roster of who may exist back inside the venue."
        ),
    )

    @field_validator("judge_names")
    @classmethod
    def require_importable_judge_names(cls, names: tuple[Slug, ...]) -> tuple[Slug, ...]:
        seen: set[str] = set()
        for name in names:
            derive_judge_package_name(name)
            if name in seen:
                raise ValueError(f"judge_names lists judge '{name}' twice")
            seen.add(name)
        return names
