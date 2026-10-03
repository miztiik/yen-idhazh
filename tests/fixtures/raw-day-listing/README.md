# Raw day listing fixture

**Last Updated**: 2026-10-03

This fixture holds one raw day listing as the compaction helper writes it.

The two `.parquet` files are 4-byte and 8-byte placeholders. They are not readable parquet. Their only job is to give the site build real file sizes so a staged listing's `bytes` field can be checked.

The listing is the output of `backend/idhazh/gardener/tasks/_index_day.py` for this day. Regenerate it by running that helper's `listing()` over the two file paths, with ledger `item-health`, day `2026-09-02` and the fixture's `listed_at` value; then write the model as JSON with LF.
