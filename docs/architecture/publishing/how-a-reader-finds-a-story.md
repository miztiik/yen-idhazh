# How a reader finds a story

**Last Updated**: 2026-11-10

How the archive answers a submitted question, and how a day page filters its own
stories. Both use the same published vectors and on-device encoder; their
interaction and date coverage are deliberately different.

## The archive lists stories, and fetches them a month at a time

The archive has one heading, "Search our archives", one form and one answer
list. On a wide screen the field, Dates disclosure and Search button share a
row. On a phone the field and Search stay together and Dates follows below.
Dates and Search pair their visible labels with shared calendar and search
glyphs. The field's X control is labelled "Clear search" for assistive
technology and is attached to the field, not to the result heading.

The archive uses the home's full-width frame and configured gutters. Story text
keeps the shared prose measure rather than stretching with the search controls.

Typing edits a draft. Search or Enter applies the question and both UTC date
bounds together. Editing a draft does not discard the current answer or replace
the input node. The native From and To fields are inclusive; leaving one empty
leaves that end open. Equal dates select a day without navigating elsewhere.
Clear dates edits the draft; Search applies it. Clearing the query restores
date-constrained browsing in the same list.

The initial list shows recent stories inside `ui.archive_window_days`, measured
from the newest registered publication date, and adds
`ui.archive_page_size` stories per request. A browse action opens at most
`assist.search_months` metadata files. It does not walk older files merely to
fill a sparse page; the reader may explicitly ask for more.

The page does not load historical day payloads at build time to count topics
or construct a calendar. It carries the month names from the named publication
inventory and the newest registered date. There are no topic pills, date
inventory, totals, retention paragraph or archive footer. Other routes keep
their shared footer.

`ui.archive_top_viewports` controls how far a reader scrolls before a lower-right
Top button appears. It respects safe-area insets, returns keyboard focus to the
page heading and avoids smooth scrolling when reduced motion is requested.

## Search reads the same month index, and says how far back it read

The assembler writes `assist/index/<YYYY-MM>.json` and its sibling vector
file from that month's published day payloads. Normal publishing rebuilds the
affected month, not a second archive-wide index. The month-shard contract and
encoder identity checks remain unchanged.

Archive search selects existing month names from the requested dates before
fetching. `assist.archive_search_months` is its explicit coverage:
`-1` means every registered month in range; a positive value limits it to that
many newest eligible months. Day search retains its independent
`assist.search_months` and `assist.search_min_days` settings.

An all-history query deliberately transfers and examines history-sized data.
It is not a constant-cost query. The browser reads and ranks one month at a
time, retaining the query vector and only the best
`assist.result_limit` hits between months. It does not hold a second global
vector index. Archive reads bypass the page-lifetime month cache and revalidate
the published files on the next submitted query. The registered month list is
the page's publication snapshot; a reload discovers newly published months.

Date eligibility is applied before scoring and before each result cap.
Per-month answers are merged with the existing cosine ordering: highest score,
then newest publication date, then item identity. This produces the same
top results as scoring all eligible stored vectors together. It does not
change the model, quantization, similarity floor or relevance guarantees.

Only result days are fetched for summaries and source links. Until a day
arrives, or if it cannot be read, the indexed title and dated story link remain.
The query never builds a URL, path, selector or markup.

## The search box is a field, and one click is the whole gesture

The field remains mounted while loading, failing and presenting an answer.
Search does not run on keystrokes. Query and date edits do not move focus,
remount the control or replace the answer before submission.

Keyboard focus on the query outlines the complete field, including its reserved
X space, not the nested text input. The X action retains its own visible focus
indicator. Neither focus nor typing changes the controls' geometry.

The archive does not render download, privacy or date-instruction disclosures.
The encoder loader and its verified fallback remain unchanged; the
[encoder contract](the-on-device-encoder-and-its-vectors.md) owns their origin
and integrity requirements.

Loading exposes Stop, and a failed download exposes Try again. Stopping or
starting a later attempt makes late results ineligible to update the page.
A canceled archive scan does not request the next month.

The answer heading, applied question, result count and date range form one
compact group directly below the controls. A capped answer names its count
as closest matches, not a total, and limited coverage remains explicit. A
successful zero-match answer is an empty result list, never a fallback to unrelated
recent stories. Missing or incompatible month files are reported as incomplete
coverage. If no eligible vectors can be read because requested files failed,
search fails with retry rather than claiming no matches. A valid date with no
indexed stories is an empty answer without a model download. A missing browsing file has retry;
an empty publication inventory renders an empty page rather than throwing.

## The filter bar: topics and a field in one strip

The shared filter bar remains on day pages, not on the archive. Its topic
links are published routes and work without JavaScript. Auto-created overflow
topics use a native disclosure; configured topics remain visible.
The unboxed strip separates itself from the edition information with a rule.
Wide screens give topics two shares of the width and the field one; narrow
screens wrap topics above the field. The selected topic has an accent tint and
outline. The strip scrolls with the page so wrapped controls cannot obscure
stories.

## The day page: one field, two tiers

Typing on a day page filters its loaded title, summary and key points without
fetching index files, vectors or an encoder. Enter or `Search other days`
requests semantic search over the configured month scope. The action appears
for a non-empty query, without moving the field. A first-use download disclosure
appears as soon as the reader can submit that query. At rest there is no
instruction or status sentence; a filtered count or search state appears when
there is something to report.

An answer replaces the day's story list. The next keystroke restores local
filtering, and a return control restores the day directly. A failed or canceled
search leaves the day as the reader had filtered it. The archive's draft-only
behavior does not change this day-page contract.

Highlighting slices plain text through `markParts`; neither fetched text nor
the query becomes HTML. Semantic answers do not highlight imaginary substring
matches or expose similarity scores as confidence.

## Design rationale

The archive exists to answer one question across optional dates. A separate
calendar, topic inventory and live title-filter mode make the same field
describe several different operations. One submitted form keeps the answer
and its scope together while retaining a bounded recent list before the first
query. Existing monthly projections already contain the required vectors;
another index would introduce a second publication and freshness obligation
without being necessary for exact cosine search.

Finding a story uses the page's full width; reading its text still needs a
bounded measure. A field-level query outline keeps the text and its clear
action visually connected without drawing competing focus rings.

On day pages the controls already have individual outlines, so another enclosing
card adds no meaning. Removing it keeps the edition compact without shrinking
tap targets. Query feedback and download disclosures remain below the strip.

## See also

- [the-on-device-encoder-and-its-vectors.md](the-on-device-encoder-and-its-vectors.md) - encoder identity, downloads and stored vectors.
- [what-a-month-shard-holds-and-how-it-reaches-a-browser.md](what-a-month-shard-holds-and-how-it-reaches-a-browser.md) - the existing month projection.
- [../../concepts/config/appearance.md](../../concepts/config/appearance.md) - schema-validated appearance and search controls.
- [../../concepts/design-system.md](../../concepts/design-system.md) - shared controls, states and typography.
