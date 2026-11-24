/** Which attempts and outcomes does the packed record establish for each UTC day? */
import type { Row } from '../../data/ledger';
import type { PublishedChart, RunRecord } from '../../server/payload';
import type { RecordRead } from '../recording';

export interface RefusalCount { reason: string; count: number }
export interface VisualAttemptDay {
	date: string;
	attempts: number;
	refusals: RefusalCount[];
}

const cell = (row: Row, name: string): string => row[name] === null || row[name] === undefined ? '' : String(row[name]);

export function visualAttemptDays(rows: readonly Row[]): VisualAttemptDay[] {
	const days = new Map<string, VisualAttemptDay>();
	for (const row of rows) {
		const date = cell(row, 'date');
		let day = days.get(date);
		if (day === undefined) {
			day = { date, attempts: 0, refusals: [] };
			days.set(date, day);
		}
		day.attempts += 1;
		const reason = cell(row, 'rejection_reason');
		if (reason !== '') {
			const held = day.refusals.find((refusal) => refusal.reason === reason);
			if (held === undefined) day.refusals.push({ reason, count: 1 });
			else held.count += 1;
		}
	}
	return [...days.values()].sort((a, b) => a.date.localeCompare(b.date)).map((day) => ({
		...day,
		refusals: day.refusals.sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason))
	}));
}

export type ChartTypeTotals = Record<string, number>;

export function tallyChartTypes(types: Iterable<string>): ChartTypeTotals {
	const counts = new Map<string, number>();
	for (const type of types) counts.set(type, (counts.get(type) ?? 0) + 1);
	return Object.fromEntries(counts);
}

interface SettledAttempt { visualId: string; planned: string; saved: string }

/** Match the assembled cohort, not every attempt on the day. */
export function visualAttemptTypes(
	date: string, rows: readonly Row[], read: RecordRead, runs: readonly Pick<RunRecord, 'runId' | 'n' | 'decided'>[],
	assets: readonly PublishedChart[]
): { proposed: ChartTypeTotals; saved: ChartTypeTotals } | null {
	if (read.state !== 'read' || date < read.first || date > read.through || read.lostDays.includes(date) ||
		[date, date.slice(0, 7), date.slice(0, 4)].some((period) => (read.setAside[period] ?? 0) > 0) ||
		runs.length === 0) return null;

	const attemptsByRun = new Map(runs.map((run) => [run.runId, new Map<string, SettledAttempt>()]));
	const idByOrdinal = new Map(runs.map((run) => [run.n, run.runId]));
	if (attemptsByRun.size !== runs.length || idByOrdinal.size !== runs.length || attemptsByRun.has('')) return null;
	for (const row of rows) {
		const items = attemptsByRun.get(cell(row, 'run_id'));
		if (items === undefined) continue;
		const itemId = cell(row, 'item_id');
		const visualId = cell(row, 'visual_id');
		const planned = cell(row, 'planned_type');
		const saved = cell(row, 'rendered_type');
		const state = cell(row, 'state');
		const decision = cell(row, 'decision');
		const declined = decision === 'none' && state === 'absent' && !planned && !saved;
		const typed = decision === 'visual' && planned && (
			(state === 'rendered' && saved) || ((state === 'absent' || state === 'render_failed') && !saved)
		);
		if (!itemId || !visualId || (!declined && !typed)) return null;

		// Assembly holds one decision per item. Identical repeats do not fill a missing
		// item; conflicting identities cannot say which decision assembly received.
		const held = items.get(itemId);
		if (held && (held.visualId !== visualId || held.planned !== planned || held.saved !== saved)) return null;
		items.set(itemId, { visualId, planned, saved });
	}
	if (runs.some((run) => attemptsByRun.get(run.runId)?.size !== run.decided)) return null;
	if (assets.some((asset) => {
		const runId = idByOrdinal.get(asset.run);
		return runId === undefined || attemptsByRun.get(runId)?.get(asset.itemId)?.saved !== asset.type;
	})) return null;
	const settled = [...attemptsByRun.values()].flatMap((items) => [...items.values()]);
	return {
		proposed: tallyChartTypes(settled.map((attempt) => attempt.planned).filter(Boolean)),
		saved: tallyChartTypes(settled.map((attempt) => attempt.saved).filter(Boolean))
	};
}
