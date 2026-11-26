/** What can the published Council steps establish about a run attempt? */
import { isDay, type Row } from '../data/slice-shapes';

export const COUNCIL_STEPS = ['select_judge_work', 'evaluate_work_part', 'combine_judge_results'] as const;
export const COUNCIL_OUTCOMES = ['completed', 'stopped_on_deadline', 'nothing_to_do', 'failed'] as const;
type Step = typeof COUNCIL_STEPS[number];
type Outcome = typeof COUNCIL_OUTCOMES[number];
const OUTCOME_LABEL: Record<Outcome, string> = {
	completed: 'Completed', stopped_on_deadline: 'Stopped at deadline', nothing_to_do: 'No work', failed: 'Failed'
};
const SAVE_JOB = 'save_council_results';
const RUN_ID = /^(\d{4}-\d{2}-\d{2})-([1-9]\d*)$/;

interface CouncilStep {
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
	runId: string;
	attempt: number;
	saveJob: boolean;
	steps: CouncilStep[];
}

export interface CouncilDayAttempt {
	attempt: CouncilAttempt;
	first: string;
	last: string;
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
		const held = attempts.get(key) ?? { key, runId: run_id, attempt, saveJob: true, steps: [] };
		held.saveJob &&= row.job === SAVE_JOB;
		held.steps.push({ date, judge: judge_id, startedAt: started_at, step, outcome,
			part: typeof work_part_index === 'number' ? work_part_index : null, width: work_part_count });
		attempts.set(key, held);
	}
	const days = new Map<string, CouncilDayAttempt[]>();
	for (const attempt of attempts.values()) {
		const times = new Map<string, CouncilDayAttempt>();
		for (const { startedAt } of attempt.steps) {
			const date = startedAt.slice(0, 10);
			const span = times.get(date) ?? { attempt, first: startedAt, last: startedAt };
			if (startedAt < span.first) span.first = startedAt;
			if (startedAt > span.last) span.last = startedAt;
			times.set(date, span);
		}
		for (const [date, span] of times) {
			const onDay = days.get(date) ?? [];
			onDay.push(span);
			days.set(date, onDay);
		}
	}
	for (const day of days.values()) day.sort((a, b) => b.last.localeCompare(a.last)
		|| b.attempt.attempt - a.attempt.attempt || a.attempt.runId.localeCompare(b.attempt.runId));
	return { days, ignored };
}

export function councilDetails(attempt: CouncilAttempt) {
	const groups = new Map<string, CouncilStep[]>();
	for (const row of attempt.steps) {
		const key = `${row.judge}/${row.date}`;
		const held = groups.get(key) ?? [];
		held.push(row);
		groups.set(key, held);
	}
	return [...groups].sort(([a], [b]) => a.localeCompare(b)).map(([key, rows]) => {
		const { judge, date } = rows[0];
		const parts = rows.filter((row) => row.part !== null)
			.sort((a, b) => (a.part ?? 0) - (b.part ?? 0));
		const reported = new Set(parts.map((part) => part.part)).size;
		const widths = new Set(rows.map((row) => row.width));
		const expected = widths.size === 1 ? rows[0].width : null;
		const prep = rows.filter((row) => row.step === 'select_judge_work');
		const combine = rows.filter((row) => row.step === 'combine_judge_results');
		const noWork = expected === 0 && prep.length === 1 && prep[0].outcome === 'nothing_to_do'
			&& parts.length === 0 && combine.every((row) => row.outcome === 'nothing_to_do');
		const phase = (steps: CouncilStep[], empty = 'Not reported') => steps.length > 0
			? [...new Set(steps.map((row) => OUTCOME_LABEL[row.outcome]))].join(', ') : empty;
		return {
			key, judge, date, reported, expected,
			activity: parts.some((row) => row.outcome === 'completed') ? 'Judging reported'
				: parts.some((row) => row.outcome !== 'nothing_to_do') ? 'Judging attempted'
				: noWork ? 'No work assigned' : 'No judging work reported',
			prepare: phase(prep), combine: phase(combine, noWork ? 'Not needed' : 'Not reported'),
			incomplete: prep.length === 0 || (expected !== null && (reported < expected || (expected > 0 && combine.length === 0))),
			parts: parts.map((part) => `Part ${part.part! + 1}: ${OUTCOME_LABEL[part.outcome]}`).join('; ')
		};
	});
}

export function councilAttemptLink(attempt: CouncilAttempt, configuredRepo: string): string | null {
	const run = RUN_ID.exec(attempt.runId);
	if (!attempt.saveJob || !run || !isDay(run[1]) || !Number.isSafeInteger(attempt.attempt) || attempt.attempt < 1) return null;
	const repo = URL.parse(configuredRepo);
	if (repo === null || repo.protocol !== 'https:' || repo.username || repo.password || repo.search || repo.hash
		|| !/^\/[^/]+\/[^/]+\/?$/.test(repo.pathname)) return null;
	repo.pathname = `${repo.pathname.replace(/\/$/, '')}/actions/runs/${run[2]}/attempts/${attempt.attempt}`;
	return repo.href;
}
