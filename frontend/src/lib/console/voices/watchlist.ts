/** Which distinct addresses did the watchlist catch on each recorded day? */
import type { Row } from '../../data/slice-shapes';
import type { Range } from '../queries/window';
import { tileStrip, type TileInput } from '../../charts/d3/tileStrip';
import { datesOf, wordOf, readingRecords, dayReadout } from './record';
export const WATCHLIST_STATE_WORDS = { absent: 'hit column not recorded completely', quiet: 'no catch recorded', fired: 'caught' };

export function watchlist(rows: readonly Row[], range: Range, marked: number, named: number) {
	rows = rows.filter((row) => wordOf(row.date, '') >= range.from && wordOf(row.date, '') <= range.to);
	const days = datesOf(range).map((date) => {
		const addresses = new Map<string, Row[]>();
		let unkeyed = 0;
		for (const row of rows.filter((one) => one.date === date)) {
			const key = wordOf(row.url_key, '');
			if (!key) { unkeyed += 1; continue; }
			addresses.set(key, [...(addresses.get(key) ?? []), row]);
		}
		let hits = 0, front = 0, unknown = unkeyed, unknownFront = 0;
		for (const group of addresses.values()) {
			if (group.some((row) => row.watchlist_hit === true)) {
				hits += 1;
				if (group.some((row) => row.watchlist_hit === true && row.on_front_page === true)) front += 1;
				else if (!group.some((row) => row.watchlist_hit === true && row.on_front_page === false)) unknownFront += 1;
			} else if (!group.every((row) => row.watchlist_hit === false)) unknown += 1;
		}
		const observed = addresses.size > 0 || unkeyed > 0;
		const tile: TileInput = hits >= marked ? { date, state: 'fired', reading: hits }
			: !observed || unknown > 0 ? { date, state: 'absent' } : { date, state: 'quiet', reading: hits };
		return { date, hits, front, unknown, unknownFront, tile };
	});
	const total = new Set(rows.filter((row) => row.watchlist_hit === true).map((row) => wordOf(row.url_key, '')).filter(Boolean)).size;
	const front = new Set(rows.filter((row) => row.watchlist_hit === true && row.on_front_page === true).map((row) => wordOf(row.url_key, '')).filter(Boolean)).size;
	const unknown = days.reduce((sum, day) => sum + day.unknown, 0);
	const unknownFront = days.reduce((sum, day) => sum + day.unknownFront, 0);
	const fired = days.filter((day) => day.hits >= marked);
	const caughtDays = days.filter((day) => day.hits > 0).length;
	const filled = fired.filter((day) => day.hits >= named);
	const last = rows.filter((row) => typeof row.watchlist_hit === 'boolean').map((row) => wordOf(row.date, '')).filter(Boolean).sort().at(-1);
	return {
		geometry: tileStrip(days.map((day) => day.tile), { thresholds: [marked, named] }),
		days, total, marked, named, fired: fired.length, caughtDays,
		lede: unknown > 0
			? `At least ${total} distinct articles have a recorded watchlist hit; ${unknown} address readings are unknown.`
			: `The watchlist caught ${total} distinct articles on ${caughtDays} of ${range.days} days; ${unknownFront ? `at least ${front}` : front} reached the front page.`,
		stale: last !== undefined && last < range.to ? `Watchlist answers stop on ${last}; later tiles have no complete recorded watchlist answer, not a recorded zero.` : null,
		finding: filled.length ? `${filled.length} days caught at least ${named} articles, against the days with no recorded catch.` : `No recorded day reached the ${named}-article naming threshold.`,
		quiet: days.length > 0 && days.every((day) => day.hits === 0 && day.tile.state === 'quiet'),
		unknown, unknownFront,
		records: dayReadout(readingRecords(days.map((day) => ({
			title: day.date, facts: [
				{ label: 'State', value: WATCHLIST_STATE_WORDS[day.tile.state] },
				{ label: 'Catch', value: day.tile.state === 'absent' ? 'not recorded completely' : `${day.hits} distinct addresses` },
				{ label: 'Front page', value: `${day.front} recorded true; ${day.unknownFront} unknown` },
				{ label: 'Unrecorded hit cells', value: String(day.unknown) }
			]
		}))))
	};
}
