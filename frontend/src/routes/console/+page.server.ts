import { evalRows, loadManifests } from '$lib/server/payload';

export const prerender = true;

interface DayStats {
	date: string;
	items: number;
	fetchMs: number;
	extractMs: number;
	summarizeMs: number;
	scoreMs: number;
	meanHhem: number;
	bands: { high: number; medium: number; low: number };
}

function median(values: number[]): number {
	if (values.length === 0) return 0;
	const sorted = [...values].sort((a, b) => a - b);
	const middle = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

/** The console reads the committed ledger and nothing else.
 *
 * Every number here was measured when the run happened and written down. None
 * of it is derived at read time, which is what lets the page be a static file
 * and what stops today's code quietly restating yesterday's numbers.
 */
export function load() {
	const { rows } = evalRows();

	const byDate = new Map<string, Record<string, string>[]>();
	for (const row of rows) {
		const date = row.date ?? '';
		if (!date) continue;
		byDate.set(date, [...(byDate.get(date) ?? []), row]);
	}

	const days: DayStats[] = [...byDate.entries()]
		.map(([date, group]) => {
			const num = (name: string) => group.map((r) => Number(r[name] ?? 0) || 0);
			const bands = { high: 0, medium: 0, low: 0 };
			for (const row of group) {
				const band = row.band as keyof typeof bands;
				if (band in bands) bands[band] += 1;
			}
			return {
				date,
				items: group.length,
				fetchMs: median(num('fetch_ms')),
				extractMs: median(num('extract_ms')),
				summarizeMs: median(num('summarize_ms')),
				scoreMs: median(num('score_ms')),
				meanHhem: num('hhem').reduce((a, b) => a + b, 0) / Math.max(group.length, 1),
				bands
			};
		})
		.sort((a, b) => b.date.localeCompare(a.date));

	return { days, manifests: loadManifests(), totalRows: rows.length };
}
