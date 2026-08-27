# Label the Faithfulness Queue

**Last Updated**: 2026-08-27

Read sixty summaries against the articles they came from, and record whether each
one asserts something the article does not support. This is the only instrument
that says what the `high`, `medium` and `low` bands mean to a person. Until it
has rows, the band cuts at 0.80 and 0.50 are a promise nobody has checked
(`CLAUDE.md` Rule #10).

You need the article text. The committed ledger does not have it: `state/scores.csv`
records a digest of the article and a digest of the summary and neither text.
The text comes from an **evidence package**, which one run writes and which is
never committed.

## Get an evidence package

Two ways in. They produce the same thing.

### A day CI produced

The work job uploads one artifact per shard, named `evidence-0` .. `evidence-N`,
kept for **14 days**. After that the day is gone and cannot be relabelled.

1. Find the run: `gh run list --workflow digest.yml --repo <owner>/<repo>`.
2. Download every evidence artifact into one directory:

   ```bash
   gh run download <run-id> --repo <owner>/<repo> --pattern 'evidence-*' --dir /tmp/evidence
   ```

   One directory per shard is fine. The tool reads the whole tree.

### A day you ran yourself

Run the pipeline as [run-the-pipeline.md](run-the-pipeline.md) describes, with
faithfulness scoring on. `work` writes the package to
`backend/var/evidence/<date>/` as it scores, and that is the default the tool
reads, so nothing needs to be downloaded or named.

## Draw the queue

Read-only. Anybody can run it and it cannot write a label:

```bash
python backend/utilities/label_queue.py
```

It prints what the ledger holds, then what the package can show:

```text
------------------------------------------------------------------------
scorer_version   hhem-2.1-open@8e4a2e6e;weights-841b70e0;metrics-3;bands=0.80/0.50;lead=0.30
eligible rows    116
run-days         1 of 10 -> 2026-08-26
fingerprints     1
drawn            38 of 60
------------------------------------------------------------------------
evidence         backend/var/evidence -> 0 file(s)
labellable       0 of 38
  38 skipped: this row was scored before the run recorded which text it read, so
  nothing here can prove an article is that text
```

Pass `--evidence /tmp/evidence` to read a downloaded package instead.

`labellable` is the number that matters. If it is 0, the package is missing, or
it belongs to a different day, or the draw is entirely rows scored before
2026-08-27 - which is every row the ledger held on that date.

## Label

```bash
python backend/utilities/label_queue.py --evidence /tmp/evidence --label --labeller <your-name>
```

Your name must already be in `evaluation.labellers` in `config/idhazh.json`. One
row at a time, one keystroke per row:

```text
------------------------------------------------------------------------
[7/38]  2026-08-27  https://blog.example-lab.org/2026/08/model-release
------------------------------------------------------------------------
Source headline: Example Lab releases a smaller model

THE ARTICLE, as the scorer read it
Example Lab published a smaller model today and said inference cost fell by
about a third against the model it replaces. ...

OUR SUMMARY
Example Lab released a smaller model, claiming a 34 percent lower cost per
million tokens and 2.1x the throughput of the model it replaces on commodity
CPUs. ...

Does this assert anything the article does not support?
  [y] yes   [n] no   [s] skip   [q] stop
```

Answer against the article on the screen, not against the link. The link is
there for one question only: is this text the article at all, or did the
extractor grab a navigation menu? That case has its own tag,
`not_the_article`.

`q` stops and keeps everything already written. Rows land in `state/labels.csv`,
which is committed.

## When a row is refused

A refused row prints its reason and asks nothing, so no keystroke can record a
verdict on text nobody saw:

```text
NOT LABELLABLE: this row was scored before the run recorded which text it read,
so nothing here can prove an article is that text.
Nothing recorded for this row.
```

| What it says | What happened | What to do |
| --- | --- | --- |
| scored before the run recorded which text it read | The row predates 2026-08-27 and no run wrote its premise down | Nothing. Label a newer day |
| this package holds no evidence for this measurement | Wrong package, or the artifact expired | Download the package for that row's date |
| its text was changed | The file no longer matches its own digest | Re-download. Do not edit an evidence file |
| a different premise from the one the ledger row was scored on | The package and the ledger disagree about what was read | Report it. This is a real defect, not a labelling problem |

## Why the text comes from the package and never from the URL

The scorer read the article after extraction, sanitizing and the truncation cap,
not the page as it stands today. Fetching the address again returns a
different document, because the page moves, the extractor changes and the cap
changes. Then the person and the scorer are answering questions about two
documents, and the disagreement measures that instead of scorer error. So the
tool checks the text against the digest the eval row carries and refuses on a
mismatch.

## Why 14 days and not longer

One evidence file is the article, the summary, and about 700 bytes naming the
measurement. Measured on 2026-08-27 against the committed ledger and the
committed digest payloads (2,237 published summaries, 227,653 words, 6.85
characters per word):

| Day | Items | Package |
| --- | --- | --- |
| 2026-08-24 | 731 | 4.63 MB |
| 2026-08-25 | 724 | 4.55 MB |
| 2026-08-26 | 621 | 3.90 MB |

The busiest day on record costs 4.63 MB, so 14 days of retention costs 64.8 MB
against the 500 MB artifact budget - 13 percent of it, and that assumes every one
of the 14 days is the biggest day ever recorded (`CLAUDE.md` Rule #2). The
ceiling would not be reached until 108 days.

Longer is not free in a different currency. The package holds somebody else's
article text, and this project does not republish article bodies
(`CLAUDE.md` section 0a). A finite retention is what keeps a local copy local.
Fourteen days is an evening of a person's time plus a fortnight to find it;
one day, which every other artifact in the workflow uses, is not a window at all.

## See also

- [../concepts/evaluation.md](../concepts/evaluation.md) - how a summary is scored and what the bands mean.
- [run-the-pipeline.md](run-the-pipeline.md) - producing a day locally.
- [../reference/repository-layout.md](../reference/repository-layout.md) - why the evidence sits under `backend/var/` and the labels sit under `state/`.
