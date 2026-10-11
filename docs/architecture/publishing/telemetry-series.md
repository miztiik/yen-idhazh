# Telemetry series

**Last Updated**: 2026-10-11

Where do Pipelines' interactive measurements come from?

Pipelines asks the native item-health ledger for the columns and UTC days its
panels draw. The query door reads the published native parquet files and their
indexes. It does not fetch monthly CSV copies.

The former `frontend/public/telemetry/` and `frontend/public/run-timeline/`
trees, their producers and row contracts have been retired. The dispatcher
still writes source health, native day metrics and the standing console band.
Nothing under `state/` was deleted by this retirement.

## Native retention

`config/gardener/telemetry-aggregate.json` keeps its full-grain window and
aggregate series. The task reads native item-health and writes native
item-health summaries. It no longer owns a public copy or deletes public month
files. Native compaction retains its own ownership and windows.

## Older readers and bands

Shared legacy chart types and their native row parser remain until the last
route stops importing them. Keeping those read-only helpers does not restore
a public producer.

New console bands omit `months`. A before-validation migration copies an older
band without that one retired field. It leaves the caller's payload unchanged,
preserves settings and checker movement facts, and still refuses every other
unknown key. Delete the migration when no committed band carries `months`.

## See also

- [console-payloads.md](console-payloads.md) - retained published shapes.
- [run-timeline.md](run-timeline.md) - native clock arithmetic.
- [../contracts/state-ledgers.md](../contracts/state-ledgers.md) - source ledgers.
