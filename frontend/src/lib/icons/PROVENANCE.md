# Icon provenance

**Last Updated**: 2026-08-29

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

Only the icons in use, as unmodified source SVG, under `svg/`. The upstream
package is NOT a dependency: it was installed once to extract these files and
removed. Measured 2026-08-29: 29 files, 11,980 B, against the 40 KB budget in
the row that added them.

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
