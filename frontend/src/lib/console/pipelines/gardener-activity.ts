/** Relate verified compact writes and published wake reports without equating their clocks. */
import { daysInWindow, windowFromDates } from '../../charts/viewport';
import { COMPACT_PERIODS, type Period } from '../../data/compact-index';
import type { CompactWriteTrack } from '../../data/compact-file-writes';
import type { CompactWrite } from '../../data/compact-write-footer';
import { isDay, type Row } from '../../data/slice-shapes';
import { clockUtc, longDate, MONTHS } from '../../format';

export const GARDENER_STOPS = ['exhausted', 'ceiling', 'failed', 'deferred'] as const;
export const GARDENER_RECOVERIES = [
	'repacked-from-raw', 'recorded-lost', 'reopened-month', 'index-rebuilt', 'set-aside', 'carried-over', 'not-deletable'
] as const;

const STOP_LABEL = { exhausted: 'Finished', ceiling: 'Limit reached', failed: 'Failed', deferred: 'Deferred' } as const;
const RECOVERY_LABEL = {
	'repacked-from-raw': 'Repacked from raw files', 'recorded-lost': 'Record lost', 'reopened-month': 'Month reopened',
	'index-rebuilt': 'Existing file restored to index', 'set-aside': 'File set aside',
	'carried-over': 'Work carried over', 'not-deletable': 'Not deletable'
} as const;
export const PERIOD_LABEL: Record<Period, string> = { daily: 'Daily', monthly: 'Monthly', yearly: 'Yearly' };
type Tracks = Partial<Record<Period, CompactWriteTrack>>;

export function writeInstant(value: CompactWrite) { return new Date(value.writtenAt).toISOString(); }
export function utcTime(stamp: string) { return `${longDate(stamp.slice(0, 10))} ${clockUtc(stamp)}`; }
export function periodLabel(period: Period, stamp: string): string {
	if (period === 'daily') return longDate(stamp);
	if (period === 'yearly') return stamp;
	return `${MONTHS[Number(stamp.slice(5)) - 1]} ${stamp.slice(0, 4)}`;
}

export function compactActivity(tracks: Tracks, days: number) {
	const byNewest = (a: CompactWrite, b: CompactWrite) =>
		b.writtenAt - a.writtenAt || a.ledger.localeCompare(b.ledger) || a.covers.localeCompare(b.covers);
	const writes = COMPACT_PERIODS.flatMap((period) => tracks[period]?.writes ?? []).sort(byNewest);
	const monthly = writes.find((write) => write.period === 'monthly') ?? null;
	const monthlyGroup = monthly === null ? [] : writes.filter((write) =>
		write.period === 'monthly' && write.runId === monthly.runId && write.attempt === monthly.attempt && write.covers === monthly.covers);
	const viewport = windowFromDates(writes.map((write) => writeInstant(write).slice(0, 10)), days);
	const calendar = viewport === null ? [] : daysInWindow(viewport);
	const byDay = new Map<string, CompactWrite[]>();
	for (const write of writes) {
		const day = writeInstant(write).slice(0, 10);
		const onDay = byDay.get(day) ?? [];
		onDay.push(write);
		byDay.set(day, onDay);
	}
	return {
		monthly, monthlyGroup, calendar, byDay,
		lanes: COMPACT_PERIODS.map((period) => {
			const track = tracks[period];
			const found = (day: string) => (byDay.get(day) ?? []).filter((write) => write.period === period);
			const cells = calendar.map((date) => {
				const written = found(date);
				const uncertain = track === undefined || track.omitted || track.issues.length > 0;
				const state = written.length > 0 ? 'written' : uncertain ? 'unavailable' : 'checked';
				const text = written.length > 0 ? `${written.length} published ${written.length === 1 ? 'file' : 'files'}`
					: track === undefined ? 'Checking files'
					: track.omitted ? 'Not checked'
					: uncertain ? 'Evidence incomplete' : 'No write found in checked files';
				return { state, text } as const;
			});
			return { name: PERIOD_LABEL[period], cells };
		})
	};
}

const count = (value: Row[string] | undefined) =>
	typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null;

export function taskReports(rows: readonly Row[]) {
	const tasks = [];
	let ignored = 0;
	for (const row of rows) {
		const { date, run_id, attempt, job, shard, task, work_ended_at, dry_run, fault, resume_from } = row;
		const stop = GARDENER_STOPS.find((word) => word === row.stopped_because);
		const runDay = typeof run_id === 'string' ? /^(\d{4}-\d{2}-\d{2})-\d+$/.exec(run_id)?.[1] : undefined;
		if (!isDay(date) || typeof run_id !== 'string' || !isDay(runDay) ||
			typeof attempt !== 'number' || count(attempt) === null || attempt < 1 ||
			(job !== 'run-tasks' && job !== 'history') || typeof shard !== 'number' || count(shard) === null ||
			typeof task !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(task) ||
			typeof work_ended_at !== 'string' || !/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\dZ$/.test(work_ended_at) ||
			!isDay(work_ended_at.slice(0, 10)) || typeof dry_run !== 'boolean' || stop === undefined) {
			ignored += 1;
			continue;
		}
		tasks.push({ date, runId: run_id, attempt, job, shard, task, workEnded: work_ended_at,
			dryRun: dry_run, stop, status: STOP_LABEL[stop], selected: count(row.selected), deleted: count(row.deleted),
			bytes: count(row.bytes_freed), fault: typeof fault === 'string' ? fault : null,
			resume: typeof resume_from === 'string' ? resume_from : null });
	}
	return { tasks, ignored };
}

type TaskReport = ReturnType<typeof taskReports>['tasks'][number];

export function gardenerWakes(rows: readonly Row[]) {
	const { tasks, ignored } = taskReports(rows);
	const byAttempt = new Map<string, TaskReport[]>();
	for (const task of tasks) {
		const key = `${task.runId}/${task.attempt}`;
		const group = byAttempt.get(key) ?? [];
		group.push(task);
		byAttempt.set(key, group);
	}
	const wakes = [...byAttempt].map(([key, tasks]) => {
		const { runId, attempt } = tasks[0];
		const dates = tasks.map((task) => task.date).sort();
		const countStops = GARDENER_STOPS.map((stop) => ({
			label: STOP_LABEL[stop], count: tasks.filter((task) => task.stop === stop).length
		})).filter(({ count }) => count > 0);
		return { key, runId, attempt, tasks, countStops, from: dates[0], to: dates.at(-1)!,
			workEnded: tasks.map((task) => task.workEnded).sort().at(-1)! };
	}).sort((a, b) => b.workEnded.localeCompare(a.workEnded) || b.attempt - a.attempt || a.runId.localeCompare(b.runId));
	return { wakes, ignored };
}

export function recoveryNotes(rows: readonly Row[]) {
	let partial = false;
	const reports: { task: string; label: string; subject: string }[] = [];
	for (const { recovered, task } of rows) {
		if (typeof recovered !== 'string' || typeof task !== 'string') {
			partial = true;
			continue;
		}
		let parsed: unknown;
		try { parsed = JSON.parse(recovered); } catch { partial = true; continue; }
		if (!Array.isArray(parsed)) { partial = true; continue; }
		for (const record of parsed) {
			const note = GARDENER_RECOVERIES.find((value) => value === record?.note);
			if (note === undefined || typeof record.subject !== 'string' ||
				!(/^[A-Za-z0-9][A-Za-z0-9._/-]*$/).test(record.subject)) { partial = true; continue; }
			reports.push({ task, label: RECOVERY_LABEL[note], subject: record.subject });
		}
	}
	return { partial, reports };
}

export function removalReport(task: TaskReport): string {
	if (task.deleted === null) return 'Removal count not recorded.';
	if (task.task === 'workflow-artifacts' || task.task === 'workflow-runs') {
		const unit = task.task === 'workflow-artifacts' ? 'workflow artifacts' : 'workflow runs';
		return `${task.dryRun ? 'Would remove' : 'Reported removed'}: ${task.deleted} ${unit}`
			+ (task.selected !== null && task.selected > task.deleted ? ` of ${task.selected} selected` : '') + '.';
	}
	if (task.deleted === 0) return 'No removals reported.';
	return `${task.dryRun ? 'Preview' : 'Task report'}: ${task.deleted} removals, cause not separated.`;
}
