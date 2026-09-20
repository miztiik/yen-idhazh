// Generated from `backend/idhazh/contracts/taxonomy.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

export interface EventDef {
	status?: LifecycleStatus;

	retired_on?: string | null;

	display_name: string;

	/** The sentence the model is scored against. It is the label, as far as the model is concerned: an id and a display name say nothing, and `research` means whatever sentence sits next to it. Edit it and the next run labels against the new text - no code change, no schema regeneration. Every figure measured against the old text is stale from that day, which is why a measurement records the version of this file it was taken under. */
	definition?: string;

	id: string;

	/** The curated terms that assign this event. Same rule as LensDef.keywords. */
	keywords?: string[];
}

export interface LensDef {
	status?: LifecycleStatus;

	retired_on?: string | null;

	display_name: string;

	/** The sentence the model is scored against. It is the label, as far as the model is concerned: an id and a display name say nothing, and `research` means whatever sentence sits next to it. Edit it and the next run labels against the new text - no code change, no schema regeneration. Every figure measured against the old text is stale from that day, which is why a measurement records the version of this file it was taken under. */
	definition?: string;

	id: string;

	/** The curated terms that assign this lens. A lens is assigned when one of them appears in the item's words as a whole-word phrase, case-folded. Nothing is derived from the id or the display name: deriving from the id was measured at 88.2 percent of items, because `ai` sits inside `said`. An empty list means the lens is never assigned. */
	keywords?: string[];

	/** What this lens adds to a story's rank when one of its terms is in the headline. Zero means the lens only labels. A weighted lens must be an under-carried theme: the bonus is there to rescue a story one outlet has and nobody has repeated yet, and on an over-carried theme it only compounds a lead that repetition already gave. */
	weight?: number;

	/** True when a model proposed this entry rather than a person writing it. The marker survives promotion on purpose: a word that arrived from an article read six weeks ago reads exactly like one a person chose, and the difference is the first thing anybody asks when a label looks wrong. A proposal lands under `draft` status with no definition, so it is offered to no prompt and rendered on no page until a person writes the sentence and changes the status in a pull request. */
	is_auto_discovered?: boolean;
}

/** Retire, never delete: a tombstone keeps old payloads valid. */
export const LIFECYCLE_STATUS = ['draft', 'active', 'retired'] as const;

export type LifecycleStatus = (typeof LIFECYCLE_STATUS)[number];

/**
 * A subject with its own reporters and its own feeds.
 *
 * It is also the desk vocabulary: a feed declares one of these and a model
 * reading the article names one of these. Two deciders, one list of words
 * (`docs/concepts/taxonomy.md`).
 */
export interface VerticalDef {
	status?: LifecycleStatus;

	retired_on?: string | null;

	display_name: string;

	/** The sentence the model is scored against. It is the label, as far as the model is concerned: an id and a display name say nothing, and `research` means whatever sentence sits next to it. Edit it and the next run labels against the new text - no code change, no schema regeneration. Every figure measured against the old text is stale from that day, which is why a measurement records the version of this file it was taken under. */
	definition?: string;

	id: string;

	/** Feed floor below which the vertical does not render at all. */
	min_feeds: number;

	/** The fewest stories this desk publishes in a day, where the day still holds a story whose second-best desk is this one. A count rather than a share, because it answers whether the desk is worth opening at all and a desk page is a fragment below six stories on a 100-story day and on a 450-story one alike. It never admits a story a gate refused and never reaches a previous day: a desk it cannot fill publishes thin, and DigestVerticalRef already carries why. Zero, the default, is no rule. */
	floor?: number;

	/** The most of a published day this desk may hold, as a share. A share rather than a count, because a count is a moving share - ten stories is 1.4 percent of a 731-story day and a quarter of a 40-story one. The stories over it are re-filed onto their second-best desk and never dropped, so the day is exactly as long either way and a desk with nowhere to send its overflow stays over its ceiling rather than shortening the day. A desk may always hold its floor whatever this says. 1.0, the default, is no rule. */
	ceiling?: number;

	/** True when a model proposed this entry rather than a person writing it. The marker survives promotion on purpose: a word that arrived from an article read six weeks ago reads exactly like one a person chose, and the difference is the first thing anybody asks when a label looks wrong. A proposal lands under `draft` status with no definition, so it is offered to no prompt and rendered on no page until a person writes the sentence and changes the status in a pull request. */
	is_auto_discovered?: boolean;
}

/** `config/taxonomy.json` - the vocabulary every payload indexes against. */
export interface Taxonomy {
	version?: string;

	verticals: VerticalDef[];

	lenses: LensDef[];

	events: EventDef[];
}
