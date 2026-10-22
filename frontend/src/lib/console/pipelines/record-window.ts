/** Which recorded start and endpoint belong to this Pipelines window? */
import type { RouteReach } from '../queries/window';
import type { RecordWindow } from '../waiting';

export function pipelinesRecord(reach: RouteReach | null, asked: number): RecordWindow | null {
	if (reach?.through === null || reach?.through === undefined) return null;
	const first = Object.values(reach.ledgers)
		.flatMap((ledger) => ledger?.state === 'ok' && ledger.first <= reach.through! ? [ledger.first] : [])
		.sort()[0];
	return first === undefined ? null : { first, through: reach.through, asked };
}

export function retryReach(previous: RouteReach | null, refreshed: RouteReach): RouteReach {
	// Successful answers belong to the original endpoint until the preset changes.
	return { ...refreshed, through: previous?.through ?? refreshed.through };
}

export function publishedShareFor<T extends { through: string; days: number }>(
	spans: readonly T[], anchor: string, days: number
): T | undefined {
	return spans.find((span) => span.days === days && span.through === anchor);
}
