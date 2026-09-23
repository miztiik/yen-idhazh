// Generated from `backend/idhazh/contracts/app_config.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * What the published day does with the items a run finished.
 *
 * Its own group rather than a knob under `assist`, because `AppearanceConfig`
 * imports `AssistConfig` whole: a threshold the pipeline applies once at build
 * time would then also land in `config/appearance.json`, where it has no
 * reader and no meaning.
 */
export interface AssembleConfig {
	same_story?: SameStoryConfig;

	/** How far apart two stories may have appeared and still be one story. A story that breaks at 23:00 and is picked up at 07:00 is one story, and a day boundary is an accident of the calendar rather than a fact about the news - so the window is hours between the two stories' own times, not which day each was published on. 36 hours covers an evening break picked up the next morning and refuses a genuine follow-up two days later. It is an ESTIMATE: what would overturn it is the age gap of the cross-day pairs a person marks as one story. The window is also what bounds the read - the pass loads only the earlier days it can still reach, so the cost is set by this number and never by how much archive exists (Guardrail #12). 0 keeps the pass inside one published day, which is what it did before this knob existed, and is the revert. */
	same_story_window_hours?: number;

	/** Whether two of a day's items are one story when their published headlines say the same thing - compatibility-normalised, casefolded, and with everything that is not a letter or a digit turned into a space. The words must match exactly; the numbers only have to agree to the coarser of the two precisions they were written with, so `$12.9 billion` and `$12.93 billion` are one acquisition while `25 percent` and `50 percent` are two different figures. This is a second way into a group beside same_story.floor_min, never a replacement: every pair inside a group still has to clear one of the two, and an item with no vector is still never grouped. It exists because the cosine is taken over `title. summary`, and the summary is our own prose about ONE article and is most of that string, so two honest tellings of one story are pulled apart by the part that is guaranteed to differ. Measured 2026-09-14 on a developer machine / Python 3.14.2 over the twenty-five committed days and 9,353 items: fifty-three cross-source pairs share a headline, their cosine has a median of 0.9177 against a floor of 0.94, and the highest-scoring pair marked as TWO stories sits at 0.9407 (2026-09-19 labels) - above both that median and the floor, so no threshold separates the two populations and lowering same_story.floor_min cannot fix this. Turning this off restores the vector-only rule, which is the revert path an operator has if a shared headline ever turns out to be two stories. Ruled by Andre and the Editor, 2026-09-14, and the rounding tolerance by the owner the same day; the reasoning is in docs/architecture/publishing/layout.md. */
	group_identical_titles?: boolean;
}

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

export interface BenchConfig {
	/**
	 * Articles one bench repeat reads. It sizes the whole dispatch: a named candidate runs a baseline case and the candidate's case, so three repeats is six passes over this many articles, and one pass is the unit the job timeout is spent in.
	 *
	 * Three because five does not fit, not because three is thrifty. Measured 2026-09-17 over the four dispatches of 2026-09-16 (35086403868, 35086407071, 35086409972, 35086412536) on stock ubuntu-latest: the slowest pass took 65.6 minutes for five articles, so six passes compute to 393.7 minutes against a 330-minute job timeout - over by 19 percent. Four articles is 315 minutes, which is 95.5 percent of the timeout and no headroom at all. Three is 236 minutes, 71.6 percent, and it fits. Guardrail #2: the timeout is GitHub's, so the design is what gives.
	 *
	 * Raising it costs the dispatch, and past three it costs the dispatch its result. Lowering it costs evidence: at five articles a per-article output-drift finding is p = 0.03 under an exact binomial, and at three it is p = 0.125 - still a finding, no longer overwhelming. What three buys back is a dispatch that finishes: article text drifted on 5 of 15 article-observations across three dispatches, so fewer articles means a better chance the run produces a usable reading at all.
	 *
	 * It never touches the qualification corpus, which is `validate.yml`'s own `corpus_per_shard` dispatch input and stays where it is. A bench says how fast; a qualification says how good, and the second needs its 30 articles to bound an undetected defect rate.
	 */
	corpus_items?: number;

	/**
	 * How many times a bench dispatch runs each case. Two is the floor because a spread needs two readings; one reading has nothing to be read against, and a dispatch that cannot produce a spread is refused before it starts.
	 *
	 * It lives here, beside `corpus_items`, because the two numbers multiply and the product is what the job timeout is spent on. A named candidate runs two cases, so three repeats is six passes over `corpus_items` articles - 236 minutes against a 330-minute timeout at three articles, which fits. Held in two files, the next person raises one of the two without seeing the other and finds out at 330 minutes, when GitHub kills the job (Guardrail #2).
	 *
	 * A case set costs more at the same number: `draft_depth` runs four cases, so three repeats there is twelve passes rather than six. That is what `measure.yml`'s `runtime_repeats` dispatch input is for - it overrules this knob for one run without a commit, and empty follows it.
	 */
	repeats?: number;

	/**
	 * Does a bench dispatch measure the model's raw speed before it measures real work? Default true, and it is removed the day the speed case stops costing a dispatch time worth saving - measured 2026-09-16 over four dispatches on stock ubuntu-latest at 9.1, 26.7, 27.2 and 87.6 minutes, so today it is worth between a tenth and a third of the whole dispatch.
	 *
	 * False runs the rest of the flow and skips that half: the fixed corpus, the real server over it, the machine record and the committed host row all still happen. What is given up is the prefill and decode rates, and with them the dossier - a dossier is both cases, so a dispatch that skipped one emits the server half and a line saying which half is missing rather than a page that reads whole.
	 *
	 * It also moves who pays for the weights. The speed case fills the cache entry the server case restores, so a dispatch that skips it downloads the candidate once in the server case instead - the same bytes, in a different job.
	 *
	 * `measure.yml`'s `model_speed_case` dispatch input overrules this for one run without a commit: `config` follows this knob, `run` and `skip` do not. This is operator control rather than a feature behind a flag, so there is no second implementation waiting behind it - the same jobs run either way and one of them is not dispatched.
	 */
	run_model_speed_case?: boolean;
}

export interface CollectConfig {
	/** Consecutive results that count against a feed before a run stops asking it, and how many runs that rest then lasts. One number for both counters because there is one question here - how much evidence is enough - and discover.resting takes it once. It replaced quarantine_after_failures, carrying the same 5: the old name read as a policy about quarantine and this one is named for what it counts. */
	availability_strikes_before_rest?: number;

	/** How many runs a rested feed is skipped before it is asked again. The rest ends on its own, so a source that came back is live on that very run and a source that is still dead costs one request per cycle rather than one per run. Still unread: the rest lasts availability_strikes_before_rest runs, because splitting one number into two is a change to the rest rule rather than a rename, and the rename is what landed. */
	availability_rest_runs?: number;

	/** Distinct runs that must each read HTTP 410 from one address before that address is retired. Distinct runs and not attempts: one bad afternoon retrying itself is one run's evidence. */
	feed_http_410_runs_before_retirement?: number;

	/** Runs to wait before asking robots.txt again after a refusal. One, because permission can be granted back at any moment and a refusal costs one small request to re-establish - a longer wait buys nothing measurable and delays a source's return. */
	robots_denied_recheck_runs?: number;

	/** The same, for permission we could not establish at all. Separate from the denial cadence because the two are different facts: one is a publisher's stated policy and the other is our own failed read. */
	robots_unreachable_recheck_runs?: number;

	/** Complete days of item-health evidence a per-source yield judgement needs before it may be made at all. Below it any yield threshold is an estimate rather than a measurement (Guardrail #10), and no source may be demoted on one. */
	source_yield_min_complete_days?: number;

	/** The yield below which a run names a source on its own summary - the share of the addresses a source decided that it turned into a story. It raises a flag for a person and moves nothing on its own: it never rests a feed, never scales a rank and never edits config/sources.json. The committed record is bimodal with a wide empty band in the middle, and the default sits inside it, so anywhere across that band names the same sources and the exact number is cheap. It is an alarm point and not a floor - reliability_floor clamps a factor, this compares a ratio, and one word for both is how the two get confused. */
	source_yield_alarm_point?: number;

	/** Addresses a source must have decided before its yield may raise the alarm. A low yield and a low volume are independent axes, and without this floor the alarm's first run names a source the project already ruled it keeps. Distinct from source_yield_min_complete_days, which counts days of record rather than decisions a source made, because a busy source clears this in a few days and a weekly one may never clear it - which is the correct answer for both. The cost is delay: a busy source spends those days, and the addresses it spends getting there buy the protection. */
	source_yield_alarm_min_decisions?: number;

	/** Running days a source must stay under source_yield_alarm_point before it retires itself. **A bad week cannot retire anything** - that is the whole reason this exists, and it is why the number is two weeks rather than seven days. The run must be unbroken: one day back at or above the alarm point resets it to zero, so a source that recovers keeps its place. This is the fourth member of the yield family and extends it rather than sitting beside it: the alarm point says what counts as too low, the two evidence floors say when we may judge at all, and this says how long the answer has to hold. */
	source_quality_dwell_days?: number;

	/** Whether a completed dwell actually files a retirement row, or only draws the countdown on /console/voices/. Default false for the first release because nothing has ever retired on this measurement and the console panel is what a person reads before trusting it. REMOVAL CONDITION: delete this flag, and the branch it guards, once one real low-yield retirement has been reviewed and accepted (Guardrail #6). */
	source_quality_auto_retire?: boolean;

	watchlist_max_entities?: number;

	/** Failure codes that will not change before tomorrow. An address that failed today with one of these is not planned again today. A paywall, a robots rule and a 404 are the same answer at 02:20 and at 18:20; a rate limit, a reset connection and an unreachable model are not, so they are absent and a later run retries them. Empty means retry everything, which is what the pipeline did before this field existed. */
	settled_failure_codes?: FailureCode[];

	/** Most items one feed may contribute to one vertical in a day. Without it, a quiet news day is whichever blog published most. */
	max_per_source?: number;

	/** Most of one day one feed may hold, counting every desk and every run. max_per_source bounds a count inside one desk in one run, and a feed sits on one desk, so what a feed can hold of a whole day is that count times the runs the day had - a fixed number whose share moves with the day's size. The most one feed has ever held is a small share of a busy day and a large share of a thin one. The default is above the largest full-day share by a factor of two, so it displaces nothing that has ever been published; it bounds the thin day, where a fixed count is most of the page. It is never tighter than max_per_source for one desk in one run - a day ceiling below that would tighten the per-desk rule, which is a different decision and was refused. */
	max_source_share_per_day?: number;

	/** The first and heaviest of the four terms the order is built from - what a source tier is worth, before the feed's own weight and its recent record scale it. The ladder spans 0.7, institution 1.0 down to community 0.3, which is wider than any other term's ceiling and is why it is term one. An estimate. Flattening every tier changes most of the head slots and several of the lead stories, so the ladder, not any bonus, is what decides the head. Institution feeds supply a small share of the stream and hold a much larger share of the head; community feeds have held none of it, so the bottom rung is not yet distinguishable from zero. Raising it, or saying that tier admits rather than ranks, is the open question. */
	tier_weights?: TierWeights;

	/** Trailing days of committed feed-health read to score a feed's reliability - how often its reads carried entries rather than failing or parsing to nothing. At least 30, because a feed publishes a few times a day at most and a shorter window would let one bad afternoon set the factor. The read is bounded by this window and never the whole ledger (Guardrail #12). */
	reliability_window_days?: number;

	/** The lowest a reliability factor may reach. The factor scales a feed's authority and is clamped to the range [floor, 1.0], so it only ever reduces a score and never removes a feed. At 0.5 the worst a feed's record can do is halve its authority - a two-to-one cut, never more - so a reliable feed of a lower tier can still be caught but a single desk is never emptied by this alone. Third of the four terms the order is built from, and its ceiling is (1 - floor) times the best tier, which is 0.5 today. An estimate. Only a couple of feeds in the committed record reach the clamp at all; at a floor of 0 the worst of them would score no authority and leave the day, which is the removal this clamp refuses. */
	reliability_floor?: number;

	/** What one more of our feeds carrying the same address is worth. A flat step that fires once at two carriers and never grows - three carriers is not three times the story. A multiplier would double the term on a second carrier and pay most to whatever already scored highest, which is the opposite of what a tie-break does. What it counts is syndication rather than agreement: carried_by counts feeds carrying one address, so two outlets writing their own piece produce two addresses and both read 1 (docs/architecture/publishing/layout.md). An estimate, and it is set by two written rules rather than by a measurement, because nothing inside the window they leave is measurable. It may not reach the smallest gap between two collect.tier_weights values, or carriage would promote a community story past a trade-press one; and it may not fall to ui.lead_shared_subject_weight, or a recurring subject would outrank a story two independent feeds carried today. The default is the midpoint of those two bounds, which is the value that stays legal when either one is edited. Pricing it against measured carriage, and then a loop that re-derives it each run, are what would overturn it, with the tier step as a hard bound. */
	carriage_step?: number;

	/** What a story about a subject on config/watchlist.json is worth, added once however many watchlist entries it names. It is the fourth and smallest of the four terms the order is built from - authority times the feed's weight, then decayed recency, then the feed's reliability, then this. An estimate. A watchlist subject fires several times as often as a second feed carrying one address, so the firing-rate method discovery.md uses for a content signal would price it far lower. That method is the wrong instrument here: a watchlist subject is not informative because it is rare, it is informative because a person chose it, and pricing it that way collapses the head onto one desk. Re-pricing this against the carriage step would move the leading block's order, so it belongs to a loop that re-derives both together each run. */
	watchlist_bonus?: number;

	/** How much freshness may move a score, inside the window max_age_hours allows. It orders what is already fresh enough to publish; it is max_age_hours, not this, that decides what is too old to add at all. Second of the four terms the order is built from, by ceiling - and the ceiling is most of what it is. An estimate. Almost every story is scored within a few hours of publishing, so a half-life of most of a day over a one-day admission window pays nearly the ceiling to everything and separates almost nothing. Raising this weight does not fix that - it scales a flat term. The half-life is what would, and no row owns it yet. */
	recency_weight?: number;

	/** Hours for the recency bonus to halve. At 18 h a day-old item keeps a third. */
	recency_half_life_hours?: number;

	/** How old a story may be and still be added. A hard gate, applied to the date we believe rather than the date the feed claimed. An article we could not date at all is not too old - first sight is its age, so it gets the day we found it and no more. */
	max_age_hours?: number;

	/** A publish date further ahead than this is not believed and the item falls back to first sight. Feeds that stamp tomorrow would otherwise take the top slot every single day. */
	max_future_hours?: number;

	/** How far back the first-sight store is consulted. It is counted in days and the store files by day, so the window names the files it opens and the prune keeps exactly those. Older day files stay committed and readable until that prune reaches them; they are just not evidence about today. */
	seen_window_days?: number;

	/** How far back the published record is consulted before an address is treated as never published. -1 means never forget, and it is the only sentinel for unbounded - not 0, not null, and not a very large number, because a large number is a cover that silently becomes finite the day the archive outgrows it. A finite value must be strictly longer than seen_window_days: the two stores answer the same question from opposite ends, and a cover that expires first hands an address to a first-sight store that has already forgotten it. load_published reads it once a run, through stage_plan. */
	published_window_days?: number;

	/** Case-insensitive substrings of a canonical address that never enter the pool. For the promotional page a working news feed syndicates: an affiliate product review is short declarative prose, so it is trivially entailed and no faithfulness threshold detects it at any cut. Empty by default - the entries are a source list and live in config/ (Guardrail #6). */
	blocked_url_markers?: string[];

	/** How alike two of a day's planned stories have to be, by cosine over the headline-and-lead vectors the plan builds, before they are recorded as one story carried at two addresses. The same number and the same reason as assemble.same_story.floor_min: set by hand labels at 0.94, the first round hundredth above the highest-scoring pair a person marked as two stories. The plan pass reuses it rather than minting a second threshold for the same question one stage earlier. This one stays a bare cosine, because the plan has no summary and no key points yet - the terms the assemble composite adds do not exist a stage earlier. Raising it misses duplicates; lowering it risks folding two stories into one, so it leans high. */
	dedup_similarity_min?: number;

	/** Whether the plan-stage duplicate pass CUTS the weaker telling of a repeated story, or only records what it would cut. False is record-only: the pass logs each would-collapse pair against what it matched and removes nothing, so a day is measured before it is trimmed. Turning it on cuts the lower-ranked of each pair before the safety ceiling and changes nothing else. It ships false, because a cut nobody has read the record of is a cut nobody can defend. */
	dedup_enforce?: boolean;
}

/** One collection's line: how old a member must be, and how many go in a pass. */
export interface CollectionPolicy {
	/** How many days a member is kept before a pass may take it. Whole days and never zero: a window that includes today would delete the artifact the running job just uploaded. */
	retain_days: number;

	/** The ceiling. One pass deletes at most this many and then stops cleanly, naming where the next pass resumes. 0 surveys: it reports the first member the window holds and deletes nothing, which is how an operator sees what a window selects without committing to a number. */
	max_deletes_per_run?: number;
}

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
 * The clocks, the width, the nights covered and the tenants one judging night runs under.
 *
 * A top-level block rather than a knob under a tenant, because every number
 * here prices a runner: a checkout, an install, a weights restore and a matrix
 * shard. No tenant can see any of them.
 *
 * Until 2026-09-21 the bound sat in `run`, which is the digest pipeline's, and
 * the width sat inside the content-similarity judge's own block - so a
 * repository with no judge configured had no width to size its matrix by and
 * no clock to stop a shard on.
 */
export interface CouncilConfig {
	/** How long one judging shard may run before GitHub kills it. 200 minutes is 2 hours 9 minutes of model time at the content-similarity judge's cap of 200 pairs over 4 shards, plus 71 minutes of headroom against a fixed cost of about 6 minutes for the checkout, the weights cache restore and the server start. That model time is derived from 9.85 tokens a second measured on a stock runner on 2026-09-09, not from a judge call. A tenant that draws more work than fits is refused when its own block is read, never answered by raising this past GitHub's 6 h job ceiling. */
	shard_timeout_minutes?: number;

	/** How much of shard_timeout_minutes is gone before the judging process starts. The job clock starts at provisioning; the process starts after a checkout, a weights cache restore, a checksum verify and a health poll, and all four are the venue's own fixed cost. 13 minutes is one minute above the worst case those four steps have been measured at, which is 12.1 minutes: provisioning 0.41, cache restore up to 1.58, checksum verify 0.12, and a health poll bounded at 10. Without it the in-process deadline lands AFTER GitHub's own kill on a slow model load, and the reserve below protects nothing. */
	shard_preamble_minutes?: number;

	/** How much of shard_timeout_minutes a judging shard keeps back for itself, so it stops on its own clock instead of being killed on the platform's. A shard killed at the bound uploads nothing, so every verdict it had already produced dies with the units it had not started. The reserve covers what happens after the last unit: writing the records and the artifact upload. Its own knob rather than a copy of run.shard_wrap_up_minutes, because a work shard is a different stage with a different preamble. Raise it if an upload is ever cut off, and never lower it to fit one more unit. */
	shard_wrap_up_minutes?: number;

	/** How many shards split one night. The workflow reads it to size its own matrix, so it is the venue's number rather than a tenant's. 4, because one llama-server on the configured weights already peaks at 12.57 to 13.16 GiB and reaches 14.31 GiB with the shard's python - 96.0 percent of the 16 GB runner, measured 2026-09-08 over four shards of run 2026-08-29-3. A second server on one runner does not fit at all. The ceiling of 8 is what a GitHub matrix job costs rather than a measured limit. A tenant may narrow it downward, so this is the ceiling and the default rather than an instruction. */
	shards?: number;

	/** The first night this council existed, and the floor under every window it asks about. Before it a date carries no verdict because nothing was judging, which is not the same thing as a night that died - and the plan has no way to tell the two apart without this. The council's store holds one day file against 30 published days, so an unfloored window names every one of those days on its first run and buys a backfill nobody asked for. A tenant that moved in later raises the floor for itself, by naming no night from before it arrived; this is the floor it gets by default. */
	first_night?: string;

	/** How many nights back the council asks its tenants about, ending the night before tonight. This tuple of dates is the whole of what a tenant is handed, so it bounds the tenant's read as well as the council's own (CLAUDE.md Guardrail #12). 7, because a night that died on a Friday is still repairable the following Thursday, and a date still unjudged after a week is one a person should look at rather than one the next run should keep retrying. */
	repair_window_nights?: number;

	/** How many older dates one night may repair, on top of tonight. Dates are a parallel axis - one job a date a shard a tenant, each under its own shard_timeout_minutes - so this buys matrix width rather than wall clock. At 4 shards and 2 tenants, 1 repair is 16 jobs against the platform's 20-job ceiling and 2 repairs is 24, which runs in two waves. 1, because a cap with no floor under the window only slows a backfill down instead of stopping it. */
	repair_dates_a_night?: number;

	/** Which tenants the council hosts, in the order it runs them. The one place a tenant is registered: the council resolves each slug to the module that declares it, and a slug nothing declares is refused by name. Empty is a legal night - every step still runs and the venue judges nothing - because a list in source would make adding a judge a code change and would put a roster of who may exist back inside the venue. */
	tenants?: string[];
}

export interface DriftConfig {
	month_over_month_pct?: number;

	year_over_year_pct?: number;

	quarterly_refresh_fraction?: number;

	/** Distinct articles with the required metric on each side of a domain comparison. A smaller sample is reported as insufficient evidence, not as drift or as healthy. This is a safety floor, not a confidence level. */
	min_domain_rows?: number;

	/** Fractional fall in median extracted article length that raises an alert. */
	source_word_count_drop?: number;

	/** Absolute rise in median copied four-word-phrase share that raises an alert. */
	extractiveness_rise?: number;

	/** Rows a window must hold on each side before a comparison of the two means anything. Below it the review fails instead of reporting no drift, because an empty window and a healthy one produce the same empty finding list. Sized against the ledger rather than picked round: measured 2026-08-30 over the 3,113 rows committed to state/scores.csv, the lightest full day holds 117 and the heaviest 731, so a seven-day recent window holding under 20 is a stopped instrument and not a quiet week - 20 is a sixth of one of those days. */
	min_window_rows?: number;
}

/**
 * How many candidate elements one article's passes may keep.
 *
 * A bound on work, never a judgement about which figures matter. The
 * candidate pass keeps every quantity the number pattern matched, in the
 * order the article wrote them, and this is the only thing that removes any
 * of them - so `ElementTable.candidates_found` ships beside the table and
 * says what the pass matched before this cap applied.
 */
export interface ElementsConfig {
	/** Candidate elements kept per article. Sized against the truncation cap rather than guessed: at 10000 tokens an article body holds about 7,692 words, and the densest committed page fixture carries 9.2 quantities per 1000 characters, which is about 420 over a body that long (measured 2026-09-08 on tests/fixtures/pages and tests/fixtures/canaries). It is 16 times visuals.max_facts because that one is a menu a small model reads by index and this one is a fact table nothing has to read at once. The cap was above that estimate until extract.truncation_cap_tokens doubled on 2026-09-09 and now sits below it, so the densest long article keeps the first 256 quantities in article order and ElementTable.candidates_found says how many the pass matched. That is a bound on work behaving as one, not a silent loss: news prose front-loads, and the planner reads at most visuals.max_facts of the table by index. */
	max_per_article?: number;
}

export interface EvaluationConfig {
	/** Words of article the faithfulness scorer reads in one window. Attention is quadratic in the premise, so a whole long article in one pass is the expensive shape. The default has never been calibrated (Guardrail #10): with no human labels there is nothing to tune it against, and a sweep would show only that the number moves. Moving it moves `scorer_version`, which restarts the run-day count in `evaluation.label_min_run_days`. */
	chunk_words?: number;

	/** Words shared between one window and the next, so a claim that straddles a boundary is still whole somewhere. Must sit below `chunk_words`. */
	chunk_overlap_words?: number;

	band_high_min?: number;

	band_medium_min?: number;

	/** Below this the summary missed the source lead. It caps a high band at medium rather than forcing low. */
	lead_coverage_min?: number;

	/** Maximum summary/source ratio for a brief item. Also caps verbatim_run on briefs and derives extract.min_source_words from the first brief ask. */
	brief_compression_ceiling?: number;

	/** Above this share of the summary copied from the source in one unbroken run, the item is refused rather than published. A starting point and not a calibrated threshold (Guardrail #10): it is the midpoint of the band left open by one run-day of eight brief items on 2026-08-26, where seven scored at or below 0.241 and the eighth scored 1.000, and eight items is not a distribution. It must sit above brief_compression_ceiling, or the brief copying gate loses the band it can still fail in. */
	verbatim_reject_ceiling?: number;

	spot_checks_per_week?: number;

	/** Who may write a faithfulness label. Empty by default, so a fresh clone can draw the queue and read it but cannot record a verdict. The list is what keeps a machine out of the label ledger: there is no author field a model could fill, and adding one would be a schema change with a written reason (CLAUDE.md section 0a). */
	labellers?: string[];

	/** Labels drawn from each hhem decile. Uniform, not weighted to the cuts: the first question is what `high` means at all, and a boundary-weighted draw cannot answer that. */
	label_draw_per_decile?: number;

	/** Distinct run-days at one scorer version before a draw is worth finalising. A draw over one day is a draw over one day's sources. It is the only collection requirement: a draw is one pool at one scorer, and the figure read off it is reported rather than withheld. */
	label_min_run_days?: number;

	golden_set_size?: number;

	/** Golden articles a candidate must be scored on before its mean counts. */
	validation_articles?: number;

	/** How far below its leaderboard number the incumbent may land before the ranking stops being a usable prior and the challengers get scored too. */
	validation_drop_max?: number;

	/** How much better a challenger must be on our own corpus to change the pick. A number, because 'materially diverges' is an argument waiting to happen. */
	validation_switch_margin?: number;

	/** Articles a qualification shard extracts for every one it replays. A floor on the choice the stratified selection gets, never a cap on the walk: a shard that has not yet been offered every length tier keeps going through its slice. Raising it buys fetch seconds, never model minutes, because the model still sees corpus_per_shard articles - one address measured 2.1 s on 2026-08-26 over 150 of them, against 330 minutes for the job. */
	qualification_pool_multiple?: number;

	/** Articles a qualification corpus aims at in each summarize band. It describes the measuring stick rather than the candidate, so a corpus short of it is reported on the verdict and blocks nothing - the gate that refuses a thin run is scored_denominator, which counts what was actually scored. */
	qualification_min_per_band?: number;

	/** Articles the corpus aims at that are long enough to be truncated. They are the only ones that exercise the cap at all. */
	qualification_min_over_cap?: number;

	/** Articles the corpus aims at that take the brief prompt, which is a different prompt - a corpus without one says nothing about that path. */
	qualification_min_brief?: number;
}

export interface ExtractConfig {
	/** A performance lever, not only a safety cap: prefill degrades with length. */
	truncation_cap_tokens?: number;

	/** Below this the item publishes through the brief tier. It is derived in AppConfig from summarize.bands[0].target_words_min divided by evaluation.brief_compression_ceiling. */
	min_source_words?: number;

	/** Sentences of prose needed before a page stops carrying the not_prose signal. */
	prose_sentence_min?: number;

	/** Words a sentence needs before it counts as prose for the shape signal. */
	prose_sentence_words_min?: number;

	/** Lines needed before the line-shape guard runs. */
	prose_line_count_min?: number;

	/** Minimum share of lines that must look like prose on a line-heavy page. */
	prose_line_ratio_min?: number;

	/** If true, a not_prose signal rejects the item. Default records and publishes. */
	reject_not_prose?: boolean;

	/** If true, a too_short signal rejects the item. Default records and publishes, which is Owner override O3. **A feed a curator declared `abstract` is never rejected by this, whatever it is set to.** That feed publishes abstracts because a person said so, and abstracts are short by definition - rejecting one would delete a source on the strength of the property it was registered for. The signal is still recorded on its row either way: the item IS short, and the census says so. What the form changes is the consequence, never the fact. */
	reject_too_short?: boolean;

	/** If true, a boilerplate signal rejects the item. Default records and publishes. */
	reject_boilerplate?: boolean;

	/** Share of an item's lines also seen on sibling items from the same host. */
	boilerplate_ratio_max?: number;

	/** Words we extracted, divided by the words the page's own markup says its article has. Past this the extraction is contaminated - it returned the publisher's front page rather than the one article we asked for. Measured over the 58 re-fetchable pages of one run, 41 of which state their own length: the median ratio is exactly 1.00, the 90th percentile 1.24 and the worst healthy page 1.64, against 3.69 on the page that started this. 2.0 sits in that gap and flags 1 of the 41 with no false positive. It is a line drawn through 41 pages of one day, which is why `reject_contaminated` is false and the run records the signal rather than acting on it. */
	corroboration_ratio_max?: number;

	/** Words a witness needs before it counts as a statement about the article's length. Below this it is a caption, a teaser or a stub, and the ratio it would give is noise rather than a reading. */
	corroboration_min_words?: number;

	/** If true, a contaminated signal rejects the item. Default records and publishes. */
	reject_contaminated?: boolean;

	/** Fallback markers used only when publisher JSON-LD does not declare the paywall. */
	paywall_markers?: string[];

	max_body_bytes?: number;

	max_retries?: number;

	backoff_initial_seconds?: number;

	backoff_multiplier?: number;

	request_timeout_seconds?: number;

	user_agent?: string;
}

/**
 * Stable failure vocabulary for item-health rows.
 *
 * **Membership is one member per knob an operator turns, not one per gate.**
 * Four HTTP members answer to one fetch, because the fix for a 404 is not the
 * fix for a rate limit. `output_truncated` and `labels_truncated` are the two
 * output budgets, derived from two different grammars, for the same reason.
 */
export const FAILURE_CODE = ['not_attempted', 'robots_denied', 'robots_unreachable', 'blocked_address', 'http_client_error', 'http_rate_limited', 'http_server_error', 'network_error', 'no_text', 'no_title', 'too_short', 'not_prose', 'boilerplate', 'contaminated', 'paywalled', 'unsupported_form', 'model_unreachable', 'model_refused', 'model_timed_out', 'context_exceeded', 'output_truncated', 'labels_truncated', 'bad_shape', 'length_out_of_range', 'copied_source', 'leaked_address', 'shard_out_of_time', 'unknown'] as const;

export type FailureCode = (typeof FAILURE_CODE)[number];

/**
 * The training corpus and the schedules that maintain it.
 *
 * Nothing here runs on the runner. Training needs a GPU and the runner has
 * none (section 0a), so these knobs size a file CI commits and a notebook
 * somewhere else reads. `teacher` names a KEY in `models` rather than a model,
 * because `models.summarize` has already moved once and a knob that spells a
 * model name is stale the day the config moves.
 *
 * There is no `student`. It named the small visual planner, retired when the
 * two calls moved onto the summarizer's weights, and a distillation session
 * needs two models: with one role left, the student could only be the teacher.
 *
 * The prune knobs live here and not in `retention`. That block is about
 * published-site images and its own `site_budget_mb`; putting corpus history
 * under the same name would file two unrelated retention policies together.
 */
export interface FinetuneConfig {
	/** A key in `models`. The model whose outputs a session fine-tunes. */
	teacher?: string;

	/** The window: how many rows `corpus/corpus.jsonl` holds. It costs storage and git history only - 2.9 KB compressed per row, measured 2026-08-27 over 2,459 scored rows and the 114 published items of that day - and it buys a bigger pool to sample a diverse session from. */
	corpus_rows?: number;

	/** The sample: how many rows one session draws from the window. A CEILING, not a demand - a session takes the lesser of this and what is left once the holdout is removed, and prints both numbers. It costs GPU hours rather than storage: estimated 1.8 h for 1000 rows over 2 epochs on a free T4, and no training job has run here yet, so that is an estimate (Guardrail #10). */
	train_rows?: number;

	/** Below this the corpus trains nothing, and a repair refuses to cut further. */
	min_rows?: number;

	/** How often the digest run harvests. A number and not a cron line: standard 5-field cron has no every-N-days field, and `on.schedule` is parsed before any step runs, so no value in config can ever reach it. The step wakes with the daily run, reads `harvested_at` from the committed meta file and decides for itself, which also means a missed day self-corrects on the next wake. */
	harvest_every_days?: number;

	/** How often `prune.yml` fires. Each firing costs one force-push of `main` - the single exception CLAUDE.md section 8 carries, and the reason it carries one is that git history is append-only, so deleting a corpus row does not delete its bytes. */
	prune_every_days?: number;

	/** Where the squash boundary sits. Retention is this number, full stop, and it is not a multiple of anything. At 30 and 60 the history holds 60 to 90 days of commits - 9 to 13 weekly harvests, 25 MB to 38 MB, flat forever. Two whole datasets survive any squash for free, because the boundary commit holds a complete copy of the corpus and so does the tip. */
	prune_keep_days?: number;

	/** The trailing days held out of training, by date and never at random. Production always runs on tomorrow's news; a random split puts the same story from three feeds on both sides and reports memorisation as success. It has to be shorter than the window has existed, or the split holds out every row and leaves nothing to train on. */
	holdout_days?: number;

	/** How many ideal summaries the hand-authored reference set aims to hold. The set is authored in slices and is usable before it is full, so this is a target rather than a floor - nothing refuses to run below it. */
	reference_rows?: number;

	/** How many of `reference_rows` are held back as test references and read line by line by a person. The rest are drafted with an expert model in an editor. Two numbers because they carry two standards and two costs: a drafted row is about two minutes, a read row about five, so this knob is the one that decides how many hours the set takes. */
	reference_test_rows?: number;

	epochs?: number;

	/** How long a training row is allowed to be. It sizes the SINGLE call, because that is the shape a training row has: a prompt the pipeline could have sent and an answer it could have returned, and the corpus holds single-call rows. At the committed extract.truncation_cap_tokens of 20,000 the worst case is 997 tokens of prompt overhead, 23,259 for the longest and hardest-tokenizing article the cap lets through, and 900 of answer - 25,156 tokens, which config/idhazh.json covers at 32,768 and this default does not. It does not follow --ctx-size on the teacher entry: that window holds the two-call pair, and nothing trains on a two-call row. A row longer than this is dropped and counted by the wrangler and by the notebook, never truncated, because a truncated target teaches the model to stop mid-summary; at the committed pair nothing is over. What it costs is GPU memory on the machine that trains, quadratically in attention - that machine is not the runner (Guardrail #2 does not reach it), and a card that cannot hold the row lowers SEQUENCE_LENGTH_OVERRIDE in notebooks/finetune.ipynb, which drops the long rows for that session only and says how many it dropped. */
	sequence_length?: number;

	/** How many write-critique-revise rounds the offline prompt loop runs before it stops (`backend/utilities/prompt_loop.py`). Nothing here runs on the runner or in the daily pipeline: the loop is manual, reads a frozen committed article set, and a candidate replaces the incumbent prompt only when it beats it on the deterministic, model-free scorers. More rounds cost more local model calls and buy more chances at a candidate that clears the gate; they change no digest a reader sees. */
	prompt_iterations?: number;
}

/**
 * What the pipeline accepts, once the prompt has asked.
 *
 * The ask lives on the band; this is the tolerance around it. Both are here
 * rather than in `evaluation` because a length miss is not a quality finding -
 * it is the model rounding a request - and a tolerance that cannot see which
 * band an item is in cannot be right for more than one of them.
 *
 * Every number is a starting point rather than a measurement (Guardrail #10). Our
 * own length figures describe a pipeline mid-repair - the prompt is being
 * tuned and a fine-tune is in flight - so none of them was used to pick one.
 */
export interface LengthPolicy {
	/** How far past the band's ask a reply may run and still publish untouched, as a share of `target_words_max`. Whichever of this and `overshoot_words` is larger wins, so a short band gets a usable allowance too: 20 percent of 45 words is nine, and nine words is one clause. */
	overshoot_ratio?: number;

	/** The same allowance as a flat word count, for the bands where a ratio is too small to mean anything. The larger of the two applies. */
	overshoot_words?: number;

	/** How far under the band's ask a reply may fall and still publish, as a share of `target_words_min`. Brevity is not a fault: a short summary of a long article is a thin summary, and the reader can see that it is short. Losing the story entirely tells them nothing. */
	undershoot_ratio?: number;

	/** Below this a reply is a failed extraction wearing a summary's clothes, and it is the one length that still fails an item. Applies only to sources longer than `floor_applies_above_source_words`, because a 40-word summary of a 60-word post is the correct answer. */
	absolute_floor_words?: number;

	/** Sources shorter than this are exempt from `absolute_floor_words`. A brief has no length to lose. */
	floor_applies_above_source_words?: number;
}

/**
 * What a run asks about its own lens weights, and how much of the answer it keeps.
 *
 * A lens weight is a number somebody picked, and nothing committed said what a
 * different number would have done. Every run now scores a bounded pool of its
 * candidates twice - once at the committed weights and once at a candidate
 * weight - and writes both to `state/counterfactual-scores/`. Nothing here
 * moves a weight, an item, or a published payload. These knobs decide what the
 * run asks and how many rows it leaves behind.
 *
 * The ledger is appended to forever, so every knob here is a bound on ONE
 * run's work rather than on the archive's size (CLAUDE.md Guardrail #12).
 * `window_days` is the other end of the same rule: it is how far back a reader
 * of the ledger may look, and it is what the retention pass keeps.
 */
export interface LensWeightsConfig {
	/** What the counterfactual multiplies each committed lens weight by. Above 1.0 on purpose: a heavier weight is the question a committed archive cannot answer afterwards, because it is the one that would have lifted a story the run refused, and a refused story leaves no other trace. 1.25 is an ESTIMATE and has not been measured - it is large enough to move a story across the cut on a crowded desk and small enough to stay inside the step a later tuning loop would allow. Exactly 1.0 asks nothing: both scores come out equal and every row is a byte with no question in it. */
	counterfactual_multiplier?: number;

	/** How many of each desk's refused candidates the run records, highest score first. Everything the run TOOK is recorded whatever this says. 20 keeps the band around the cut, where a bonus decides; a candidate further down would not cross under any weight this probe asks about, so its row carries no question. At about 80 items taken and five desks this is roughly 180 rows a run. 0 records the taken items alone. */
	counterfactual_refused_per_desk?: number;

	/** How far back a reader of the counterfactual ledger may look, and so how much of it the retention pass keeps. Both ends of one rule, in one knob, because a window a reader opens and a window the prune keeps have to be the same window or the reader reads a hole. 30 days is an ESTIMATE: long enough that a lens firing a few times a day still has a few hundred rows in it, short enough that a weight changed last month is not still being argued from. */
	window_days?: number;
}

export const LOG_LEVEL = ['DEBUG', 'INFO', 'WARNING', 'ERROR'] as const;

export type LogLevel = (typeof LOG_LEVEL)[number];

/**
 * Which records the pipeline builds, and how loud the logger that prints them is.
 *
 * Those are two different questions and this block holds both. **The flags
 * choose which records EXIST; `level` chooses how loud the logger is.** Turning
 * the level down to WARNING does not stop a per-item record being built, and
 * turning it up to DEBUG does not create one.
 *
 * One switch would not have done. Per-item lines cost a few hundred bytes a
 * run and prompt capture costs a run artifact, so an operator has to be able to
 * keep the cheap instrument and drop the expensive one. That is why there are
 * five flags here rather than a verbosity dial (Fowler, 2026-09-14).
 *
 * Every flag defaults ON, because the reason they exist is a 5x model-time
 * regression that ran for six days with nothing printing during a 200-minute
 * shard. They are defaulted on to be switched off once that is closed, so
 * **every one of them except `item_lines` carries its removal condition on the
 * line that declares it** (Guardrail #6), and each condition names the reading
 * that retires it rather than a piece of work that lands.
 */
export interface LoggingConfig {
	/** How loud the logger is, and nothing else. Unrelated to the flags beside it: they decide which records are built, this decides which of the built records are printed. It predates them and no removal condition applies. */
	level?: LogLevel;

	/** Whether an item logs a record when it starts and another when it finishes, success or failure. NO REMOVAL CONDITION, on purpose: this is the permanent instrument and not a debugging aid. A run that cannot say which item it is on, and which ones it got through, is the blind window the rest of this block exists to end. It is a knob at all only so an operator re-running one shard by hand can quieten it for that invocation. */
	item_lines?: boolean;

	/** Whether fetch, extract, label, summarize and faithfulness each log a record when they end. Retire it when the per-stage split has stopped saying anything the completion record does not: a week of runs in which no stage's share of item time moves by more than the run-to-run spread, and no item time is left unattributed. Until then a shard that dies on a timeout names no stage at all, and the completion record arrives only for an item that finished. */
	stage_lines?: boolean;

	/** How often, in seconds, to log elapsed time while a model call is in flight. 0 turns the heartbeat off and IS the retirement, so this knob retires itself rather than being deleted. A NEGATIVE VALUE IS REFUSED: a number that quietly means never when the operator meant often is the worst shape a misconfiguration of this knob can take. Set it to 0 once the slowest single model call in a full run has stayed under a minute for a week, because then a stuck call is visible from its own completion record and elapsed time adds nothing. Today the slowest call returns after 22 minutes having printed nothing at all. */
	waiting_heartbeat_seconds?: number;

	/** Whether the rendered prompts are written to a run artifact. Retire it when the prompt is no longer in question - a week of runs in which every item's recorded prompt token count matches what the budget predicts, with nothing truncated. At that point the SHA-256 and the token count each row already carries say what the text said, for a fraction of the bytes. */
	capture_prompts?: boolean;

	/** Whether the raw model replies are written to a run artifact. The most expensive thing this block can switch on, because a reply is the longest text in the run. Retire it when no item has been cut short for a week and the decoded token counts agree with what each row records, because the reply text is then answering a question nobody is asking. */
	capture_replies?: boolean;
}

/**
 * What the pipeline records about itself, and what an operator may switch off.
 *
 * Four switches rather than one master switch. Collection, scoring, publishing
 * and tracing fail in different ways and a reader has to behave differently
 * for each of them, so one switch would leave nobody able to say which
 * instrument went dark.
 *
 * **The item-health census is not on this list and must never be added to it.**
 * Every rate this project publishes divides by that census, so switching it off
 * would not thin a measurement - it would make every other measurement
 * unreadable. A rate printed without its denominator beside it is the exact
 * defect the census exists to prevent.
 *
 * An instrument that did not run writes an EMPTY cell, never a zero. A switch
 * here decides whether a row is written at all; it never changes the shape of a
 * row, so a month file stays readable across a day somebody turned something
 * off.
 *
 * **Every store names its own cleanup age.** One age covered
 * `state/item-health/` while `state/feed-health/`, `state/scores/` and
 * `frontend/public/telemetry/` had none, so three of the four grew with nothing
 * to stop them and the fourth was tuned by a number that said nothing about
 * them. The four full-grain windows are checked against the shards a console
 * read can still select, and a summary that replaces a full-grain window must
 * outlive it.
 */
export interface ObservabilityConfig {
	/** Whether the faithfulness scorer runs. False writes no row to state/scores.csv, so for those days the eval dashboard and the console's score panels list nothing and each item bands from the model-free counterweights instead. The digest still publishes. `--no-faithfulness` is the same switch for one invocation and overrides this; no flag turns it back on. It governs the daily pipeline's work stage only: `validate` and `qualify` are asked for by hand and each refuses outright without a scorer, so a standing switch cannot silence them into measuring nothing. Every run records the state of this switch on its run manifest. */
	evaluation_enabled?: boolean;

	/** Whether a run copies its item-health rows into frontend/public/telemetry/<YYYY-MM>.csv. False leaves that month file at whatever the last publishing run wrote, so every console chart ends on that date and the page says which day it read to. Nothing is lost: state/item-health/ still holds every row, so switching it back on republishes the gap. */
	telemetry_publish?: boolean;

	/** Whether a job records what silicon it drew - processor family, model, stepping, instruction-set flags, cache, and the platform's own name for the machine size - into state/host-fingerprint/<YYYY>/<MM>/<DD>.csv. False writes no row, and every throughput number that run takes becomes uncomparable with any other run's, because nothing says which machine produced it. Retire it when the platform stops mixing processor generations in one runner pool: a quarter of runs in which every job reports the same family, model and flags, which would make the row a constant and a constant is not a reading. */
	host_fingerprint?: boolean;

	/** The smallest buffer each side of the memory-bandwidth probe may allocate, so the probe holds twice this. Zero switches the probe off and leaves the bandwidth cell empty; every other cell of the fingerprint still gets written. It is a floor and not the answer: a buffer that does not clear the cache measures cache and reads as a memory figure several times too high, and the reported L3 across the machines this project draws spans 32 MiB to 480 MiB. So the probe raises the buffer to host_fingerprint_bandwidth_cache_multiple times whatever cache the machine it drew reports, and this value is what a machine reporting no cache at all gets. memcpy_probe_mib on the row records the size that was used. */
	host_fingerprint_bandwidth_floor_mib?: number;

	/** How many times the reported cache each side of the memory-bandwidth probe has to be. The probe holds two buffers, so at 2 the working set is four times the cache and no part of the copy can be served from it; below that the reading stops being a memory reading, and above it the runner pays memory it does not get back before the model server starts. It is one value because two readers need the same one: the probe sizes its buffer by it, and the console grades a committed row by it and withholds the copy speed of a row whose buffer did not clear the cache by this much. Two numbers in two languages would let a row the probe wrote correctly be refused by the page that draws it. */
	host_fingerprint_bandwidth_cache_multiple?: number;

	/** The fraction of RUNS whose scorer runs - never the fraction of items. A run scores every item or none, so a day's rows are never a partial sample of that day and a per-day rate stays honest. Below 1.0 most days write no eval row and the console's score panels thin to the sampled days. Not a switch: `evaluation_enabled` is the way to say off, and a rate of zero is refused so the two can never disagree about it. The draw is a digest of the run id, so it is reproducible from the committed manifest and blind to the run's content, and both the rate and the draw land on the run manifest whether or not the run was taken. A published rate is still computed from the item-health census, which is never sampled; the thinned ledger publishes distributions only. */
	sample_rate?: number;

	/** Whether a work shard builds a span tree. On by default: a span tree is the one thing the three ledgers cannot hold - a start instant, a parent, and a step too small to earn a column, the robots read inside the fetch and the prompt render and reply parse either side of the model call. It stays an instrument nothing reads: no page renders a span, no gate consults one, and the ledgers stay the record. True writes one JSON line per span to the committed trace under state/traces/, a short rolling window observability.trace_window_days bounds, and folds the shard's spans into the committed span rollup. That file is the only destination a span has, so no run reaches a third party whatever this says. */
	tracing_enabled?: boolean;

	/** How many days of raw span traces state/traces/ keeps. A trace is the evidence an operator opens to see one recent run step by step; the committed record is the span rollup, so a trace has a short life and a file past this window is deleted whole rather than folded - a fold would invent a total nobody reads. Seven days covers a week of runs, and the window is what keeps state/traces/ a constant size whatever the project's age rather than one that grows with it (Guardrail #12). It does nothing until observability.tracing_enabled is true: before that no trace is written and the prune walks an empty tree. */
	trace_window_days?: number;

	/** How long state/item-health/ stays readable item by item. Past it a month is folded to one row per (date, stage) and the full-grain shard goes, so a reader keeps every daily total and loses the per-item detail the console's failure list offers. Fourteen because console.max_window_days is 366, and a 366-day window reads 367 inclusive days, which can fall in fourteen calendar months - a window ending on the first of a month starts on the last day of another. Thirteen looks like a year plus the month being written and is one shard short of what the console can still ask for. */
	item_health_full_grain_months?: number;

	/** Months after which the folded item-health month is removed outright. Null means never, and never is the default: the fold is a small fraction of the shard it summarises, and deleting it would make a year-over-year comparison unanswerable, which Guardrail #10 then forbids citing at all. Set, it must sit ABOVE item_health_full_grain_months, or a month would be deleted before it was ever folded. */
	item_health_aggregate_keep_months?: number | null;

	/** How long state/feed-health/ keeps a month. It is a per-feed-per-run record rather than a measurement worth summarising, so its retention is one number and there is no aggregate under it. Fourteen for the same reason the item-health window is: the console reaches 367 inclusive days and those days can fall in fourteen calendar months. The ledger files by day and this age is still a month, so the prune takes a month's day files whole. */
	feed_health_keep_months?: number;

	/** How long state/host-fingerprint/ keeps a month. Null means never, and never is the default, so a clone that configures nothing deletes nothing. config/idhazh.json sets 14. A row here is one job's silicon on one run - the machine the platform handed us and what its model server counted - so it is deleted rather than folded: a total over a month fourteen months back names no machine and answers nothing. Without a window this tree grows every run for ever, one row per job per shard (Guardrail #12). Set, it may not sit below public_machine_keep_months, because the published machine shard is rebuilt from this ledger. The ledger files by day and this age is a month, so the prune takes a month's day files whole. */
	host_fingerprint_keep_months?: number | null;

	/** How long state/scores/ stays readable item by item. The eval ledger is the only record of how a summary scored, and the console's model panels take medians and percentiles over the rows themselves - so this is the window inside which a quality question can still be asked of the items rather than of a total. Fourteen matches the census it is read beside; a shorter one would leave a day whose failures are still readable and whose quality is not. */
	scores_full_grain_months?: number;

	/** Months after which a summarised score month is removed outright. Null means never, on the same argument as item_health_aggregate_keep_months: a summary is kilobytes and it is the only thing that makes a year-over-year quality claim citable. Set, it must sit ABOVE scores_full_grain_months. */
	score_archive_keep_months?: number | null;

	/** How long state/visuals/ stays readable attempt by attempt. Past it a month is folded to the eight-term group VisualAggregateRow declares and the full-grain shard goes, so a reader keeps every cause breakdown and every stratum and loses the per-attempt row and its join key. Fourteen matches the two ledgers it is read beside; a shorter one would leave a day whose failures are still readable and whose refused pictures are not. It is NOT in full_grain_months() yet, and the reason is that no console read opens one of these shards today - the panels that will are their own plan, and the window joins that check in the same commit as the first of them. */
	visuals_full_grain_months?: number;

	/** Months after which a folded visual month is removed outright. Null means never, on the same argument as the other two aggregates: the fold is the only record that a gate ever refused anything, and it is kilobytes. Set, it must sit ABOVE visuals_full_grain_months. */
	visual_aggregate_keep_months?: number | null;

	/** How long frontend/public/telemetry/ keeps a published shard. It must EQUAL item_health_full_grain_months and the contract refuses any other pair: the projection is the browser's copy of that ledger, so a published month whose source has been folded away is a rate nobody can check, and a source month with no published copy is a window the console cannot draw. */
	public_telemetry_keep_months?: number;

	/** How long frontend/public/run-days/ keeps a month of day rows. Fourteen because the console reaches 367 inclusive days and those days can fall in fourteen month shards, which is the same reason feed_health_keep_months is fourteen. It has no state ledger to be paired with: the source is the committed day payloads themselves, whose retention is the archive's, and this row is a reduction of two of them to counts. */
	public_run_days_keep_months?: number;

	/** How long frontend/public/day-metrics/ keeps a month of day records. Fourteen on the same argument as public_run_days_keep_months. The source under state/day-metrics/ has no age of its own - a day record is a few kilobytes and it is the only place a band count or an extraction census survives once the day's items are folded - so this bounds the published copy without claiming to bound the ledger. */
	public_day_metrics_keep_months?: number;

	/** How long frontend/public/machine/ keeps a month of machine rows. Fourteen on the same argument. The shard is folded from state/item-health/ and state/host-fingerprint/, so it may not outlive either source: a published month whose source months are gone cannot be rebuilt, which is the argument public_telemetry_keep_months makes for its own pair. */
	public_machine_keep_months?: number;

	/** How long frontend/public/span-rollup/ keeps a published shard. Fourteen on the same argument as the item-health copy above. */
	public_span_rollup_keep_months?: number;

	/** How long frontend/public/run-timeline/ keeps a published shard. Two, not fourteen, and it is the one published series no window preset can reach: the panel draws ONE run and names it, so a month older than the newest buys nothing a reader can select. The second month is there so a run on the first of a month still has the day before it. At roughly a kilobyte per item this is the widest published row we write, so keeping it at the console's window would publish megabytes nothing fetches. */
	public_run_timeline_keep_months?: number;

	/** The currency the console prints the counterfactual cost in, as an ISO 4217 code. Named rather than assumed: a bare number with a symbol in front of it is the shape a bill takes, and this figure is not a bill. */
	cost_currency?: string;

	/** What a hosted provider would charge for a million PROMPT tokens, in cost_currency. Priced apart from output because a provider prices them apart - output usually runs three to five times input - and one blended rate would understate a run that wrote a lot and overstate one that read a lot. This is the operator's number to set: nothing bills us, so the committed value is a documented starting point rather than a measurement (CLAUDE.md Guardrail #10's one carve-out). The console prints the rate it used and says whether it came from here or from the operator, and it labels the result a counterfactual - what the run would have cost elsewhere - never an amount owed. */
	cost_input_per_million?: number;

	/** What a hosted provider would charge for a million GENERATED tokens, in cost_currency. Same standing as cost_input_per_million: a documented starting point the operator sets, never a bill. Zero is allowed and means free rather than unknown, so a rate nobody has chosen is the committed default and not an empty cell. */
	cost_output_per_million?: number;
}

/** What to do with a reply that overshoots its band by more than the policy allows. */
export const OVER_LENGTH_ACTION = ['trim', 'publish'] as const;

export type OverLengthAction = (typeof OVER_LENGTH_ACTION)[number];

/**
 * A gzip-size guardrail per prerendered route, enforced by
 * `frontend/scripts/bundle-gate.mjs`.
 *
 * The gate reads `config/idhazh.json`, never this model, so a number here
 * would be a second copy of what the file already holds, free to drift from
 * the one the gate enforces. The default is empty for that reason: the
 * committed config is the single source, and this model owns only the shape
 * and the validation (Guardrail #6).
 *
 * **A number may live here only if it does not have to move when a run
 * publishes.** A weight that rises when the pipeline appends a day cannot be
 * bounded by a constant: the only way past a firing is to type a bigger one,
 * and a number too loose reads as green exactly like a number that is right.
 * A route whose weight moves at publish speed takes no number here, and the
 * property it stood in for is asserted directly instead -
 * `frontend/tests/payload-weight.spec.ts` looks for a day-payload marker in
 * every document that does not render a day, so it returns the same verdict
 * whatever the archive holds.
 *
 * A route that takes a number moves only when a person edits source. A number
 * that changes at review speed is a design statement; a number that changes at
 * publish speed is the defect above. A page that renders a day is never named,
 * for the neighbouring reason: the only way under such a number is to publish
 * fewer items, which caps the news rather than catching a regression. Those
 * pages are counted, reported and never failed.
 *
 * **Every number here is gzip -5, because that is what the reader pays.** The
 * reading behind that choice is in
 * `docs/reference/site-weight.md`.
 *
 * **A document is capped and a payload is capped, and they are different
 * jobs.** A document number catches a page that took on bytes it does not
 * render. A payload number catches a file a browser fetches growing past what
 * somebody priced, which no document number can see because the bytes are not
 * in the document at all. Every payload number survives the test above by
 * construction rather than by luck: each is derived from a bounded knob, so
 * publishing more cannot move one. `console/band.json` is bounded by
 * `observability.public_*_keep_months`, and `telemetry/` by the longest month
 * at the heaviest day a run can produce.
 */
export interface PageWeightConfig {
	/** Route class -> the largest gzip -5 size that route's prerendered HTML may reach. The committed values live in config/idhazh.json, which the gate reads; this default is empty so the numbers are not duplicated here where they could drift from the file the gate enforces (Guardrail #6). A route the object does not name is measured and reported by the gate but not failed. **A route may be named here only if its weight does not move when a run publishes** - a weight that rises as the pipeline appends a day cannot be bounded by a constant, and the property is asserted directly by frontend/tests/payload-weight.spec.ts instead. A page that renders a day is never named, because the only way under such a number is to publish less. */
	ceilings_bytes?: Record<string, number>;

	/** Build-relative POSIX path -> the largest gzip -5 size a file a reader's browser fetches may reach. A key naming a file bounds that file; a key ending in / bounds every file under that directory, each on its own, so a month series takes one number rather than one a month. Empty by default for the same reason as ceilings_bytes: config/idhazh.json is the single source and the gate reads the file. A key that matches no file in the build fails the gate - a guardrail over nothing still reads as a bound somebody checked. Each number is a guardrail on the same rule the routes follow: at least twice the heaviest the file can realistically reach, so only a change of a different order fires it. */
	payload_ceilings_bytes?: Record<string, number>;

	/** The largest gzip -5 total the console's payload fetches may reach on a cold load at console.default_window_days. It bounds the design rather than the data: the per-file guardrails say how heavy one shard may be, and this says how many of them one opening of the page is allowed to want. Zero means unchecked, and the committed config is where the real number lives. */
	cold_console_load_bytes?: number;
}

/**
 * The frame a person sets over the head of the published day, and what age does to it.
 *
 * Nobody reads this digest before it publishes and it publishes five times a
 * day, so a standing editorial decision can only reach a reader as arithmetic
 * that runs without one. These six numbers are that decision. The rule they
 * express and the measurements behind them are in docs/concepts/placement.md.
 *
 * Every cap here displaces and none of them shortens: a story a cap holds out
 * of the head keeps its place in the day, lower down. A reader cannot see what
 * was left out, so leaving something out is the one thing a frame may not buy.
 *
 * The three `freshness_` numbers are not caps and take nothing away either.
 * They are one curve, read when the page is drawn rather than when the story
 * was planned, and they decide where a story that has been running all day
 * sits against one that broke an hour ago. `placement.freshness_multiplier`
 * owns the arithmetic.
 */
export interface PlacementConfig {
	/** How many of the day's first stories the frame governs. A COUNT and never a share: what a reader sees before deciding whether to scroll does not grow with the day, and a share of a 731-story day is a head nobody reaches (Jony, 2026-09-11). The stream pages at twelve, so 20 is the cold load plus one page action. Past this slot the order is the score's alone. 0 switches the frame off and publishes the score's order whole. */
	head_items?: number;

	/** How many of the first head_items stories one desk may hold. 5 of 20 with five desks is the largest cap that still guarantees three different desks in the first twelve stories - the cold load - and four in the first twenty; 6 guarantees only two in the first twelve. Set on what the reader is guaranteed rather than on how often it fires, because measurement killed the alternative: over the 13 committed days carrying rank_score, read 2026-09-13 on Intel Core i7-1265U / Windows 11 / Python 3.14.2, the biggest desk in the top 20 ran at a median of 12 and reached all 20 on 2026-09-07, so EVERY cap from 4 to 10 fires on 85 percent of days or more and 'rarely binds' was not available to buy. Ruled 5 by Jony and by Editor independently. Raising it costs desks on the first screen; lowering it to 4 pins the head at four of each desk every day, which is a quota rather than a cap and cannot report a day one desk genuinely owned. */
	max_desk_in_head?: number;

	/** How far down the head one feed may not repeat. No feed holds more than one of the first this-many stories. Measured over the same 13 days, the biggest feed in the first ten ran from 3 to 8, so this is load-bearing rather than decorative. 0 switches the feed rule off and leaves the desk cap alone. */
	head_no_repeat?: number;

	/** How many hours a story keeps its whole score before age counts against it at all. A flat shoulder rather than a curve that starts falling at minute one: a story nothing has had time to answer yet should not be marked down for being new. 6 hours is an ESTIMATE and not a measurement - the day publishes five times, so 6 hours is about one publishing cycle, which is the shortest shoulder that lets a story reach the next run at full value. What would overturn it is the published age of the stories that actually led each committed day. 0 removes the shoulder, and age starts counting from the minute a story appeared. */
	freshness_offset_hours?: number;

	/** How far past the shoulder a story has to be before it is worth freshness_decay_at_scale of what it was. Read the two as one sentence: at this many hours past the shoulder, a story keeps that much of its score. The width of the curve is derived from those two numbers rather than typed, so a person sets a sentence they can read instead of a variance nobody can picture. 24 hours is collect.max_age_hours, the age past which a story may not be added to the day at all, so the shipped pair says a story that has been running for a whole admission window past its shoulder is worth half. */
	freshness_scale_hours?: number;

	/** What a story is worth freshness_scale_hours past the shoulder, as a share of what it was worth inside it. 0.5 is half, the same word collect.recency_half_life_hours already uses at plan time, so an operator reads one vocabulary rather than two. Exactly 1.0 switches the whole curve off: every story scores 1.0 at every age and the leading block is ordered the way it was before the curve existed. That is the revert, and it is one edit to one line. */
	freshness_decay_at_scale?: number;
}

/**
 * Every collection a pass may take from, and the word an operator types.
 *
 * A closed vocabulary, so a word outside it is refused with the whole list
 * rather than resolved against anything. The same rule `idhazh telemetry
 * prune` holds for its stores: a deletion command whose destination is an
 * arbitrary string is a deletion primitive pointed at whatever the caller
 * happened to pass (Guardrail #11).
 */
export const PRUNABLE_COLLECTION = ['workflow-artifacts', 'workflow-runs'] as const;

export type PrunableCollection = (typeof PRUNABLE_COLLECTION)[number];

/** The collections a pass may take from, and whether it may take anything at all. */
export interface PruneConfig {
	/** Report what a live pass would delete and delete nothing. True by default, so a fresh clone removes nothing it was not asked twice for. The CLI's --no-dry-run is the second word. */
	dry_run?: boolean;

	/** One policy per collection this may be pointed at. A collection absent from this map is refused by name: the vocabulary says the word exists and the map says whether this repository has drawn a line for it. */
	collections?: Record<string, CollectionPolicy>;
}

/**
 * The floors `corpus/reference-dataset-1/` is built to, and the manners it is built with.
 *
 * Every number here is a floor or a cap rather than a measurement, and the
 * builder refuses loudly rather than emitting a set that misses one. They are
 * config because a dataset whose floors are literals cannot be rebuilt at a
 * different size without a code change (Guardrail #6).
 *
 * Nothing here runs on the runner. `build_reference_dataset.py` reads the open
 * web once, by hand, off the daily path.
 */
export interface ReferenceDatasetConfig {
	/** The floor each side must clear. A disjointness test passes on an empty set, so a builder that wrote every article to one side would satisfy 'no domain on both sides' perfectly. This is what it cannot satisfy. */
	rows_per_split_min?: number;

	/** Distinct registrable domains each side must carry. A side drawn from three outlets measures those three outlets. */
	domains_per_split_min?: number;

	/** How many articles one outlet may contribute. Without a cap the set is the two largest wire services and a tail. */
	rows_per_domain_max?: number;

	/** Shorter than this and there is not enough article for a person to label, so the disagreement it produces is about the stub rather than about the words. */
	article_words_min?: number;

	/** Pause between fetches. A measurement is not a licence to hammer a server. */
	request_delay_seconds?: number;
}

/**
 * Every default here deletes nothing. A default is a promise, not a placeholder.
 *
 * The committed file is one step ahead of the defaults from 2026-09-13:
 * `image_months` is 13 there and -1 here. `dry_run` is true in both, so the
 * committed config names a window and still removes nothing - which is the
 * order this was landed in, so that the first evidence of what the window
 * selects arrives before the deletion rather than after it.
 */
export interface RetentionConfig {
	/** How long a rendered visual stays before the cleanup may take it. -1 disables the age window entirely and is the default, so a clone that configures nothing deletes nothing. Age-based only, never size: a size trigger deletes most on the day the reader has most to read. config/idhazh.json sets 13 from 2026-09-13, which is the first age window this project has ever had. `retention.cutoff` spends a month as 30 days, so 13 here is 390 days and not thirteen calendar months - 5.7 days shorter, which holds slightly less rather than slightly more. It is an archive policy and not a cap defence, and the measurement says so: rendered visuals arrive at 324,580 bytes a published day, so 390 days stands at 120.7 MiB for ever, 11.8 percent of the 1 GiB Pages ceiling, where 12 months would stand at 111.4 and 14 at 130.0. Those are 18.6 MiB apart against a one-spread band of 47.6 MiB, so the byte budget cannot separate them and the owner's 13 stands (Carmack, 2026-09-13). The derivation is docs/reference/site-weight.md, 'What a published day adds in rendered visuals'. */
	image_months?: number;

	dry_run?: boolean;

	/** How many months of day-validation receipts are kept under state/day-validations/. A receipt says one published day passed the rules as they stood, and it is consulted only to skip re-reading that day - so a receipt for a day the published archive no longer holds cannot be read and answers nothing. Fourteen matches the published windows the console reads, so the receipts outlive the days by a month rather than going first and costing a full re-validation. */
	day_validation_keep_months?: number;

	/** The fuse. An off-by-one in a date parse must not eat the archive. */
	max_deletes_per_run?: number;

	/** How long a trial run's ledgers under `state/<run.trial_state_dirname>/` are kept. Ninety days because it is the artifact retention this project already uses everywhere else, so a trial's rows outlive the run's own artifacts by nothing and a question asked of one can still be asked of the other. Nothing reads these rows - no published series, no gate, no console band - so the window is about disk and about a reader who opens `state/` and wonders what a directory is, rather than about evidence. */
	trial_state_days?: number;

	/** The size at which the built site can no longer be published, in MB. `idhazh site-weight` fails the job above it, and that failure is the whole difference between this knob and site_budget_mb: the other one warns and this one stops. Bounded on purpose - the 1 GB belongs to GitHub Pages, so config can lower the cap a run enforces and can never raise it (Guardrail #2). Lowering it buys an earlier and louder failure while there is still headroom to act in; no value buys more room. The console's site band is drawn against the platform's own 1 GB rather than this, because it reports the ceiling that exists and not the one this run chose to stop at. */
	pages_hard_cap_mb?: number;

	/** Logs a warning above this, and does nothing else: it never fails a build and never deletes. Sized in days of warning, not in round numbers. It sits 224 MB below the platform's 1 GB ceiling, which is 26 days of warning at the fastest growth this project has measured (a PNG on every item, 8,537 KB/day, 2026-08-23), against a 14-day target. The target is a judgement about one maintainer acting on one warning, not a measurement (Guardrail #10). The arithmetic and its inputs are in docs/reference/pipeline-cost.md, 'Where the alarm fires, and what it buys'. */
	site_budget_mb?: number;
}

export interface RunConfig {
	/** How many days behind the run's own date a day has to be before its writer files are folded into one settled file. Every job writes its own file under the day its rows name, which is what stops two jobs conflicting - and it leaves about a hundred small files in a busy day. Folding a day nobody will write again costs nothing and changes no answer, because a reader settles the rows either way. Seven days rather than one, because a day can still gain rows: a re-run reaches back, and a shard that died can be re-dispatched. Raise it if a late writer is ever seen landing in a folded day; lower it only to save files, and it saves none the day after it is lowered. */
	settled_fold_after_days?: number;

	/** What one run may hand the workers. It protects a worker from its own timeout: this number sizes the worst case a work shard and the route stage have to finish, and a worker killed at run.shard_timeout_minutes uploads nothing, so the items it held are lost. It is a guardrail and it only ever refuses - it never chooses content, ranks it, or reorders it. It began as a crash guard against a mis-parsed feed and supply overtook it: items_planned has been exactly this number on every run since 2026-08-25. Owner decision, 2026-09-05: 80, down from 160. What it is NOT is a bound on the day - the day runs five times, so 80 here publishes about 400. safety_ceiling_per_day is the one that answers that. */
	safety_ceiling_per_run?: number;

	/** What the whole day may publish, across every run of it. The per-run ceiling could never answer this: the day runs five times, so anybody reading 80 and picturing an 80-item day is wrong by a factor of five. A guardrail like its neighbour - it only ever refuses, and a day under it is untouched. It counts what earlier runs of this date actually put in front of a reader, so a run that failed to publish costs the day nothing. The default is the arithmetic of the design that already ships - five runs at safety_ceiling_per_run - so turning it on changes no day that has ever been published and only refuses a runaway. Lowering it is an editorial decision about how long a day should be, and it is the owner's. */
	safety_ceiling_per_day?: number;

	/** URLs per worker VM. Set by measured model-load amortization, not by taste. It does not decide the fan-out on its own and has not since the run ceiling came down: the fan-out is min(ceil(safety_ceiling_per_run / shard_size), max_parallel), which is min(16, 4) at the committed numbers, so max_parallel binds and a worker draws 20 items. Re-derived on 2026-09-14 against the two-span item and left here: it would have to rise above 20 to move the fan-out at all, and a worker carrying more items is the opposite of what a longer item wants. */
	shard_size?: number;

	/** The most workers a run may derive for itself. It is four rather than the eight digest.yml lets an operator dispatch, because eight has never published a day; the three conditions that would move it are in docs/reference/pipeline-cost.md. */
	max_parallel?: number;

	/** The work job's own timeout, which digest.yml reads from here. A backstop, never a budget: a worker has no clock of its own, and one killed at this bound uploads nothing, so the run loses every item that worker held. It rose to 200 from 150 as headroom for the coming two-call summariser change, not because any worker got slower - at run.safety_ceiling_per_run of 80 a worker draws 20 items, half of the 40 it drew before, so the base work roughly halves. Sized from the worst measured shard, not the median: over 80 shard rows on 2026-09-02 the worst used 135.4 minutes of the old 150-minute bound and the median used 78.5, and the second model call an item spends exactly that margin. **Re-derived on 2026-09-14 for the two-span item and left at 200.** The worst of those 80 rows carried 40 items, so the worst measured item is 203.1 s; each of the item's two calls now opens with a 256-token thinking span, which is 42.6 s a span at the measured 6.01 +/- 0.11 tokens a second (2026-08-23, ubuntu-latest, EPYC 9V74, llama.cpp b10598, three repeats), so the derived worst item is 288.3 s and a 20-item worker's worst shard is 96.1 minutes. 200 is 56 percent of the six-hour platform ceiling, well inside Guardrail #2. A slow worker is still answered by lowering the ceiling, never by raising this. */
	shard_timeout_minutes?: number;

	/**
	 * How much of shard_timeout_minutes the worker keeps back for itself, so it stops on its own clock instead of being killed on the platform's. A worker killed at shard_timeout_minutes uploads nothing, so every item it had already finished dies with the ones it had not started: on 2026-09-15 two of four shards went that way and the day published 66 stories against a plan of 80.
	 *
	 * What the worker does with it: once the time left is less than the slowest item this shard has already finished, it starts no more. That needs no estimate and calibrates itself to whichever processor the shard drew, which is worth 24 percent between an EPYC and a Xeon. This reserve covers what happens after the last item - writing the records, the manifest, and the artifact upload. It is the one number here that is not derived: raise it if an upload is ever cut off, and never lower it to fit one more story.
	 */
	shard_wrap_up_minutes?: number;

	/** How long a job may keep trying to push what it already committed. The loop was three attempts, and a fixed count is spent at once however high it is set once several runs commit together - an optimistic rebase-and-push converges at any commit rate and a counter does not. 300 s is 25 percent of the assemble job's 20-minute timeout: measured on run 35701213155, that job used 1.8 of its 20 minutes, so 18.2 minutes were spare. The work shard does not read this number. Its commit step names 120 s in its own env block, because the whole of what it keeps back for everything after its last item is shard_wrap_up_minutes, which is 12 minutes - 300 s would be 5 of them. What would move this is the `push attempt=` line the loop prints, over twenty runs: a first-push success rate above 95 percent means the deadline is almost never spent and the number can rise, and below 80 percent means no deadline is the right answer for what is going wrong. */
	push_deadline_seconds?: number;

	/** Below this, the run additionally opens an issue. */
	success_floor_pct?: number;

	/** Where a trial run's ledgers go, under `state/`. Null is production and is the default, so a run that says nothing writes where it always did. Set it and every day shard this run appends lands under `state/<name>/` instead - the seen store, feed health, item health, the published ledger, the traces and the rollups, all of them, because a run that split them would put half a trial in the published series. Owner decision, 2026-09-15: a run that exists to exercise production's code path must not be readable as a production day. `retention.trial_state_days` is what empties it again. */
	trial_state_dirname?: string | null;

	/** How many times a qualification shard replays each item. Three is the smallest count that separates a model that is deterministic from one that happened to agree twice, and it is the floor rather than the default because a report built on fewer passes is a report that cannot fail. It used to be a dispatch input an operator typed per run, where `1` was legal and nothing downstream could refuse it. Ten is the ceiling because that is past any determinism question; a run that wants more edits this field. `idhazh qualify --repeats` overrides it for one invocation and is refused on the same floor. */
	qualification_repeats?: number;

	/** Whether `idhazh qualify` summarizes the way the digest does. True is the digest's own path: the article is labelled and then summarized, in two adjacent calls. False is the qualification's own single call, which is what it did until 2026-09-15 and what every shard before that date measured. True by default because a gate that clears a call path nothing publishes has cleared nothing, and the switch exists so a run that goes wrong on it can be put back without a code change. Moving it moves every per-item number in a shard, so `QualificationShard.calls_per_item` records which side produced one. */
	qualify_on_the_production_path?: boolean;
}

/**
 * How alike two of a day's items have to be before they are one story.
 *
 * One score, and the score is a weighted sum of terms that each run 0 to 1.
 * Nested rather than three flat knobs under `assemble` because the weights
 * carry an invariant ACROSS them - they sum to 1.0 - and a knob whose legal
 * value depends on another knob's value belongs in the model where a validator
 * can see both.
 *
 * **The sum-to-one rule is what keeps the floor meaning something.** The floor
 * is a number on the same 0-to-1 scale as every term, so a person reading
 * `config/idhazh.json` can compare the floor against a term without first
 * working out what the weights add up to. Let them sum to 1.3 and the floor
 * silently becomes easier to clear every time a weight moves, which is the
 * failure this model exists to make impossible.
 *
 * It ships with all the weight on the cosine, which is exactly what the pass
 * scored before this model existed. The weights are fitted against hand labels
 * in a later change; until then this is a rewrite that changes no published
 * group rather than a retune.
 */
export interface SameStoryConfig {
	/** How much of the score is the cosine between the two vectors the day already carries. 1.0 ships, which is the whole score and is what the pass used before the composite existed - so the composite lands changing no published group, and the weights move against labels rather than against taste. It is the strongest single term measured so far: it separates 97.4 percent of the labelled pairs. NOT comparable to assist.similarity_floor, which scores a reader's query against an item rather than two items against each other, so the two distributions are different shapes. */
	cosine_weight?: number;

	/** How much of the score is the share of words the two items' key points have in common - the words of both lists reduced the way a headline is reduced, then what they share over what they have between them. 0.0 ships, so the term is computed and logged and carries no weight yet: the composite is a rewrite first and a retune second. It is the only term beside the cosine whose different-story pairs stay below its same-story pairs with room to spare - a 99th percentile of 0.0962 against a same-story median of 0.2419, so the two populations barely touch - which is why it is the second term rather than one of several. */
	key_point_weight?: number;

	/** What the weighted score has to reach before two items are one story, and EVERY pair inside a group has to reach it - not only each item against the one it joined. On the same 0-to-1 scale as every term, because the weights sum to 1.0. Set by labels rather than by taste: 0.94 is the first round hundredth above the highest pair marked as two stories in the eleven committed days read on 2026-09-01, which put that pair at 0.9317. The 200 pairs labelled on 2026-09-19 put it at 0.9407 instead - ABOVE this line - so the margin this number used to carry is gone and the line now admits one known two-story pair. No line fixes that: the same labels mark a pair at 0.9406 as one story and another at 0.9409 as one story, so the two populations interleave inside three slots. Raising this costs missed duplicates, which a reader sees as the same story twice; lowering it costs a false merge, which is a story that never ran, so the two errors are not equal and this number leans high. It was measured against the cosine alone, which is what the shipped weights still score. */
	floor_min?: number;

	/** The content-similarity judge's own knobs, absent when that judge is not configured. Optional rather than built by a default factory, because a factory cannot express 'no judge is configured' - absent and present-at-defaults read the same afterwards, so nothing could tell the council's own night apart from a night this judge runs. The council's runner numbers are in `council` and stand whether or not this block does. */
	adaptive_dedup_threshold?: SimilarityThresholdConfig | null;
}

/**
 * How the merge line fits itself, and the gates it has to clear before it may.
 *
 * Nested inside `SameStoryConfig` rather than flat under `assemble`, for the
 * reason that model's own docstring gives: a knob whose legal value depends on
 * another knob's value belongs where a validator can see both. The daily caps
 * are counted in slots of `bin_width` and have to stay inside the band the
 * record slices, and `band_low` has to sit below the line `floor_min` currently
 * holds.
 *
 * The line falls fast and rises slow. Lowering it publishes less, which is the
 * house rule, so both the damping weight and the daily cap are larger going
 * down than going up - and a validator here refuses a config that reverses it.
 *
 * **Nothing reads this block yet.** It ships with `enabled` off, so a fresh
 * clone publishes exactly what it published before the block existed.
 */
export interface SimilarityThresholdConfig {
	/** Whether assemble reads the fitted line instead of floor_min. Ships off, so a fresh clone publishes exactly what it published before this feature existed. Removal condition: delete this flag once row 9 has run 14 days and the fitted line has moved no published group a person disagreed with. */
	enabled?: boolean;

	/** The lowest score worth judging. Below it two items are nowhere near one story, so a verdict costs a model call and moves nothing. 0.88 is where the measured pairs start: the lowest of the 200 labelled pairs sits at 0.8807, so the band opens below every decision the line has to get right. */
	band_low?: number;

	/** The top of the band. 1.00, because a cosine goes no higher and a pair at 0.999 is still a pair the record should hold a slot for. */
	band_high?: number;

	/** How finely the record slices the band, and therefore the resolution of the fitted line. 0.001 is already finer than the labels can be read apart: the 200 pairs marked on 2026-09-19 put a one-story pair at 0.9406, a two-story pair at 0.9407 and another one-story pair at 0.9409, so three slots hold both marks. Finer costs slots and buys no separation the labels can support. */
	bin_width?: number;

	/** What share of the record's agreed-NO verdicts the fit sets aside at the top before placing the line - a share of NO readings, never of judged pairs. It is what stops a handful of wrong NO verdicts setting the number: a single NO at 0.97 would otherwise pin the line at 0.971 for ever, because the line is the stopped slot's upper edge. The question it answers is how many wrong NO verdicts ONE news cluster can produce before it sets the line, and the answer is not one. In the 200 labelled pairs of 2026-09-19 all four two-story marks came from a single cluster that produced 29 pairs. At minimum_negatives of 200, floor(total * 0.03) sets six verdicts aside, which survives that night; 0.01 sets two aside, which does not. */
	discard_share?: number;

	/** How close a proposal has to come to the applied line before the day counts as no move at all, counted in slots of bin_width. 1 slot, because a smaller move is one the fit cannot represent: the line is a slot's upper edge, so a step of half a slot lands on no edge the next walk can produce. Without it the damping leaves a geometric tail whose steps shrink below one slot for ever and the applied line never formally arrives at its proposal. */
	dead_zone_bins?: number;

	/** How much of a DOWNWARD move lands today. Down is the fast direction: lowering the line publishes less, and the house rule is to err on the side of publishing less. 0.50 is half the remaining gap a day rather than the whole gap, because one judge misreading one news cluster produces a block of adjacent wrong verdicts on one night, and an undamped fall would take that whole block at once. An ESTIMATE; what replaces it is the first fortnight of written rows. */
	fall_weight?: number;

	/** How much of an UPWARD move lands today. Up is the slow direction: raising the line merges more stories together and publishes fewer of them separately, so it arrives over a month. 0.15 with the up cap takes the line from 0.88 back to 0.94 in about thirty-three days, against about ten days for the same distance downwards. An ESTIMATE, replaced by the first fortnight of rows. */
	rise_weight?: number;

	/** The furthest the line may fall in one day, counted in slots of bin_width. 10 slots is 0.010 at the committed width. Counted in slots rather than written as a decimal because 10 slots down is checkable against the record the line was fitted from, and 'one percent of the scale' is not. Bounded by the band: a step wider than the band leaves the record that proposed it. */
	max_down_bins?: number;

	/** The furthest the line may rise in one day, counted in slots of bin_width. 3 slots is 0.003 at the committed width - under a third of the fall cap, which is the whole asymmetry in one number. Both directions are capped rather than one, because damping alone is not a brake a reader can bound and the step-change guard ships off. */
	max_up_bins?: number;

	/** How far out of line one day's evidence has to be before the guard holds. Measured against the median daily shift of the last fourteen rows, never a standard deviation: the daily shift shrinks as 1/days and is not normally distributed, so a sigma is the wrong ruler. 5 is an ESTIMATE. What replaces it is the spread of the first fourteen written rows. */
	step_change_multiple?: number;

	/** Whether the guard actually holds the line or only records that it would have. Ships off, because enforcing a hold on a multiple nobody has measured lets an unchecked number freeze the line. Removal condition: delete this flag once step_change_multiple carries a value measured from fourteen written rows. */
	step_change_guard_enforced?: boolean;

	/** How many pairs a day may be judged. 200 pairs over the council's committed four shards is 50 pairs a shard, which at the worst pair measured - 110.98 s on 2026-09-18 - is 1 hour 32 minutes of model time a shard, and 1 hour 19 minutes at the measured average of 94.53 s (docs/reference/benchmarks/what-a-judge-pair-costs.md). Raising it is a job-timeout question before it is a quality one, and this judge refuses a value that does not fit the window the council leaves a unit to work in - checked when the council resolves this judge, not when config is read, because the per-pair cost is this judge's own measurement. */
	pair_budget?: number;

	/** How many pairs a judging shard finishes before it writes its verdict file again. Every pair, because the file holds one shard's slice of pair_budget - 50 rows at the committed numbers - and rewriting 50 rows is not measurable beside a pair that costs 110.98 s. It buys the case the cadence exists for: a shard that stops on its clock, or dies, still leaves every pair it had already judged. Counted in pairs because a pair is the unit this judge stops between. Raise it only if a run ever shows the rewrite costing anything. */
	flush_every_pairs?: number;

	/** How far the judge's sampler may stray from the likeliest word. 0.0, because every pair is read twice with the two summaries swapped and the two readings are then compared: at 0.0 a disagreement is position bias, which is the thing disagreement_max gates on. Above 0.0 the same pair can answer differently with nothing swapped at all, so the comparison measures sampling noise instead and the gate stops meaning what its own name says. It sits here rather than on models.summarize.inference because that entry pins its temperature for writing summaries, which is a different job on the same weights. */
	judge_temperature?: number;

	/** Agreed NO verdicts the record needs before the fit may set the line at all. 200, because discard_share is 0.03 and three percent of 200 sets six verdicts aside - enough to absorb the four wrong NO verdicts one news cluster produced in the 200 labelled pairs of 2026-09-19. Three percent of 100 sets three aside, which does not. */
	minimum_negatives?: number;

	/** Judged pairs at or above the current line the record needs before the fit runs. 30 is an ESTIMATE of enough to notice a wrong merge rate; what replaces it is the first month of holdout readings. These pairs are the entire precision measurement and are never sampled away. */
	minimum_above_line?: number;

	/** Distinct dates the record needs before the fit runs. 10, so the line is never set by a fortnight of one kind of news. */
	minimum_days?: number;

	/** How often the two orders may disagree before the run holds with judge_unstable. 0.15 means one pair in seven flipping with the order, at which point the verdicts are reading the prompt layout rather than the articles. An ESTIMATE; what replaces it is the first fourteen written rows. */
	disagreement_max?: number;

	/** What share of readings may be UNCLEAR before the run holds with judge_uncertain. 0.35 is where the middle bucket starves the two the line is fitted on. UNCLEAR means the text does not say enough, never that the pair is halfway between. An ESTIMATE, replaced the same way. */
	unclear_max?: number;

	/** How far back step 4 looks to ask whether a whole week of fresh judgements changed the answer. 7 days, because that is a week of news rather than a statistical window: the damping already carries a day-to-day correlation of 0.85, so a shorter window asks the smoothing whether the smoothing worked. */
	settled_window_days?: number;

	/** How small the week-on-week move has to be to count as settled. 0.001, which is one bin width, so settling is measured at the line's own resolution and never at a precision the fit cannot produce. */
	settled_delta?: number;

	/** How many days back assemble will look for a fitted line before it falls back to the config floor. 7, because the fit writes a row every day, so a gap longer than a week means the judge has been down a week and the committed config value is the honest answer. */
	applied_lookback_days?: number;

	/** How many written rows the guard's median is taken over. 14 rows, counted as rows rather than as days: a window in days returns fewer rows than it names after any missed run, and a median over four rows would let the guard fire on noise. The fit reads a window of days wide enough to find them and takes the newest 14 it has. */
	step_change_window_rows?: number;
}

/**
 * What the prompt asks the model for, and what the pipeline accepts back.
 *
 * A prompt is a request and a gate is a rule. Asking for a tighter range than
 * we accept is what stops a two-word miss from losing a story, so the ask
 * (`bands`) and the tolerance around it (`length_policy`) both live here,
 * where an operator editing one can see the other.
 *
 * The allowance is derived from the band rather than applied flat to all five
 * rungs, so it can see which band an item is in. No length outcome except
 * `length_policy.absolute_floor_words` drops an item: a reply outside the
 * tolerance is still a story, and deleting it would cost the day a story to
 * punish the model for rounding.
 *
 * Every band and title number here is substituted into the prompt text at
 * render time, so the prompt cannot drift from the bounds the pipeline enforces
 * (Guardrail #6). `key_point_restatement_ceiling` is the one value that is not asked
 * for: it is a post-parse check `to_summary` runs on what the model returned,
 * and it lives here because the count it protects - the band's key_points_min -
 * does too.
 */
export interface SummarizeConfig {
	/** One length ask per article size, ordered by min_source_words. A release note and a long read asked for the same range gives a padded summary of the first and a thin one of the second. */
	bands?: SummaryBand[];

	/** How far a reply may miss its band's ask and still publish, and what happens when it misses by more. Config rather than code so the tolerance can move with the prompt while the prompt is still being tuned. */
	length_policy?: LengthPolicy;

	/** Shortest title the prompt asks for. Below this a headline stops naming who did what, and the reader is back to guessing from the source's own framing. */
	title_words_min?: number;

	/** Longest title the prompt asks for, and the decoder's ceiling. Unlike the summary there is no floor on the decoder: a headline does not stop early, and a floor would only pad a good short one. Capped at 40 so the widest decoder ceiling this can produce still fits an UntrustedLine, which is what the payload field is. */
	title_words_max?: number;

	/** Longest quotation the prompt allows, and it must be attributed. Long enough to carry a real sentence somebody said, short enough that a summary cannot become the article. The ledger measures the run that actually came back (`verbatim_run`), so this number is the ask and that column is the answer. */
	max_verbatim_words?: number;

	/** Longest key point the decoder will emit, spent as a character rail at 12 characters a word the same way the title and the summary are. There was no rail here at all until the two-call planner needed one: with an unbounded string in the reply shape, the worst-case reply length is not arithmetic, and a budget derived from bounds that do not exist is a guess with a table next to it. Deliberately above anything observed rather than tight to it - a maxLength is a hard grammar stop that truncates mid-word, so a rail set at the observed maximum turns a slightly long key point into a parse failure for the whole item. It sits well above the longest key point the pipeline has published, so only a reply of a different order reaches it. */
	key_point_words_max?: number;

	/** Above this share of a key point's four-word phrases already appearing in the summary, `to_summary` drops the key point as a restatement and keeps the item with the rest. A distinctness floor, not a word ban: only the overlap ratio counts, never a single shared word, so a key point may reuse the summary's words and still add a fact. A starting point, not a calibrated threshold (Guardrail #10): it sits in the wide gap between a key point that adds a fact and one that is a verbatim slice of the summary. The drop never removes the last key point - the payload requires one - so a reply whose every key point restates still publishes with the least-restating up to the band's key_points_min. */
	key_point_restatement_ceiling?: number;

	/** Most paragraphs a published summary may hold. One turns the feature off and folds every summary back to a single block, which is what every day published before 2026-09-17 carries. Two is what ships: a reader scanning a wall of 114 words gets one place to breathe, and a third break in a summary this length makes paragraphs that are one sentence each. The cap is enforced by folding the extra text into the last paragraph kept rather than by dropping it, so it can never shorten a summary. */
	paragraphs_max?: number;

	/** The length, in words of the ASK, at and above which the prompt asks for a second paragraph. Below it the prompt asks for one block, because a break in a 45-word summary makes two half-thoughts rather than two paragraphs. Compared against the band's target_words_max, so the question is asked once per band rather than per article: at the committed bands that is the two longest of five. A request, not a control - the shape a reply actually has is whatever `normalize_prose` folds it into, and a model that writes one paragraph for a long article is published as one. */
	second_paragraph_from_words?: number;

	/** Whether the two-call sequence is sized for a summarize-and-plan call that asks for a picture. True is what the production run does and what ships. It exists so a case of the pipeline test workflow can run the summary-only path end to end: setting `visuals.enabled_kinds` to nothing takes the plan fields off that call's grammar, and this takes the plan's decode budget out of the window sizing beside it. The two move together or the sizing is wrong in the expensive direction - it reserves room for a decode that never happens, and refuses articles that would have fitted. */
	asks_for_a_visual_plan?: boolean;
}

/** How long a summary to ask for, once the article is at least this long. */
export interface SummaryBand {
	/** The band applies to articles this long and longer. */
	min_source_words: number;

	/** The shortest summary the prompt asks for. */
	target_words_min: number;

	/** The longest summary the prompt asks for. */
	target_words_max: number;

	/** What to do with a reply that overshoots past the policy's allowance. A short band trims at the last complete sentence that fits, because wire-shaped prose front-loads and a tail cut is safe. A long band publishes over-length instead: on a feature the qualification lands last, so cutting the tail is how a summary becomes wrong rather than merely long. */
	over_length_action?: OverLengthAction;

	/** The fewest key points this band asks for, and the decoder's floor for the band. The prompt and the response schema read this same number. Never below 1: the published digest refuses an item with no key points. */
	key_points_min?: number;

	/** The most key points this band asks for, and the decoder's ceiling for the band. A short band asks for fewer: a 40-word summary of a 60-word post cannot carry five distinct facts on top of itself, so the extra key points only restate it. On the band, not the whole config, so the shortest band asks for one where the longest asks for five. */
	key_points_max?: number;
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

/** The ranking weight of a source tier. Tier 1 is the institution that IS the fact. */
export interface TierWeights {
	institution?: number;

	trade_press?: number;

	community?: number;
}

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

export const VISUAL_KIND = ['chart', 'none'] as const;

export type VisualKind = (typeof VISUAL_KIND)[number];

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

/**
 * Planning, rendering and serving knobs. "Nothing" is the common answer, by design.
 *
 * `enabled_kinds` is the gate that keeps an unbuilt renderer unreachable. It
 * is a list rather than a flag so that a kind added later is switched on by a
 * config edit rather than by a code change.
 *
 * `asset_base_url` is the same shape at the other end of the pipeline: where a
 * browser asks for a drawing the pipeline already published. It ships empty,
 * which means this site, and the whole point of it existing empty is that
 * moving the bytes off the 1 GB Pages cap is then a config edit rather than a
 * project.
 */
export interface VisualsConfig {
	/** Kinds the planner may choose. `none` is always available and never listed. Chart is the only one left: diagram drawing shipped off - the model drafted it zero times in 88 items and rendered it zero times in 703 (ubuntu-latest, 2026-08-24/25), while its presence made the planner's own pre-filter unfireable, because a diagram's steps come from prose and nothing about it is decidable in advance - and its renderer was deleted with the Mermaid round trip on 2026-09-05. */
	enabled_kinds?: VisualKind[];

	/** Below this a chart says less than the sentence it sits under. */
	min_chart_points?: number;

	max_chart_points?: number;

	/** How many equal-width bins a histogram's values fall into. Binning is config and never the model's - it has no numeric field that could say. A histogram's bins ARE the marks a reader counts, so this sits inside the same min_chart_points to max_chart_points window every other type's mark count does, and a value outside it is refused here rather than left to refuse every histogram of every run for a reason no article can fix. It is also the floor on how many values a histogram may cite: fewer values than bins leaves a bin empty, and a bar counting nothing has no chain and draws nothing. The default is min_chart_points rather than a textbook rule for a sample size this stage never sees. */
	histogram_bins?: number;

	min_diagram_steps?: number;

	max_diagram_steps?: number;

	/** The ladder, as one list: how many rungs it has and how high each one is. Entry n is the percentile of depth-0 published mark counts a downgrade at depth n+1 must reach, so the length is the deepest permitted downgrade and the depth after it refuses. Two entries is the design's own ladder - the median at the first step down, the 75th percentile at the second, refuse at the third. An empty list is the ladder switched off, which is one knob doing two jobs on purpose: a separate on-off flag can disagree with the rungs beside it, and zero rungs is already an unambiguous no. It must rise, because a floor that does not is not an escalating one. The floor it reads is a mark count, which the validator already bounds to min_chart_points to max_chart_points, so two adjacent percentiles can land on one integer and the ladder quietly stops escalating - that is visible as two depths recording one floor, and the answer is to move these numbers rather than the mechanism. */
	downgrade_floor_percentiles?: number[];

	/** The planner emits a small object. It does not need the summarizer's budget. */
	max_output_tokens?: number;

	/** How many quantities the router may choose between. A long indexed menu is lost-in-the-middle for a small model picking an integer index. */
	max_facts?: number;

	/** How much of the article's own opening the router reads beside the summary. This is most of each request's prefill, and prefill is most of the stage's wall-clock, so it is a measured lever rather than a literal (Guardrail #6). */
	lead_words?: number;

	/** One routing POST may wait this long. Sized from the measured worst routed item - 56.0 s on ubuntu-latest, 2026-08-24 - doubled. The stage used the summarizer's 150-minute shard bound before this existed, which is longer than the job it runs in, so it could never fire. */
	request_timeout_minutes?: number;

	/** Where a browser asks for a published drawing. Empty means this site, and empty is what ships: the drawings sit in the bundle, and the bundle is what the 1 GB Pages ceiling counts. An absolute `https://` prefix moves the drawings a reader scrolls to off that ceiling, and the committed path is joined onto it unchanged - so which file is asked for never moves, only where it is asked for. Two costs, both measured 2026-09-02 against the candidate host: it caches for five minutes, so a repeat reader refetches, which is real on a slow connection; and the page's own `connect-src` gains that one origin, so the browser stops being the thing that makes reaching anywhere else impossible. Kept shut until the site's measured growth says otherwise. */
	asset_base_url?: string;
}

/** `config/idhazh.json` - every tunable, schema-validated. */
export interface AppConfig {
	version?: string;

	run?: RunConfig;

	council?: CouncilConfig;

	bench?: BenchConfig;

	collect?: CollectConfig;

	extract?: ExtractConfig;

	elements?: ElementsConfig;

	/** Which file under config/models/ holds the active model. The whole swap: every fact about a set of weights - the repository, the digest, the window they were measured in, the markers their server renders - lives in the file this names, so pointing at another committed file swaps the model and pointing back reverts it, with the previous model's measured numbers still on disk rather than in git history. It carries a default naming the committed file so a fresh clone runs unconfigured (Guardrail #6). */
	models_file?: string;

	summarize?: SummarizeConfig;

	evaluation?: EvaluationConfig;

	drift?: DriftConfig;

	retention?: RetentionConfig;

	prune?: PruneConfig;

	visuals?: VisualsConfig;

	assemble?: AssembleConfig;

	placement?: PlacementConfig;

	lens_weights?: LensWeightsConfig;

	ui?: UiConfig;

	assist?: AssistConfig;

	console?: ConsoleConfig;

	page_weight?: PageWeightConfig;

	finetune?: FinetuneConfig;

	reference_dataset?: ReferenceDatasetConfig;

	logging?: LoggingConfig;

	observability?: ObservabilityConfig;
}
