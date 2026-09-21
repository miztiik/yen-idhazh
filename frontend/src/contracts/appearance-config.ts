// Generated from `backend/idhazh/contracts/appearance_config.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * On-device archive search: what the encoder reads, where it comes from, what shows.
 *
 * Every value here was a literal with no override path (Guardrail #6). The first two
 * describe how much of an item the encoder is allowed to read; the five `model_`
 * keys describe where a browser may fetch the encoder and how it proves the bytes
 * are ours; the rest describe what the reader's list keeps. All of them are set
 * from measurement rather than from taste.
 *
 * **Our own origin is primary and the committed weights stay.** The `model_` keys
 * are a failover, reached only when this site cannot serve a reader the weights it
 * committed. A second origin without `model_digests` would be a permission rather
 * than a fallback, so the manifest is the load-bearing half and the URL is the
 * convenience.
 */
export interface AssistConfig {
	/** How far into an item's text the encoder reads before it truncates. 512 is the hard ceiling because that is the encoder's position table; the default is 256 because that is what the model was trained at, and almost no published item runs past it. Raising it would read a little more text and re-date every committed vector. */
	max_tokens?: number;

	/** How much of an item's alphabet the encoder has to know before the item gets a vector at all. The committed weights carry an English uncased vocabulary, so an item written in another script still produces a confident unit vector that no query can retrieve. Below this share the item gets no vector and the run records why. Half is a plain reading of 'mostly not in our alphabet', and it sits in the middle of an empty band: a published item either scores near zero or near one, so every threshold between them selects the same items. */
	min_readable_letter_share?: number;

	/** The SECOND origin a browser may fetch the encoder from, and only after our own copy has failed that reader. Our origin stays primary: the weights are committed under frontend/static/assist/models/ and every reader gets them from us. This is the failover, and it is a repository prefix rather than a bare host so the fetch is built from one value - the path in it is a directory on that host, not a permission, and frontend/asset-base.js takes only the ORIGIN into connect-src. A GitHub Release asset cannot serve this: it carries no Access-Control-Allow-Origin on any hop, so a browser refuses the fetch. Nothing here reaches the encoder as text (Guardrail #11), and no payload field, model output or fetched string builds this URL. */
	model_base_url?: string;

	/** The origins model_base_url redirects a large file to, listed because a browser checks the redirect target against connect-src and would otherwise refuse it. The small files answer on the base host; the quantized model redirects to this CDN. Listing the base host alone passes the four small files and blocks the weights, which is the worst of both - the reader waits, and then gets nothing. Kept a separate knob from model_base_url because it is the other party's delivery network rather than our fetch address, and it moves when they move it. */
	model_cdn_origins?: string[];

	/** The upstream commit the committed weights are the bytes of, as a full 40-hex SHA-1. A branch name is refused by the pattern, because a branch hands back whatever was uploaded last and a fetch built on one describes bytes nobody can fetch again (Guardrail #10). The file tree at this commit returns a git blob SHA-1 for each small file and an LFS SHA-256 for the model, all five equal to model_digests below, and every response at this revision returns it as X-Repo-Commit. It does NOT identify one commit - the parent carries the same five files - so it is the head of main on the fetch date rather than something derived from the bytes. ENCODER_VERSION in frontend/src/lib/assist/encoder.ts is the browser's copy and backend/tests/test_embed.py fails when the two differ. */
	model_revision?: string;

	/** SHA-256 of every encoder file, keyed by its path under the model directory. This is what makes reaching a second origin safe at all: the browser hashes what arrived and discards the WHOLE set on any miss - a non-200, a truncation, a timeout or a wrong digest - so provenance is never mixed across files. Without it, model_base_url would be a permission for a second party to put bytes into a reader's tab. Re-derived from the committed files and equal to what the upstream tree reports at model_revision; backend/tests/test_embed.py hashes the committed files against this map, so a manifest that drifts from the weights fails the build rather than failing closed on every reader. */
	model_digests?: Record<string, string>;

	/** How long the whole second-origin fetch may take before the browser gives up and tells the reader the download did not finish. It covers all five files together rather than each one, because a reader is waiting on the set and a per-file deadline lets four slow files add up to a wait nobody bounded. Two minutes is the download this failover exists to complete: the hub serves the quantized model uncompressed where our origin gzips it, which is seconds on a fast line and minutes on a slow one. A reader on less than that is better served by the sentence than by a spinner. */
	model_fetch_deadline_ms?: number;

	/** Cosine similarity a result must reach to be shown at all. A SELECTOR, never reported to a reader as a quality signal. It sits above where same-domain noise lands and below where right answers do, so it keeps almost every right answer and drops almost all of the noise. The noise distribution did not move when the corpus grew several times over, so the floor does not move with the archive either. Raising it cuts noise further and costs measurable recall; the readings are in docs/concepts/evaluation.md. */
	similarity_floor?: number;

	/** How many results the flat list shows. The list carries no rank cue, so this is also the denominator the recall bar is measured against - the denominator is min(right answers, this), because more right answers than slots cannot all be shown. */
	result_limit?: number;

	/** How many month shards a search always reads, newest first. The reader waits on the download, not on the arithmetic: the fetch is an order of magnitude more than the ranking at every scope, so this knob buys download seconds and never compute seconds. One month is the only scope whose first search starts inside about five seconds. This is a floor rather than a ceiling: assist.search_min_days can add one more shard when the newest one is thin. The page names the days it read, so a wider scope is a sentence a reader can see. */
	search_months?: number;

	/** The fewest days of published stories a search tries to reach. The scope is month shards, and a calendar month is not a window: on the last day of a month the newest shard holds 31 days, and on the next morning it holds one. That is 31 times less reach for a reason no reader can see, and a search that finds nothing then looks exactly like a story that was never published. When the shards search_months names cover fewer days than this, a search reads ONE more shard - one more and no more, so the cost is bounded at a single extra fetch. Seven is this knob's own number rather than one borrowed from a neighbouring window. The extra fetch fires only in the first days of a month, and only when the shard a search already reads is small, so the two shards together early in a month move about what the one shard at the end of a month already moves. The bytes are levelled across the month rather than doubled. */
	search_min_days?: number;

	/** The regression bar for recall@result_limit over the committed query set, counted over right answers that carry a vector, scored against the corpus pinned by eval_corpus_through. Coverage is excluded on purpose: an item the pipeline never embedded cannot be retrieved at any threshold, so counting it here would fail this gate for a defect in another stage. Set two standard errors below the pinned baseline, so ordinary sampling noise does not fail it. THIS BAR HAS NO EXPIRY DATE, and that is the whole point of the pin: a bar scored against a growing corpus expires on its own, whatever value it is given. Both inputs are fixed, so the number moves only when the ranking moves or the labels are completed - and completing the labels raises it rather than eroding it. It is still a LOWER BOUND: most filled slots hold an item no labeller judged either way, and every one of them is counted as a wrong answer. `config/idhazh.json` owns the value. This is a pipeline gate rather than a drawn surface: the one reader is `backend/tests/test_retrieval_eval.py`, and the frontend's own `AssistConfig` does not declare the field at all. See docs/concepts/evaluation.md. */
	recall_min?: number;

	/** The last published day the retrieval gate scores against, as YYYY-MM-DD. Set to the day the label set was pooled, so the gate's competitor set is the one the labellers saw. THIS IS THE FIX FOR A GATE THAT EXPIRES. Scored against the live archive, recall@10 measures two things at once: the ranking, and how many stories were published since the labels were written. Only the first is something a merge candidate can change. The second is unbounded and monotone - the result list holds a fixed number of slots and every new item that outranks a gold item evicts it - so the numerator erodes while the denominator, min(gold_with_vector, slots), does not move at all. A few publishing days are then enough to move the instrument as far as the effect the gate exists to catch, with no code change at all. Pinned, the drift term is zero and recall_min measures ranking. Null reads the whole archive, which is what the printed diagnostic beside the gate reports, because that number is what a reader actually gets. The reasoning is in docs/concepts/evaluation.md. */
	eval_corpus_through?: string | null;
}

/** How a chart is drawn, and what it does when a pointer reaches it. */
export interface ChartConfig {
	/** The drawn height of a standard console chart, in CSS pixels. Raised from 180 when the frame widened: a chart that grows only in one dimension flattens its own signal. */
	height_px?: number;

	/** The width a chart is drawn at on the SERVER, in CSS pixels. A prerendered chart has no element to measure, so this is what the page ships complete at; the client re-measures and redraws once a script runs. It must track the console frame - set it far below what the container gives and the chart visibly snaps on first paint. */
	width_px?: number;

	/** Whether a pointer, a tap or an arrow key over a chart names the value it is nearest, in words. The readout is additive: it may never be the only place a fact appears, and every value it shows is also derivable from the axis - which is what keeps the old rule against tooltips carrying critical information intact while still answering 'what is that bar'. */
	hover_readout?: boolean;

	/** The widest the readout strip under a plot may be, as a share of that plot. The strip sits below the plot rather than over it, so it cannot cover a mark at any width; the cap is what stops it becoming a paragraph beside a chart a reader is glancing at. Measured 2026-08-29, the floating box this replaced covered 88 to 121px of a 220px plot - 40 to 55 percent of the chart it was explaining. */
	readout_max_share?: number;

	/** Which ramp a chart draws from. Never the confidence ramp. */
	palette?: ChartPalette;

	/** The MOST date labels a chart's day axis may carry. A ceiling and never a target: the axis then measures the labels against the room the plot actually has and drops more of them until no two touch. A count alone cannot hold at two widths - measured 2026-08-31 at 390px, six labels over a thirty-day window overlapped by 13.6px. Every column this number allows keeps its tick mark whether or not its date survived, because a reader counting columns needs the grid. */
	tick_density?: number;

	/** A sparkline inside a card. Direction at a glance, no axis. The ceiling is below `height_px`'s floor of 120 on purpose, so a sparkline can never be configured taller than a chart - the bound does the work a cross-field validator would, and a validator that cannot fire is worse than none. */
	sparkline_height_px?: number;

	/** The stroke of a donut gauge. Thin enough that the hole carries the number, thick enough that the arc is the thing the eye lands on. */
	donut_thickness_px?: number;
}

/**
 * Which categorical ramp a chart draws from.
 *
 * Never the confidence ramp. `design-system.md` records the chart that
 * borrowed the band tokens and told a reader the slowest stage was the
 * failing one; both ramps here are green-free, amber-free and red-free for
 * that reason.
 */
export const CHART_PALETTE = ['categorical', 'sequential'] as const;

export type ChartPalette = (typeof CHART_PALETTE)[number];

/** Knobs for the operator console's time viewport. */
export interface ConsoleConfig {
	/** Initial time span for the console charts. A viewport, not a deletion. Thirty rather than fourteen because the page states its own retirement rules over fourteen days, so a window equal to the rule shows the rule with no margin either side of it. */
	default_window_days?: number;

	/** The day counts the console's window control offers, ascending and distinct. A short list rather than a slider: every value is a distinct fetch cost, because a wider window pulls more month files, and most values in between are indistinguishable on the page. `default_window_days` must be one of them, or the console would open on a window its own control cannot name. One day is the narrowest read the console can offer - one month file, and the run that has just finished - and it is the setting an operator wants when a run has gone wrong and the surrounding month is noise around it. It is also the only preset a reader can pick that reads no history at all. */
	window_presets?: number[];

	/** Where today sits in the initial viewport when enough history exists. */
	today_anchor?: TodayAnchor;

	/** Days moved by one arrow-key pan. */
	pan_days?: number;

	zoom_factor?: number;

	/** The narrowest span a preset may name. One, because the preset list offers a single day and a floor above it would refuse the list. It bounds the presets and nothing else - a reader sets the span through them and through no other control. */
	min_window_days?: number;

	/** The widest span a preset may name, and through that the oldest month shard the pipeline may delete. It is a retention floor rather than a viewport clamp: the preset radio buttons are the only span control a reader can reach, so no page is held to this number and `observability` is - `AppConfig` refuses a cleanup age shorter than the months a window this wide can touch. Lowering it therefore does not make any page cheaper; it authorises deleting shards the console can still ask for, and a deleted shard draws as a gap that reads like a day the pipeline did nothing. Three hundred and sixty-six is a leap year, so a full year of history stays readable on every date. */
	max_window_days?: number;

	/** Below this count a rate is outlined because the denominator is thin. */
	min_attempts_for_rate?: number;

	/** How many times assemble.same_story.adaptive_dedup_threshold.discard_share the precision axis reaches. The fit places the line so that the discard share of judged two-story pairs stays above it, so 1 percent is where the line should hover; ten times that shows the target and a tenfold overshoot on one fixed scale. A value past the top is clamped at the top and printed in the readout, because the worst day is the one a hidden mark would cost. */
	precision_axis_multiple?: number;

	/** The drawn height of a console chart, in CSS pixels. The same number `chart.height_px` carries: both were raised from 180 when the frame widened, because a chart that grows in one dimension only flattens its own signal. `config/appearance.json` owns the value, as `console.chart_height`. */
	chart_height?: number;

	/** The width a console chart is drawn at on the server, in CSS pixels. A prerendered chart has no element to measure, and a chart drawn in arbitrary units and then stretched by its viewBox renders its labels at whatever the stretch factor happens to be - measured 2026-08-25, one page put the same font-size at 4.5px and at 16.6px. It is a seed rather than the final width: the client re-measures its container once a script runs, and the drawn SVG was its host's width to within a pixel at 1440, 768 and 390 (measured 2026-09-01). 760 is the same number `chart.width_px` carries, so a console page has one answer to how wide a chart starts. `config/appearance.json` owns the value, as `console.chart_width`. */
	chart_width?: number;

	/** How long a reserved console block stays still before it starts to shimmer, in milliseconds. The block is drawn the moment the document is, so this knob decides nothing about the shape of the page - only whether a wait short enough to be over already gets animated on its way past. Four hundred is a DECLARED ESTIMATE and not a measurement (CLAUDE.md Guardrail #10), and it stays one: the number it needs is the median time a payload takes to reach a READER, and a reader-facing timing measurement is scoped out by the same owner ruling that authorised the fetch (2026-09-08). Everything measurable instead is localhost, where arrival is a few milliseconds and any threshold derived from it is one nobody ever crosses. What would settle it is in docs/reference/pipeline-cost.md under Still unmeasured. `config/appearance.json` owns the value, as `console.shimmer_after_ms`. */
	shimmer_after_ms?: number;

	/** How many failed items the console lists before it offers more. The shape comes first and the rows come on demand: an uncapped list put the compression chart 9000 pixels down the page. */
	failure_list_max?: number;

	/** How many sources the console ranks by the articles their failures cost, before it states the tail in one sentence. Measured 2026-09-01 over the committed projection, a thirty-day window holds 60 sources with a loss, which is a list nobody reads to the end. Ten, matching the source-cut list above it. */
	source_rows?: number;

	/** How many failing feeds the console lists before it states the tail in one sentence. Measured 2026-09-01 over the committed ledger, 26 of 182 checked feeds have failed at least once. Ten, matching `console.source_rows`. */
	feed_rows?: number;

	/** How many summaries the console names as furthest from the length the prompt asked for. Capped, with the tail stated in a sentence, because the list exists to be acted on and the far tail is a one-word miss nobody chases. Ten, matching the source-cut table beside it. */
	band_outlier_rows?: number;

	/** How many sources the Summaries route ranks by the summaries its faithfulness checker doubted, before it states the tail in one sentence. Measured 2026-09-01 over the committed score ledger, a thirty-day window holds 112 sources carrying at least one doubted summary and the worst ten hold 266 of the 1,047 doubts - so the tail is sources with a single doubt in a month, which nobody acts on. Ten, matching `console.source_rows` and `console.feed_rows`. */
	doubt_rows?: number;

	/** How many items the run timeline draws as bars before it states the tail in one sentence. The bars are in start order, so the first this many show the shape of the run - a staircase or a block - which is what the panel is for. Measured 2026-09-16 over the committed census, a day holds 349 to 465 rows, and a bar a row would put a thousand spans in a prerendered document for a queue whose shape is settled in its first minute. It is a cap on the DRAWING and never on the arithmetic: every figure the panel prints is over the whole run. */
	timeline_bars?: number;

	/** The span the chart retirement rule is stated over. A median taken over any other span is the same figure with a different meaning and nothing on the page to say which one is being read, so under this many days the section prints the rule's own span and no number at all. */
	chart_rule_days?: number;

	/** Router minutes per published chart above which the median day retires chart drawing. Drawn as a marker on the bar, never as a subtraction the reader performs. */
	chart_minutes_target?: number;

	/** The share of a day's published items that must carry a chart, in whole percent. Below this on the median day chart drawing is retired: drawing that reaches almost nothing is paying for a capability the digest does not use. */
	chart_coverage_pct?: number;

	/** How many recorded job placements the console needs before it draws the machines as bars. Under it the panel lists the counts in words, because bars over a handful of placements read as a distribution and it is not one. A DECLARED ESTIMATE and not a measurement (CLAUDE.md Guardrail #10): the rarest of the six machine kinds on record held 11 of 356 counter rows on 2026-09-17, 3.1 percent, and 5 of those - the floor min_attempts_for_rate already sets - needs about 162 rows. A seventh machine kind lowers every share and raises the bar, so re-derive it rather than argue with it. */
	fleet_min_rows?: number;

	/** How many kinds of machine keep a bar of their own on the fleet trend before the rest fold into one row named in words. A grouped bar is only a bar while it is wide enough to paint. At chart_width of 760 and the widest span the window control offers, 90 days, a day band is 8.4 px; five bars in it draw 1.09 px each after the chart engine's own gaps and seven draw 0.77 px, which is the sub-pixel band the chart rules already refuse. Four kinds plus the fold row is the largest set that stays over a pixel there. It costs little: of the 40 placements on the committed machine record on 2026-09-20, seven distinct machines in all, the top four hold 37. The upper bound is six because the colour ramp keeps seven stops and the fold row needs one of them. */
	fleet_top_kinds?: number;

	/** How many distinct machine kinds must carry a memory-bandwidth reading before bandwidth may be plotted against decode speed. Two points define a line, so a scatter of two is a claim rather than a measurement. Nothing plots it today - the panel was refused on 2026-09-17 and this is half of the trigger that would bring it back, the other half being fleet_min_rows. */
	bandwidth_min_kinds?: number;

	/** How many machines get a colour of their own before the rest fold into one row named in words. Seven, because the chart ramp holds eight stops and the eighth is reserved for shards that recorded no machine at all - an absence is not a machine and must not take a machine's hue. Folding is what keeps the assignment bounded: without it a seventh kind would either collide with a sixth or need a ninth stop nobody has drawn. */
	machine_colour_stops?: number;

	/** The share of an interval the host gave to another tenant's machine at which that day is drawn as a filled tile rather than an outlined one. One percent is where a reading stops rounding to zero, which is a statement about the platform's own accounting rather than about this design. A floor above zero, because a threshold of zero would mark a day on which nothing was taken. A DECLARED ESTIMATE and not a measurement (CLAUDE.md Guardrail #10): no committed row separates what the host took from what we spent, because the busy figure holds both. What replaces it is the distribution of the separated reading over the first day that records one. */
	processor_lost_pct_marked?: number;

	/** The share at which the panel's headline sentence names that day as its worst case, instead of leaving the tiles to speak for themselves. Ten percent is anchored on the work shard's own budget: a tenth of run.shard_timeout_minutes is the size of loss that turns a shard which fits into one which does not. A DECLARED ESTIMATE on the same footing as the mark above it, and the same reading replaces both. */
	processor_lost_pct_named?: number;

	/** How many times the model server had to go to disk for memory it expected to be resident before that day is drawn as a filled tile. Counted over the items that are NOT first in their shard: the server maps its weights, so the first touch of each page is itself a read from disk, and item_index 0 records a server starting rather than a kernel taking pages back. What that exclusion costs, stated rather than implied: a reclaim inside the first item of a shard is invisible, and the panel says so. One, because with the exclusion the honest expected value is zero and the first recorded read is the finding. A DECLARED ESTIMATE and not a measurement (CLAUDE.md Guardrail #10); what replaces it is the first day recording a non-zero count away from index 0. */
	model_disk_reads_marked?: number;

	/** How many such reads put that day in the panel's headline sentence. Equal to the mark, and deliberately: a signal whose expected value is zero has no distribution to separate the two, so every day worth marking is worth naming. The pair is two knobs rather than one so that the day a steady background appears, somebody raises this number in the config file instead of editing a chart. */
	model_disk_reads_named?: number;

	/** Which percentile of an item's context use a run draws beside its largest. A run gets two marks because one cannot carry both the ordinary article and the worst one, and the decision to shrink the window turns on the worst. Ninety-nine rather than the largest twice: measured 2026-09-21 over the 1,312 committed item rows that record both a window and a per-call token split, the 99th item used 9,900 tokens and the largest used 13,569, so the pair says how far the worst sits past the crowd. Lowering it draws a more typical article and hides how long the tail is; raising it collapses the two marks onto each other. */
	context_high_percentile?: number;

	/** The word the model server uses when a reply stopped because it ran out of window rather than because the model finished. The vocabulary is llama-server's, not this project's, which is why it is a knob: a runtime that spells it differently is a config edit rather than a code change. Measured 2026-09-21, the committed rows record one reason across 2,624 calls and it is `stop`, so nothing has ever been cut off - a panel that could not name the other word could not say that. */
	context_cut_off_reason?: string;

	/** The order the panels of a console route are drawn in, and the headings they group under. Keyed by route id. A column of equal siblings gives the eye nothing to land on first, and a heading naming a time grain answers no question anybody arrives with - so each Hardware heading names a decision instead, in the order an operator takes them: what the machine was doing, where the time went, how close we are to the limits, and what the model spends. Each group's answer decides whether the next is worth reading. A grain is a fact about one panel and is stated on that panel, which is what lets one group hold a snapshot of a run beside a reading over the open span. The first panel of the first group is the one that verdicts the rest. The Pipelines route takes one untitled group, because what it needed was an order rather than a grouping. An id here is a panel the route implements, and the route refuses a list that names one it does not. */
	panel_groups?: Record<string, ConsolePanelGroup[]>;
}

/** One heading on a console route, and the panels that sit under it in order. */
export interface ConsolePanelGroup {
	/** What the group is called in markup, drawn as `data-console-group`. Lower case and hyphens, so it is a stable handle a test can name while the heading above it is reworded. */
	id: string;

	/** The heading drawn above the group. An empty title draws no heading and no group element, so the panels stay flat siblings - which is what a route that wants an order without a grouping asks for. A route mixes the two at its peril, so the contract refuses it. */
	title: string;

	/** The panels under this heading, in the order they are drawn. Each entry is a panel id the route implements; the route's `load` refuses a list that names a panel it does not draw, or omits one it does, so a rename here fails the build rather than dropping a panel off the page in silence. */
	panels: string[];
}

/**
 * How wide the page is, and where the reading measure lives.
 *
 * The measure is a property of a text element and never of the shell. Putting
 * it on the shell is the single defect behind the 40.6-percent measurement:
 * one `max-w-2xl` on the root layout gave the whole application a paragraph's
 * width, including a console with five tables and six charts in it.
 */
export interface FrameConfig {
	/** The widest the reader-facing frame grows, in CSS pixels. The frame is fluid below this and centred at it. It is NOT the width of a line of prose - `measure_ch` is - so raising it widens the page furniture and leaves the summary alone. */
	reading_max_px?: number;

	/** The widest the operator frame grows. Wider than the reading frame on purpose: an instrument has tables and charts where a digest has sentences, and a table is allowed the screen it is on. */
	console_max_px?: number;

	/** The reading measure, in characters, applied to a title, a summary and a key point. Applied to the text element, never to a container that also holds furniture. */
	measure_ch?: number;

	/** The page's side padding on the narrowest screen. Measured 2026-08-28, a 312px window spent 52px of its width on gutter - about two words a line, on the surface with the fewest words per line to spare. */
	gutter_min_px?: number;

	/** The page's side padding once the frame has room for it. */
	gutter_max_px?: number;

	/** Exactly three, ascending. Three is a decision rather than a default: one phone-to-tablet step, one step where a side rail becomes possible, and one step where a third column does. A breakpoint must earn a STRUCTURAL change - a grid that splits on a viewport width instead of on its own available width is the bug that drew three charts at 164px, and `auto-fit` with a minimum is what replaces it. */
	breakpoints_px?: number[];

	/** The reading item's leading column, which carries the source monogram at every width. In rem, never pixels: the mark says whether the story has been read, so it grows with a reader who set their browser text larger. */
	zone_mark_rem?: number;

	/** The reading item's trailing column, which carries the item footer from the middle breakpoint to the wide one. It retires at the wide breakpoint, where the day's aside becomes the page's trailing column instead. */
	zone_rail_rem?: number;

	/** The day's trailing column from the wide breakpoint, which carries the leading stories beside the stream instead of above it. One trailing column at a time: a 68-character measure plus both this and the item's own rail does not fit inside `reading_max_px`. */
	zone_aside_rem?: number;
}

/** The icon set, and how it takes colour. */
export interface IconsConfig {
	/** The default drawn size of an inline icon, in CSS pixels. */
	size_px?: number;

	/** Whether an icon takes the hue of what it means, or stays with the text. */
	tint_mode?: TintMode;

	/** A mark beside a topic name. Legal because a topic is a classification the pipeline actually made and carries in the payload. There is deliberately no switch for an icon beside a HEADLINE: 'what kind of story is this' is an assertion no stage ever produced, and a mark that invents it is the same failure the visual-routing rule already guards against. */
	topic_icons_enabled?: boolean;
}

/** The motion budget. Small on purpose; a reading surface that animates interrupts. */
export interface MotionConfig {
	/** The named set only: content arriving, a skeleton while a payload parses, and the rare notice. `prefers-reduced-motion` is a hard kill-switch above this flag and is not configurable - a reader who asked their operating system for stillness is not overridden by a config file. */
	enabled?: boolean;

	duration_fast_ms?: number;

	duration_base_ms?: number;
}

/**
 * The two themes. There is no third member for "follow the device".
 *
 * `system` is not a theme - it is the absence of a choice - and keeping it here
 * would let an operator set a value no surface can honour. `UiConfig` migrates
 * an older file that names it (section 11).
 */
export const THEME_CHOICE = ['light', 'dark'] as const;

export type ThemeChoice = (typeof THEME_CHOICE)[number];

/**
 * What the surface is allowed to draw with.
 *
 * Every switch here defaults to on. They exist so a surface can be measured
 * with and without a treatment, not so the treatment can be quietly left off:
 * a flag that ships false is a feature nobody built.
 */
export interface ThemeConfig {
	/** Gradients on chrome and identity only - the wordmark, a panel wash, an empty state. Never on an item and never inside a chart. A gradient that encodes nothing is decoration and is unconstrained; a gradient whose hue would tell a reader something is semantic colour and is refused. */
	gradient_enabled?: boolean;

	/** The shadow and raised-surface scale. A page with one surface colour is a page where nothing is in front of anything. On the dark theme this lifts the surface and adds a hairline instead of deepening a shadow, because a shadow on a dark ground reads as nothing. */
	elevation_enabled?: boolean;

	/** A self-hosted display face on headings. The body keeps the system stack: it renders on the first frame at zero bytes and the body is what the reader came for. Guardrail #1 permits a third-party asset; this project self-hosts because the HTTP cache is partitioned per site, so the shared-cache argument is dead and the request is the larger cost. */
	display_face_enabled?: boolean;

	/** How strongly a panel takes the hue of what it means. Capped at 0.15 because past that a tint stops being a surface and starts being a fill, and a fill competes with the text on it. The reference surfaces measured 2026-08-29 sit between 0.055 and 0.086. */
	surface_tint_alpha?: number;

	/** `--movement-good` on the light theme: a figure went the way we wanted. Not the confidence ramp and never equal to it - health says a thing is broken, movement says a number moved the right way, and a summary that got 3 percent slower is not broken. Text weight, so it clears 4.5:1 on the surface; measured 2026-08-31 the default reads 5.905:1. */
	movement_good_light?: string;

	/** `--movement-bad` on the light theme. Quieter than `--band-low` on purpose: measured 2026-08-31 the default is 44.2 percent saturation against the confidence ramp's 70.6, so a movement reads as a direction beside a status chip rather than as a second status. 6.544:1 on the surface. */
	movement_bad_light?: string;

	/** `--movement-good` on the dark theme. Designed rather than derived: the light value over a dark ground is ink, not a colour. 9.118:1 on the dark surface, measured 2026-08-31. */
	movement_good_dark?: string;

	/** `--movement-bad` on the dark theme. 8.344:1 on the dark surface, measured 2026-08-31. */
	movement_bad_dark?: string;
}

/**
 * How an icon takes its colour.
 *
 * `SEMANTIC` tints a monochrome glyph from the token that matches what it
 * means, which is how one glyph set covers every status and how a new status
 * arrives with a slot already waiting. `MONO` is the fallback for a surface
 * where a coloured mark would compete with the thing beside it.
 */
export const TINT_MODE = ['semantic', 'mono'] as const;

export type TintMode = (typeof TINT_MODE)[number];

export const TODAY_ANCHOR = ['right', 'centre'] as const;

export type TodayAnchor = (typeof TODAY_ANCHOR)[number];

/**
 * The published surface's knobs.
 *
 * `sections` is the modularity story: reordering the page is a config edit,
 * not a code change. What is deliberately absent is a per-element layout
 * engine - on the surface that matters, a phone, there is no left and no
 * right, and a per-reader layout would break the promise that a shared link
 * shows the recipient what the sender saw.
 */
export interface UiConfig {
	/** Render order of the day page's sections, by registry id. */
	sections?: string[];

	/** The theme a reader who has never touched the control is served. It is the theme `:root` carries in tokens.css, so it is also what a page paints before any script runs and what a page with no script keeps. */
	theme_default?: ThemeChoice;

	/** Where a story's figure sits relative to its text. Nothing reads it yet, and the default is what `DigestItem.svelte` renders: the figure comes after the summary at every width. It stays reserved until the render spec is handed the width the figure will occupy, because a chart drawn at 825 x 437 is illegible in a 20rem column (docs/concepts/design-system.md). `config/appearance.json` owns the value, as `digest.visual_side`. */
	visual_side?: VisualSide;

	/** The monogram beside a source name. A scanning aid, not the id. */
	source_mark?: boolean;

	/** Whether the page folds a group of the same story into one card. On, a story that names another as its story is not drawn as its own card, and the anchor's card carries a stack of publisher names that link to it. Off, every story is drawn on its own card and the stack is not drawn - which is exactly the page as it was before 2026-09-16. Nothing is unpublished either way: a folded story keeps its address, its archive entry and its month search entry (docs/architecture/publishing/layout.md). Retire it when the grouping's false-merge rate has been measured on a published day and the Editor has accepted it; until then it is the revert path, and one config edit puts every story back on its own card. */
	draw_same_story?: boolean;

	/** An in-place filter inside the topic row. Never a top-level search bar: on a page this short it would promise an archive it cannot reach. */
	show_filter?: boolean;

	/** How many characters a reader types before an in-place filter narrows a list. It binds the day page and the archive, which share one panel. Two rather than one because one letter narrows nothing: a single letter matches most story titles and the commonest matches almost all of them, where a two-letter pair matches a small fraction. A first keystroke that redraws the page and removes almost nothing is work the reader watches for no answer. Over 8 the field stops narrowing anything a reader would think to type. */
	filter_min_chars?: number;

	/** Retired and read by nothing. The all-topics page drew this many of each topic under a heading and put the rest behind a link, which on a busy day published a handful of stories and hid hundreds. The leading block replaced the headings and the flat stream carries the whole day. Kept as a field, and dropped from the committed config, so a file written before today still validates - an unknown key is refused (section 11). */
	items_per_topic?: number;

	/** The most stories the leading block may hold. They are chosen across the whole day, so the block is the page's first screen and the stream below it still carries every story in the published order. */
	leading_stories?: number;

	/** The most leads one desk may hold. It matters more than it looks: 25 of the 30 committed watchlist entries are technology companies, so the shared-subject term is structurally biased toward the AI and business desks, and this is the only thing holding it. */
	leading_per_desk?: number;

	/** The fewest leads worth drawing a block for. Under it nothing renders and the day goes straight to the stream, because four real leads beat five with one filler. */
	leading_min?: number;

	/** How many distinct sources must name one entity in their published titles before that shared subject counts for anything. Under it the term is zero. Three rather than two is the stronger claim, and it costs a small number of stories their cluster. */
	lead_cluster_floor?: number;

	/** What a qualifying shared subject adds to a story's rank inside the leading block. It is a step and not a ramp: no measurement supports a shape, and a shape nobody measured may not justify a design (Guardrail #10). It must stay below what one more feed carrying the same address is worth, which is collect.carriage_step, so a recurring subject cannot outrank a story two independent feeds carried today. A shared subject fires several times as often as a second carrier, so this weight is the smaller of the two. Re-deriving it against the step would move the leading block's order, so it belongs to a loop that re-derives both together each run. */
	lead_shared_subject_weight?: number;

	/** The most leads the block may give to stories the feed dated to the previous calendar day. A day's leading stories are today's; one late arrival is a catch-up and three are yesterday's page. */
	lead_max_yesterday?: number;

	/** How much of a lead's score is the number the planning step gave the story. 1.0 ships, which is what the block scored before it was a weighted sum at all, so the composite landed changing no published block. It is the only term measured over every story the day carries: every other signal here fires on a minority of them, so a weight on this is what stops the block being chosen by whichever minority signal happened to fire. */
	lead_rank_weight?: number;

	/** What each OTHER source that carried the same story adds to a lead's score. 0.0 ships, so the term is computed and logged and carries no weight yet: at today's recall the count is 0 on most genuinely multi-source stories, so a weight on it would reward the pass for finding a group rather than the story for being carried. Turn it on when the same-story pass has a measured recall the owner accepts - that measurement is the labelling study, and until it exists this knob has no number a person could defend. Removal condition (Guardrail #6): it stops being a placeholder the day that study sets it above zero. */
	lead_also_covered_weight?: number;

	/** How many topic pills stay on the row before an auto-created one goes inside a disclosure. A SOFT cap: a desk a person put in config/taxonomy.json is never folded away, so this bounds only the model-proposed desks sitting on the row beside them, and the row's height is the length of the vocabulary. The cut is decided by each topic's story count at build time, never by measuring the row in pixels - one order is computed in the backend and published, so a measurement taken on a reader's device could disagree with the order the payload carries. Five rather than eight: config/taxonomy.json declares five verticals, so eight was a cap nothing could reach, and the number now says what the row is for. */
	topic_pills_max?: number;

	/** How many stories ahead a desk must be before it takes another desk's place on the topic row. The row orders by how much of the day each desk holds and is redrawn at every publish, so with no margin a one-story lead reorders a control the reader is pointing at. One is strict count order and stays reachable. Three is the ceiling because every inversion above it sits between three-digit desks a reader cannot tell apart, so the margin stops protecting anything visible and hands the row back to the alphabet. What it does NOT buy is steadiness across days - a bigger margin moves the row MORE, not less. It bounds the reason a desk moves, never how often. */
	pill_move_min?: number;

	/** The most stories a desk may publish and still be called thin. A thin desk prints one sentence saying how many stories its sources offered and how many were too old to run; every other desk prints nothing, because a shortfall sentence under all five is a column of absences pretending to be information. Twelve is one page of the stream - what a reader sees before the first `Show more` - so a desk under it is a desk they see the whole of at once, which is where 'is this broken?' starts. The committed record has a wide gap below it, so any value in that gap selects the same startup desks. */
	desk_thin_max?: number;

	/** How many of a day's stories a prerendered document carries. It is the one knob in this block a browser is never told, because the root layout inlines the rest of them into every document and a number no page reads would ride to every reader for ever. Fifteen covers the twelve a flat list pages at and the five the leading block draws. It is a floor rather than the whole answer: a lead is chosen across the whole day and is not inside any prefix, so the document has to carry those as well, and on a busy day they sit deep in the order. Re-derive it when the block or the page size moves; do not raise it to cover a busy day, because the stories past the seed arrive by fetch - the first fifteen are a small fraction of what a busy day would cost a prerendered document. */
	shell_seed_items?: number;

	/** How long a reader may wait for the rest of a day before the page says one sentence about it. The opposite of `shell_seed_items`: this is the one knob in this block only a browser reads, because the wait happens in the browser and a prerendered document is the only way to tell it anything. No spinner and no bar - a sentence, which is what a state a reader has to act on gets (docs/concepts/design-system.md). Under 250 ms the sentence fires on a fetch that was never slow, which teaches a reader to ignore it; over 30 s they have already decided the page is broken. The default is orders of magnitude above what a healthy fetch takes on a fast connection, so it cannot fire on one. That bound comes from a server on the same machine and not a reader's connection, which is exactly why this is a knob and not a constant. */
	payload_slow_ms?: number;

	repo_url?: string;

	site_title?: string;

	tagline?: string;

	/** How far back a read mark is kept, counted in calendar days from today. Marks are held per digest date, so a mark made on one day can never grey out a different day's article, and every page load drops the dates that now sit outside this window. Fourteen days, the same span `archive_recent_days` lists, so the days the archive offers as rows of their own are exactly the days a reader can still see their own marks on. THIS RULE TRUSTS THE DEVICE CLOCK AND THE RULE IT REPLACED DELIBERATELY DID NOT: keeping the newest N dates present in the store needed no clock at all, and expiry by calendar cannot work without one, so a clock set wrong now keeps marks too long or drops them early. That is the price. It is worth paying because the old rule bounded the store by how often a reader came back rather than by time: a reader who opened one day a month kept marks from seven different months, and every one of them greyed out an article last seen most of a year ago. A wrong mark is the thing this store exists to avoid. */
	read_mark_days?: number;

	/** How many stories the archive's list adds each time a reader asks for more. The day page pages at twelve because a day is short and the reader came to read it; the archive holds thousands and the reader came to find one, so it opens on the same twenty-five the console's failure list does. */
	archive_page_size?: number;

	/** How many of the newest published days the archive lists as rows of their own, each carrying the long date, the story count and whether every story finished. Every other day sits inside a disclosure for its month, so this block is the shortcut and never the only way in. Fourteen, and it matches `read_mark_days` for the same reason it matched it at seven: a row here is an invitation back to a day, and a day whose marks have already been dropped comes back looking unread. The two numbers move together or the block starts offering days it misrepresents. The ceiling is a month: above that the block is the wall of dates it replaced, and a month row already reaches any date in two clicks. Read by the build alone, like `shell_seed_items`, so it never rides to a reader. */
	archive_recent_days?: number;

	/** The span the archive's window control opens on, in days. IT MUST BE ONE OF `console.window_presets`, and `AppConfig` and `AppearanceConfig` both refuse a file where it is not - that is how the archive reuses the console's list of spans instead of declaring a second one, so the two surfaces cannot offer different day counts for the same idea. It names a span rather than a list for the reason `console.default_window_days` does: the list is the presets, and a second list is one more thing to keep in step. Thirty, because that is the span the console opens on and about the reach `assist.search_months` gives a search today, so the control ships opening on what the archive already costs. NOTHING READS IT YET - the archive has no window control, so the span one would open on is declared and unused. Read by the build alone, like `archive_recent_days`, so it never rides to a reader. */
	archive_window_days?: number;

	/** The version the offline reader carries. The site ships a service worker so a day already opened can be read again with no network, and this number is how a build says which worker it is. It is compared against `offline_retired_through`, and nothing else reads it. Raise it by one to bring the worker back after a retirement; leave it alone otherwise. Read by the build alone, like `shell_seed_items`, so it never rides to a reader. */
	offline_version?: number;

	/** The switch that turns the offline reader off and cleans up after it. Every worker whose `offline_version` is at or below this number unregisters itself and deletes every cache it owns, the first time it activates. Zero retires none, because the lowest version a worker can carry is one. This is the one thing a worker outliving the tab needs and an ordinary page does not: a way out that does not depend on the worker being well (docs/concepts/ui-shell.md). It is published as `service-worker-kill.json` at the site root, so a retirement can be pushed as one file. Read by the build alone, so it never rides to a reader. */
	offline_retired_through?: number;

	/** How many opened days the offline reader keeps on the reader's device. The worker caches a day only after that day has been fetched once - it never prefetches a day nobody asked for - and this is what stops the kept set growing with the archive. Fourteen is two weeks, the same span `read_mark_days` keeps a read mark for, so a day a reader can still see their marks on is a day they can still open with no network. A day payload varies by more than two orders of magnitude, which is why a day count cannot be the only bound - `offline_bytes_kept` is the other one. Read by the build alone, so it never rides to a reader. */
	offline_days_kept?: number;

	/** The most bytes of cached day payloads the offline reader keeps on the reader's device. A SECOND BOUND BESIDE `offline_days_kept`, NOT A REPLACEMENT FOR IT, because a day count cannot bound bytes: one day payload varies by more than two orders of magnitude, so fourteen days is anything from a fraction of a megabyte to tens of them, and the count alone promises the reader nothing. Twenty million bytes sits just above what the day count already permits at the largest day seen, so on today's payloads the day count still binds first and this is the backstop for when day payloads grow. The floor is above the largest single day seen, so no reachable value can leave the cache unable to hold one day - a ceiling that evicts a day as fast as it arrives is worse than no cache, because the reader pays the download and keeps nothing. The ceiling is 100 MB, a little over twice the 43.2 MB the on-device search model and its runtime already take, because taking a tenth of a gigabyte of somebody's phone for a news digest is not a thing a config edit should be able to do quietly. NOTHING READS IT YET - the offline cache evicts on `offline_days_kept` alone, so this ceiling is declared and unenforced. Read by the build alone, so it never rides to a reader. */
	offline_bytes_kept?: number;
}

/**
 * Where a figure sits relative to the text it belongs to.
 *
 * `above` puts it before the text, `leading` beside the text on the side
 * reading starts from, `trailing` after the text. A card is one column at
 * every width the site ships, so `leading` cannot yet differ from `trailing`
 * - a figure has no column of its own until the render spec is handed the
 * width it will occupy (docs/concepts/design-system.md).
 */
export const VISUAL_SIDE = ['above', 'leading', 'trailing'] as const;

export type VisualSide = (typeof VISUAL_SIDE)[number];

/** `config/appearance.json` - everything the published surface is drawn from. */
export interface AppearanceConfig {
	version?: string;

	/** The day page's knobs. Formerly `AppConfig.ui`, unchanged in shape. */
	digest?: UiConfig;

	/** The operator console's viewport. Formerly `AppConfig.console`. */
	console?: ConsoleConfig;

	/** On-device archive search. Formerly `AppConfig.assist`. */
	assist?: AssistConfig;

	frame?: FrameConfig;

	theme?: ThemeConfig;

	chart?: ChartConfig;

	icons?: IconsConfig;

	motion?: MotionConfig;
}
