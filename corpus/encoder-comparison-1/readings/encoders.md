# Encoder readings

Taken 2026-10-08 on a GitHub `ubuntu-latest` runner: 4 processor threads, 16 GB, no graphics card.

**Separation** is the chance this encoder scores a likely-same pair above a likely-different one. 1.0 is perfect, 0.5 is a coin toss. No difference in similarity scale can distort it.

**Spread** is how far apart the two averages sit. A wide spread leaves more room for a decision to sit between them.

**Middle lean** is the share of uncertain pairs - the ones whose titles share something but not much - that this encoder scores above the halfway mark between matching and mismatching. Nobody knows whether those pairs match, so this is never right or wrong. High means the encoder will join too much; low means it will leave one story in pieces.

| Encoder | Numbers | Size | Separation | Spread | Same | Different | Middle | Middle lean | Articles a second | 15,122 take | A day takes | Peak memory |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `gte-base` | 768 | 109M | **0.9942** | 0.205 | 0.929 | 0.724 | 0.834 | 0.535 | 8.4 | 29.9 min | 0.67 min | 1.56 GB |
| `minilm-l6` | 384 | 22M | **0.9925** | 0.658 | 0.760 | 0.102 | 0.462 | 0.540 | 28.0 | 9.0 min | 0.20 min | 0.88 GB |
| `e5-base` | 768 | 109M | **0.9910** | 0.167 | 0.903 | 0.736 | 0.826 | 0.515 | 4.5 | 55.7 min | 1.24 min | 1.44 GB |
| `bge-base` | 768 | 109M | **0.9905** | 0.384 | 0.841 | 0.457 | 0.666 | 0.537 | 4.6 | 55.2 min | 1.23 min | 1.54 GB |
| `bge-large` | | | encoding 6144/10553 | | | | | | | | | |
| `mxbai-large` | | | encoding 1024/10553 | | | | | | | | | |
| `bge-m3` | | | encoding 5120/10553 | | | | | | | | | |
| `qwen3-embedding-0.6b` | | | did not report  | | | | | | | | | |

Why each encoder is in the list:

- **`gte-base`** - Same size as bge-base, trained differently. The pair proves whether size or training is doing the work.
- **`minilm-l6`** - What the search surface runs today. Every other row is read as a gain or a loss against it.
- **`e5-base`** - Third model at the same size. It needs a prefix on its input, and leaving it off costs quality silently, so the run proves the prefix as well as the model.
- **`bge-base`** - A widely used mid-sized English model. Packs unrelated pairs close together, which costs a fixed cut-off and not a rank score.
- **`bge-large`** - Three times bge-base. The question is whether the extra time fits the job.
- **`mxbai-large`** - Same size as bge-large, trained differently. It repeats the size-against-training control at the large end, where one pair alone would leave it untested.
- **`bge-m3`** - The one with a different shape: a meaning vector and a weight for every word from one pass, which is two channels from one model. Carries languages this corpus never uses.
- **`qwen3-embedding-0.6b`** - The most recent design in the list. Its vector can be cut short without encoding again, so a smaller form costs nothing extra to measure.
