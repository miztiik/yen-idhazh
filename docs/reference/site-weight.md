# What a reader downloads

**Last Updated**: 2026-10-02

The published site's size, the bytes a browser receives, and the rules for
measuring both. [pipeline-cost.md](pipeline-cost.md) covers production compute.
The committed settings in [config/idhazh.json](../../config/idhazh.json) are the
source of truth for the controls below.

## Current controls

The configuration's site-size fields use MiB: 1 MiB is 1,048,576 bytes. Transfer
limits use bytes compressed with gzip level 5, not raw file sizes.

Table A - Configured bounds

| ID | Control | Value | Effect |
| --- | --- | ---: | --- |
| A1 | `retention.pages_hard_cap_mb` | 1,024 MiB | Refuse an oversized built site; the configured limit cannot exceed the platform's 1 GiB limit. |
| A2 | `retention.site_budget_mb` | 800 MiB | Warn while publishing can continue; delete nothing. |
| A3 | `page_weight.ceilings_bytes`, `/404` | 4,400 compressed bytes | Bound this route's prerendered HTML. |
| A4 | `page_weight.payload_ceilings_bytes`, `console/band.json` | 2,000 compressed bytes | Bound this fetched payload. |
| A5 | `page_weight.payload_ceilings_bytes`, `telemetry/` | 1,100,000 compressed bytes | Bound each file under this build-relative prefix, not their combined size. |
| A6 | `page_weight.cold_console_load_bytes` | 2,300,000 compressed bytes | Bound the payload total for a cold console opening: two telemetry month shards at the 14-day default window, the band, and 98,000 bytes of room. |
| A7 | `page_weight.payload_ceilings_bytes`, `state/compact/<ledger>/index/`, one key per published ledger | 2,200 compressed bytes | Bound each of a published ledger's two indexes, each on its own. |

These are limits, not measurements of the current site. Measure the completed
build before reporting its size or remaining capacity. Use the commands in
[run-the-gates.md](../how-to/run-the-gates.md).

## What each measure counts

- **Deployed size:** raw bytes in the directory uploaded to Pages,
  `frontend/build/`. Use the `site-weight` command with an explicit `--site-tree`.
  Neither the source checkout nor the committed digest payloads are this tree.
- **Transfer size:** compressed bytes of the document and fetched assets needed
  for the interaction being measured. `bundle-gate` checks the configured HTML
  and payload bounds; an HTML-only reading misses later downloads.
- **Growth:** the additional deployed bytes produced by more content under the
  same code and build settings. A smaller total after a code change is a saving,
  not a negative content-growth rate.

Use the project's gzip level for comparable transfer figures. An origin can
compress responses differently, so distinguish a local compressed size from an
observed network transfer. Compression reduces transfer bytes; it does not
reduce the raw deployed-size total.

## Design rationale

### Warning and hard cap

The warning leaves time to act without withholding a working digest. The hard
cap stops a publication that Pages cannot accept. Neither a warning nor a size
estimate authorizes deleting content; the
[retention policy](../architecture/publishing/retention.md) decides that.
The [size instrument](../architecture/publishing/what-the-site-weighs-and-when-it-stops-fitting.md)
owns which checks run before publication and which run after it.

### Page and payload guardrails

Fixed page ceilings apply to routes whose size changes with source edits, not
with ordinary publication. A fixed ceiling on a growing archive or dashboard
would force less coverage or repeated increases without identifying a defect.
Those surfaces instead need checks that they load bounded data and do not inline
the whole archive.

Moving data from HTML to a fetched file does not remove its cost to a reader.
Payload limits cover that file, and the cold-load limit covers the combined
request. Serial request dependencies also affect waiting time and need their own
browser check; byte totals cannot detect them.

### Bounded loading

Keep page shells small and fetch the day, month or selected window the reader
needs. Do not copy the complete corpus into every document. Search entries and
vectors have separate costs; counting only the index metadata understates the
download. The [archive design](../architecture/publishing/how-a-reader-finds-a-story.md)
and [month-index contract](../architecture/publishing/what-a-month-shard-holds-and-how-it-reaches-a-browser.md)
own the loading and partition rules.

### Optional assets

Load the search encoder and browser query engine only when their features need
them. Lazy loading saves the initial transfer, but emitted assets still count
against the site's raw-size cap. A remotely hosted asset is outside that total
and still costs the reader a download. The published ledgers the query engine
reads count against the cap as well, whether or not a page asks for them; what
they weigh and what bounds it is on the
[query-door page](../architecture/publishing/how-the-query-door-answers-a-panel.md#what-the-site-holds-for-the-door).

Report first-use cost separately from repeat-use cost. Do not assume unchanged
file contents stay cached across deployments: verify the origin's cache headers
and the application's cache behavior. The
[query-engine design](../architecture/publishing/how-the-query-door-answers-a-panel.md)
and [encoder design](../architecture/publishing/the-on-device-encoder-and-its-vectors.md)
own those choices.

The query engine's same-origin files have a separate content-named service-worker
cache. It keeps one engine version on first use, not on site installation, and
survives a deploy whose engine files are unchanged. This reduces repeat network
transfer, not deployed size or first-use cost. The cached bodies consume device
storage at their decoded size; the ledger and off-origin add-on are not part of
this cache.

### What a published day adds in rendered visuals

Measure the emitted pictures, not the source article's size. Retention trades
archive coverage for space: removing a picture takes context away from the
reader of that older article. Choose the window through the
[visual-retention policy](../concepts/adaptive-pruning.md), not from a forecast
that silently assumes a fixed number or format of pictures per day.

### Reader-facing trade-offs

A byte saving must preserve readable layouts, working static entry points and
deep links, and the declared search-quality requirements. Check those properties
directly; a lighter build alone proves none of them. Layout belongs in the
[design system](../concepts/design-system.md), and retrieval quality belongs in
[search-quality.md](../concepts/search-quality.md).

## Growth estimates

- Use one code revision and real content sets when measuring marginal growth.
  Cloning a day can make compression unrealistically effective.
- Separate fixed assets from content-dependent bytes. Dividing the entire site
  by its item count does not measure what the next item will add.
- Count bytes and items from the same built tree. A manifest's payload-tree
  total cannot stand in for the deployed site.
- State whether a rate is per item, per run or per published day. A per-run
  item limit is not a daily publication rate.
- Divide remaining raw site bytes by a growth rate for that same tree and unit.
  A calendar forecast also needs an explicit publication-frequency assumption.
- Name the measured inputs, method, compression and uncertainty with any figure.
  Re-measure when the publisher, asset format, dependencies or content mix changes.
  Report an unknown rate as unknown, not as unlimited capacity.
- Keep only the current reading for a quantity. Replace superseded numbers;
  do not append build transcripts, incident timelines or developer-machine setup.

## See also

- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - build, size and browser checks.
- [../concepts/config/run-limits.md](../concepts/config/run-limits.md) - the warning and hard-cap settings.
- [../architecture/publishing/console-site-size.md](../architecture/publishing/console-site-size.md) - what the operator's size display measures.
- [benchmarks/prerender-on-and-off.md](benchmarks/prerender-on-and-off.md) - the prerendering comparison and its limits.
