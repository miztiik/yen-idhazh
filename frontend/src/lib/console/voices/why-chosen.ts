/** How did authority and four bonuses choose each newest-day article? */
import type { Row } from '../../data/slice-shapes';
import { partsOfOne } from '../../charts/d3/partsOfOne';
import { numberOf, wordOf, readingRecords } from './record';
import { shortDate } from '../../format';

const COLUMNS = ['authority_score', 'recency_bonus', 'lens_bonus', 'watchlist_bonus', 'carriage_step'] as const;
const NAMES = ['Authority', 'Recency', 'Lens', 'Watchlist', 'Carriage'] as const;
const runNumber = (row: Row): number | null => {
	const suffix = /-(\d+)$/.exec(wordOf(row.run_id, ''));
	return suffix === null ? null : Number(suffix[1]);
};
function authorityWords(row: Row): string {
	const factors = ['tier_score', 'feed_weight', 'feed_reliability'].map((key) => numberOf(row[key]));
	const words = `tier ${factors[0] ?? 'not recorded'} x weight ${factors[1] ?? 'not recorded'} x reliability ${factors[2] ?? 'not recorded'}`;
	if (factors.some((value) => value === null)) return `${row.authority_score}; ${words}. The multiplication cannot be checked.`;
	const product = factors.reduce<number>((value, factor) => value * factor!, 1);
	return Math.abs(product - numberOf(row.authority_score)!) <= 0.000001
		? `${row.authority_score} = ${words}`
		: `${row.authority_score}; ${words}. The recorded factors do not reproduce authority.`;
}
export function whyChosen(rows: readonly Row[], cap: number) {
	const newest = new Map<string, Row>();
	const day = rows.map((row) => wordOf(row.date, '')).filter(Boolean).sort().at(-1);
	const additive = (row: Row) => COLUMNS.every((key) => numberOf(row[key]) !== null) &&
		numberOf(row.selection_score) !== null &&
		Math.abs(COLUMNS.reduce((sum, key) => sum + numberOf(row[key])!, 0) - numberOf(row.selection_score)!) <= 0.000001;
	let unknownIdentity = 0;
	for (const row of rows) {
		if (day !== undefined && row.date !== day) continue;
		const id = wordOf(row.item_id, '');
		const n = runNumber(row);
		if (!id || n === null) { unknownIdentity += 1; continue; }
		const held = newest.get(id);
		// Several stages may carry the same item/run. Prefer its recorded score,
		// never an older run's score when the newest run left it unknown.
		if (held === undefined || n > runNumber(held)! || (n === runNumber(held) && additive(row) && !additive(held))) newest.set(id, row);
	}
	const candidates = [...newest.values()];
	const complete = candidates.filter(additive);
	complete.sort((a, b) => numberOf(b.selection_score)! - numberOf(a.selection_score)! || wordOf(a.item_id).localeCompare(wordOf(b.item_id)));
	const drawn = complete.slice(0, cap);
	const authority = candidates.map((row) => numberOf(row.authority_score)).filter((n): n is number => n !== null).sort((a, b) => b - a);
	const threshold = candidates.length >= cap && authority.length === candidates.length ? authority[cap - 1] : null;
	const displaced = threshold === null || drawn.length < cap || complete.length !== candidates.length || unknownIdentity > 0 ? null : drawn.filter((row) => numberOf(row.authority_score)! < threshold).length;
	const bonuses = NAMES.slice(1).map((label, index) => ({
		label, value: drawn.reduce((sum, row) => sum + numberOf(row[COLUMNS[index + 1]])!, 0)
	})).sort((a, b) => b.value - a.value);
	const finding = unknownIdentity > 0
		? `${unknownIdentity} newest-day rows lack an item identity or numeric run suffix. The bonuses' effect on the ${cap}-article choice cannot be established.`
		: threshold !== null && complete.length !== candidates.length
		? `The authority threshold was recorded, but only ${complete.length} of ${candidates.length} candidates have complete selection scores. The bonuses' effect on the ${cap}-article choice cannot be established.`
		: displaced === null
		? `The ${cap}-article authority threshold cannot be established from ${candidates.length} candidates with this evidence.`
		: `On ${day === undefined ? 'the newest recorded day' : shortDate(day)} the bonuses brought in ${displaced === 0 ? 'none' : displaced} of the ${cap}: ${displaced === 0 ? `their sources' standing alone picks the same ${cap}.` : `on their sources' standing alone they would not have made it. ${bonuses[0].label} added most.`}`;
	return {
		geometry: partsOfOne(drawn.map((row) => ({
			label: wordOf(row.item_id), parts: NAMES.map((label, index) => ({ label, value: numberOf(row[COLUMNS[index]])! }))
		})), { order: NAMES, quantityByLabel: { Authority: 'authority', Recency: 'recency', Lens: 'lens', Watchlist: 'watchlist', Carriage: 'carriage' } }),
		count: candidates.length, drawn: drawn.length, complete: complete.length, hidden: complete.length - drawn.length,
		incomplete: candidates.length - complete.length, unknownIdentity,
		lede: finding, finding,
		records: readingRecords(drawn.map((row) => ({
			title: wordOf(row.item_id), facts: [
				{ label: 'Source', value: wordOf(row.source_id) }, { label: 'Newest run', value: wordOf(row.run_id) },
				{ label: 'Selection score', value: String(row.selection_score) },
				...NAMES.map((label, index) => ({ label, value: index === 0
					? authorityWords(row)
					: String(row[COLUMNS[index]]) })),
			]
		})))
	};
}
