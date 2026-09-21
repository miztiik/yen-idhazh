"""What one night at the council costs a runner, whatever judges it hosts."""

from __future__ import annotations

from pydantic import Field

from idhazh.contracts.base import DateStamp, Model, Slug


class CouncilConfig(Model):
    """The clocks, the width, the nights covered and the tenants one judging night runs under.

    A top-level block rather than a knob under a tenant, because every number
    here prices a runner: a checkout, an install, a weights restore and a matrix
    shard. No tenant can see any of them.

    Until 2026-09-21 the bound sat in `run`, which is the digest pipeline's, and
    the width sat inside the content-similarity judge's own block - so a
    repository with no judge configured had no width to size its matrix by and
    no clock to stop a shard on.
    """

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
            "tell the two apart without this. The council's store holds one day file "
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
    tenants: tuple[Slug, ...] = Field(
        default=(),
        description=(
            "Which tenants the council hosts, in the order it runs them. The one place a "
            "tenant is registered: the council resolves each slug to the module that "
            "declares it, and a slug nothing declares is refused by name. Empty is a "
            "legal night - every step still runs and the venue judges nothing - because "
            "a list in source would make adding a judge a code change and would put a "
            "roster of who may exist back inside the venue."
        ),
    )
