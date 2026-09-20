// Generated from `backend/idhazh/contracts/watchlist.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** How the SEC submissions endpoint is consulted, when it is. */
export interface EdgarPolicy {
	enabled?: boolean;

	/** Declared in the User-Agent. SEC refuses the request without one. */
	contact_email?: string | null;

	requests_per_second?: number;

	submissions_url_template?: string;

	company_tickers_url?: string;
}

/** One entry in the registry: a named organisation, or a running subject. */
export interface EntityDef {
	status?: LifecycleStatus;

	retired_on?: string | null;

	id: string;

	display_name: string;

	/** Whether this entry names a standing organisation or a running subject. A subject - a pandemic, a tournament, an export-control regime - has no filer id and often no feed, so the registry has to say which kind it holds. Absent means organisation, which is what every entry written before the field existed was. */
	kind?: EntityKind;

	/** Every name this entity is called. An item is tagged with the entity when one of these appears in its words as a whole-word phrase, case-folded, and the same set decides the watchlist ranking bonus against a candidate's feed title. Nothing is derived from the id or the display name. An entity with no alias is never matched and never lifts a score. */
	aliases?: string[];

	/** Ten-digit, zero-padded SEC filer id. Null for a non-US entity, and null for every subject, because only an organisation files with the SEC. */
	cik?: string | null;

	feeds?: EntityFeed[];
}

/** A newsroom or blog feed belonging to one entity. */
export interface EntityFeed {
	status?: LifecycleStatus;

	retired_on?: string | null;

	id: string;

	title: string;

	url: string;

	tier?: SourceTier;
}

/** What the entry names: a standing organisation, or a running subject. */
export const ENTITY_KIND = ['organisation', 'subject'] as const;

export type EntityKind = (typeof ENTITY_KIND)[number];

/** Retire, never delete: a tombstone keeps old payloads valid. */
export const LIFECYCLE_STATUS = ['draft', 'active', 'retired'] as const;

export type LifecycleStatus = (typeof LIFECYCLE_STATUS)[number];

/** The tier IS the ranking weight (docs/architecture/sources/discovery.md). */
export const SOURCE_TIER = [1, 2, 3] as const;

export type SourceTier = (typeof SOURCE_TIER)[number];

/** `config/watchlist.json` - the entities whose news gets a ranking bonus. */
export interface Watchlist {
	version?: string;

	entities: EntityDef[];

	edgar?: EdgarPolicy;
}
