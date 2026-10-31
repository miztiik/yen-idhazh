# Planner data in the published site

**Last Updated**: 2026-10-31

Which planner table files may a site build publish?

Only current native planner formats are published. Older planner files remain
in the repository but are not copied into the built site as current data.
This does not change any other ledger family's format or historical reader.

## Admission before copying

The frontend publication stage first reads its existing consented ledger
indexes and configured publication window. The native TypeScript reader checks
only the named planner compact files in that copy.

An unsupported planner envelope or row stamp produces a body-free refusal
warning. The generated copy omits those bytes and projects unavailable coverage
into its existing compact indexes: a daily entry is lost; a month or year
has no file and names every covered day as unavailable. Counts describe only
published files, not measured reads. The source Parquet files, their counts and
committed indexes are unchanged. Unavailable coverage is not a measured zero
or a quiet period. Queries and automatic column reads do not fetch refused files.

A current-format file with corrupt bytes, invalid rows or an unsafe path still
fails the build. There is no old-format decoder, migration or success-shaped
fallback.

## The final column check

The existing `Check published ledger columns` CI step runs the Python
published-column command on the built site. It delegates planner-file checking
to the TypeScript validator; Python does not own a second planner row model.
The HTTP operator API is not part of this check.

The gate remains strict. Export admission prevents old incompatible files from
being presented as current published data, rather than weakening the final
validation rule.

## Design rationale

The planner's native schema is the single authority at both publication
boundaries. Reusing the existing Bun and Parquet runtime adds a bounded read
of the named planner publication files, with no new library or server. A refusal
is shown as unavailable coverage instead of deleting history or accepting an
older format.

## See also

- [Planner ledger formats](../../reference/feed-planner-ledgers.md)
- [Published frontend](frontend.md)
- [Final data delivery](committing.md)
