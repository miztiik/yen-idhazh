# Chrome: what a host prints on every page, and how a run learns it

**Last Updated**: 2026-09-17

This page owns one question: how does a run know that a page it just fetched is
mostly the host's own furniture rather than an article? It owns the store that
answers it - `state/chrome.csv` - the reduction that decides what two printings
of a line have in common, the counts, the bound, and where the answer is used.

It does not own what happens next. Whether a page that fails this test still
publishes is `extract.reject_boilerplate`, which is false, and
[sources/item-health.md](../sources/item-health.md) owns what the resulting cell
means.

## The problem

`extract.boilerplate_ratio` has been in the tree since the extractor was
written. It takes an article's lines and a set of lines seen on that host's
other pages, and returns the share that appear in both. Nothing ever passed the
second argument. It divided by an empty set and returned 0.0 on every page this
pipeline has ever fetched - **zero `boilerplate` cells in 12,277 committed
item-health rows**.

So a host that serves a navigation template where an article should be was
caught by `too_short` if the template was small, and not at all if it was not.
The signal was not wrong. It had one side of a comparison.

## What is stored

One row per host and line, in `state/chrome.csv`, under
[`backend/idhazh/contracts/chrome_line.py`](../../../backend/idhazh/contracts/chrome_line.py).

| Column | Holds |
| --- | --- |
| `host` | the registrable host of the page's canonical address, lowercased, `www.` dropped |
| `line_rule` | which reduction produced the hash |
| `line_hash` | the reduced line, as a sha256 |
| `pages_seen` | how many DISTINCT pages of this host have carried it |
| `first_seen` | the published day it was first counted on |
| `last_seen` | the published day it was last counted on |

**Only hashes.** A line is fetched text. It is reduced, hashed and counted; the
text itself never reaches a file, a log line or a name, so nothing in this store
can carry an instruction a page tried to give us (Guardrail #11). A sha256 is
also the only form in which storing it is cheap: the store answers one question -
have we seen this exact line before - and a hash answers it as well as the line.

**The grain is the host, never the feed.** Chrome belongs to the server
template. Several of our feeds are one broadcaster and two are one paper, so
keying on the feed would split one template's evidence across several rows and
count each page once - the same mistake the outlet rule already repaired for
grouping. It is also the whole host rather than the registrable domain: two
newsrooms on one publisher's platform run two templates, and folding them would
let one paper's furniture mark the other paper's articles as chrome.

## The reduction

`chrome.reduce_line` is compatibility-normalised (NFKC), case-folded, then
whitespace-collapsed and stripped. The same three steps `assemble.story_key`
applies to a headline, and for the same reason: a template that renders one
non-breaking space differently on two pages is one template. A raw string
comparison read `Subscribe  now` and `Subscribe\u00a0now` as two different
lines, so a host that renders its own furniture inconsistently was invisible
however many pages it printed.

**`line_rule` is a column and not a comment.** The reduction decides what two
lines have to share, so changing it makes every stored hash mean something else.
A read filters to the rule it computes with, which turns a changed normaliser
into rows that age out - and the alternative is worse than it sounds: rows that
silently never match read as "this host prints nothing twice", which is the
answer a clean host gives.

## Who counts and who reads

**`assemble` folds.** The question is how many DISTINCT pages of a host carried
one line, and a work shard sees `index % shards` of the day - so eight shards
would each answer a fraction of it, and eight partial answers would race into
one file through a `merge=union` that cannot add numbers. The assemble stage is
the one place a day's whole item set exists.

It folds every article the day fetched, not only the ones that published. A page
that degraded is exactly where a template shows through, so dropping those would
throw away the evidence the signal is for.

**`stages.common._fetch_one` reads.** It passes the host's line set into the
`seen_elsewhere` parameter `extract.to_article_with_source` has always had.
`backend/idhazh/extract.py` gained one line for this: it hashes each line before
comparing. A shard loads the store once, because what a host prints on every
page cannot change inside a shard.

A line is withheld from that set until `extract.chrome_pages_min` distinct pages
have carried it - three by default. Two pages sharing a sentence is a wire story,
which happens every day; three is a template. The line is still stored under
three, because the count has to climb somehow.

## What bounds the file

Two caps and an eviction order, all three in `config/idhazh.json`.

| Knob | Default | What it bounds |
| --- | --- | --- |
| `extract.chrome_lines_per_host_max` | 200 | lines one host may keep |
| `extract.chrome_forget_days` | 90 | days a line is kept after the last page carried it |
| `extract.chrome_pages_min` | 3 | pages before a line counts as chrome |

The file is therefore bounded by hosts times `chrome_lines_per_host_max`. It
grows with the source registry and then stops - never with the archive
(Guardrail #12). `state/traces/` is the precedent.

**200 is an estimate and is labelled one** (Guardrail #10). A page template is
tens of lines rather than hundreds, so this is several times the largest one we
expect. What would overturn it is a host whose kept lines sit at the cap while
its page count still climbs; the prune's own log line prints both numbers.

**The eviction order is load-bearing and it is not recency.** A host over its cap
gives up the line seen on the FEWEST pages first, and the oldest `last_seen`
breaks the tie. Evicting the newest would throw away the template and keep the
coincidences. Evicting by recency alone would throw away the chrome that the very
articles being compared against it are printing - the store would run coldest
exactly where it is most useful.

`stages.prune_state._prune_chrome_lines` is what makes the bound real. The fold
caps each host on the way in, but a `merge=union` can put back a line a fold
evicted, and nothing in the fold removes a line whose host rebuilt its template.
Both are the prune's job, and it runs after the day is committed, so the worst a
failure costs is one run's worth of rows.

## Design rationale

**The one ledger that rewrites.** Every other file under `state/` appends,
because every other row is a fact about a run and a run that ran twice did happen
twice. A chrome row is not that shape: it is one running count, so a second row
is the same fact with a bigger number and appending them would make a reader add
a count to itself.

Rewriting a `merge=union` file has a cost, and it is paid rather than hidden. Two
runs whose folds differ leave both lines in the merged file. `CHROME_LINE_KEY`
plus `ledger._chrome_line_rule` settle them afterwards by keeping the larger
count - a fold that counted more pages read more of the archive, so it is a
superset rather than a contradiction. What that settlement cannot undo is an
eviction, which is why the prune re-applies the cap rather than trusting the
fold.

**No day or month layout.** Chrome learned in August is chrome in September, so
every partition would be opened on every read and the walk would buy a directory
listing and nothing else.

**One file, and the read carries no clock.** A window in days would forget a
template that is still on the page. What keeps the read cheap is the cap, not a
cutoff.

## See also

- [../sources/item-health.md](../sources/item-health.md) - what a `boilerplate` cell means, and why it counts against the source now.
- [../contracts/schemas.md](../contracts/schemas.md) - the contract subsystem and the drift gate over the generated schema.
- [../../concepts/growing-reads.md](../../concepts/growing-reads.md) - what a read over a growing collection has to declare.
- [../../concepts/config.md](../../concepts/config.md) - every knob, including the three above.
- [../publishing/retention.md](../publishing/retention.md) - the prune inventory this store joined.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #10 (measure, and label an estimate), Guardrail #11 (fetched text is data), Guardrail #12 (growth must not become recurring work).
