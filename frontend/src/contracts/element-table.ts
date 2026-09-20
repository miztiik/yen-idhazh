// Generated from `backend/idhazh/contracts/element.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One fact, and the characters it was cut from. */
export interface Element {
	/** <kind>-<span_start>-<span_end>, recomputed on read, never trusted. */
	element_id: string;

	kind: ElementKind;

	/** Index into Article.text. Inclusive. */
	span_start: number;

	/** Index into Article.text. Exclusive. */
	span_end: number;

	/** The verbatim slice Article.text[span_start:span_end]. Untrusted text: data and never instruction (Guardrail #11), and never republished to a reader. */
	span_excerpt: string;

	/** What the span reads as - a decimal for a quantity, a date or a year for a date, and null for the four kinds that are words. Stated even when null. */
	value: string | null;

	/** A quantity's normalised unit, and null on every other kind. */
	unit: string | null;

	/** Which sentence of Article.text the span starts in, from zero. */
	sentence_index: number;

	extractor: Extractor;

	/** Tier 2. The watchlist entity this element is about. */
	entity?: string | null;

	/** Tier 2. When the element applies, if that is not now. */
	time?: string | null;

	/** Tier 2. What is measured, in the article's own words. */
	measure?: string | null;

	/** Tier 2. The same measure under one controlled name, so two articles' words for it compare as a string. A free-text canonical name is not canonical, it is a second wording. */
	measure_canonical?: string | null;

	/** Tier 2. What the element is broken down by. */
	dimension?: string | null;

	/** Tier 2. How much of the story this fact is. */
	salience?: number | null;

	/** Tier 2. Who the article said it, if anyone. */
	attribution?: string | null;

	/** Tier 2. Whether the article hedged the fact rather than asserting it. */
	hedge?: boolean | null;

	/** Tier 2 provenance. Which model or person assigned the judgements. */
	label_source?: string | null;

	/** Tier 2 provenance. The date-stamp of the pass that assigned them. */
	ledger_version?: string | null;
}

/**
 * The six things an element can be.
 *
 * Declared in the order the producers arrive: `quantity` and `date` are pure
 * patterns over the bytes and ship with this contract's first two producers.
 * The other four need a model to point at them, and until that producer exists
 * they are legal and never written.
 */
export const ELEMENT_KIND = ['quantity', 'date', 'entity', 'place', 'quote', 'claim'] as const;

export type ElementKind = (typeof ELEMENT_KIND)[number];

/**
 * Which path found the element.
 *
 * It exists so a later run can measure the two apart. Without it a fall in the
 * quantity count reads the same whether a pattern stopped matching or a model
 * stopped pointing, and those have different fixes.
 *
 * Not to be confused with `Article.extractor_version`, which is the version of
 * the HTML-to-text extractor that produced the article body. That names the
 * stage that made the string; this names the pass that found a fact inside it.
 */
export const EXTRACTOR = ['regex', 'model'] as const;

export type Extractor = (typeof EXTRACTOR)[number];

/** Every element one article yielded, and the text they were cut from. */
export interface ElementTable {
	version?: string;

	item_id: string;

	/** sha256 of canonical_url. The same identity Article carries, rebuilt on read. */
	url_key: string;

	/** The address url_key derives from. */
	canonical_url: string;

	/** sha256 of the Article.text every span indexes - one hash per article, not per element. A per-element hash would be redundant against this plus the re-slice, on every article for ever. */
	source_text_hash: string;

	/** Characters in that same string. It is what lets this shape refuse a span past the end of the text without holding the text. */
	source_text_length: number;

	/** In the order the article wrote them. Uncapped here: what a producer keeps is a tunable and lives in config, not in the shape. */
	elements?: Element[];

	/** How many candidates each pass matched, before any dedupe, before the rule that settles two passes claiming one span, and before the cap. It is one count per pass and never a total: two passes may both count one stretch of characters, because both matched it and only one kept it. `elements` saturates at the cap and this does not, so the two together say whether the cap bit and by how much. */
	candidates_found: Record<string, number>;
}
