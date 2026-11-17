/** Which recorded item clocks supply comparable stage means and an explicit overlap deduction? */
import type { Row } from '../data/ledger';
import { isDay } from '../data/slice-shapes';
import type { SeriesInput } from '../charts/d3/dateSeries';
import { finiteCell } from './rates';
import { SERIES_TOKENS } from './series-tokens';

/** The stages an item's clock is tiled by, in the order the work happens. */
export const DURATION_STAGES = [
	['fetch_ms', 'Fetch', SERIES_TOKENS.fetch],
	['extract_ms', 'Extract', SERIES_TOKENS.extract],
	['analyze_ms', 'Analyze', SERIES_TOKENS.analyze],
	['summarize_ms', 'Summarize', SERIES_TOKENS.summarize],
	['faithfulness_ms', 'Checking', SERIES_TOKENS.checking]
] as const;
export const DURATION_DETAILS = [
	['label_ms', 'Label call'],
	['summary_ms', 'Summary call, including visual plan'],
	['visual_plan_ms', 'Visual plan, inside the summary call']
] as const;

/** Stages an older row has no clock for because the step did not exist yet. The
 * item spent no time there, so a missing clock reads as zero; for every other
 * stage a missing clock keeps the row out of the cohort. */
const ZERO_WHEN_THE_STEP_DID_NOT_EXIST: ReadonlySet<string> = new Set(['analyze_ms']);

/** One stage's milliseconds on one row, or null where the row recorded none. */
export function stageClock(row: Row, cell: string): number | null {
	const clock = finiteCell(row[cell]);
	return clock === null && ZERO_WHEN_THE_STEP_DID_NOT_EXIST.has(cell) ? 0 : clock;
}

export function durationCohort(rows: readonly Row[], calendar: readonly string[]) {
	if (new Set(calendar).size !== calendar.length || calendar.some((date, index) =>
		!isDay(date) || (index > 0 && date <= calendar[index - 1]))) {
		throw new Error('A duration cohort needs distinct UTC days in ascending order.');
	}
	const byDay = new Map<string, Row[]>(calendar.map((date) => [date, []]));
	for (const row of rows) {
		if (typeof row.date !== 'string' || !isDay(row.date)) throw new Error('An item clock needs a UTC date.');
		byDay.get(row.date)?.push(row);
	}
	const days = calendar.map((date) => {
		const own = byDay.get(date)!;
		let missing = 0;
		let invalid = 0;
		let inconsistent = 0;
		const cohort = own.flatMap((row) => {
			const values = [...DURATION_STAGES.map(([cell]) => stageClock(row, cell)),
				finiteCell(row.item_total_ms), finiteCell(row.stage_gap_ms)];
			if (values.some((value) => value === null)) {
				missing += 1;
				return [];
			}
			const known = values.filter((value): value is number => value !== null);
			const stages = known.slice(0, DURATION_STAGES.length);
			const elapsed = known[DURATION_STAGES.length];
			const gap = known[DURATION_STAGES.length + 1];
			if (elapsed < 0 || stages.some((value) => value < 0)) {
				invalid += 1;
				return [];
			}
			if (stages.reduce((sum, value) => sum + value, 0) + gap !== elapsed) {
				inconsistent += 1;
				return [];
			}
			return [{ row, stages, elapsed, gap }];
		});
		const mean = (values: readonly number[]) => values.length === 0 ? null
			: values.reduce((sum, value) => sum + value, 0) / values.length;
		return {
			date, recorded: own.length, count: cohort.length, missing, invalid, inconsistent,
			elapsedSum: cohort.reduce((sum, item) => sum + item.elapsed, 0),
			elapsed: mean(cohort.map((item) => item.elapsed)),
			stages: DURATION_STAGES.map(([cell, label], index) => ({ cell, label, value: mean(cohort.map((item) => item.stages[index])) })),
			unattributed: mean(cohort.map((item) => Math.max(0, item.gap))),
			overlap: mean(cohort.map((item) => Math.max(0, -item.gap))),
			signedGap: mean(cohort.map((item) => item.gap)),
			overlapping: cohort.filter((item) => item.gap < 0).length,
			details: DURATION_DETAILS.map(([cell, label]) => {
				const values = cohort.map((item) => finiteCell(item.row[cell]));
				const recorded = values.filter((value): value is number => value !== null && value >= 0);
				return { cell, label, timed: recorded.length,
					value: recorded.length === cohort.length ? mean(recorded) : null };
			})
		};
	});
	const count = days.reduce((sum, day) => sum + day.count, 0);
	const series: SeriesInput[] = [
		...DURATION_STAGES.map(([, label, token], index) => ({
			label, token, points: days.map((day) => ({ date: day.date, value: day.stages[index].value }))
		})),
		{ label: 'Unattributed duration', token: SERIES_TOKENS.unattributed,
			points: days.map((day) => ({ date: day.date, value: day.unattributed })) }
	];
	return {
		days, count, recorded: days.reduce((sum, day) => sum + day.recorded, 0), series,
		meanMs: count === 0 ? null : days.reduce((sum, day) => sum + day.elapsedSum, 0) / count,
		reconciliation: {
			elapsed: { label: 'Elapsed time', token: '--color-text-tertiary' as const,
				points: days.map((day) => ({ date: day.date, value: day.elapsed })) },
			overlap: { label: 'Overlap', token: '--color-text-secondary' as const,
				points: days.map((day) => ({ date: day.date, value: day.overlap })) }
		}
	};
}
