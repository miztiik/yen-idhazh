/** Which permissions hold a source back, and what did its complete-day offers yield? */
import type { SourceHealthView, SourceHealthRow } from '../../server/payload';
import { rankedList } from '../../charts/d3/rankedList';

const PERMISSION = [
	['allowed', 'the site allows us', 'nothing'],
	['denied', 'the site refuses us', 'nothing from it reaches the digest until a later run reads its rules again'],
	['unreachable', 'we could not read its rules', 'the address is not asked at all until a later run establishes permission'],
	['unrecorded', 'no run has recorded an answer', 'nothing'],
	['unavailable', 'the latest permission is not known', 'the saved times do not prove which permission answer came last']
] as const;
const AVAILABILITY = [
	['answering', 'answering with articles', 'nothing'],
	['failing', 'its last read failed', 'the digest is short of what it carries until it answers again'],
	['resting', 'resting after repeated failures', 'nothing it carries reaches the digest until the run asks it again'],
	['never_asked', 'unread in this record', 'nothing from it is reaching the digest'],
	['unavailable', 'observation order is not known', 'tied observations do not select a rest decision']
] as const;
const ORDER: Record<string, number> = { retired: 5, denied: 4, unreachable: 3, unavailable: 2, never_asked: 2, resting: 1, failing: 0 };
export function sourceHealth(view: SourceHealthView | null, cap: number) {
	if (view === null) return null;
	const reason = (row: SourceHealthRow) => row.retired ? 'retired' : row.permission === 'denied' || row.permission === 'unreachable' || row.permission === 'unavailable' ? row.permission : row.availability !== 'answering' ? row.availability : null;
	const held = view.sources.filter((row) => reason(row) !== null).sort((a, b) => ORDER[reason(b)!] - ORDER[reason(a)!] || a.source_id.localeCompare(b.source_id));
	const notes = held.slice(0, cap).map((row) => {
		const facts = ['denied', 'unreachable', 'unavailable'].includes(row.permission) ? PERMISSION : AVAILABILITY;
		return {
			...row, withheld: row.retired ? 'no run asks this address again until its configured address changes' : facts.find(([id]) => id === reason(row))?.[2] ?? 'nothing it carries reaches the digest'
		};
	});
	const tally = (facts: typeof PERMISSION | typeof AVAILABILITY, field: 'permission' | 'availability') => facts.map(([id, label, withheld]) => ({ id, label, withheld, count: view.sources.filter((row) => row[field] === id).length })).filter(fact => fact.id !== 'unavailable' || fact.count > 0);
	const yields = view.sources.filter((row) => row.opportunities > 0);
	const geometry = rankedList(yields.map((row) => ({
		label: row.source_id, value: view.yield_readable ? row.publications / row.opportunities : row.publications,
		context: `${row.publications} published of ${row.opportunities} offered; ${row.source_failures} source-owned failures`,
		status: view.yield_readable ? undefined : `Counts only: ${view.complete_dates} of ${view.min_complete_days} complete days`
	})), { max: cap });
	if (geometry && view.yield_readable) for (const row of geometry.rows) row.row.value = `${Math.round(row.value * 100)}%`;
	return {
		view, notes, geometry, permission: tally(PERMISSION, 'permission'), availability: tally(AVAILABILITY, 'availability'),
		totals: view.sources.reduce((all, row) => ({ offered: all.offered + row.opportunities, published: all.published + row.publications, failures: all.failures + row.source_failures }), { offered: 0, published: 0, failures: 0 }),
		withheld: held.length, hidden: Math.max(0, held.length - cap), retired: view.sources.filter((row) => row.retired).length,
		headline: view.sources.length === 0 ? 'This run published an empty source census.' : view.headline_sentence,
		maxText: geometry ? view.yield_readable ? `${Math.round(geometry.max * 100)}% published out of offered` : `${geometry.max} publications` : ''
	};
}
