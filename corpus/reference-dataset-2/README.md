# Reference dataset 2

**Built**: 2026-09-13
**State**: step 4 of 12. The URL list is snapshotted and the manifest is built. Nothing is fetched yet.

A collection built from a URL list supplied by hand, not drawn from what this
pipeline published. It exists so that the article classifier can later be run
over a balanced sample of outlets this project does not already read.

This is the datasheet. [`TODO/20260913-reference-dataset-2-plan.md`](../../TODO/20260913-reference-dataset-2-plan.md)
is the plan that builds it.

**It is not [`reference-dataset-1/`](../reference-dataset-1/README.md).** That is
the frozen hand-label set drawn from the digest archive, with its own rows,
splits and article files. The two are numbered siblings and separate
collections. Nothing here reads or writes that one.

## What it is

| | |
| --- | --- |
| Built by | `backend/utilities/build_reference_dataset.py`, run by hand |
| Drawn from | a supplied URL list, snapshotted here as `urls.txt` |
| Settings | `config.json` in this directory, and nowhere else |
| Manifest | `manifest.json`, one record per input URL line, with `manifest.meta.json` beside it |
| Article text | `extractions/<run-id>/articles.json`, one result per manifest record |
| Samples | `selections/<selection-id>/urls.json`, one directory per selection |
| Labels | none. This collection carries no label, desk or model verdict |

## What is in it today

Measured 2026-09-13 by `build_reference_dataset.py import-urls`, read back off the
files it wrote.

| | Count |
| --- | ---: |
| Input lines | 1,661 |
| Manifest rows | 1,661 |
| Unique identities | 1,661 |
| Equivalent addresses | 0 |
| Invalid lines | 0 |
| Hosts | 55 |
| Publishers | 55 |
| Registered domains | 16 |
| Publisher keys that needed lengthening | 0 |
| Rows with no vertical | 1,455 |

- `urls.txt` is **115,415 bytes**, SHA-256
  `64dc5e2787d08aae67faef31fd32b6309bf81b902edbeaf17062ca11ad54e071`, which is
  byte-identical to the supplied file. The list already used LF and carried no
  duplicate and no malformed address, so the snapshot changed nothing.
- **55 publishers against 16 registered domains** is the grouping decision doing
  its work: 1,075 of the 1,661 URLs sit under `substack.com`, and they are 40
  separate newsletters rather than one outlet.
- The five deepest publishers are `globaltimes` with 63 URLs, `semianalysis`
  with 58, `ai-supremacy` with 52, and `bengoertzel` and `chipbriefing` with 50
  each.
- No two hosts produced the same publisher key, so every key kept its short
  form.
- 55 publishers against a target of 20 URLs each is 1,100 places wanted, so the
  cap of 1,000 binds and a sample cannot give every publisher its full target.

## What it is for, and what it is not for

- It is for a balanced classification sample: a bounded number of articles per
  publisher, with the full pool kept in reserve to fill a publisher that runs
  short.
- It is **not** a training set, and it is not the held-out benchmark. Using it
  as a benchmark needs a separate overlap and source-separation check under
  [`docs/how-to/measure-a-classifier.md`](../../docs/how-to/measure-a-classifier.md).
- It publishes nothing. `corpus/` is not part of the site, and no reader-facing
  page reads this directory.
- This repository is public. Article text committed here is readable by anyone,
  which is why committing it is a decision taken per run and not a default.

## Rules the writers follow

- Every setting lives in `config.json` here. The pipeline's `config/idhazh.json`
  is not read and not changed.
- A file name comes only from a recomputed `url_key`. Fetched page text never
  supplies a path, an argument or a URL to fetch.
- `scratch/` holds resume checkpoints and trial runs. It is ignored by git and
  nothing durable depends on it.
- Saved article text is the full sanitized prose. A download stopped by its byte
  limit is a failure, not a short article.
