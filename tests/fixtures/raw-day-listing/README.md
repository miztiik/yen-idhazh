# Raw day listing fixture

**Last Updated**: 2026-10-03

This fixture holds one raw day listing in the shape an older compaction wrote: no `bytes` field.

The two `.parquet` files are 4-byte and 8-byte placeholders. They are not readable parquet. Their only job is to give the site build real file sizes so a staged listing's `bytes` field can be checked.

The compaction no longer writes listings; only the site build does. Edit the listing by hand: `files` names the two files in ascending order, and `content_sha256` is the SHA-256 of those names joined with one newline, as `RawDayIndex` declares. `backend/tests/contracts/test_raw_day_listing_fixture.py` checks both. Write it as JSON with LF.
