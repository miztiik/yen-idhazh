# Encoder readings

Taken 2026-10-09 on a GitHub `ubuntu-latest` runner: 4 processor threads, 16 GB, no graphics card.

Saved rows are not re-encoded. Each row's date, model options and task settings remain in `encoders.json`.

**Separation** is the chance this encoder scores a likely-same pair above a likely-different one. 1.0 is perfect, 0.5 is a coin toss. No difference in similarity scale can distort it.

**Spread** is how far apart the two averages sit. A wide spread leaves more room for a decision to sit between them.

**Middle lean** is the share of uncertain pairs - the ones whose titles share something but not much - that this encoder scores above the halfway mark between matching and mismatching. Nobody knows whether those pairs match, so this is never right or wrong. High means the encoder will join too much; low means it will leave one story in pieces.

**Second-piece lean** is the same reading for one outlet's second article on one subject in one day - a correction or a follow-up. Near one means this encoder cannot tell an update from a new story.

| Encoder | Numbers | Size | Separation | Spread | Same | Different | Middle | Middle lean | Second piece | Second-piece lean | Articles a second | 15,122 take | A day takes | Peak memory |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `jina-v5-nano` | 768 | 212M | **0.9961** | 0.349 | 0.886 | 0.537 | 0.740 | 0.593 | 0.881 | 0.982 | 3.5 | 72.6 min | 4.80 min | 1.91 GB |
| `gte-small` | 384 | 33M | **0.9944** | 0.196 | 0.934 | 0.738 | 0.844 | 0.539 | 0.931 | 0.971 | 90.3 | 2.8 min | 0.18 min | 1.14 GB |
| `gte-base` | 768 | 109M | **0.9943** | 0.205 | 0.929 | 0.724 | 0.834 | 0.535 | 0.925 | 0.961 | 1.2 | 202.9 min | 13.43 min | 0.97 GB |
| `minilm-l6` | 384 | 22M | **0.9925** | 0.658 | 0.760 | 0.102 | 0.462 | 0.540 | 0.746 | 0.971 | 28.6 | 8.8 min | 0.58 min | 0.87 GB |
| `gte-modernbert` | 768 | 149M | **0.9915** | 0.384 | 0.859 | 0.475 | 0.687 | 0.557 | 0.852 | 0.963 | 0.6 | 400.1 min | 26.47 min | 1.08 GB |
| `embeddinggemma-two` | 768 | 270M | **0.9905** | 0.154 | 0.917 | 0.763 | 0.848 | 0.546 | 0.919 | 0.986 | 3.0 | 85.3 min | 5.64 min | 3.3 GB |
| `bge-base` | 768 | 109M | **0.9905** | 0.384 | 0.841 | 0.457 | 0.666 | 0.537 | 0.838 | 0.973 | 5.1 | 49.6 min | 3.28 min | 1.48 GB |

Why each encoder is in the list:

- **`jina-v5-nano`** - The selected February 2026 nano encoder with its official text-matching adapter already merged. Both summaries use Document: once. The merged weights contain about 212M parameters; the multi-adapter model advertises 239M. CC-BY-NC-4.0: evaluation only, not commercial adoption.
- **`gte-small`** - The same training as gte-base at the same 384 numbers an article the current encoder uses. It asks whether gte-base's lead is its training or its size, and whether the smallest useful vector can carry it.
- **`gte-base`** - Best separation of the six measured, at 0.96 GB. The leader to beat, and the other half of the size-against-training question.
- **`minilm-l6`** - What the search surface runs today. Every other row is read as a gain or a loss against it.
- **`gte-modernbert`** - The same training again, on a newer foundation than the rest of the list. Sits within forty million parameters of gte-base, so the pair reads as a change of foundation rather than a change of size. It is the one row that asks whether anything has moved since the models here were built.
- **`embeddinggemma-two`** - The selected October 2026 encoder, loaded text-only. Both summaries use the sentence-similarity instruction. Apache-2.0; this run measures quality and CPU cost, not a production adoption.
- **`bge-base`** - The same size as gte-base from a different group. One pair at one size is what separates a training difference from a size difference.
