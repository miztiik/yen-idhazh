/** How much of each prompt the model read again, and how fast it read the rest.
 *
 * The finding is the SPREAD. Re-measured 2026-09-21 over the committed item
 * ledger, reuse runs from a floor of 0.00 percent to a ceiling of 99.60 across
 * the requests one article makes, so a single figure for the article is the
 * mean of a request that re-read everything and one that reused almost all of
 * it, and it describes neither. Reading speed is the half that moves: pooled
 * over the same requests it spans 4.71 to 43.33 tokens a second, a 9.20-fold
 * range, while writing speed spans 2.76 to 7.49.
 *
 * **Nothing here is keyed to how many requests an article makes.** The requests
 * are discovered from the ledger's own column names, so merging two into one or
 * splitting into three changes what the panel draws and changes no code. That
 * is a hard rule rather than a preference: the count is a config value, so a
 * design that assumes it breaks on a config edit with nothing to warn the
 * person who makes it.
 */
import { quantile } from '$lib/charts/machine';

/** The column the ledger writes one of per request, and the name inside it.
 *
 * A format literal, not a knob: it is how the producer spells the column, so a
 * config that changed it would be a contract change with a schema stamp
 * (`CLAUDE.md` section 11) rather than a setting somebody turns.
 */
const REUSE_COLUMN = /^(.+)_cache_pct$/;

/** The column carrying the rate the same request read its prompt at. */
const readColumnFor = (request: string) => `${request}_prefill_tokens_per_s`;

/** The low, middle and high of one reading over the items in a span.
 *
 * Three numbers and never one: the panel exists because the middle of this
 * spread answers nothing.
 */
export interface Spread {
	low: number;
	median: number;
	high: number;
	/** Item rows that carried the reading. */
	from: number;
}

/** One request an article makes, as the ledger recorded it. */
export interface RequestSpread {
	/** The ledger's own name for the request, off the column prefix. An address
	 * rather than a label: the page numbers requests by their place instead,
	 * because a column prefix is a word about the pipeline. */
	name: string;
	/** Where the ledger's columns put it, counting from one. */
	place: number;
	/** How much of its prompt it read again, as a percentage. */
	reuse: Spread | null;
	/** How fast it read the rest, in tokens a second. */
	read: Spread | null;
}

/** Which request held an end of the reuse spread, and at what value. */
export interface ReuseEnd {
	place: number;
	pct: number;
}

/** The spread of prompt reuse and reading speed over a span of days. */
export interface PromptReuse {
	/** One entry a request the ledger carries, in the order it fills them. The
	 * length is read off the data and is the panel's track count. */
	requests: RequestSpread[];
	/** Item rows in the span, and the ones that carried any reuse reading. */
	rowsRead: number;
	items: number;
	/** The two ends of the whole spread, with the request each belongs to. Null
	 * where nothing in the span was measured. */
	floor: ReuseEnd | null;
	ceiling: ReuseEnd | null;
}

/** Every request the ledger's columns name, in the order they appear.
 *
 * Exported because the count is the whole finding of this module: a caller
 * that wants to know how many requests a row set describes asks the columns
 * rather than a constant.
 */
export function requestNames(columns: readonly string[]): string[] {
	const found: string[] = [];
	for (const column of columns) {
		const match = REUSE_COLUMN.exec(column);
		if (match && !found.includes(match[1])) found.push(match[1]);
	}
	return found;
}

function cell(value: string | undefined): number | null {
	if (value === undefined || value === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

/** Two decimals, which is what the ledger itself records these cells to. */
const round = (value: number) => Math.round(value * 100) / 100;

function spreadOf(values: number[]): Spread | null {
	if (values.length === 0) return null;
	const sorted = [...values].sort((left, right) => left - right);
	return {
		low: round(sorted[0]),
		median: round(quantile(sorted, 0.5)),
		high: round(sorted[sorted.length - 1]),
		from: sorted.length
	};
}

/**
 * `columns` is the ledger's own header, which is where the request count comes
 * from. A row set whose header names three requests produces three entries and
 * one that names one produces one, with no arithmetic in between.
 */
export function promptReuse(
	rows: readonly Record<string, string>[],
	columns: readonly string[]
): PromptReuse {
	const names = requestNames(columns);
	const requests: RequestSpread[] = names.map((name, index) => ({
		name,
		place: index + 1,
		reuse: spreadOf(rows.map((row) => cell(row[`${name}_cache_pct`])).filter(known)),
		read: spreadOf(rows.map((row) => cell(row[readColumnFor(name)])).filter(known))
	}));

	let floor: ReuseEnd | null = null;
	let ceiling: ReuseEnd | null = null;
	for (const request of requests) {
		if (request.reuse === null) continue;
		if (floor === null || request.reuse.low < floor.pct) {
			floor = { place: request.place, pct: request.reuse.low };
		}
		if (ceiling === null || request.reuse.high > ceiling.pct) {
			ceiling = { place: request.place, pct: request.reuse.high };
		}
	}

	return {
		requests,
		rowsRead: rows.length,
		items: rows.filter((row) => names.some((name) => cell(row[`${name}_cache_pct`]) !== null))
			.length,
		floor,
		ceiling
	};
}

function known(value: number | null): value is number {
	return value !== null;
}
