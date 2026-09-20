// Generated from `backend/idhazh/contracts/sources.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One RSS/Atom feed, attached to exactly one vertical. */
export interface FeedDef {
	status?: LifecycleStatus;

	retired_on?: string | null;

	id: string;

	vertical: string;

	title: string;

	url: string;

	tier: SourceTier;

	/** Who is speaking. A reader needs this before they will share an item. */
	kind?: SourceKind;

	/** What the feed publishes. Abstract feeds are declared by a curator, never detected from source text. */
	form?: SourceForm;

	/** Soft retirement: drop the weight, observe, then retire. */
	weight?: number;
}

/** Retire, never delete: a tombstone keeps old payloads valid. */
export const LIFECYCLE_STATUS = ['draft', 'active', 'retired'] as const;

export type LifecycleStatus = (typeof LIFECYCLE_STATUS)[number];

/**
 * A published fact about a URL already in the pool. It never discovers.
 *
 * A vote sets `on_front_page` on the item, so the page can say another desk
 * led with this story. It was also worth `collect.front_page_bonus` in the
 * selection score until 2026-09-13, when the term was removed: it fired on 8
 * of 5,682 published stories - 0.1 percent - while being worth more than the
 * step between two source tiers, and a move nobody can attribute to a term is
 * not a ranking term. The vote is still recorded, so restoring the term costs
 * one weight once the signal is actually being supplied.
 *
 * There is no per-feed weight here and there never was a use for one. An
 * aggregator has no subject taxonomy to be graded on.
 */
export interface SalienceFeedDef {
	status?: LifecycleStatus;

	retired_on?: string | null;

	id: string;

	title: string;

	url: string;
}

export const SOURCE_FORM = ['article', 'abstract'] as const;

export type SourceForm = (typeof SOURCE_FORM)[number];

/**
 * What kind of speaker this is - the thing a reader uses to decide belief.
 *
 * "A company said its product is faster" and "a reporter measured it" are not
 * the same claim, and without this they arrive looking identical. The
 * dangerous case is `announcement`: forwarding a vendor's own copy without
 * knowing it was the vendor is how a reader ends up carrying an ad.
 */
export const SOURCE_KIND = ['reporting', 'announcement', 'research', 'analysis', 'government', 'community'] as const;

export type SourceKind = (typeof SOURCE_KIND)[number];

/** The tier IS the ranking weight (docs/architecture/sources/discovery.md). */
export const SOURCE_TIER = [1, 2, 3] as const;

export type SourceTier = (typeof SOURCE_TIER)[number];

/** `config/sources.json` - what the Collect stage consults. */
export interface Sources {
	version?: string;

	/** The live list. Collect loops exactly this, so nothing retired belongs here. */
	feeds: FeedDef[];

	salience: SalienceFeedDef[];

	/** Tombstones. Never fetched, never ranked, still able to name an id. */
	retired?: FeedDef[];
}
