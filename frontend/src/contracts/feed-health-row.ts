// Generated from `backend/idhazh/contracts/feed_health.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * Why one read of one address ended the way it did.
 *
 * Deliberately coarser than an HTTP status. What a later decision needs is
 * whether the address is worth asking again, and 403 and 404 answer that the
 * same way while 503 answers it differently.
 */
export const FETCH_OUTCOME = ['ok', 'robots_denied', 'blocked', 'permanent', 'transient', 'skipped'] as const;

export type FetchOutcome = (typeof FETCH_OUTCOME)[number];

/**
 * What `robots.txt` said about this address, as a decision and never a body.
 *
 * Three answers because three are actionable. A host that publishes no rules
 * and a host whose rules allow us are the same permission, so they are one
 * member; a refusal and a robots file we could not read are different, because
 * the first is a publisher's stated policy and the second is our own failure
 * to establish one. Neither of the last two says anything about whether the
 * feed itself works, so neither is evidence about availability.
 */
export const ROBOTS_OUTCOME = ['allowed', 'denied', 'unreachable'] as const;

export type RobotsOutcome = (typeof ROBOTS_OUTCOME)[number];

/** One feed, one run, one row. */
export interface FeedHealthRow {
	version?: string;

	run_id: string;

	date: string;

	feed_id: string;

	checked_at: string;

	outcome: FetchOutcome;

	/** The HTTP status, when the request got far enough to have one. */
	status?: number | null;

	/** Candidates the feed yielded. Zero with an ok outcome is its own kind of broken - a feed that parses to nothing is not a feed that is working. */
	items?: number;

	/** Our own one-line reason. Never the response body (Guardrail #11). */
	detail?: string | null;

	/** The sha256 of the configured feed URL this run asked, from derive_endpoint_key. It identifies the address rather than the feed, so a feed whose URL is edited starts a fresh record. Empty on a row written before the column existed. */
	endpoint_key?: string | null;

	/** What robots.txt said about this address. Empty on a row written before the column existed, which is not the same fact as allowed. */
	robots_outcome?: RobotsOutcome | null;

	/** When permission was established, so a recheck cadence has a clock. */
	robots_checked_at?: string | null;

	/** The status robots.txt itself answered with, when there was one. */
	robots_status?: number | null;

	/** Did this run request the feed address itself? False for a run that stopped at robots.txt or rested the feed, so evidence about the feed can be told apart from evidence about permission. The cell is spelled True or False, as every other boolean cell under state/ is. */
	target_attempted?: boolean | null;
}
