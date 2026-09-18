# Compressing the telemetry, against re-encoding it

**Last Updated**: 2026-09-18
Two ways to make the committed telemetry smaller, raced against each other on
the same store: gzip against ordinal encoding of its closed-vocabulary columns.

**Compression takes 9.6 times what ordinal encoding takes, off the same store,
and costs no readability.** Re-encoding every closed-vocabulary column as an
integer saves 369,855 bytes of `state/item-health/`. Compressing the same files
saves 3,551,430.

`gzip` at level 9 with `mtime=0`, **CPython 3.14.2**, three repeats per file,
identical output each time - the transform is deterministic, so the spread is
zero by construction rather than by luck. A byte count belongs to no machine, so
the runtime is the provenance and the box is not named. Retake it with
`python -c "import gzip,pathlib;b=pathlib.Path('<file>').read_bytes();print(len(b),len(gzip.compress(b,9,mtime=0)))"`.

| Subject | On disk | Compressed | Saved |
| --- | ---: | ---: | ---: |
| `state/item-health/`, 23 day files, 12,277 rows | 5,194,794 | 1,643,364 | 3,551,430, **68.4 percent** |
| its largest day, `2026/09/03.csv` | 288,766 | 93,063 | 195,703, 67.8 percent |
| `frontend/public/telemetry/2026-09.csv`, the month the console fetches | 1,186,543 | 254,252 | 932,291, 78.6 percent |
| all seven published projections, 12 files | 8,726,606 | 2,006,164 | 6,720,442, **77.0 percent** |

**The "about 80 percent" this replaces was an estimate and it was close**: 77.0
percent measured across the published projections, 79.5 percent across
`telemetry/` alone. The estimate of "11 times the ordinal" was the one that
moved - it is 9.6 times. Neither correction changes the ordering: compression is
still most of the file where the ordinal is a fifteenth of it, it needs no
legend shipped beside the data, and `grep failed` over a committed day keeps
working. An ordinal taken first would be re-encoded when compression lands.

**One published file gets bigger.** `span-rollup/` is 67 bytes and gzips to 77,
because the header costs more than the payload. Any switch has to leave a file
alone when compressing it does not pay.

## See also

- [../measurements.md](../measurements.md) - the figure this record puts in force, beside every other producer figure.
- [../documentation-structure.md](../documentation-structure.md) - what a benchmark record carries, and why a re-run replaces it.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #10, which is why every number here carries its conditions.
