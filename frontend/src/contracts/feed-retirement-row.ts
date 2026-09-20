// Generated from `backend/idhazh/contracts/feed_retirement.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * Why an address was retired. Two members, and adding a third is a design change.
 *
 * Retiring on anything softer than `410 Gone` eventually removes unique
 * primary or regional reporting over a bad week, and nothing here can put it
 * back without a person noticing it went. That clause stands. `LOW_YIELD` is
 * what it costs to answer it: three evidence floors and a dwell, spelled out
 * in this module's docstring, so no single bad week reaches this row.
 */
export const RETIREMENT_CAUSE = ['http_410', 'low_yield'] as const;

export type RetirementCause = (typeof RETIREMENT_CAUSE)[number];

/** One retired endpoint, one row. */
export interface FeedRetirementRow {
	version?: string;

	feed_id: string;

	/** The address that was retired, as `feed_health.derive_endpoint_key` spells it. */
	endpoint_key: string;

	retired_on: string;

	/** The run that read the evidence and wrote this row. */
	decided_by_run: string;

	cause: RetirementCause;

	/** The distinct runs whose results justify the retirement, oldest first. Space-separated in the CSV cell. Recorded rather than counted, so the decision can be checked against the ledger that produced it. The evidence cell an `http_410` retirement fills: five runs read five `410` answers. */
	evidence_run_ids?: string[];

	/** The distinct complete days whose yield justifies the retirement, oldest first. Space-separated in the CSV cell. The evidence cell a `low_yield` retirement fills, because that decision is made on days and not on runs: a day the schedule fired five times is still one day under the mark, and recording its five run ids would say a fortnight's dwell was a fortnight and a half. */
	evidence_dates?: string[];
}
