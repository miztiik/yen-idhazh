/** Which answer should the route say once, while retaining each missing count? */
import type { LedgerReach, SliceResult } from '../data/ledger';

export type RouteState = 'loading' | 'ok' | 'quiet' | 'missing' | 'unreachable';

export function tallyAsks(answers: readonly (SliceResult | LedgerReach | 'pending')[]): {
	readonly state: RouteState; readonly missing: number; readonly unreachable: number
} {
	const missing = answers.filter((answer) => answer !== 'pending' && answer.state === 'missing').length;
	const unreachable = answers.filter((answer) => answer !== 'pending' && answer.state === 'unreachable').length;
	const state = answers.includes('pending') ? 'loading'
		: unreachable > 0 ? 'unreachable'
			: missing > 0 ? 'missing'
				: answers.every((answer) => answer !== 'pending' && answer.state === 'quiet') ? 'quiet' : 'ok';
	return { state, missing, unreachable };
}
