/** Where did an evidence-bearing fetch spend its whole recorded time? */
import type { Row } from '../../data/slice-shapes';
import { rankedList } from '../../charts/d3/rankedList';
import { SERIES_TOKENS } from '../series-tokens';
import { numberOf, wordOf, readingRecords } from './record';

const CLOCKS = ['robots_ms', 'retry_total_ms', 'fetch_connect_ms', 'fetch_ttfb_ms'] as const;
const PARTS = ['Robots check', 'Retries', 'Connecting', 'Waiting for headers', 'Rest of fetch'] as const;
const TOKENS = [SERIES_TOKENS['robots-check'], SERIES_TOKENS.retries, SERIES_TOKENS.connecting, SERIES_TOKENS['waiting-headers'], SERIES_TOKENS['fetch-rest']];
export function fetchTime(rows: readonly Row[], cap: number) {
	const sources = new Map<string, Row[]>();
	let excluded = 0;
	for (const row of rows) {
		if (numberOf(row.fetch_ms) === null || numberOf(row.robots_ms) === null) { excluded += 1; continue; }
		const id = wordOf(row.source_id, '');
		if (!id) { excluded += 1; continue; }
		sources.set(id, [...(sources.get(id) ?? []), row]);
	}
	const summaries = [...sources].map(([id, group]) => {
		const total = group.reduce((sum, row) => sum + numberOf(row.fetch_ms)!, 0) / group.length;
		const complete = group.filter((row) => CLOCKS.every((key) => numberOf(row[key]) !== null));
		const overlap = complete.filter((row) => CLOCKS.reduce((sum, key) => sum + numberOf(row[key])!, 0) > numberOf(row.fetch_ms)!);
		// A partial population cannot supply parts of the full population's mean.
		const split = complete.length === group.length && overlap.length === 0;
		const means = CLOCKS.map((key) => group.every((row) => numberOf(row[key]) !== null)
			? group.reduce((sum, row) => sum + numberOf(row[key])!, 0) / group.length : null);
		const rest = split ? group.reduce((sum, row) => sum + numberOf(row.fetch_ms)! - CLOCKS.reduce((parts, key) => parts + numberOf(row[key])!, 0), 0) / group.length : null;
		const segments = split ? [...means, rest].map((value, index) => ({ label: PARTS[index], value: value!, token: TOKENS[index] })) : undefined;
		const retries = group.every((row) => numberOf(row.retry_count) !== null)
			? group.reduce((sum, row) => sum + numberOf(row.retry_count)!, 0) : null;
		return { id, total, count: group.length, complete: complete.length, overlap: overlap.length, means, rest, segments, retries };
	}).sort((a, b) => b.total - a.total || a.id.localeCompare(b.id));
	const geometry = rankedList(summaries.map((source) => ({
		label: source.id, value: source.total, segments: source.segments,
		context: `${source.count} fetches; ${source.complete} complete clock readings`,
		status: source.overlap > 0 ? 'Clocks overlap; split unavailable' : source.segments === undefined ? 'Split not recorded for every fetch' : undefined
	})), { max: cap });
	if (geometry) for (const row of geometry.rows) row.row.value = `${(row.value / 1000).toFixed(2)} s`;
	const drawn = summaries.slice(0, cap);
	const slowest = drawn[0];
	const largest = slowest?.segments?.reduce((best, part) => part.value > best.value ? part : best);
	return {
		geometry, summaries, excluded,
		lede: slowest ? `${slowest.id} is slowest, averaging ${(slowest.total / 1000).toFixed(2)} seconds a fetch.` : 'No fetch has the recorded whole and robots clocks this comparison needs.',
		finding: largest ? `${largest.label} is its largest recorded part, against the other four parts.` : 'The whole is useful; missing or overlapping clocks cannot supply a five-part split.',
		maxText: geometry ? `${(geometry.max / 1000).toFixed(2)} seconds` : '',
		tail: `${excluded} rows lack a whole, robots clock or source. ${Math.max(0, summaries.length - cap)} sources lie below this list.`,
		noRetries: rows.length > 0 && rows.every((row) => numberOf(row.retry_count) === 0),
		records: readingRecords(drawn.map((source) => ({
			title: source.id,
			facts: [
				{ label: 'Whole mean', value: `${source.total.toFixed(2)} ms over ${source.count} fetches` },
				...PARTS.map((label, index) => ({ label, value: (index === 4 ? source.rest : source.means[index]) === null ? 'not recorded for every fetch' : `${(index === 4 ? source.rest : source.means[index])!.toFixed(2)} ms` })),
				{ label: 'Retry count', value: source.retries === null ? 'not recorded for every fetch' : String(source.retries) }
			]
		})))
	};
}
