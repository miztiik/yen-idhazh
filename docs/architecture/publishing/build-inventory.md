# Build Inventory

**Last Updated**: 2026-10-04

How does the Pages cap measure every deployed byte without discovering source history?

## Fresh output, then one named reading

`npm run build` captures its input identity before compilation. That start step
removes the previous generated `frontend/build/`, its completion record and
`frontend/build.publication.json`. Source files and committed data are not removed.
Adapter-static then creates this run's output.

The completion hook checks that compilation used unchanged inputs and that both
static and preview output exist. A missing start record or changed inputs cannot
certify old output. The build runs on Node alone and starts no Python.

`idhazh site-weight --site-tree build` writes the inventory, then reads it. It
runs right after `npm run build` in the three jobs that measure the site: the
`site` job of `ci.yml`, the `assemble` job of `digest.yml` before the day's
commit, and `backfill.yml`. The Pages deploy builds a commit one of those jobs
already measured, and writes no inventory.

The writer, `build_publication.record_build_inventory`, walks only the generated
output directory. It measures every regular file: generated HTML and JavaScript,
drawings, projected digests, static assets, copied ledger files and ledger
indexes. A symlink fails the step. For each dated `digest.json`, it checks the
UTC date against the path and counts the projected item list. A missing list or
an unreadable digest fails the step.

The writer uses the existing `PublicationInventory` contract. Entries have
`root=public`; their paths are relative to the deployed build directory.
Dates and counts come from that output, never from a source inventory.
The inventory lives at `frontend/build.publication.json`, outside the uploaded
`frontend/build/` tree. It is ignored by Git and is not deployed. There is no
inventory self-size to omit from the Pages cap.
The source `publication.json` is not staged into the deployed tree either.

`site_weight.measure` reads this one validated file for bytes, file count,
directory totals and published items. `count_published_items` reads its item
total, not historical digest payloads. The stage reads the inventory once.
Missing or invalid inventories fail rather than falling back to directory
discovery. A valid empty inventory still fails the stage's empty-site check.
The alarm and Pages cap keep their existing configured meanings.

## Design rationale

Source payload size cannot stand in for deployed bytes. Compilation creates
HTML and JavaScript; staging projects digests and copies ledger files. Measuring
this run's output includes all of those changes and pairs its bytes with the
items actually deployed. Removing the previous output at build start prevents
leftovers from entering the cap or item count.

The step that measures writes the inventory because it is the only reader.
Written inside `npm run build`, it made every build run backend Python, and the
Pages deploy installs only Node. It also made the writer's refusals a deploy
gate, which [what-the-site-weighs-and-when-it-stops-fitting.md](what-the-site-weighs-and-when-it-stops-fitting.md)
rejects: a refused deploy leaves the reader on yesterday's digest. The refusals
still run on the same fresh tree in every job that measures, and in `digest.yml`
they run before the commit, the one place a refusal can stop a bad day.

No additional persisted shape or version migration is needed: the existing entry
and total semantics are unchanged, and this generated artifact is replaced every
time the site is measured.

This page answers the deployed measurement question. The source inventory and
its explicit initialization stay on their own page because they have different
writers, lifetimes and failure handling.

## See also

- [publication-inventory.md](publication-inventory.md) - source publication names and totals.
- [retention.md](retention.md) - alarm, cap and pruning.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - build verification and local checks.
