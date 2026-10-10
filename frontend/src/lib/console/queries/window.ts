/** Which days does a panel ask, and which one answer does this page keep? */
import type {
	DateStamp, LedgerName, LedgerReach, Predicate, SliceOptions, SliceResult
} from '../../data/ledger';
import { isDay } from '../../data/slice-shapes';

export interface PanelQuery {
	readonly name: string;
	readonly ledger: LedgerName;
	readonly columns: readonly string[];
	readonly where?: readonly Predicate[];
	readonly span: 'window' | 'newest-day' | 'widest';
}

export interface RouteReach {
	readonly through: DateStamp | null;
	readonly ledgers: Readonly<Partial<Record<LedgerName, LedgerReach>>>;
}

export interface Range {
	readonly from: DateStamp;
	readonly to: DateStamp;
	readonly days: number;
	readonly asked: number;
}

/** UTC milliseconds in one day; a calendar unit, not a tunable. */
const DAY_MS = 86_400_000;

function positiveDays(days: number, name: string): void {
	if (!Number.isSafeInteger(days) || days <= 0) {
		throw new Error(`${name} must be a positive whole number of UTC days`);
	}
}

function dayMillis(day: DateStamp, name: string): number {
	if (!isDay(day)) throw new Error(`${name} is not a YYYY-MM-DD UTC day: ${day}`);
	return Date.parse(`${day}T00:00:00Z`);
}

export function windowRange(asked: number, through: DateStamp, first: DateStamp): Range {
	positiveDays(asked, 'asked');
	const to = dayMillis(through, 'through');
	const began = dayMillis(first, 'first');
	if (began > to) throw new Error(`first ${first} comes after through ${through}`);
	const from = Math.max(began, to - (asked - 1) * DAY_MS);
	if (!Number.isFinite(new Date(from).getTime())) {
		throw new Error(`asked ${asked} reaches outside the UTC calendar`);
	}
	const fromDay = new Date(from).toISOString().slice(0, 10);
	if (!isDay(fromDay)) throw new Error(`asked ${asked} reaches outside the YYYY-MM-DD UTC calendar`);
	return { from: fromDay, to: through, days: (to - from) / DAY_MS + 1, asked };
}

/** Presets arrive from the route's console value, never a second config reader. */
export function rangeFor(
	query: PanelQuery, preset: number, reach: RouteReach, windowPresets: readonly number[]
): Range | LedgerReach {
	positiveDays(preset, 'preset');
	const ledger = reach.ledgers[query.ledger];
	if (ledger === undefined) throw new Error(`${query.name}: route reach names no ${query.ledger}`);
	if (ledger.state !== 'ok') return ledger;
	if (reach.through === null) throw new Error(`${query.name}: an ok ledger needs route through`);
	// A ledger that began after the common end has no day in this route's window.
	if (ledger.first > reach.through) return { state: 'quiet' };
	if (query.span === 'newest-day') return windowRange(1, reach.through, ledger.first);
	if (query.span === 'window') return windowRange(preset, reach.through, ledger.first);
	if (windowPresets.length === 0) throw new Error(`${query.name}: window_presets names no preset`);
	for (const days of windowPresets) positiveDays(days, `${query.name}: window_presets`);
	return windowRange(Math.max(...windowPresets), reach.through, ledger.first);
}

/** The real browser door, or its disk twin in a correctness test. */
export interface PanelDoor {
	readonly reach: (ledger: LedgerName) => Promise<LedgerReach>;
	readonly rows: (ledger: LedgerName, options: SliceOptions) => Promise<SliceResult>;
}

export interface QueryWindow {
	routeReach(ledgers: readonly LedgerName[]): Promise<RouteReach>;
	sliceOnce(query: PanelQuery, range: Range): Promise<SliceResult>;
	/** Forget selected answers before retry; the door retries failed fetches itself. */
	retryAsks(queries?: readonly PanelQuery[]): void;
}

/** One held range per query name, not an accumulating map of every past range. */
export function createQueryWindow(door: PanelDoor): QueryWindow {
	const held = new Map<string, { from: DateStamp; to: DateStamp; answer: Promise<SliceResult> }>();
	return {
		async routeReach(ledgers) {
			const entries = await Promise.all([...new Set(ledgers)].map(async (ledger) =>
				[ledger, await door.reach(ledger)] as const));
			const days = entries.flatMap(([, reach]) => reach.state === 'ok' ? [reach.through] : []);
			return { through: days.sort()[0] ?? null, ledgers: Object.fromEntries(entries) };
		},
		sliceOnce(query, range) {
			const previous = held.get(query.name);
			if (previous?.from === range.from && previous.to === range.to) return previous.answer;
			const forget = (answer: Promise<SliceResult>) => {
				// An older range completing late must not evict its replacement.
				if (held.get(query.name)?.answer === answer) held.delete(query.name);
			};
			const answer: Promise<SliceResult> = door.rows(query.ledger, {
				columns: query.columns, from: range.from, to: range.to,
				...(query.where === undefined ? {} : { where: query.where })
			}).then(
				(result) => {
					if (result.state === 'missing' || result.state === 'unreachable') forget(answer);
					return result;
				},
				(error: Error) => { forget(answer); throw error; }
			);
			held.set(query.name, { from: range.from, to: range.to, answer });
			return answer;
		},
		retryAsks(queries) {
			if (queries === undefined) held.clear();
			else for (const query of queries) held.delete(query.name);
		}
	};
}

const page = createQueryWindow({
	reach: async (ledger) => (await import('../../data/ledger')).ledgerReach(ledger),
	rows: async (ledger, options) => {
		const { slice } = await import('../../data/ledger');
		return slice(ledger, options);
	}
});

export const routeReach = page.routeReach;
export const sliceOnce = page.sliceOnce;
export const retryAsks = page.retryAsks;

export { tallyAsks, type RouteState } from '../query-state';
