# What Operations draws

**Last Updated**: 2026-11-27

Operations shows reported Council work and retained Gardener writes without
combining them into a workflow health score. The top Console preset sets one
UTC interval, anchored on the mounted UTC clock. Neither chart moves that
interval when its packed evidence ends earlier. Inspecting a mark does not
change the interval or fetch raw data.

Operations uses the Console's shared loading status, delayed shimmer and
retry as the two report reads and the pack checks settle. Changing the visible
window reuses the bounded reads. **Data sources** names their packed date spans
separately from the window: a read begins no earlier than the first indexed
coverage in the widest preset, even when a monthly file covers earlier dates
than its first row. Council files by digest date; Gardener files by pass day.

## Council reports by judge

The Council collector files the steps in `council-run-records`. The browser asks
for their named columns over the widest staged digest span. An older digest
can be judged later. This bounded read is not a full census of backfills.

The activity grid has a row for each configured judge and each judge found in
the packed reports. A mark goes on the UTC day its step started. A filled mark
means a step reported activity, including a failure or deadline stop; an
outline means the reports for that day say no work was assigned. A dash means
no report, not a skipped or cancelled run. Narrow plots retain the whole
timeline and add a single control for exact day selection.

The separate parts and combine charts group work by the first recorded step
of each digest and reported attempt. They retain completed, failed and
deadline-stopped parts, explicit no-work, missing parts, and combine outcomes.
A part cannot satisfy another judge, digest or retry.

## Gardener's write calendar

Gardener's compaction tasks write the retained files and their indexes. The
calendar places each verified footer (metadata stored inside a retained pack)
on its UTC write day, separate from the day, month or year the file covers.
The receipt gives rows and bytes from the
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
deferral can be true on the same day. An unreadable pack means a file needed
for a retry or late input was missing or unreadable, so that work was
deferred. Cleanup is a detail of inspected task
reports: preview counts are not removals, and numbers for compaction input
replacement are not retention deletion totals.
