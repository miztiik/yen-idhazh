# Build Inventory

**Last Updated**: 2026-10-03

How does the Pages cap measure every deployed byte without discovering source history?

## Fresh output, then one named reading

`npm run build` captures its input identity before compilation. That start step
removes the previous generated `frontend/build/`, its completion record and
`frontend/build.publication.json`. Source files and committed data are not removed.
Adapter-static then creates this run's output.

The completion hook first checks that compilation used unchanged inputs and
that both static and preview output exist. It invokes
`python -m idhazh.build_publication --tree frontend/build` with the backend on
the Python path. The hook uses `IDHAZH_PYTHON` when set, otherwise `python`.
An inventory failure fails the build without writing a completion record.
A missing start record or changed inputs cannot certify old output.

The writer walks only this freshly generated output directory. It measures
every regular file: generated HTML and JavaScript, drawings, projected digests,
static assets, copied ledger files and ledger indexes. A symlink fails the build.
For each dated `digest.json`, it checks the UTC date against the path and counts
the projected item list. A missing list or unreadable digest fails explicitly.

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

The build owns this directory, so its writer can enumerate the run it just
created. Later readers ask only for the named inventory. No additional persisted
shape or version migration is needed: the existing entry and total semantics
are unchanged, and this generated artifact is replaced on every build.

This page answers the deployed measurement question. The source inventory and
its explicit initialization stay on their own page because they have different
writers, lifetimes and failure handling.

## See also

- [publication-inventory.md](publication-inventory.md) - source publication names and totals.
- [retention.md](retention.md) - alarm, cap and pruning.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - build verification and local checks.
