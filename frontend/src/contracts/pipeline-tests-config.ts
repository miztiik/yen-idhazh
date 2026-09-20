// Generated from `backend/idhazh/contracts/pipeline_tests.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One address a dispatch may draw, and the feed it came from. */
export interface PipelineTestCandidate {
	/** An article this pipeline has fetched, extracted and summarized before. Real rather than synthetic: the extractor's job is other people's markup, and a page we wrote would test none of it. */
	url: string;

	/** The feed in `config/sources.json` that carried it. Everything else the run needs about the address - the vertical, the tier, the form - is read off that feed, so it is declared once and this file cannot disagree. */
	source_id: string;

	/** The page's own headline. A daily run reads this off the feed entry, and a dispatch has no feed to read - the address is pinned and has long since fallen out of its feed's window. So it is declared here, and the plan step fills it in exactly where `discover` would have. Required rather than optional: an item with no headline is one the extractor now refuses, so an optional field would let a dispatch draw a candidate it cannot summarize. */
	title: string;
}

/**
 * One pass over the two articles, and what it changes about the run.
 *
 * A case is a whole pass rather than a knob, because the numbers that matter -
 * wall clock, tokens a second, what the picture cost - are per pass. Three cases
 * over the same two articles is what makes the difference between two of them
 * readable; one case over six articles is not.
 */
export interface PipelineTestCase {
	/** What the case is called in the log and in the artifact. */
	id: string;

	/** The model server's slot count for this case. None leaves the committed value, which is what the production run serves. A case that moves it needs the server restarted, because the slot count is fixed when the process starts. */
	n_parallel?: number | null;

	/** The window for this case. None leaves the committed value. A case that raises the slot count raises this with it: llama-server divides the window it is given between its slots, so two slots on the committed window is a 32,768-token slot rather than the 65,536 the production gate admits articles against - and the worst article the truncation cap admits needs 54,887. Leaving it alone would make the case a test of a smaller window wearing a concurrency case's name. */
	n_ctx?: number | null;

	/** Whether the second call may ask for a picture at all. False writes an empty `visuals.enabled_kinds`, so no picture is reachable and the gate takes the plan fields off the grammar, and it writes `summarize.asks_for_a_visual_plan` false so the window is sized for the call that is really sent. One knob, because the two have to agree: a window sized for a plan that is never asked for refuses articles that fit. */
	asks_for_a_visual_plan?: boolean;
}

/** `config/pipeline-tests.json` - the candidate addresses and the cases. */
export interface PipelineTestsConfig {
	version?: string;

	/** How many addresses one dispatch draws. Two is what fits the hour: the cases run in sequence over the same articles, so the cost is this number times the number of cases. */
	articles_a_dispatch?: number;

	/** What one dispatch is allowed. The workflow's own `timeout-minutes` is this number, and a test holds the two together so the bound lives in config rather than in the YAML. */
	budget_minutes?: number;

	/** The addresses a dispatch draws from. One per feed, all distinct. */
	candidates: PipelineTestCandidate[];

	/** The passes, in order. The first is the baseline the rest are read against, so there are at least two: one case measures nothing it can be compared with. */
	cases: PipelineTestCase[];
}
