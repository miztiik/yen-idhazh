/** Keep one fixed-span token assessment from the staged browser data door. */
import { readSession } from '../../data/read-session';
import { isDay, type Row, type SliceResult } from '../../data/slice-shapes';
import type { TokenDeviationOptions } from '../../data/token-deviation-query';
import type { ReadWriteMetric } from '../route-console';
import type { Range } from './window';

export interface TokenAssessment {
	date: string;
	runId: string;
	metric: ReadWriteMetric;
	trace: 'read' | 'written';
	value: number | null;
	measured: number;
	recorded: number;
	priorCount: number | null;
	priorMean: number | null;
	priorStddev: number | null;
	priorMeasured: number | null;
	priorRecorded: number | null;
	priorFirst: string | null;
	priorLast: string | null;
	distance: number | null;
	threshold: number | null;
	warning: boolean | null;
	reason: string | null;
}

export interface TokenHistory {
	state: SliceResult['state'];
	readings: readonly TokenAssessment[];
	incomplete: boolean;
}

function assessment(row: Row): TokenAssessment {
	const numeric = (name: string): number | null => {
		const value = row[name];
		if (value === null || (typeof value === 'number' && Number.isFinite(value))) return value;
		throw new Error(`Token assessment returned an invalid ${name}.`);
	};
	const text = (name: string): string | null => {
		const value = row[name];
		if (value === null || typeof value === 'string') return value;
		throw new Error(`Token assessment returned an invalid ${name}.`);
	};
	if (!isDay(row.date) || typeof row.run_id !== 'string' ||
		(row.metric !== 'total' && row.metric !== 'median') || (row.trace !== 'read' && row.trace !== 'written') ||
		(row.warning !== null && typeof row.warning !== 'boolean') ||
		(row.reason !== null && typeof row.reason !== 'string')) throw new Error('Token assessment returned an invalid identity or verdict.');
	const measured = numeric('measured'), recorded = numeric('recorded');
	if (measured === null || recorded === null) throw new Error('Token assessment returned no article coverage.');
	return {
		date: row.date, runId: row.run_id, metric: row.metric, trace: row.trace,
		value: numeric('value'), measured, recorded,
		priorCount: numeric('prior_count'), priorMean: numeric('prior_mean'), priorStddev: numeric('prior_stddev'),
		priorMeasured: numeric('prior_measured'), priorRecorded: numeric('prior_recorded'),
		priorFirst: text('prior_first'), priorLast: text('prior_last'),
		distance: numeric('distance'), threshold: numeric('threshold'), warning: row.warning, reason: row.reason
	};
}

let held: { key: string; session: symbol; answer: Promise<TokenHistory> } | null = null;

export function tokenDeviationsOnce(range: Range, options: TokenDeviationOptions): Promise<TokenHistory> {
	const key = JSON.stringify([range.from, range.to, options]);
	const session = readSession();
	if (held?.key === key && held.session === session) return held.answer;
	const answer = import('../../data/ledger').then(({ tokenDeviations }) =>
		tokenDeviations(range.from, range.to, options)).then((result): TokenHistory => {
		if (result.state === 'missing' || result.state === 'unreachable') {
			if (held?.answer === answer) held = null;
		}
		return {
			state: result.state, readings: result.state === 'ok' ? result.rows.map(assessment) : [],
			incomplete: 'lostDays' in result && (result.lostDays.length > 0 || Object.keys(result.setAside).length > 0)
		};
	}).catch((error: unknown) => {
		if (held?.answer === answer) held = null;
		throw error;
	});
	held = { key, session, answer };
	return answer;
}
