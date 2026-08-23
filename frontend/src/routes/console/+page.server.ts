import { collectConfig, runConfig } from '$lib/server/config';
import {
	evalRows,
	feedResults,
	itemHealthRows,
	loadManifests,
	type FeedResult,
	type RunRecord
} from '$lib/server/payload';

export const prerender = true;

interface TimingStats {
	date: string;
	items: number;
	fetchMs: number;
	extractMs: number;
	summarizeMs: number;
	scoreMs: number;
}

interface ScoreStats {
	date: string;
	items: number;
	scoreMs: number;
	meanHhem: number;
	bands: { high: number; medium: number; low: number };
}

/** Green: it worked. Amber: look at it. Red: it did not work. */
export type Health = 'green' | 'amber' | 'red';

export interface RunSquare {
	runId: string;
	n: number;
	health: Health;
	label: string;
}

export interface DayColumn {
	date: string;
	squares: RunSquare[];
}

export interface FeedTrouble {
	feedId: string;
	attempts: number;
	failures: number;
	lastOutcome: string;
	lastDetail: string;
	lastDate: string;
	nearQuarantine: boolean;
}

function median(values: number[]): number {
	if (values.length === 0) return 0;
	const sorted = [...values].sort((a, b) => a - b);
	const middle = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function measured(row: Record<string, string>, name: string): number | null {
	const raw = row[name];
	if (raw === undefined || raw === '') return null;
	const value = Number(raw);
	return Number.isFinite(value) ? value : null;
}

function byDate(rows: Record<string, string>[]): Map<string, Record<string, string>[]> {
	const grouped = new Map<string, Record<string, string>[]>();
	for (const row of rows) {
		const date = row.date ?? '';
		if (!date) continue;
		grouped.set(date, [...(grouped.get(date) ?? []), row]);
	}
	return grouped;
}

/** One square's colour, from what the run wrote down about itself.
 *
 * Skipped items are not failures. An article already published, or one a feed
 * repeated, is skipped by design - counting it against the run would paint a
 * healthy day amber for doing its job. So the rate is over what was attempted.
 *
 * The floor is the same knob CI uses to decide whether a run opens an issue, so
 * a red square and an open issue can never disagree.
 */
function health(run: RunRecord, floorPct: number): Health {
	if (run.status === 'failed') return 'red';
	const attempted = run.succeeded + run.failed;
	// Nothing was attempted. Not a failure, but never what you expect to see.
	if (attempted === 0) return 'amber';
	if ((run.succeeded / attempted) * 100 < floorPct) return 'red';
	if (run.failed > 0 || run.status !== 'completed' || run.sourceListStale) return 'amber';
	return 'green';
}

function describe(date: string, run: RunRecord): string {
	const parts = [`${date} run ${run.n}`, `${run.succeeded} of ${run.planned} succeeded`];
	if (run.failed > 0) parts.push(`${run.failed} failed`);
	if (run.skipped > 0) parts.push(`${run.skipped} skipped`);
	if (run.sourceListStale) parts.push('source list was stale');
	if (run.status !== 'completed') parts.push(run.status);
	return parts.join(', ');
}

/** The same rule as `FeedHealthRow.failing` in the contract.
 *
 * A feed that answered with nothing counts as failing: an empty answer and a
 * refused one cost the digest the same articles. A robots refusal does not -
 * that source said no, and honouring it is the pipeline working correctly.
 *
 * See `backend/idhazh/contracts/feed_health.py`, which is the source of truth.
 */
const FAILING_OUTCOMES = new Set(['blocked', 'permanent', 'transient']);

function failing(row: FeedResult): boolean {
	if (row.outcome === 'ok') return row.items === 0;
	return FAILING_OUTCOMES.has(row.outcome);
}

/** Every feed that failed at least once, worst first.
 *
 * A feed with a clean record is not listed. The operator came here to find what
 * is broken, and a list that names all seventy sources hides the four that are.
 */
function trouble(rows: FeedResult[], quarantineAfter: number): FeedTrouble[] {
	const byFeed = new Map<string, FeedResult[]>();
	for (const row of rows) {
		// A skipped feed was never asked, so it can neither pass nor fail.
		if (row.outcome === 'skipped') continue;
		byFeed.set(row.feedId, [...(byFeed.get(row.feedId) ?? []), row]);
	}

	const found: FeedTrouble[] = [];
	for (const [feedId, group] of byFeed) {
		const failures = group.filter(failing);
		if (failures.length === 0) continue;
		const newest = [...group].sort((a, b) => a.date.localeCompare(b.date)).at(-1) as FeedResult;
		found.push({
			feedId,
			attempts: group.length,
			failures: failures.length,
			lastOutcome: newest.outcome,
			lastDetail: newest.detail,
			lastDate: newest.date,
			nearQuarantine: failures.length >= quarantineAfter
		});
	}
	return found.sort((a, b) => b.failures - a.failures || a.feedId.localeCompare(b.feedId));
}

/** The console reads the committed ledger and nothing else.
 *
 * Every number here was measured when the run happened and written down. None
 * of it is derived at read time, which is what lets the page be a static file
 * and what stops today's code quietly restating yesterday's numbers.
 */
export function load() {
	const { rows } = evalRows();
	const itemRows = itemHealthRows().rows;
	const floorPct = runConfig().success_floor_pct;
	const quarantineAfter = collectConfig().quarantine_after_failures;

	const scoresByDate = byDate(rows);
	const itemHealthByDate = byDate(itemRows);

	const timingDays: TimingStats[] = [...itemHealthByDate.entries()]
		.map(([date, group]) => {
			const nums = (name: string) =>
				group.map((row) => measured(row, name)).filter((value) => value !== null);
			const scoreGroup = scoresByDate.get(date) ?? [];
			const scoreMs = scoreGroup.map((row) => Number(row.score_ms ?? 0) || 0);
			return {
				date,
				items: group.length,
				fetchMs: median(nums('fetch_ms')),
				extractMs: median(nums('extract_ms')),
				summarizeMs: median(nums('summarize_ms')),
				scoreMs: median(scoreMs)
			};
		})
		.filter((day) => day.fetchMs > 0 || day.extractMs > 0 || day.summarizeMs > 0 || day.scoreMs > 0)
		.sort((a, b) => b.date.localeCompare(a.date));

	const scoreDays: ScoreStats[] = [...scoresByDate.entries()]
		.map(([date, group]) => {
			const num = (name: string) => group.map((r) => Number(r[name] ?? 0) || 0);
			const bands = { high: 0, medium: 0, low: 0 };
			for (const row of group) {
				const band = row.band as keyof typeof bands;
				if (band in bands) bands[band] += 1;
			}
			return {
				date,
				items: group.length,
				scoreMs: median(num('score_ms')),
				meanHhem: num('hhem').reduce((a, b) => a + b, 0) / Math.max(group.length, 1),
				bands
			};
		})
		.sort((a, b) => b.date.localeCompare(a.date));

	const manifests = loadManifests();
	const grid: DayColumn[] = manifests.map((day) => ({
		date: day.date,
		squares: day.records.map((run) => ({
			runId: run.runId,
			n: run.n,
			health: health(run, floorPct),
			label: describe(day.date, run)
		}))
	}));

	const results = feedResults();
	return {
		timingDays,
		scoreDays,
		manifests,
		totalRows: rows.length,
		itemHealthRows: itemRows.length,
		grid,
		floorPct,
		quarantineAfter,
		feeds: trouble(results, quarantineAfter),
		feedsChecked: new Set(results.map((row) => row.feedId)).size,
		feedRuns: new Set(results.map((row) => row.runId)).size
	};
}
