"""What the published site is allowed to weigh, and how long a picture is promised to stay."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

from pydantic import Field, model_validator

from idhazh.contracts.base import Model
from idhazh.contracts.knobs.removed import refuse_a_removed_knob

#: The platform's own ceiling on a published Pages site, in MB. A property of the
#: host rather than a preference, so it is the bound `retention.pages_hard_cap_mb`
#: is validated against and never a value config can reach past: an operator may
#: make the site gate stricter and may not make it looser (Guardrail #2).
#:
#: This number is MiB and GitHub's published limit is 1 GB, so the gate is
#: optimistic by 7.37 percent: `retention.BYTES_PER_MB` is 1024 * 1024, making
#: 1024 here 1,073,741,824 bytes against 1,000,000,000. If GitHub means the
#: decimal gigabyte, a site can pass this gate 73.7 MB over what the host will
#: publish. Nothing has tested which reading is right, and the runway measured
#: 2026-09-10 is 727 published days, so the gap costs about 76 days at the end
#: of it rather than anything now. Narrowing it is a config edit, not a code
#: change - the field below refuses anything above this line and nothing above.
PAGES_HARD_CAP_MB: Final = 1024

#: The `retention` names this block used to carry, and where the same number
#: lives now: the declaration of the gardener task that reads it.
SUPERSEDED_RETENTION_KNOBS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "dry_run": "dry_run in every config/gardener/<task>.json",
        "max_deletes_per_run": "max_deletes_per_run in config/gardener/visual-prune.json",
        "trial_state_days": "window.value in config/gardener/trials.json",
    }
)


class RetentionConfig(Model):
    """What the site may weigh, and the picture window the archive states to a reader.

    Every default here deletes nothing. A default is a promise, not a placeholder.
    The committed file is one step ahead of the defaults from 2026-09-13:
    `image_months` is 13 there and -1 here. What deletes is the gardener's
    `visual-prune` task, whose own declaration carries the window in days, its
    fuse and its `dry_run`; `config.load_gardener` refuses a window that is not
    this one, so the page never states a window the cleanup does not keep.
    """

    image_months: int = Field(
        default=-1,
        ge=-1,
        description=(
            "How long a rendered visual stays before the cleanup may take it. -1 "
            "disables the age window entirely and is the default, so a clone that "
            "configures nothing deletes nothing. Age-based only, never size: a "
            "size trigger deletes most on the day the reader has most to read. "
            "config/idhazh.json sets 13 from 2026-09-13, which is the first age "
            "window this project has ever had. The cleanup spends a month "
            "as 30 days, so 13 here is 390 days and not thirteen calendar months - "
            "5.7 days shorter, which holds slightly less rather than slightly "
            "more. It is an archive policy and not a cap defence, and the "
            "measurement says so: rendered visuals arrive at 324,580 bytes a "
            "published day, so 390 days stands at 120.7 MiB for ever, 11.8 percent "
            "of the 1 GiB Pages ceiling, where 12 months would stand at 111.4 and "
            "14 at 130.0. Those are 18.6 MiB apart against a one-spread band of "
            "47.6 MiB, so the byte budget cannot separate them and the owner's 13 "
            "stands (Carmack, 2026-09-13). The derivation is "
            "docs/reference/site-weight.md, 'What a published day adds in "
            "rendered visuals'."
        ),
    )
    pages_hard_cap_mb: int = Field(
        default=PAGES_HARD_CAP_MB,
        ge=1,
        le=PAGES_HARD_CAP_MB,
        description=(
            "The size at which the built site can no longer be published, in MB. "
            "`idhazh site-weight` fails the job above it, and that failure is the "
            "whole difference between this knob and site_budget_mb: the other one "
            "warns and this one stops. Bounded on purpose - the 1 GB belongs to "
            "GitHub Pages, so config can lower the cap a run enforces and can never "
            "raise it (Guardrail #2). Lowering it buys an earlier and louder failure while "
            "there is still headroom to act in; no value buys more room. The console's "
            "site band is drawn against the platform's own 1 GB rather than this, "
            "because it reports the ceiling that exists and not the one this run "
            "chose to stop at."
        ),
    )
    site_budget_mb: int = Field(
        default=800,
        ge=1,
        description=(
            "Logs a warning above this, and does nothing else: it never fails a build "
            "and never deletes. Sized in days of warning, not in round numbers. It sits "
            "224 MB below the platform's 1 GB ceiling, which is 26 days of warning at "
            "the fastest growth this project has measured (a PNG on every item, "
            "8,537 KB/day, 2026-08-23), against a 14-day target. The target is a "
            "judgement about one maintainer acting on one warning, not a measurement "
            "(Guardrail #10). The arithmetic and its inputs are in "
            "docs/reference/pipeline-cost.md, 'Where the alarm fires, and what it buys'."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _refuse_a_removed_knob(cls, data: Any) -> Any:
        """Fail a config still spelling a knob a gardener declaration took, naming the file.

        The fuse, the trial window and the dry-run switch each moved into the
        declaration of the task that reads it, so a number left here would be
        read by nothing and believed by whoever set it.
        """
        return refuse_a_removed_knob("retention", data, SUPERSEDED_RETENTION_KNOBS)
