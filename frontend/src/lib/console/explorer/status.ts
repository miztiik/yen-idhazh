import type { FetchCost } from '$lib/data/ledger';
import { daysBetween } from '$lib/data/slice';
import { plural as countNoun, shortDate } from '$lib/format';
import { explorerMissingSentence } from '$lib/console/waiting';
import { formatNumber, type NumberFormatConfig } from '../../number-format';

export type ExplorerStatusState =
	| 'idle'
	| 'link'
	| 'notice'
	| 'costing'
	| 'running-fetch'
	| 'running-query'
	| 'answered'
	| 'quiet'
	| 'refused'
	| 'missing'
	| 'unreachable-engine'
	| 'unreachable-files';

export type ExplorerStatusInput = {
	state: ExplorerStatusState;
	files?: number;
	bytes?: number;
	ledgers?: number;
	readFrom?: string | null;
	readTo?: string | null;
	firstRun?: boolean;
	ms?: number | null;
	read?: FetchCost | null;
	ledger?: string;
	through?: string;
	linkNotices?: readonly string[];
	notice?: string | null;
};

export function plural(count: number, noun: string): string {
	return countNoun(count, noun, `${noun}s`);
}

function formattedPlural(count: number, noun: string, numberFormat: NumberFormatConfig): string {
	return `${formatNumber(count, numberFormat, { exact: true })} ${count === 1 ? noun : `${noun}s`}`;
}

export function size(bytes: number, numberFormat: NumberFormatConfig): string {
	if (bytes > 0 && bytes < 102_400) return `${formatNumber(Math.max(1, Math.round(bytes / 1024)), numberFormat, { exact: true })} KB`;
	return `${formatNumber(bytes / 1024 / 1024, numberFormat, { si: false })} MB`;
}

export function elapsed(ms: number | null | undefined, numberFormat: NumberFormatConfig): string {
	if (ms === null || ms === undefined) return '0 ms';
	return ms < 1000
		? `${formatNumber(ms, numberFormat, { exact: true })} ms`
		: `${formatNumber(ms / 1000, numberFormat, { si: false })} s`;
}

export function statusSentence(input: ExplorerStatusInput, numberFormat: NumberFormatConfig): string {
	switch (input.state) {
		case 'notice':
			return input.notice ?? '';
		case 'link':
			return input.linkNotices?.join(' ') ?? '';
		case 'costing':
			return 'Checking SQL tables and query limits.';
		case 'running-fetch':
			return `Fetching ${formattedPlural(input.files ?? 0, 'file', numberFormat)}, ${size(input.bytes ?? 0, numberFormat)}.`;
		case 'running-query':
			return 'Running the question.';
		case 'answered':
			return (input.read?.files ?? 0) === 0 ? `Answered in ${elapsed(input.ms, numberFormat)}.` : `Answered in ${elapsed(input.ms, numberFormat)}. Read ${formattedPlural(input.read?.files ?? 0, 'file', numberFormat)}, ${size(input.read?.bytes ?? 0, numberFormat)}.`;
		case 'quiet':
			return (input.read?.files ?? 0) === 0 ? `Ran in ${elapsed(input.ms, numberFormat)} and matched no rows.` : `Ran in ${elapsed(input.ms, numberFormat)} and matched no rows. Read ${formattedPlural(input.read?.files ?? 0, 'file', numberFormat)}, ${size(input.read?.bytes ?? 0, numberFormat)}.`;
		case 'refused':
			return 'Did not run. The reason is where the answer would be.';
		case 'missing':
			return `Did not run. ${explorerMissingSentence(input.ledger ?? 'This ledger')}`;
		case 'unreachable-engine':
			return 'Did not run. The query engine did not start.';
		case 'unreachable-files':
			return 'Did not run. The ledger files could not be fetched.';
		case 'idle': {
			const from = input.readFrom;
			const to = input.readTo;
			const days = from && to ? daysBetween(from, to).length : 0;
			const dates = days === 1 && to ? `: ${shortDate(to)}` : days > 1 && from && to ? `, from ${shortDate(from)} through ${shortDate(to)}` : '';
			const prefix = `Run will read ${formattedPlural(input.files ?? 0, 'file', numberFormat)}, ${size(input.bytes ?? 0, numberFormat)} from ${formattedPlural(input.ledgers ?? 0, 'ledger', numberFormat)} over ${formattedPlural(days, 'UTC day', numberFormat)}${dates}.`;
			const engine = input.firstRun ? ' It also starts the query engine.' : '';
			const empty = input.ledger !== undefined && input.through !== undefined ? ` Nothing in ${input.ledger} after ${shortDate(input.through)}.` : '';
			return `${prefix}${engine}${empty}`;
		}
	}
}
