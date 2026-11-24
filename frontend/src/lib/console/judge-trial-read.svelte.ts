/** Keep a trial projection inside its named packed dates and current read session. */
import { daysBetween, windowOfDays, type TimeWindow } from '../charts/viewport';
import type { LedgerReach, SliceResult } from '../data/ledger';
import { readSession } from '../data/read-session';
import { whenNear } from '../reveal';
import { retryAsks, type PanelQuery, type Range } from './queries/window';

type Request = Range | LedgerReach | null;

export function revealJudgeTrial(node: HTMLElement, ready: () => void) {
	return { destroy: whenNear(node, ready) };
}

export function judgeTrialRange(window: TimeWindow, cap: number, ...reaches: readonly LedgerReach[]): Request {
	let { start: from, end: to } = window;
	for (const reach of reaches) {
		if (reach.state !== 'ok') return reach;
		if (reach.first > from) from = reach.first;
		if (reach.through < to) to = reach.through;
	}
	if (from > to) return { state: 'quiet' };
	const capped = windowOfDays(to, cap, 'right').start;
	if (capped > from) from = capped;
	return { from, to, days: daysBetween(from, to), asked: daysBetween(window.start, window.end) };
}

export function inTrialRange(request: Request, date: string): boolean {
	return request !== null && 'from' in request && date >= request.from && date <= request.to;
}

export function useJudgeTrialAnswer(query: PanelQuery, select: () => Request, ask: (range: Range) => Promise<SliceResult>) {
	let count = $state(0);
	let read = $state.raw<{ key: string; answer: SliceResult } | null>(null);
	const request = $derived(select());
	const key = $derived(request !== null && 'from' in request ? `${request.from}/${request.to}` : null);
	$effect(() => {
		const range = request;
		const current = key;
		void count;
		if (range === null || !('from' in range) || current === null) return;
		let active = true;
		const session = readSession();
		read = null;
		void ask(range).then((answer) => {
			if (active && session === readSession()) read = { key: current, answer };
		}, (error: unknown) => {
			if (!active || session !== readSession()) return;
			console.warn('[judgement] The trial projection could not be read.', query.name, error);
			read = { key: current, answer: { state: 'unreachable', rows: [], at: range.from, fault: null } };
		});
		return () => { active = false; };
	});

	return {
		get answer() {
			if (request === null) return 'pending' as const;
			if (!('from' in request)) return request;
			return read?.key === key ? read?.answer ?? 'pending' as const : 'pending' as const;
		},
		retry() {
			retryAsks([query]);
			count++;
		}
	};
}
