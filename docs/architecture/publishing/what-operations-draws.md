# What Operations draws

**Last Updated**: 2026-11-26

Operations shows reported Council work and retained Gardener writes without
combining them into a workflow health score. The top Console preset sets one
UTC interval, anchored on the mounted UTC clock. Neither chart moves that
interval when its packed evidence ends earlier. Inspecting a mark does not
change the interval or fetch raw data.

## Council reports by judge

The Council collector files the steps in `council-run-records`. The browser asks
for their named columns over the widest staged digest span and displays the
work whose first recorded step is inside the selected execution interval.
Backfills for older digests outside the packed span are not a complete run
census. The chart names the digest span it checked.

Each judge has its own labelled chart. Within it, one column represents a
digest and reported run attempt. The column distinguishes completed, failed
and deadline-stopped parts, explicit no-work and missing parts against a
consistent reported width. A separate cap shows combine outcomes. A part
cannot satisfy another judge, digest or retry. No report does not prove that
a job missed its schedule or was cancelled.

## Gardener's write calendar

Gardener's compaction tasks write the retained files and their indexes. The
calendar places each verified footer on its UTC write day, separate from the
day, month or year the file covers. The receipt gives rows and bytes from the
index and the input count when the footer recorded it. It does not date the
push. The latest monthly milestone is only the latest verified within the
selected window. Month and year rows show milestones, not daily obligations.

The [static query door](how-the-query-door-answers-a-panel.md#what-the-site-holds-for-the-door)
reads consented indexes and prices the named file reads before opening them.
It checks monthly and yearly evidence first and may shorten the daily read to
fit the existing file and byte limits. The display keeps its full calendar;
a patterned day means evidence is incomplete, and an outlined day means no
write was found in the checked files. Neither says the workflow did not run.
Current indexes and footers do not reconstruct older versions removed by
folding, replacement or expiry.

The `gardener` ledger separately supplies task stops and recovery notes on
their reported work day. Red crosses mark explicit failures. Amber marks
limits or deferrals and connects consecutive dates only where the same task
and reason are recorded. Blue diamonds mark recovery notes. A write and a
deferral can be true on the same day. Cleanup is a detail of inspected task
reports: preview counts are not removals, and numbers for compaction input
replacement are not retention deletion totals.
