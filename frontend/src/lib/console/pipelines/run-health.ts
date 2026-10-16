/** A private manifest supplies run facts; no item-ledger cuts cross the built page. */
import { health, tried, underFloor, type DayColumn, type RunFacts } from '../run-square';
import { shortDate } from '../../format';

export function runHealthGrid(days: readonly { date: string; records: readonly (RunFacts & { runId: string })[] }[], floorPct: number): DayColumn[] {
	return [...days].reverse().map((day) => ({
		date: day.date, squares: day.records.map((run) => {
			const attempted = tried(run);
			const parts = [attempted === 0 ? 'nothing new to try' : `${run.succeeded} of ${attempted} succeeded`];
			if (underFloor(run, floorPct)) parts.push(`under ${floorPct}%`);
			if (run.failed > 0) parts.push(`${run.failed} failed`);
			if (run.skipped > 0) parts.push(`${run.skipped} skipped`);
			if (run.sourceListStale) parts.push("reused yesterday's list of sources");
			if (run.status === 'partial' && run.failed === 0) parts.push("another run's failed article was still missing");
			if (run.status === 'failed') parts.push('the run failed');
			const outcome = parts.join(', ');
			return { runId: run.runId, n: run.n, health: health(run, floorPct), outcome,
				label: `Run ${run.n} on ${shortDate(day.date)}: ${outcome}` };
		})
	}));
}
