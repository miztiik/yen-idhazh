# Icon provenance

**Last Updated**: 2026-10-08

## Source

[Lucide](https://lucide.dev), version `0.544.0` of `lucide-static`, downloaded 2026-08-29.

## Licence

ISC. Lucide is a fork of Feather Icons; the ISC licence text ships with the
upstream package and permits use, copying and modification with the copyright
notice retained.

```
Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of
Feather (MIT). All other copyright (c) for Lucide are held by Lucide Contributors
2022.
```

## What is committed

The explorer's three further chart choices use unmodified Lucide 0.544.0 sources:
`shape-side-by-side` from Lucide `align-start-vertical`, SHA-256 is `c5263b3a6c487881926ca3e54bc99d6f6078c3e5ed747b436919a3b15ea7a97a`;
`shape-days` from Lucide `calendar-check`, SHA-256 is `397142a6dac44158ef3dee0c575c2a81527c416a1222d87ee2ec870c96a3d110`;
`shape-flow` from Lucide `split`, SHA-256 is `ff1bca7cff2e92d35251d641fe1e36eb5c0393f5a96e0878bfd8d633ba4cdd84`.

Only the icons in use, as unmodified source SVG, under `svg/`. Data explorer added `query-run` from Lucide `play`, `list-refresh` from `refresh-cw`, `sort-ascending` from `arrow-up`, `sort-descending` from `arrow-down`, `copy` from `copy`, `saved` from `bookmark`, `forget` from `x`, `history` from `history`, `share-link` from `link`, `shape-series` from `chart-line`, `shape-ranked` from `chart-bar`, `shape-distribution` from `chart-column`, `shape-scatter` from `chart-scatter` and `docs` from `book-open`. The upstream
package is NOT a dependency: it was installed once to extract these files and
removed. Data explorer density added `ledgers` from Lucide `database`,
`query-editor` from `square-terminal` and `column-list` from `columns-3`.
The Data explorer's column pills added `choice-list` from Lucide `chevron-down`,
the mark at a pill's end that says the pill opens a list; the unmodified file's
SHA-256 is `547c967aba14e42e708e9635cac3cd98282b513e89ac18d87d0c07db3e2748da`.
Measured 2026-10-08: 35 files, 4,251 B of marks, against the 40 KB budget in the rows
that added them.

Each file keeps Lucide's own geometry, its 24-unit box and its `currentColor`
stroke. The filename is a semantic id this project chose - `topic-ai`, not
`cpu` - because the page names what a mark means, never what it looks like.

## How a new icon is added

1. Take the SVG from Lucide, unmodified, into `svg/<semantic-id>.svg`.
2. Run `npm run build:icons`. `generated.ts` and `manifest.json` are outputs and
   are never hand-edited.
3. Use it. `icons.spec.ts` fails on an icon nothing references and on a
   reference to an icon that does not exist, so a set cannot rot in either
   direction.
