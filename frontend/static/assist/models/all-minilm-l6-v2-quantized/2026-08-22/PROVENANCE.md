# all-MiniLM-L6-v2 (quantised ONNX)

**Last Updated**: 2026-09-09

The sentence encoder this project commits and serves from its own origin.

| | |
| --- | --- |
| Upstream | `Xenova/all-MiniLM-L6-v2` on Hugging Face |
| Derived from | `sentence-transformers/all-MiniLM-L6-v2` |
| Licence | Apache-2.0 |
| Fetched | 2026-08-22 |
| Revision | `751bff37182d3f1213fa05d7196b954e230abad9` |
| Identifier | `all-minilm-l6-v2-quantized` - stamped into every day's `embeddings.model_id` |
| Served from | `assist/models/all-minilm-l6-v2-quantized/2026-08-22/` |
| Files | `onnx/model_quantized.onnx` (22,972,370 bytes), `tokenizer.json` (711,661 bytes), plus three small config files |
| Output width | 384 dimensions, mean-pooled, L2-normalised |
| Input limit | 256 tokens; longer text is truncated, never refused |

## The revision, and how it was checked

The revision row was blank until 2026-09-09. A date says when somebody fetched;
it does not say what they got, because `main` moves. The 40-hex commit does, and
these five files are the bytes at it - checked two ways, in
[`../../../../../../docs/reference/measurements.md`](../../../../../../docs/reference/measurements.md):
the file tree at that commit returns a git blob SHA-1 for each small file and an
LFS SHA-256 for the model, and all five equal what is committed here.

**The digests do not name one commit.** The parent commit carries the same five,
because the commit that is now the head added other ONNX variants and left the
quantised one alone. So the revision above is the head of `main` on the fetch
date rather than something derived from the bytes.

The same five files are published as a GitHub Release under the tag
`encoder-2026-08-22`. That release is a copy, not a source: a browser cannot read
a release asset cross-origin, so nothing fetches it. The tag is what earns its
keep - it holds the commit these files are committed in.

## Why the directory carries a date

The path is `<identifier>/<the date above>`, so different weights are a
different URL. A browser caches all 43 MB of this on first search. Without the
date in the path, a reader who searched last month would answer a new day's
vectors with last month's encoder, and the only symptom is worse ranking -
nothing errors, nothing 404s.

The date moves only when the weights move, because moving it makes every
returning searcher pay the whole download again.

## Why this file is in the repository

Rule #1 forbids a runtime fetch to any origin but our own. A browser that
loaded weights from a third-party hub would break that, so the weights are
committed and served beside the pages that use them.

The same file is loaded by the runner. `backend/idhazh/embed.py` runs it under
`onnxruntime` to embed the day's items; the browser runs it under
`transformers.js` to embed a reader's query. **One artifact, two runtimes.** Two
copies of the same weights agree right up until one of them is updated, and the
failure is silent - queries and items land in subtly different spaces and search
just gets worse.

## Why 384 dimensions rather than 256

The plan asked for 256. That number assumes a Matryoshka-trained encoder, whose
vectors can be truncated without losing the ranking. MiniLM is not one, so
truncating would throw away a third of the signal to save 128 bytes per item. At
int8 the full width is 384 bytes; a fifteen-item day is under 8 KB of base64
inside a payload the page already fetches.

## Why quantised

The quantised ONNX is 22.6 MB against roughly 90 MB for the float build. The
download is the reader's cost, paid once and then cached, and it is the number
stated to them before anything is fetched.

## See also

- [`../../../../../../docs/architecture/publishing/visuals.md`](../../../../../../docs/architecture/publishing/visuals.md) - the other build-time renderer.
- [`../../../../../../CLAUDE.md`](../../../../../../CLAUDE.md) - Rule #1 and section 0a.
