/** What can the published Council steps establish about a run attempt? */
import type { TimeWindow } from '../charts/viewport';
import { isDay, type Row } from '../data/slice-shapes';

export const COUNCIL_STEPS = ['select_judge_work', 'evaluate_work_part', 'combine_judge_results'] as const;
export const COUNCIL_OUTCOMES = ['completed', 'stopped_on_deadline', 'nothing_to_do', 'failed'] as const;
type Step = typeof COUNCIL_STEPS[number];
type Outcome = typeof COUNCIL_OUTCOMES[number];
const OUTCOME_LABEL: Record<Outcome, string> = {
	completed: 'Completed', stopped_on_deadline: 'Stopped at deadline', nothing_to_do: 'No work', failed: 'Failed'
};
const RUN_ID = /^(\d{4}-\d{2}-\d{2})-([1-9]\d*)$/;

export interface CouncilStep {
	date: string;
	judge: string;
	startedAt: string;
	step: Step;
	outcome: Outcome;
	part: number | null;
	width: number;
}

export interface CouncilAttempt {
	key: string;
	attempt: number;
	steps: CouncilStep[];
}

export function councilHistory(rows: readonly Row[]) {
	const attempts = new Map<string, CouncilAttempt>();
	let ignored = 0;
	for (const row of rows) {
		const { date, run_id, attempt, judge_id, started_at, work_part_count, work_part_index } = row;
		const identity = typeof run_id === 'string' ? RUN_ID.exec(run_id) : null;
		const step = COUNCIL_STEPS.find((value) => value === row.evaluation_step);
		const outcome = COUNCIL_OUTCOMES.find((value) => value === row.outcome);
		const part = step === 'evaluate_work_part';
		if (!identity || !isDay(identity[1]) || typeof run_id !== 'string' || !isDay(date) ||
			typeof attempt !== 'number' || !Number.isSafeInteger(attempt) || attempt < 1 ||
			typeof judge_id !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(judge_id) ||
			typeof started_at !== 'string' || !/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\dZ$/.test(started_at) ||
			!isDay(started_at.slice(0, 10)) || step === undefined || outcome === undefined ||
			typeof work_part_count !== 'number' || !Number.isSafeInteger(work_part_count) || work_part_count < 0 ||
			(part ? typeof work_part_index !== 'number' || !Number.isSafeInteger(work_part_index) ||
				work_part_index < 0 || work_part_index >= work_part_count : work_part_index !== null)) {
			ignored += 1;
			continue;
		}
		const key = `${run_id}/${attempt}`;
		const held = attempts.get(key) ?? { key, attempt, steps: [] };
		held.steps.push({ date, judge: judge_id, startedAt: started_at, step, outcome,
			part: typeof work_part_index === 'number' ? work_part_index : null, width: work_part_count });
		attempts.set(key, held);
	}
	return { attempts: [...attempts.values()], ignored };
}

export interface CouncilWork {
	key: string;
	judge: string;
	digest: string;
	startedAt: string;
	attempt: CouncilAttempt;
	expected: number | null;
	parts: ReadonlyMap<number, Outcome>;
	combine: Outcome | null;
	prepare: Outcome | null;
	noWork: boolean;
}

function outcome(steps: readonly CouncilStep[], step: Step): Outcome | null {
	const states = new Set(steps.filter((row) => row.step === step).map((row) => row.outcome));
	return states.size === 1 ? states.values().next().value ?? null : null;
}

/** A cohort is one judge, digest and attempt; a retry can never supply another cohort's part. */
function councilWork(attempt: CouncilAttempt): CouncilWork[] {
	const groups = new Map<string, CouncilStep[]>();
	for (const row of attempt.steps) {
		const key = `${row.judge}/${row.date}`;
		const held = groups.get(key) ?? [];
		held.push(row);
		groups.set(key, held);
	}
	return [...groups].map(([key, rows]) => {
		const { judge, date } = rows[0];
		const widths = new Set(rows.map((row) => row.width));
		const expected = widths.size === 1 ? rows[0].width : null;
		const candidates = new Map<number, Set<Outcome>>();
		for (const row of rows) {
			if (row.part === null) continue;
			const states = candidates.get(row.part) ?? new Set<Outcome>();
			states.add(row.outcome);
			candidates.set(row.part, states);
		}
		const parts = new Map<number, Outcome>();
		for (const [part, states] of candidates) {
			const state = states.values().next().value;
			if (states.size === 1 && state !== undefined) parts.set(part, state);
		}
		const prepare = outcome(rows, 'select_judge_work');
		const combine = outcome(rows, 'combine_judge_results');
		const noWork = expected === 0 && prepare === 'nothing_to_do' && candidates.size === 0 &&
			(combine === null || combine === 'nothing_to_do');
		const startedAt = rows.reduce((first, row) => row.startedAt < first ? row.startedAt : first, rows[0].startedAt);
		return { key: `${attempt.key}/${key}`, judge, digest: date, startedAt, attempt, expected, parts, prepare, combine, noWork };
	});
}

export function councilJudges(attempts: readonly CouncilAttempt[], window: TimeWindow) {
	const judges = new Map<string, Map<string, CouncilWork[]>>();
	for (const work of attempts.flatMap(councilWork)) {
		const day = work.startedAt.slice(0, 10);
		if (day < window.start || day > window.end) continue;
		const days = judges.get(work.judge) ?? new Map<string, CouncilWork[]>();
		const at = days.get(day) ?? [];
		at.push(work);
		days.set(day, at);
		judges.set(work.judge, days);
	}
	return [...judges].sort(([a], [b]) => a.localeCompare(b)).map(([judge, days]) => ({
		judge, days: new Map([...days].map(([day, items]) => [day, items.sort((a, b) =>
			a.startedAt.localeCompare(b.startedAt) || a.key.localeCompare(b.key))]))
	}));
}

export function councilPartCounts(work: CouncilWork) {
	const reported = { completed: 0, stopped_on_deadline: 0, failed: 0, nothing_to_do: 0 };
	for (const part of work.parts.values()) reported[part] += 1;
	return {
		...reported,
		unreported: work.expected === null ? 0 : Math.max(0, work.expected - work.parts.size),
		reported: work.parts.size
	};
}

export function councilOutcomeLabel(value: Outcome | null): string {
	return value === null ? 'Not reported' : OUTCOME_LABEL[value];
}

/** Each step counts on its own execution day. Silence is never an explicit no-work result. */
export function councilActivity(attempts: readonly CouncilAttempt[], roster: readonly string[], calendar: readonly string[]) {
	type Activity = 'reported' | 'checked';
	const byJudge = new Map<string, Map<string, Activity>>(roster.map((judge) => [judge, new Map()]));
	const inWindow = new Set(calendar);
	for (const { steps } of attempts) {
		for (const step of steps) {
			const days = byJudge.get(step.judge) ?? new Map<string, Activity>();
			byJudge.set(step.judge, days);
			const day = step.startedAt.slice(0, 10);
			if (!inWindow.has(day)) continue;
			if (step.outcome !== 'nothing_to_do') days.set(day, 'reported');
			else if (!days.has(day)) days.set(day, 'checked');
		}
	}
	return [...byJudge].sort(([a], [b]) => a.localeCompare(b)).map(([judge, days]) => ({
		name: judge.replaceAll('-', ' '),
		cells: calendar.map((date) => {
			const state = days.get(date) ?? 'unreported';
			return { state, text: state === 'reported' ? 'Step reported' : state === 'checked' ? 'No work assigned' : 'No report' } as const;
		})
	}));
}
