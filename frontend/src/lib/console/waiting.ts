/** What a native console panel, route or written question says while it has no answer. */
import { shortDate } from '$lib/format';
import { grouped } from '$lib/charts/series';
import { formatNumber } from '../number-format';
import type { NumberFormatConfig } from '../number-format';
import { nameSpan } from '$lib/console/span-words';
import type { AskRefusal } from '$lib/data/ledger';
import { isDay } from '$lib/data/slice-shapes';

export type PanelState = 'ready' | 'loading' | 'quiet' | 'missing' | 'unreachable' | 'refused';
export type ChartState = PanelState | 'too-few';

export const STATE_WORDS = {
	quiet: 'Nothing recorded.',
	missing: 'Not published yet.',
	unreachable: 'Did not arrive.'
} as const;

export interface RouteStanding {
	state: 'loading' | 'ok' | 'quiet' | 'missing' | 'unreachable';
	days: number;
	through: string | null;
	missing: number;
	unreachable: number;
	shimmer: boolean;
}

export function routeStanding(reading: RouteStanding): string {
	if (!Number.isInteger(reading.days) || reading.days < 1) throw new Error('A route standing needs a positive day count.');
	if (reading.state === 'loading') return reading.shimmer ? 'Fetching the record.' : '';
	if (reading.state === 'unreachable') {
		return `Part of the record did not arrive, so ${reading.unreachable} ${reading.unreachable === 1 ? 'panel has' : 'panels have'} nothing to draw.`;
	}
	if (reading.state === 'missing') {
		return `${reading.missing} ${reading.missing === 1 ? 'panel reads' : 'panels read'} a record this site has not published yet, so ${reading.missing === 1 ? 'it has' : 'they have'} nothing to draw.`;
	}
	if (reading.state === 'quiet') return `Nothing was recorded in ${nameSpan(reading.days)}.`;
	if (!isDay(reading.through)) throw new Error('A loaded route standing must name the day its panels reach.');
	return `The panels below reach ${shortDate(reading.through)}.`;
}

export interface RecordWindow {
	asked: number;
	first: string | null;
	through: string | null;
}

/** Freshness is anchored on the returned record, never on the current clock. */
export function recordWindowSentence(record: RecordWindow): string {
	if (!Number.isSafeInteger(record.asked) || record.asked < 1) throw new Error('A record window needs a positive preset.');
	if (record.first === null || record.through === null) return '';
	if (!isDay(record.first) || !isDay(record.through)) throw new Error('A record window needs ordered UTC days.');
	const start = Date.parse(`${record.first}T00:00:00Z`);
	const end = Date.parse(`${record.through}T00:00:00Z`);
	if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) throw new Error('A record window needs ordered UTC days.');
	const dayMs = 86_400_000;
	const available = Math.floor((end - start) / dayMs) + 1;
	const days = Math.min(record.asked, available);
	const shown = `Showing ${days} ${days === 1 ? 'day' : 'days'}, to ${shortDate(record.through)}.`;
	if (available >= record.asked) return shown;
	const fills = new Date(start + (record.asked - 1) * dayMs).toISOString().slice(0, 10);
	return `${shown} The record starts on ${shortDate(record.first)}; the ${record.asked}-day window fills on ${shortDate(fills)}.`;
}

export function quietSentence(days: number, widen: number | null): string {
	const read = `Nothing was recorded in ${nameSpan(days)}.`;
	return widen === null
		? `${read} No wider window reaches a day that has anything.`
		: `${read} The ${widen}-day window reaches back to months that do.`;
}

export function tooFewSentence(
	have: number,
	floor: number,
	noun: string,
	numberFormat: NumberFormatConfig,
	place = 'in this window'
): string {
	const are = have === 1 ? 'is' : 'are';
	return `Only ${grouped(have, numberFormat)} of the ${grouped(floor, numberFormat)} ${noun} this chart needs ${are} ${place}, so it is not drawn.`;
}

function mb(bytes: number, numberFormat: NumberFormatConfig): string {
	return `${formatNumber(bytes / 1024 / 1024, numberFormat, { si: false })} MB`;
}

function fileCount(count: number, numberFormat: NumberFormatConfig): string {
	return `${formatNumber(count, numberFormat, { exact: true })} ${count === 1 ? 'file' : 'files'}`;
}

export function refusedSentence(because: AskRefusal, numberFormat: NumberFormatConfig): string {
	if (because.kind === 'statements') return `Run one statement at a time. This has ${formatNumber(because.count, numberFormat, { exact: true })}.`;
	if (because.kind === 'not-read-only') return `Only questions run here: start with SELECT, WITH, DESCRIBE, SUMMARIZE or EXPLAIN. This starts with ${because.word}.`;
	if (because.kind === 'too-long') return `This question is ${formatNumber(because.chars, numberFormat, { exact: true })} characters long; the most this page runs is ${formatNumber(because.max, numberFormat, { exact: true })}.`;
	if (because.kind === 'over-ceiling') return `These days would fetch ${mb(because.bytes, numberFormat)} from ${fileCount(because.files, numberFormat)}, and one question may fetch ${mb(because.max, numberFormat)}. Pick fewer days or fewer ledgers.`;
	if (because.kind === 'too-many-files') return `These days need ${fileCount(because.files, numberFormat)}; one question permits ${fileCount(because.max, numberFormat)}. Pick fewer days or fewer ledgers.`;
	if (because.kind === 'ledger-not-enabled') return `${because.ledger} is not enabled for the Data explorer. Refresh the ledger list and choose an enabled ledger.`;
	return 'The engine could not run this:';
}

export function explorerIdleSentence(): string {
	return 'Press Run and the answer appears here, as a table.';
}

export function explorerQuietSentence(): string {
	return 'Your question ran and matched no rows.';
}

export function explorerMissingSentence(ledger: string): string {
	return `${ledger} has no available compact record yet. Newest data waits for packing.`;
}

export function explorerUnreachableSentence(ledger: string | null, day: string | null, fault: string | null): string {
	if (fault === 'engine') {
		return 'The query engine did not start in this browser. A current version of Chrome, Edge, Firefox or Safari runs it.';
	}
	if (fault === null) return `${ledger ?? 'The ledger'} for ${day ?? 'that day'} did not arrive, so the question did not run.`;
	return `The compact record for ${ledger ?? 'the ledger'} at ${day ?? 'that day'} could not be read (${fault}). Press Refresh, then Run, to try again.`;
}

export function explorerChartIdleSentence(): string {
	return 'If the answer holds a number, it is drawn here.';
}
