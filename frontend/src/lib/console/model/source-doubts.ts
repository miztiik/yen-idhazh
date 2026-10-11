import type { Row } from '../../data/ledger';
import { sourceDoubts as reduceSources } from './work';
import { median, number, textRows } from './rows';

export function sourceDoubts(scores: readonly Row[], items: readonly Row[], window: { start: string; end: string; days: number }, options: { limit: number; minForShare: number }) {
	// A repeated URL takes the later scored date, never a fabricated item identity.
	const latest = new Map<string, Row>();
	const unkeyed: Row[] = [];
	for (const row of scores) {
		if (typeof row.url_key !== 'string' || row.url_key === '') { unkeyed.push(row); continue; }
		const held = latest.get(row.url_key);
		if (held === undefined || String(row.date) >= String(held.date)) latest.set(row.url_key, row);
	}
	const kept = [...latest.values(), ...unkeyed];
	const reduced = reduceSources(textRows(kept), textRows(items), window, options);
	const sources = new Map(items.filter((row) => row.url_key && row.source_id).map((row) => [row.url_key, row.source_id]));
	return {
		...reduced,
		share: reduced.summaries - reduced.unattributed === 0 ? null :
			reduced.doubted / (reduced.summaries - reduced.unattributed),
		rows: reduced.rows.map((source) => {
			const group = kept.filter((row) => sources.get(row.url_key) === source.sourceId);
			const reading = (key: string) => {
				const value = median(group.map((row) => number(row[key])).filter((n): n is number => n !== null));
				return value === null ? null : Math.round(value * 10000) / 10;
			};
			return { ...source, evidential: reading('evidential_density'), speculative: reading('speculative_density') };
		})
	};
}
