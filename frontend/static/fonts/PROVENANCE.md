# Inter Variable, Latin subset

**Last Updated**: 2026-08-29

The display face. Headings only - the body keeps the system stack, because the
system stack renders on the first frame at zero bytes and the body is what the
reader came for.

| Field | Value |
| --- | --- |
| File | `inter-latin-variable.woff2` |
| Family | Inter Variable (`InterVariable`), weight axis 100-900 |
| Subset | Latin |
| Bytes | 48,256 |
| SHA-256 | `3100e775e8616cd2611beecfa23a4263d7037586789b43f035236a2e6fbd4c62` |
| Source package | `@fontsource-variable/inter` 5.3.0 |
| Source file | `files/inter-latin-wght-normal.woff2` |
| Upstream | https://github.com/rsms/inter |
| Licence | SIL Open Font License 1.1, in `LICENSE` beside this file |
| Copied | 2026-08-29 |

## Why it is committed rather than fetched

Rule #1 as amended 2026-08-23 permits a third-party static asset, and a webfont
is judged on bytes, licence and privacy behaviour rather than on hostname. This
project self-hosts anyway, for two reasons that are not about the rule:

- The HTTP cache is partitioned per site, so the "the reader already has it from
  another site" argument has not been true for years. A CDN request is a DNS
  lookup, a connection and a round trip that a same-origin file does not need.
- `frontend/svelte.config.js` sets `default-src 'self'`. Allowing a font origin
  would widen the content-security policy for one file.

## What it costs

48,256 bytes, committed once. The published site was 128,064,853 bytes on
2026-08-27 and grows about 16.6 MB per published day, so this is **about three
tenths of one percent of a single day's growth** and does not move the 1 GB cap
date in [`docs/architecture/publishing/layout.md`](../../../docs/architecture/publishing/layout.md).

One variable file covers every weight the surface uses, which is why it is a
variable face rather than three static cuts: three cuts at this subset would be
roughly double the bytes for less range.

## How to update it

```
npm install --no-save @fontsource-variable/inter@<version>
cp node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2 \
   static/fonts/inter-latin-variable.woff2
cp node_modules/@fontsource-variable/inter/LICENSE static/fonts/LICENSE
```

Then restate the version, the byte count and the SHA-256 in the table above. The
package is installed with `--no-save` on purpose: it is a source of bytes, not a
runtime or build dependency, and CI should not pay to install it on every run.
