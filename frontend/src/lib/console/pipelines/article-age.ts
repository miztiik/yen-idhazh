/** How old were articles with a source-stated publication time when their work started? */
import type { Row } from '../../data/ledger';
import { nearestRank } from '../rates';

function instant(cell: Row[string] | undefined): number | null {
	if (typeof cell !== 'string' || !cell.endsWith('Z')) return null;
	const value = Date.parse(cell);
	return Number.isFinite(value) ? value : null;
}

export function articleAge(rows: readonly Row[]) {
	const published = rows.filter((row) => row.outcome === 'ok');
	let inferred = 0;
	let unknown = 0;
	let future = 0;
	const hours = published.flatMap((row) => {
		if (row.time_source === 'first_seen') { inferred += 1; return []; }
		if (row.time_source !== 'feed') { unknown += 1; return []; }
		const source = instant(row.published_at);
		const start = instant(row.item_started_at);
		if (source === null || start === null) { unknown += 1; return []; }
		const age = (start - source) / 3_600_000;
		if (age < 0) { future += 1; return []; }
		return [age];
	});
	return {
		hours, inferred, unknown, future, published: published.length,
		median: nearestRank(hours, 0.5), overDay: hours.filter((hour) => hour > 24).length,
		lede: `${hours.length} source-stated publication times are measured. ` +
			`${inferred} of ${published.length} successful items have inferred times and are not drawn. ` +
			`${unknown} have no usable source time; ${future} have a publication time after our run.`
	};
}
