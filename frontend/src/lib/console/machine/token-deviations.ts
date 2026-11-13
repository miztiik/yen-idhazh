/** Explain DuckDB's token flag without recalculating its statistics or verdict. */
import type { RunTokenWork } from '../../charts/machine';
import type { ReadoutLine } from '../../charts/readout';
import type { TokenDeviationRules } from '../../data/token-deviation-query';
import type { TokenAssessment, TokenHistory } from '../queries/token-deviations';
import type { ReadWriteMetric } from '../route-console';

const REASONS: Readonly<Record<string, string>> = {
	'incomplete-history': 'the fixed history contains lost days or unread files.',
	'no-reading': 'no paired token reading.',
	'settings-unavailable': 'the dated settings record does not cover this run.',
	'change-day': 'settings changed this UTC day; the record cannot place the change between its runs.',
	'unknown-setup': 'recorded settings are unknown or mixed in the measured articles.',
	'baseline-unavailable': 'the prior baseline is unavailable.'
};

export function tokenAssessmentKey(date: string, runId: string, metric: ReadWriteMetric, trace: 'read' | 'written'): string {
	return JSON.stringify([date, runId, metric, trace]);
}

export function tokenDeviationReading(
	run: RunTokenWork,
	metric: ReadWriteMetric,
	trace: 'read' | 'written',
	history: TokenHistory | null,
	readings: ReadonlyMap<string, TokenAssessment>,
	rules: TokenDeviationRules,
	tokens: (value: number) => string,
	formatNumber: (value: number) => string
): { warning: boolean | null; line: ReadoutLine } {
	const label = `${trace === 'read' ? 'Read' : 'Written'} assessment`;
	const unassessed = (reason: string) => ({
		warning: null, line: { label, value: `Unassessed: ${reason}`, swatch: null }
	});
	if (run[metric][trace] === null) return unassessed(REASONS['no-reading']);
	if (history === null) return unassessed('checking earlier matching runs.');
	if (history.incomplete) return unassessed(REASONS['incomplete-history']);
	if (history.state === 'missing') return unassessed('earlier token history is not published.');
	if (history.state === 'unreachable') return unassessed('earlier token history did not arrive.');
	if (history.state === 'quiet') return unassessed('nothing is recorded in the fixed history.');
	const row = readings.get(tokenAssessmentKey(run.date, run.runId, metric, trace));
	if (row === undefined || row.value !== run[metric][trace] ||
		row.measured !== run.measured || row.recorded !== run.recorded) {
		return unassessed('the displayed measured cohort does not match the history reading.');
	}
	if (row.reason === 'insufficient-history') {
		return unassessed(`${formatNumber(row.priorCount ?? 0)} earlier matching runs; need at least ${formatNumber(rules.minimumRuns)}, using up to ${formatNumber(rules.historyRuns)}.`);
	}
	if (row.reason !== null) {
		if (!(row.reason in REASONS)) throw new Error(`Unknown token assessment reason: ${row.reason}`);
		return unassessed(REASONS[row.reason]);
	}
	if (row.warning === null || row.priorCount === null || row.priorMean === null || row.priorStddev === null ||
		row.priorMeasured === null || row.priorRecorded === null || row.priorFirst === null || row.priorLast === null ||
		row.distance === null || row.threshold === null) throw new Error('An assessed token reading has no baseline.');
	return {
		warning: row.warning,
		line: {
			label,
			swatch: row.warning ? 'var(--band-medium)' : null,
			value: `${row.warning ? 'Investigate; not proof of failure.' : 'Not flagged.'} ` +
				`Distance from prior mean ${tokens(row.distance)} ${row.warning ? '>' : '<='} ${formatNumber(rules.multiplier)} sample standard deviations (${tokens(row.threshold)}). ` +
				`Baseline: ${formatNumber(row.priorCount)} earlier matching runs, ${row.priorFirst} through ${row.priorLast} UTC; ` +
				`${formatNumber(row.priorMeasured)} measured of ${formatNumber(row.priorRecorded)} recorded articles; ` +
				`mean ${tokens(row.priorMean)}, sample deviation ${tokens(row.priorStddev)}.`
		}
	};
}
