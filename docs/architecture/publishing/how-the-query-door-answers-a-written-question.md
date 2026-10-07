# How the query door answers a written question

**Last Updated**: 2026-10-07

The query door can run one operator-written, read-only DuckDB statement over the ledgers and UTC days the page chose. The statement sees views, not files.

## Views

`ask()` lives beside `slice()` in `frontend/src/lib/data/ledger.ts`. It uses the same page keeper as the panel path. For each selected ledger, `ask-reader.ts` creates one DuckDB view whose name is a member of `LEDGER_NAMES`. The files inside that view are engine-minted names such as `door/1.parquet`; no index, cell, caller text or fetched text becomes a file name.

Each call first drops every unselected ledger view. This matters because the page keeper can still hold files from an earlier run. Without the drop, a later statement could read a ledger the operator did not select and did not see priced.

Calls run one at a time. The engine has one connection, and each call rewrites the same set of ledger views. The column rail's call waits in the same line.

A view holds only the days its span asked for. `filesFor()` picks the coarsest packed file that holds a day, so a span that starts or ends inside a month reads that month's file, and the site and the archive can both hold a month that crosses the site's oldest day. Such a file gets a read of its own, `WHERE "covers" >= '{first day}' AND "covers" <= '{last day}'`, and the view joins its reads with `UNION ALL BY NAME`, which matches columns by name as `union_by_name` does inside one read. `covers` is the day a row was filed under. Every packed row carries it, even inside a month or year file, and the files and both keepers divide a ledger's days by it; `date` would not do, because `published` and `seen` have no such column. Day files, writers' files and a month or year file wholly inside its days share one read. Each day is checked as `YYYY-MM-DD` before it is written into the statement, because it comes from an index. On the site a year file is opened by address, and the same filter lets the engine skip its row groups outside the span.

A selected ledger with no file in the span still gets a view, so a statement that names it binds: an empty view (`LIMIT 0`) over the files of its newest day or period that has a file. Those files come from its listing when the build listed a day after the newest packed one, and otherwise from the newest index entry that names a file; an `empty` or `lost` entry names none, so an older one is taken. A packed file with zero rows is used here, though a span's own read skips it: the empty view needs only the file's columns, and a ledger whose packed days all hold zero rows, as `candidate-models` does today, would otherwise reach the engine as `read_parquet([])`, which DuckDB refuses. A selected ledger with no file at all to read its columns from answers `missing`.

**The column rail lists each chosen ledger's columns from the files its empty view reads, whatever window is selected.** `askColumns()`, beside `ask()` in `ledger.ts`, reads them through `ledger-columns.ts` and takes no window: it reads at most that one file, or one listed day's files, and it chooses, widens or moves no window. So a ledger whose newest days are empty or lost, or whose writer stopped before the window, still lists its columns. A ledger with no such file lists no column. So does one whose files are over the fetch ceiling, which are not fetched, or cannot be read, and the browser console then says which files and why.

## Statement wraps

`statement.ts` is a courtesy refusal. It rejects more than one statement, a statement that does not start with `SELECT`, `WITH`, `DESCRIBE`, `SUMMARIZE` or `EXPLAIN`, and a statement beyond the caller's character limit. It is not the boundary; the browser content policy is.

Before the answer runs, `ask()` asks DuckDB to describe the statement. That gives the answer columns even when no row matches. The run itself wraps most statements as:

```sql
SELECT COLUMNS(*)::VARCHAR FROM (
<operator statement>
) LIMIT <max rows + 1>
```

The statement sits on its own lines so a final `--` comment cannot comment out the closing bracket. `EXPLAIN` runs without that wrap because DuckDB does not parse it there. `SUMMARIZE` and `DESCRIBE` do parse there. Every cell crosses back as text, so decimals, dates, lists and structs keep the engine's own spelling.

**A timestamp with a time zone prints in UTC until the engine loads its time-zone add-on, and in a fixed zone it picks from the page's zone after that.** The engine downloads that add-on, ICU, the first time a statement needs it, such as one that reads `current_setting('TimeZone')`, and keeps it for the rest of the page's life. So the same question can print `+00` first and `+01` later. In Chromium with DuckDB-Wasm 1.5.4 on 2026-10-06, with the add-on loaded, a page in New York got `Etc/GMT+5` and printed `-05`, Berlin `Etc/GMT-1` and `+01`, India `Etc/GMT-5` and `+05`, and UTC `+00`: each zone's standard-time offset cut to whole hours, with no daylight saving. So on a page in Berlin, 23:30 UTC then prints as `00:30:00+01` on the next day. Every value carries its offset, so its UTC instant can be read back from the text.

## Writers' tier

A date is read through exactly one tier. Packed files win first: year, month, then day, through `filesFor()`. For dates after the newest packed day, `ask()` may read the writers' own parquet files, but only through a staged `RawDayIndex` listing.

The listing must carry `bytes`, one size per file. `askCost()` uses those sizes before a data file is fetched. `ask()` refuses a span above the byte ceiling before a data file is fetched. The page keeper checks the same size when the file arrives.

The site build stages those listings for raw days after each ledger's newest
packed day, up to the widest console preset. A day whose raw directory holds a
non-parquet writer file is left unlisted and the build log names that file. A
listing that is absent inside the listed range is a file gap, not an empty day.

The build hands the page each ledger's newest listed day as
`__RAW_LISTED_THROUGH__`. A page script that sets `__RAW_LISTED_THROUGH__` to
an empty object reads no writer's file, as the browser tests that serve a
ledger they built do: a built ledger has no writer's files, so the build's list
would name days of the canary's. The shipped page sets nothing, and no page
script can name a day the build did not list.

## Archive tier

The archive is the committed repository, which holds every packed file a ledger still keeps. Data explorer reads it from `ledger.archive_base_url` in `config/idhazh.json`; the shipped value is `https://raw.githubusercontent.com/miztiik/yen-idhazh/main`.

**The archive is read only for days the site copy may have dropped.** The site build keeps each published ledger's index entries that overlap the widest console preset of UTC days ending on the newest day the ledger's indexes name ([what the site holds](how-the-query-door-answers-a-panel.md#what-the-site-holds-for-the-door)). One function, `frontend/src/lib/data/site-window.ts`, holds that rule for the build and for this page, and the build hands the page the number of days as `__SITE_WINDOW_DAYS__`. The copy may have dropped days only when the site's first day is on or before the first day it keeps. Then a window that begins before the site's first day asks the archive for the days before it. Otherwise the archive host gets no request.

**Days before a ledger began are cut from the selected window.** When the selected window begins before the first day any tier it read names, that ledger's earlier days are cut, so its answer starts on that first day. Nothing failed. Only that start moves, and only later: the page still opens on the reader's UTC day, the presets still end on it, no end moves, and nothing reads a ledger's first day to choose, widen or end a window. A day after that first day that no index names is still a hole, `day-missing`. With `ledger.archive_base_url` empty, the site is the only tier.

`ok` and `quiet` carry `cut`: one entry for each ledger whose earlier days were cut, in the order chosen, with `before`, its first day. The page prints one grey sentence for each, after the span line, never joined with another: `Days of the {ledger} record before {day} are not on this site.` When that day is after the window's last day, the ledger gave the answer nothing, and the sentence ends `are not on this site, so nothing from that record is in this answer.` instead.

**The span line counts the days the answer read.** `ok` carries `readFrom`: the window's first day, unless every selected ledger's answer starts later, because its earlier days were cut or the repository could not give them; then the earliest day one of them starts on. An answer with rows read at least one day, so `readFrom` is never after the window's last day. The page prints `Read from {n} UTC days, {readFrom} to {last day}.`, or `Read from 1 UTC day, {day}.`, where the last day is the window's, and every date carries its year. The page keeps the window a run asked for with its answer, so moving the dates before the next Run changes nothing in the line. A quiet answer prints no span line: its sentences follow `Your question ran and matched no rows.`

**When the archive cannot give those days, the ledger is read from the site's days alone, and the answer says so.** That covers a host that does not answer, an index or a file the archive does not hold, an index this build cannot read, and a file of the wrong size. Each ledger's archive files are held first, one ledger at a time, before any site file is fetched. A ledger the archive fails for is planned again from the site's first day, so its site files are fetched once; the files of it that did arrive are dropped. Every other ledger keeps its archive days. A day the archive's indexes skip after the ledger began is still `day-missing`: the archive answered, and the hole is in the ledger.

`ok` and `quiet` carry `unanswered`: one entry for each ledger the archive failed for, in the order chosen, with `before`, its first day on this site, where its answer starts. That start is never in `cut`. The page prints those entries in the warning colour, after the grey sentences and before the gap lines: one sentence for each ledger, `Days of the {ledger} record before {day} are not in this answer, because this page could not read them from the repository.`, then `Press Refresh, then Run, to try again.` The browser console gets one line that names the index or file and why, and ends `so the question reads this ledger from this site alone`.

The archive uses its own page keeper and its own three compact indexes. It chooses files with the same `filesFor()` rule as the site, but it fetches every archive data file whole. It never hands the archive address to DuckDB. The engine sees only buffers under engine-minted names.

`FetchCost` sums both keepers. A file the site already holds and a file the archive already holds both count as already held. An archive file dropped because another file of its ledger failed is not counted.

## Reach and cost

`through` is the newest UTC day any selected tier can answer. A daily entry counts as that day. A month counts through its last UTC day. A year counts through 31 December. A staged writer listing can move `through` later than the packed indexes.

`FetchCost` is the keeper's reading for this call. A whole file counts at the bytes that arrived. A file read by byte range counts at the whole indexed length, because the page cannot see which ranges the engine read and that length is the most the read can cost. `alreadyHeld` counts files the keeper already had registered before this call. The Data explorer page action line prints the whole-file bytes the page keeper still holds in the engine; byte-range files are opened for one call and dropped, so they do not inflate the reload total.

## Unreachable fields

`unreachable` carries the fields its sentence prints.

- `ledger` names the ledger when the failure belongs to one ledger; it is `null` for an engine that did not start.
- `at` names the UTC day to retry or explain. For a day file it is that day. For a month or year file it is the first span day that file was chosen for. For a refused daily index it is the span's first day.
- `fault` names a file gap when the indexes prove one: `index-missing`, `file-missing` or `day-missing`. It is `null` for a file that did not arrive whole. It is `engine` when the engine did not start.

When no selected ledger holds a file in the span, `ask()` answers `quiet` and starts no engine. When files are in the span and the statement matches no rows, it also answers `quiet`, with the columns from `DESCRIBE`.

## What an answer is missing

`ok` and `quiet` carry `gaps`: each selected ledger that is missing something inside the span, in the order the ledgers were chosen, with the days its indexes record lost and the files its periods set aside unread (`lostDays` and `setAside`, as a [slice answers them](how-the-query-door-answers-a-panel.md#what-a-panel-asks-for-and-the-four-answers)). A ledger missing nothing is not named. A span of nothing but lost days is `quiet` and still names them.

The Data explorer page prints one line a ledger and a state under the span line, in the plain note type, lost days first: a lost day has no record, so nothing from it is in the answer, and a set-aside file may hold rows the answer lacks. The set-aside line counts files, never days, because a month counts every file it set aside, and it names the folder a person reads them in, `state/raw/<ledger>/set-aside/`. The quiet answer carries the same lines. The chart panel repeats none of them.

The date chart draws a lost day as a day with no value. A day a selected ledger lost, between the answer's first and last day and with no row of its own, sits on the axis with nothing drawn, so the line breaks there instead of joining the days either side as if that day held data. Pointing at it reads `No number for this day`, the strip's words for any day with no number. Any other day without a row stays off the axis, because the page cannot know what the question would make of a day with no rows. A lost day before the answer's first day or after its last also stays off, so it never lengthens the chart or stands beside days the question left out (Jony, 2026-10-05). The page cannot tell which selected ledger a row came from, so it takes the lost days of every selected ledger: the chart may show a gap that one ledger did not cause, but it never joins a line across a day with no record.

## Date range and address

The Data explorer page uses two native date inputs, `From (UTC)` and `To (UTC)`. By default they accept the reader's UTC day and the 364 UTC days before it. The bound is `console.explorer_reach_days`, so an operator can widen or narrow it with a config edit rather than a source edit.

Preset tiles remain shortcuts. Pressing one sets `To (UTC)` to the reader's UTC day and `From (UTC)` to the preset's span ending on that day.

A shared link carries a preset as `days=<n>`. A custom span replaces `days` with `from=YYYY-MM-DD` and `end=YYYY-MM-DD`. A date that is not a real UTC day, such as `2026-08-32`, a date outside the reach, or `from` after `end` is dropped with a sentence, and the page ends today. The day check is the door's own `isDay()`, which answers rather than throws. A link never runs a question.

A question this browser keeps, saved or recently run, is read back with the same three checks. One that fails any of them is dropped, and the browser console names the list it was dropped from.

## Boundary

The engine module is unchanged. The only module importing `@duckdb/duckdb-wasm` remains `frontend/src/lib/data/engine.ts`. The browser's shipped `connect-src` policy applies to the engine worker, so a statement that tries to read an unlisted origin is refused by the browser. The boundary test builds its support page with the same policy directives as `svelte.config.js` and asserts the refused request never reaches the network.

## Design rationale

**Days before a ledger began are cut from a window, not refused.** The owner ruled on 2026-10-05: when a Data explorer question begins before a ledger's first day, the explorer cuts that ledger's earlier days from the selected window and names that first day, as it already did with no archive set. The rejected choice kept refusing such a question and changed only the test data. Ledgers start, pause, resume and stop, so a day before a ledger's first is outside the ledger, not a missing file. The cut moves only the start of that ledger's answer, and only later: the page still opens on the current day, a preset still ends on it, and a ledger that began years ago never moves a window into the past.

**Each cut ledger is named with its own first day, and the span line counts the days read.** Reader chose the words on 2026-10-07. Before, one sentence, `Days before {day} are not on this site.`, named the earliest first day of all the chosen ledgers and named no ledger, so for two ledgers that began on different days it was false for one of them. The span line counted the days asked, not the days read. It printed its first date with no year, `16 Jun to 15 Jun 2030`, and it counted again whenever the dates moved after a run. One span line for the whole answer says the usual case once, and a sentence for each cut ledger names each exception, so five ledgers that began years ago cost one sentence, not five. The rejected choice, a span line for each ledger, repeated that usual case once a ledger. The sentences are never joined, so each puts its ledger's name in the same place. `Not on this site` stays true whether the ledger began on that day, its first month is packed from the 1st, or the page reads the site alone; `began on` would be false for the last two. The longer form says when a ledger gave the answer nothing, which an operator would otherwise work out from two dates.

**The archive is asked only when the site copy's own rule says it may have dropped days.** That costs one shared function and one build constant. In return, a ledger the copy did not trim, which is every ledger for its first window, answers from the site with no request to a third-party host. Asking the archive whenever a window begins before the site's first day would send three cross-origin requests a ledger, every time, for days no tier holds. A `trimmed_before` field written by the site copy would be exact, but it changes a persisted shape (`CLAUDE.md` section 6, Level 5). Dropping the archive would lose every day older than the site window, while `console.explorer_reach_days` offers a year. The rule's one cost: a ledger whose oldest entry holds the first day the copy keeps reads as trimmed, and costs one needless archive read.

**An archive that cannot be read degrades the answer and does not fail it** (`CLAUDE.md` section 1a). Two choices were rejected. Failing the question in the site's words blamed the site for the archive's fault (`No file on this site holds ...`, or `... has no days on this site yet.` when the archive had no index), and threw away the site's days, which were readable. Failing it in the archive's words told the truth and answered nothing. Reader and Jony chose the words on 2026-10-07. They chose `repository`, because the console never says `archive`, and on the reader site Archive is the list of past digests. They did not choose `GitHub`, because the address is a config value. `Could not read` stays true for all four faults, where `did not answer` does not. One sentence for each ledger never names a ledger the archive answered for. The retry is there because the design system gives every failed fetch one ([design-system.md](../../concepts/design-system.md)).

**The column rail reads a ledger's newest file, not a day of the window.** Fowler ruled on 2026-10-07. Before, the rail asked `DESCRIBE` over the ledger's newest named day, so a ledger whose newest day was empty or lost listed no column; `candidate-models` listed none on the live site. Two choices were rejected. Describing from the newest day that holds rows would be a second rule for "the newest file", and it skips a file with zero rows, which the empty view reads. Letting `DESCRIBE` alone read the empty views would make one statement a special case of the rule that a span with no file answers `quiet`. The rail may read a file older than the window, because it returns no rows: the window chooses which rows an answer holds, and columns belong to the ledger, not to a day. The cost: when a ledger's newest file is a closed month's, the rail fetches that whole file once a page.

## See also

- [how-the-query-door-answers-a-panel.md](how-the-query-door-answers-a-panel.md) - the panel entry point this one extends.
- [../contracts/schemas.md](../contracts/schemas.md) - the `RawDayIndex` contract and the frontend hand copy.
