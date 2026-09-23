"""What the published site is allowed to delete, where every default deletes nothing."""

from __future__ import annotations

from typing import Final

from pydantic import Field

from idhazh.contracts.base import Model

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


class RetentionConfig(Model):
    """Every default here deletes nothing. A default is a promise, not a placeholder.

    The committed file is one step ahead of the defaults from 2026-09-13:
    `image_months` is 13 there and -1 here. `dry_run` is true in both, so the
    committed config names a window and still removes nothing - which is the
    order this was landed in, so that the first evidence of what the window
    selects arrives before the deletion rather than after it.
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
            "window this project has ever had. `retention.cutoff` spends a month "
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
    dry_run: bool = True
    day_validation_keep_months: int = Field(
        default=14,
        ge=1,
        description=(
            "How many months of day-validation receipts are kept under "
            "state/day-validations/. A receipt says one published day passed the "
            "rules as they stood, and it is consulted only to skip re-reading that "
            "day - so a receipt for a day the published archive no longer holds "
            "cannot be read and answers nothing. Fourteen matches the published "
            "windows the console reads, so the receipts outlive the days by a "
            "month rather than going first and costing a full re-validation."
        ),
    )
    max_deletes_per_run: int = Field(
        default=200,
        ge=0,
        description="The fuse. An off-by-one in a date parse must not eat the archive.",
    )
    trial_state_days: int = Field(
        default=90,
        ge=1,
        description=(
            "How long a trial run's ledgers under `state/<run.trial_state_dirname>/` "
            "are kept. Ninety days because it is the artifact retention this project "
            "already uses everywhere else, so a trial's rows outlive the run's own "
            "artifacts by nothing and a question asked of one can still be asked of "
            "the other. Nothing reads these rows - no published series, no gate, no "
            "console band - so the window is about disk and about a reader who opens "
            "`state/` and wonders what a directory is, rather than about evidence."
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
