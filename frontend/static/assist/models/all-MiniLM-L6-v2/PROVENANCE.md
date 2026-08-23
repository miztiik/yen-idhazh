# all-MiniLM-L6-v2 (quantised ONNX)

**Last Updated**: 2026-08-22

The sentence encoder this project commits and serves from its own origin.

| | |
| --- | --- |
| Upstream | `Xenova/all-MiniLM-L6-v2` on Hugging Face |
| Derived from | `sentence-transformers/all-MiniLM-L6-v2` |
| Licence | Apache-2.0 |
| Fetched | 2026-08-22 |
| Files | `onnx/model_quantized.onnx` (22,972,370 bytes), `tokenizer.json` (711,661 bytes), plus three small config files |
| Output width | 384 dimensions, mean-pooled, L2-normalised |
| Input limit | 256 tokens; longer text is truncated, never refused |

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

- [`../../../../../docs/architecture/publishing/visuals.md`](../../../../../docs/architecture/publishing/visuals.md) - the other build-time renderer.
- [`../../../../../CLAUDE.md`](../../../../../CLAUDE.md) - Rule #1 and section 0a.
