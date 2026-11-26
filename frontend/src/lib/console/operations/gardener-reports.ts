/** Place Gardener stops and recovery notes on the UTC day the work was reported. */
import { isDay, type Row } from '../../data/slice-shapes';

export const GARDENER_STOPS = ['exhausted', 'ceiling', 'failed', 'deferred'] as const;
export const GARDENER_RECOVERIES = [
	'repacked-from-raw', 'recorded-lost', 'reopened-month', 'index-rebuilt', 'set-aside', 'carried-over', 'not-deletable'
] as const;
const RECOVERY_LABEL = {
	'repacked-from-raw': 'Repacked from raw files', 'recorded-lost': 'Record lost', 'reopened-month': 'Month reopened',
	'index-rebuilt': 'Existing file restored to index', 'set-aside': 'File set aside',
	'carried-over': 'Work carried over', 'not-deletable': 'Not deletable'
} as const;
const count = (value: Row[string] | undefined) =>
	typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null;

function recoveryNotes(value: Row[string] | undefined) {
	const reports: { label: string; subject: string }[] = [];
	if (value === null) return { reports, partial: true };
	let records: unknown;
	try { records = typeof value === 'string' ? JSON.parse(value) : null; }
	catch { return { reports, partial: true }; }
	if (!Array.isArray(records)) return { reports, partial: true };
	let partial = false;
	for (const record of records) {
		const note = GARDENER_RECOVERIES.find((word) => word === record?.note);
		if (note === undefined || typeof record.subject !== 'string' ||
			!(/^[A-Za-z0-9][A-Za-z0-9._/-]*$/).test(record.subject)) { partial = true; continue; }
		reports.push({ label: RECOVERY_LABEL[note], subject: record.subject });
	}
	return { reports, partial };
}

export function gardenerReports(rows: readonly Row[]) {
	const byDay = new Map<string, TaskReport[]>();
	let ignored = 0;
	let partial = false;
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
		const recovery = recoveryNotes(row.recovered);
		partial ||= recovery.partial;
		const day = work_ended_at.slice(0, 10);
		const tasks = byDay.get(day) ?? [];
		tasks.push({
			runId: run_id, attempt, job, shard, task, dryRun: dry_run, stop, recovery: recovery.reports,
			checked: count(row.candidates_seen), selected: count(row.selected), deleted: count(row.deleted),
			bytes: count(row.bytes_freed), through: isDay(row.handled_through) ? row.handled_through : null,
			fault: typeof fault === 'string' ? fault : null, resume: typeof resume_from === 'string' ? resume_from : null
		});
		byDay.set(day, tasks);
	}
	return { byDay, ignored, partial };
}

interface TaskReport {
	runId: string;
	attempt: number;
	job: string;
	shard: number;
	task: string;
	dryRun: boolean;
	stop: (typeof GARDENER_STOPS)[number];
	recovery: { label: string; subject: string }[];
	checked: number | null;
	selected: number | null;
	deleted: number | null;
	bytes: number | null;
	through: string | null;
	fault: string | null;
	resume: string | null;
}

export function gardenerOutcomeLanes(calendar: readonly string[], byDay: ReadonlyMap<string, readonly TaskReport[]>) {
	const tracks = calendar.map((day) => {
		const tasks = byDay.get(day)?.filter((task) => !task.dryRun);
		return {
			reported: (tasks?.length ?? 0) > 0,
			failed: tasks?.filter(({ stop }) => stop === 'failed') ?? [],
			deferred: tasks?.filter(({ stop }) => stop === 'deferred' || stop === 'ceiling') ?? [],
			recovered: tasks?.flatMap(({ recovery }) => recovery) ?? []
		};
	});
	const sharedReason = (a: readonly TaskReport[], b: readonly TaskReport[]) => a.find((left) =>
		left.fault !== null && b.some((right) => right.fault === left.fault && right.task === left.task))?.fault ?? null;
	return (['failed', 'deferred', 'recovered'] as const).map((state) => ({
		name: { failed: 'Failed', deferred: 'Deferred', recovered: 'Recovery' }[state],
		cells: tracks.map((track, index) => {
			const reports = track[state];
			const before = state === 'deferred' ? sharedReason(tracks[index - 1]?.deferred ?? [], track.deferred) : null;
			const after = state === 'deferred' ? sharedReason(track.deferred, tracks[index + 1]?.deferred ?? []) : null;
			return {
				state, draw: reports.length > 0,
				links: state === 'deferred' ? { before: before !== null, after: after !== null } : undefined,
				caption: after !== null && before !== after ? after.replaceAll('-', ' ') : undefined,
				text: reports.length === 0 ? (track.reported ? 'None in reported tasks' : 'No task report') :
					`${reports.length} ${state === 'recovered' ? 'recovery notes' : 'task reports'}`
			};
		})
	}));
}
