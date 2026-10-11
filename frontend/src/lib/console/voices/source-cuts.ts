/** Which source lost most articles to a recorded cut, counted once per address? */
import type { Row } from '../../data/slice-shapes';
import type { Range } from '../queries/window';
import type { SourceCuts } from '../../server/model-work';
import { numberOf, wordOf } from './record';

export function sourceCuts(rows: readonly Row[], range: Range, cap: number): SourceCuts & { unknown: number; zeroLengths: number; zeroCaps: number } {
	const unique = new Map<string, { source: string; date: string; before: number | null; after: number | null }>();
	for (const row of rows) {
		if (wordOf(row.date, '') < range.from || wordOf(row.date, '') > range.to) continue;
		const source = wordOf(row.source_id, ''), key = wordOf(row.url_key, '');
		if (!source || !key) continue;
		const article = { source, date: wordOf(row.date, ''), before: numberOf(row.source_words_before_cap), after: numberOf(row.source_words) };
		const held = unique.get(`${source}\u0000${key}`);
		if (held === undefined || (article.before !== null && (held.before === null || article.before > held.before)) ||
			(article.before === held.before && article.after !== null && held.after === null)) unique.set(`${source}\u0000${key}`, article);
	}
	const articles = [...unique.values()];
	const measured = articles.filter((article) => article.before !== null && article.after !== null);
	const cuts = measured.filter((article) => article.after! < article.before!);
	const bySource = [...new Set(cuts.map((article) => article.source))].map((sourceId) => {
		const source = measured.filter((article) => article.source === sourceId);
		const lengths = source.map((article) => article.before!).filter((words) => words > 0).sort((a, b) => a - b);
		return { sourceId, articles: source.length, cut: cuts.filter((article) => article.source === sourceId).length,
			lengths: { min: lengths[0], median: lengths[Math.floor(lengths.length / 2)], max: lengths[lengths.length - 1] } };
	}).sort((a, b) => b.cut - a.cut || a.sourceId.localeCompare(b.sourceId));
	const losses = cuts.map((article) => article.before! - article.after!).sort((a, b) => a - b);
	const caps = [...new Set(cuts.map((article) => article.after!).filter((words) => words > 0))].map((words) => {
		const dates = cuts.filter((article) => article.after === words).map((article) => article.date).sort();
		return { words, first: dates[0], last: dates[dates.length - 1] };
	}).sort((a, b) => a.first.localeCompare(b.first) || a.words - b.words);
	return {
		rows: bySource.slice(0, cap), moreSources: Math.max(0, bySource.length - cap),
		moreCuts: bySource.slice(cap).reduce((sum, source) => sum + source.cut, 0),
		measured: measured.length > 0, unknown: articles.length - measured.length,
		zeroLengths: measured.filter((article) => article.before === 0).length,
		zeroCaps: cuts.filter((article) => article.after === 0).length,
		cost: losses.length === 0 ? null : { n: losses.length, median: losses[Math.floor(losses.length / 2)], max: losses[losses.length - 1] },
		caps, days: range.days, articles: measured.length
	};
}
