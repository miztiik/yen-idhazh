/** How many articles failed at each stage on each recorded day? */
import type { Row } from '../../data/ledger';
import type { SeriesInput } from '../../charts/d3/dateSeries';
import { SERIES_TOKENS } from '../series-tokens';

const STAGES = [
	{ name: 'fetch', label: 'Fetch', token: SERIES_TOKENS.fetch },
	{ name: 'extract', label: 'Extract', token: SERIES_TOKENS.extract },
	{ name: 'summarize', label: 'Summarize', token: SERIES_TOKENS.summarize }
] as const;

export function nativeFailureMix(rows: readonly Row[], calendar?: readonly string[]) {
	const dates = calendar ?? [...new Set(rows.map((row) => String(row.date)))].sort();
	const failures = rows.filter((row) => row.outcome === 'failed');
	const claimed = STAGES.map((stage) => ({
		...stage, count: failures.filter((row) => row.stage === stage.name).length
	}));
	const other = failures.filter((row) => !STAGES.some((stage) => stage.name === row.stage));
	const series: SeriesInput[] = claimed.map((stage) => ({
		label: stage.label, token: stage.token,
		points: dates.map((date) => ({ date, value: rows.some((row) => row.date === date)
			? failures.filter((row) => row.date === date && row.stage === stage.name).length : null }))
	}));
	if (other.length > 0) series.push({
		label: 'Other stages', token: SERIES_TOKENS.other,
		points: dates.map((date) => ({ date, value: rows.some((row) => row.date === date)
			? other.filter((row) => row.date === date).length : null }))
	});
	const stages = [...new Set(failures.map((row) => String(row.stage)))].sort((a, b) =>
		failures.filter((row) => row.stage === b).length - failures.filter((row) => row.stage === a).length || a.localeCompare(b));
	return {
		series, failures: failures.length, articles: rows.length,
		share: rows.length === 0 ? null : failures.length / rows.length,
		stages, chosenStage: stages[0] ?? null,
		rules: stages.map((stage) => {
			const stageRows = failures.filter((row) => row.stage === stage);
			const counts = new Map<string, number>();
			let unknown = 0;
			for (const row of stageRows) {
				if (typeof row.failed_rule !== 'string' || row.failed_rule === '') { unknown += 1; continue; }
				counts.set(row.failed_rule, (counts.get(row.failed_rule) ?? 0) + 1);
			}
			return { stage, failures: stageRows.length, unknown,
				rules: [...counts].map(([rule, count]) => ({ rule, count })).sort((a, b) => b.count - a.count || a.rule.localeCompare(b.rule)) };
		})
	};
}
