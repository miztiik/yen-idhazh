# How to analyze a pipeline artifact

**Last Updated**: 2026-09-18

How to find out what the model was asked about one story, what it answered, what
that cost, and whether the summary it wrote is any good.

The run records each model call's rendered prompt and raw reply to the
`captures-<shard>` artifact. `backend/utilities/pipeline_artifact_analyzer.py`
turns one item's calls into a markdown document. Read that document, not the
capture files: one capture is a single JSON object holding a 15,000-character
prompt on one line, so a text editor shows a wall.

**Two workflows write captures.** `digest.yml` writes one per call per item, for
90 days. `validate.yml` writes one per call per item **per repeat**, for 30 days,
because a qualification reads each article several times - so its captures sit in
`repeat-1/`, `repeat-2/` and so on under the artifact. The analyzer walks the
tree, so pointing it at the downloaded directory finds all of them. On the pair,
the second prompt replays the first call's reply, so two repeats of one article
do not share a prompt and neither copy is redundant.

## When to run it

- A summary reads wrong and you need the article beside it.
- An item took far longer than its neighbours.
- A reply did not parse and the log said only `ValidationError`.
- Today's run differs from a run weeks ago and you need both prompts.

## Inputs

| Input | Where it comes from | Needed |
| :--- | :--- | :--- |
| A run id | `gh run list --workflow digest.yml`, or `--workflow validate.yml` for a qualification | Always |
| The `captures-<shard>` artifact | `gh run download`. 90 days from a digest run, 30 from a qualification | Always |
| The day's item-health ledger | `state/item-health/<yyyy>/<mm>/<dd>.csv`, committed | Only for a capture written before 2026-09-15 |

## Steps

1. Download every shard's captures into one directory. The tool reads the tree,
   so the per-artifact subdirectories do not matter.

   ```powershell
   gh run download <run-id> --repo miztiik/yen-idhazh --pattern 'captures-*' --dir test-results/captures/<run-id>
   ```

2. List every item, to pick the one worth opening. Add `--health` and the
   columns fill with what each item cost.

   ```powershell
   python backend/utilities/pipeline_artifact_analyzer.py test-results/captures/<run-id> --health state/item-health/<yyyy>/<mm>/<dd>.csv
   ```

3. Write one item's document. `--item` takes any part of an item id.

   ```powershell
   python backend/utilities/pipeline_artifact_analyzer.py test-results/captures/<run-id> --item <part-of-an-item-id> --health state/item-health/<yyyy>/<mm>/<dd>.csv --out report.md
   ```

4. Read the document top to bottom. It is numbered in the order the questions
   get asked, not the order the run produced them.

| Section | What it answers |
| :--- | :--- |
| 1. The story these calls read | The canonical link, the outlet, the article and summary word counts, how the item ended, which run and shard |
| 2. What to look at | Only what is wrong. Empty means nothing is |
| 3. What the calls cost | One row a call: the server's own clock, tokens in, tokens the cache answered, tokens really read, tokens out, decode rate, stop reason. Then what the cache saved, then the summary's share of the decode against the picture's |
| 4 and 5. What each call sent back | Each reply parsed into tables of what it says |
| 6. The raw text | Every prompt and reply whole, folded into a `<details>` block |

5. To judge the summary, open the link in section 1 and read section 5 beside
   it. That is the only check that settles it; nothing inside the document can.

## Options

| Flag | What it does |
| :--- | :--- |
| `--item <id>` | Any part of an item id. Omit to list every item |
| `--health <csv>` | The day's item-health ledger, for a capture that carries no cost or link of its own |
| `--out <path>` | Write markdown to a file instead of the terminal |
| `--head N` | Keep only the first N characters of each raw block. Everything is printed by default |
| `--tail N` | Characters kept from the back when `--head` is set |

## When it does not work

| What you see | What it means |
| :--- | :--- |
| `holds no capture files` | The run had `logging.capture_prompts` and `logging.capture_replies` both off, so the upload was a green no-op |
| `No call in this pair recorded what it cost` | A capture written before 2026-09-15. Pass `--health` |
| `This capture does not say which story it was about` | The same. Pass `--health` |
| `the prompt was not captured` on a call | One flag was off for that run |
| `This reply cannot be read as JSON` | That is the finding, and section 6 has the bytes. The message names the character it broke at |

## See also

- [../reference/github-actions.md](../reference/github-actions.md) - every artifact a run leaves, how long each is kept, and the platform limits behind those windows.
- [../architecture/sources/item-health.md](../architecture/sources/item-health.md) - the ledger `--health` reads, column by column.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - what the two calls ask for, and why in that order.
- [../../CLAUDE.md](../../CLAUDE.md) - section 0a on why a rendered prompt is never committed, Guardrail #11 on fetched text.
