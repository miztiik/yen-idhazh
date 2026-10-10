/** Which cells were recorded, and which UTC days does the answer actually cover? */
import type { Row, SliceResult, LedgerReach } from '../../data/ledger';
import type { Range } from '../queries/window';
import { factsOf, recordsOf, readoutOf, type ReadoutFacts } from '../../charts/readout';

export type Answer = SliceResult | LedgerReach | 'pending';
export const numberOf = (value: Row[string] | undefined): number | null =>
	typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
export const wordOf = (value: Row[string] | undefined, fallback = 'not recorded'): string =>
	typeof value === 'string' && value.length > 0 ? value : fallback;
export const rowsOf = (answer: Answer): Row[] => answer !== 'pending' && 'rows' in answer && answer.state === 'ok' ? answer.rows : [];
export const stateOf = (answer: Answer) => answer === 'pending' ? 'loading' as const : answer.state === 'ok' ? 'ready' as const : answer.state;
export function datesOf(range: Range): string[] {
	const found: string[] = [];
	for (let at = Date.parse(`${range.from}T00:00:00Z`); at <= Date.parse(`${range.to}T00:00:00Z`); at += 86_400_000) {
		found.push(new Date(at).toISOString().slice(0, 10));
	}
	return found;
}
export function evidenceOf(answer: Answer, range: Range | null): string[] {
	if (answer === 'pending' || !('rows' in answer) || (answer.state !== 'ok' && answer.state !== 'quiet') || range === null) return [];
	const notes: string[] = [];
	if (range.days < range.asked) notes.push(`Only ${range.days} of the ${range.asked} requested days are recorded, from ${range.from}.`);
	if (answer.through !== null && answer.through < range.to) notes.push(`The record stops on ${answer.through}; later days are not quiet days.`);
	if (answer.lostDays.length > 0) notes.push(`${answer.lostDays.length} days lost their record: ${answer.lostDays.join(', ')}.`);
	const missing = Object.values(answer.setAside).reduce((sum, count) => sum + count, 0);
	if (missing > 0) notes.push(`${missing} files were set aside unread; the counts may be short.`);
	return notes;
}
export function readingRecords(rows: readonly { title: string; facts: readonly { label: string; value: string }[] }[]) {
	return recordsOf(rows.map((row) => factsOf(row.title, [...row.facts], 'not recorded')));
}
export function dayReadout(records: readonly ReadoutFacts[]) {
	return readoutOf({
		type: 'tileStrip', columns: records.map((record) => record.subject), series: [],
		events: { lines: records.map((record) => record.facts.map((fact) => ({ label: fact.label, value: fact.value ?? record.notMeasured, swatch: null }))) },
		notMeasured: 'not recorded', resting: 'last'
	});
}
