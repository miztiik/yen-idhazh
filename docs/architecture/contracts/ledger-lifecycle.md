# A ledger's life, as its indexes record it

**Last Updated**: 2026-10-07

What a ledger's three compact indexes hold at each stage of its life, from declared to stopped, and what they cannot tell apart. A ledger starts, pauses, resumes and stops, and so does the gardener task that packs it. Neither is written down as an event: the three indexes under the ledger's compact folder, `index/daily.json`, `index/monthly.json` and `index/yearly.json`, are the whole record. What one entry says is [persistence.md](persistence.md#what-an-index-entry-says), and how the compaction writes the entries is [ledger-compaction.md](../publishing/ledger-compaction.md). What a reader answers at each stage is on the two door pages: a console panel in [how-the-query-door-answers-a-panel.md](../publishing/how-the-query-door-answers-a-panel.md), and the Data explorer in [how-the-query-door-answers-a-written-question.md](../publishing/how-the-query-door-answers-a-written-question.md).

## Two statuses, and neither is in the indexes

A family's `lifecycle_status` in `config/ledgers.json` says whether its writers may file new rows now ([ledger-registry.md](ledger-registry.md#the-three-lifecycle-statuses-and-what-each-one-changes)). A compaction task's `lifecycle_status`, in its declaration under `config/gardener/`, says whether the gardener wakes the task: only an `active` task runs. Each holds its current value and no date, and the site carries neither. So a stage is read off the entries, and a change of status shows only in what the entries do after it.

## The stages

| # | Stage | What the indexes record |
| --- | --- | --- |
| 1 | Declared, never packed | Nothing: the ledger has no compact folder. A pass that finds no raw day due writes nothing, not even empty indexes. The first pass that packs a day writes all three |
| 2 | Packed, never held a row | Every entry `empty`, with no file. A `packed` entry with 0 rows is a file written before a quiet period got none, and a reader takes it as quiet too |
| 3 | Begins mid-month | The first daily entry is the first raw day, and no day before it has an entry. Once that month closes, its entry covers the month from the 1st and lists no earlier day in `lost_days`. Once its year packs, the year entry covers it from 1 January and lists no day of an earlier month as lost |
| 4 | Quiet day | An `empty` entry with no file. A month or a year with no row is `empty` too |
| 5 | Lost day | A `lost` daily entry, or the day in a month's or a year's `lost_days` |
| 6 | Writer paused, then resumed | An `empty` entry for each day the writer filed nothing, so the newest entry still moves at every wake |
| 7 | Writer stopped or retired | As stage 6, with no end: `empty` days up to the newest due day, and each month with no row closes `empty` |
| 8 | Packing paused, then resumed | No new entry while the gardener does not wake the task, so the newest entry stops moving and raw days wait after it. After the resume, each wake moves it on by at most `max_periods_per_run` days until it reaches the newest due day |
| 9 | Packing stopped | As stage 8, and the indexes stop changing |
| 10 | Trimmed off the site, still in the archive | The committed indexes do not change. The site's copy leaves out each entry that ends before its trim line, and carries no mark of what it left out |
| 11 | Dropped by retention | A month past the monthly window is deleted with its entry, so the oldest day the indexes name moves later |
| 12 | Index missing | Some of the three indexes, not all of them. A fault |
| 13 | A hole inside the ledger | A day after the oldest named day that no entry names. A fault |
| 14 | Not packed yet | Raw days after the newest packed day, which no index names yet |

`backend/tests/gardener/tasks/test_compaction_lifecycle.py` wakes the real compaction through stages 1, 3, 6, 7 and 8. Each test files its own raw rows, builds its own declaration, and checks every entry its wakes leave against values it writes out. `frontend/tests/ledger-copy.spec.ts` copies a tree for stages 1 to 8, 10, 12 and 14 in the same way.

## What the indexes cannot tell apart

- **A paused writer, a stopped writer and a quiet stretch.** Each is a run of `empty` days. Only the family's current `lifecycle_status` says which, and it carries no date.
- **The days before a ledger began, once its first month closes.** The month entry covers its month from the 1st, so those days read as quiet days of that month. Before the month closes, the daily index starts on the first day, and a reader cuts the days before it.
- **A day before a ledger began and a day dropped by retention.** Both are days before the oldest day the indexes name.
- **Packing that stopped and packing that is behind.** Both leave a newest entry older than the newest due day.

## Design rationale

**No field records a stage, so a stage is read off the entries.** A field naming a ledger's first day, and a mark for a pause or a stop, are each a change to a persisted shape ([../../../CLAUDE.md](../../../CLAUDE.md) section 11), and the mark also needs writers that record "ran and wrote nothing" apart from "did not run". The list above is what leaving them out costs. Each is added when a surface must show something that list says the indexes cannot.

## See also

- [persistence.md](persistence.md) - the two roots, and what one index entry says.
- [ledger-registry.md](ledger-registry.md) - families, ledgers and the writers' lifecycle statuses.
- [../publishing/ledger-compaction.md](../publishing/ledger-compaction.md) - how a pass chooses its periods and writes their entries.
- [../publishing/how-the-query-door-answers-a-panel.md](../publishing/how-the-query-door-answers-a-panel.md) - what a console panel answers at each stage.
- [../publishing/how-the-query-door-answers-a-written-question.md](../publishing/how-the-query-door-answers-a-written-question.md) - what the Data explorer answers at each stage.
- [../../../CLAUDE.md](../../../CLAUDE.md) - section 11, the rule a persisted shape changes under.
