/** Only complete, reconciling item clocks can supply an additive composition. */
import type { Row } from '../../data/ledger';
import type { SeriesInput } from '../../charts/d3/dateSeries';
import { finiteCell } from '../rates';
import { SERIES_TOKENS } from '../series-tokens';

const PARTS = [
	['fetch_ms', 'Fetch', SERIES_TOKENS.fetch], ['extract_ms', 'Extract', SERIES_TOKENS.extract],
	['label_ms', 'Label call', SERIES_TOKENS['label-call']], ['summary_only_ms', 'Summary call', SERIES_TOKENS['summary-call']],
	['visual_plan_ms', 'Visual plan', SERIES_TOKENS['visual-plan']], ['model_unsplit_ms', 'Model, unsplit', SERIES_TOKENS['model-time']],
	['faithfulness_ms', 'Checking', SERIES_TOKENS.checking],
	['stage_gap_ms', 'Time no named step claimed', SERIES_TOKENS.unattributed]
] as const;

export function nativeTimeSplit(rows: readonly Row[], calendar?: readonly string[]) {
	const dates = calendar ?? [...new Set(rows.map((row) => String(row.date)))].sort();
	const days = dates.map((date) => {
		const own = rows.filter((row) => row.date === date && finiteCell(row.item_total_ms) !== null && Number(row.item_total_ms) >= 0);
		const complete = own.flatMap((row) => {
			if (['fetch_ms', 'extract_ms', 'summarize_ms', 'label_ms', 'summary_ms', 'visual_plan_ms', 'faithfulness_ms', 'stage_gap_ms']
				.some((cell) => finiteCell(row[cell]) === null)) return [];
			const split: Row = { ...row, summary_only_ms: Number(row.summary_ms) - Number(row.visual_plan_ms),
				model_unsplit_ms: Number(row.summarize_ms) - Number(row.label_ms) - Number(row.summary_ms) };
			const sum = PARTS.reduce((total, [cell]) => total + Number(split[cell]), 0);
			return sum === row.item_total_ms ? [split] : [];
		});
		const mean = (input: readonly Row[], cell: string) => {
			const values = input.flatMap((row) => {
				const value = finiteCell(row[cell]);
				return value === null ? [] : [value];
			});
			return { value: values.length === 0 ? null : values.reduce((sum, value) => sum + value, 0) / values.length, timed: values.length };
		};
		return { date, items: own.length, total: mean(own, 'item_total_ms'), composable: complete.length,
			compositionTotal: mean(complete, 'item_total_ms'),
			parts: PARTS.map(([cell, label]) => ({ cell, label, ...mean(complete, cell) })),
			readings: ['fetch_ms', 'extract_ms', 'summarize_ms', 'label_ms', 'summary_ms', 'visual_plan_ms', 'faithfulness_ms', 'stage_gap_ms']
				.map((cell) => ({ cell, ...mean(own, cell) })) };
	});
	const series: SeriesInput[] = PARTS.map(([cell, label, token], at) => ({
		label, token, points: days.map((day) => ({ date: day.date, value: day.parts[at].value }))
	}));
	const signedDates = days.filter((day) => day.parts.some((part) => part.value !== null && part.value < 0)).map((day) => day.date);
	const total = rows.flatMap((row) => {
		const value = finiteCell(row.item_total_ms);
		return value === null || value < 0 ? [] : [value];
	});
	return { days, series, signed: signedDates.length > 0, signedDates,
		meanMs: total.length === 0 ? null : total.reduce((sum, value) => sum + value, 0) / total.length };
}
