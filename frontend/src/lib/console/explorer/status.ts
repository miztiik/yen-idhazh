import { megabytes } from '$lib/assist/session';
import type { FetchCost } from '$lib/data/ledger';
import { shortDate } from '$lib/format';

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
	days?: number;
	firstRun?: boolean;
	ms?: number | null;
	read?: FetchCost | null;
	ledger?: string;
	through?: string;
	linkNotices?: readonly string[];
	notice?: string | null;
};

export function plural(count: number, noun: string): string {
	return `${count} ${noun}${count === 1 ? '' : 's'}`;
}

export function size(bytes: number): string {
	if (bytes > 0 && bytes < 102_400) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
	return `${megabytes(bytes)} MB`;
}

export function elapsed(ms: number | null | undefined): string {
	if (ms === null || ms === undefined) return '0 ms';
	return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export function statusSentence(input: ExplorerStatusInput): string {
	switch (input.state) {
		case 'notice':
			return input.notice ?? '';
		case 'link':
			return input.linkNotices?.join(' ') ?? '';
		case 'costing':
			return 'Choosing a ledger fetches one day of it to list its columns.';
		case 'running-fetch':
			return `Fetching ${plural(input.files ?? 0, 'file')}, ${size(input.bytes ?? 0)}.`;
		case 'running-query':
			return 'Running the question.';
		case 'answered':
			return `Answered in ${elapsed(input.ms)}. Read ${plural(input.read?.files ?? 0, 'file')}, ${size(input.read?.bytes ?? 0)}.`;
		case 'quiet':
			return `Ran in ${elapsed(input.ms)} and matched no rows. Read ${plural(input.read?.files ?? 0, 'file')}, ${size(input.read?.bytes ?? 0)}.`;
		case 'refused':
			return 'Did not run. The reason is where the answer would be.';
		case 'missing':
			return `Did not run. ${input.ledger ?? 'This ledger'} is not on this site yet.`;
		case 'unreachable-engine':
			return 'Did not run. The query engine did not start.';
		case 'unreachable-files':
			return 'Did not run. The ledger files could not be fetched.';
		case 'idle': {
			const prefix = `Run reads ${plural(input.files ?? 0, 'file')}, ${size(input.bytes ?? 0)} from ${plural(input.ledgers ?? 0, 'ledger')} over ${plural(input.days ?? 0, 'UTC day')}.`;
			const engine = input.firstRun ? ' It also starts the query engine.' : '';
			const empty = input.ledger !== undefined && input.through !== undefined ? ` Nothing in ${input.ledger} after ${shortDate(input.through)}.` : '';
			return `${prefix}${engine}${empty}`;
		}
	}
}
