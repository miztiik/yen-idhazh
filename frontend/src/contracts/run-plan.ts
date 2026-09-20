// Generated from `backend/idhazh/contracts/run_plan.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * One URL that survived deduplication and was chosen for the day.
 *
 * `item_id` is derived from `url_key`, so the same article carries the same
 * id on every run of every day. `published_at` is the time the run believes -
 * the feed's own date, unless it claimed a future too far ahead to be true,
 * in which case it is when we first saw the address. `time_source` says which
 * of the two it is.
 *
 * `rank_score` is the number the day is ordered on, and the eight terms under
 * it are what it was built from: `authority_score` plus `carriage_step` plus
 * `watchlist_bonus` plus `lens_bonus` plus `recency_bonus` is `rank_score`,
 * and `tier_score` times `feed_weight` times `feed_reliability` is
 * `authority_score`. Every one of the thirteen score fields is null on a plan
 * written before 2026-09-14 - unknown, and never a term worth nothing.
 */
export interface PlannedItem {
	item_id: string;

	url_key: string;

	/** The address as the feed gave it. */
	source_url: string;

	/** After canonicalisation. url_key derives from it. */
	canonical_url: string;

	/** The feed that carried it first. */
	source_id: string;

	tier: SourceTier;

	/** Declared feed form, carried from config so workers never infer it. */
	source_form?: SourceForm;

	vertical: string;

	title?: string | null;

	published_at?: string | null;

	/** Which clock published_at came from. Null on a plan written before the field existed - unknown, and never a claim about a clock. */
	time_source?: TimeSource | null;

	/** Independent feeds that carried this story today. */
	carried_by?: number;

	watchlist_hit?: boolean;

	/** A salience feed voted for it. A vote, never a discovery. */
	on_front_page?: boolean;

	rank_score: number;

	/** The best-trusted feed that carried this story, scored: its tier score times its own weight times its reliability. The largest term of the score, and the only one that is a product rather than a step. */
	authority_score?: number | null;

	/** collect.tier_weights for that feed's tier. From the same feed that won authority_score, never from another carrier of the story. */
	tier_score?: number | null;

	/** That feed's own weight from config/sources.json. Soft retirement. */
	feed_weight?: number | null;

	/** That feed's factor from the trailing feed-health window, built once per run by ledger.reliability. 1.0 means no recent evidence against it. */
	feed_reliability?: number | null;

	/** collect.carriage_step when more than one feed carried this address, and 0.0 when one did. A flat step that fires once, never a count. */
	carriage_step?: number | null;

	/** collect.watchlist_bonus when watchlist_hit, and 0.0 when not. */
	watchlist_bonus?: number | null;

	/** The weight of the one lens this story earned most from, matched on the headline. Never the sum of several, and 0.0 when no lens matched. */
	lens_bonus?: number | null;

	/** collect.recency_weight decayed by age at plan time. Orders what the age gate already admitted; it never admits anything itself. */
	recency_bonus?: number | null;

	/** How sure the label call was of what this article is about. No producer yet - declared so the row shape stops moving, and null until the article-classification work writes it. */
	label_confidence?: number | null;

	/** How well the picture a run planned matches the relationship the article states. No producer yet - null until the visual planning work writes it. */
	relationship_score?: number | null;

	/** How well the chosen chart form fits the data it draws. No producer yet - null until the visual planning work writes it. */
	fit_weight?: number | null;

	/** The pair of readings a two-axis story is scored on. No producer yet - null until the known-defects work writes it. */
	dual_score?: number | null;

	/** What this story scores against the no-visual baseline. No producer yet - null until the known-defects work writes it. */
	null_score?: number | null;
}

/**
 * How many refused addresses fall in one band of days since publication.
 *
 * A count on its own says the guard fired. It cannot say whether a cover of a
 * given width would have let any of those addresses through, and that is what
 * the width of the cover turns on - so the bands are recorded beside the count.
 *
 * Every declared band is written, including the empty ones. A band that is
 * absent and a band holding nothing are different answers, and only one of
 * them is a measurement.
 */
export interface PublishedAgeBand {
	/** Days since publication, inclusive. */
	from_days: number;

	/** Exclusive upper edge, in days. Null on the open-ended oldest band. */
	to_days?: number | null;

	/** Distinct addresses the guard refused in this band. */
	addresses: number;
}

export const SOURCE_FORM = ['article', 'abstract'] as const;

export type SourceForm = (typeof SOURCE_FORM)[number];

/** The tier IS the ranking weight (docs/architecture/sources/discovery.md). */
export const SOURCE_TIER = [1, 2, 3] as const;

export type SourceTier = (typeof SOURCE_TIER)[number];

/**
 * Which clock the time on an item came from.
 *
 * `rank.appeared_at` prefers the feed's own date and falls back to when we
 * first saw the address. Both answers used to land in one field, so nothing
 * downstream could tell them apart - and the fallback is the one a reader
 * would want flagged, because it is our clock and not the publisher's.
 */
export const TIME_SOURCE = ['feed', 'first_seen', 'unknown'] as const;

export type TimeSource = (typeof TIME_SOURCE)[number];

/** Why a vertical contributed what it did, including when it contributed nothing. */
export interface VerticalPlan {
	id: string;

	/** Distinct URLs the feeds offered. */
	considered: number;

	planned: number;

	/** Feeds on this desk whose configured address this run may lawfully ask: not a curated tombstone, not a retired endpoint, and not one robots.txt refused or left unknown. A resting or failing endpoint is counted, because the floor measures how many independent sources a desk has rather than how many answered today. */
	eligible_feeds: number;

	/** The vertical's own min_feeds this count was measured against, so a payload can be read without the config that produced it. Null on a plan written before the field existed - unknown, never a floor of zero. */
	feed_floor?: number | null;

	/** Under its floor, so it is collected but never rendered. */
	below_feed_floor?: boolean;

	/** Of those considered, how many were past collect.max_age_hours. A desk whose feeds serve a back catalogue thins for this reason and no other, and a thin desk that cannot say why reads as a broken run. */
	too_old?: number;
}

/** What the plan job decided, before a single byte of an article was fetched. */
export interface RunPlan {
	version?: string;

	date: string;

	run_id: string;

	generated_at: string;

	/** Discovery failed and an earlier list was reused. Never skip a day silently. */
	stale?: boolean;

	feeds_read?: number;

	feeds_failed?: number;

	/** Never asked this run: resting out a quarantine, or configured at an address the retirement ledger holds. Neither read nor failed. */
	feeds_skipped?: number;

	/** Distinct addresses this run collected on a desk it plans and then refused, because the published ledger already holds them. Null on a plan written before the field existed - unknown, and never a run where the guard refused nothing. */
	dropped_published?: number | null;

	/** How old those addresses were, cut on PUBLISHED_AGE_BANDS. Every band is written, so a zero here is a measured zero. Null exactly when dropped_published is. */
	dropped_published_ages?: PublishedAgeBand[] | null;

	verticals?: VerticalPlan[];

	items?: PlannedItem[];
}
