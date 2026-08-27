import type { RateSpread, StageTiming, StageTimingDay, ThroughputDay } from '$lib/charts/series';
import { modelByDate, modelWork } from '$lib/server/model-work';
import { collectConfig, consoleConfig, runConfig, summarizeConfig, uiConfig } from '$lib/server/config';
import {
	evalRows,
	feedResults,
	itemHealthRows,
	loadManifests,
	publishedCharts,
	telemetryMonths,
	telemetryRows,
	TELEMETRY_ROOT,
	type FeedResult,
	type RunRecord,
	type RunSummary
} from '$lib/server/payload';

export const prerender = true;

type TimingStats = StageTimingDay;

interface CompressionPoint {
	date: string;
	item_id: string;
	source_words: number;
	summary_words: number;
	truncation_flagged: boolean;
}

/** Green: it worked. Amber: look at it. Red: it did not work. */
export type Health = 'green' | 'amber' | 'red';

// The page prints these; the derivation is server-only, so the shape crosses
// as a type and the ledger reader never reaches a browser bundle.
export type { ModelDay, ModelRow } from '$lib/server/model-work';

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

/** What one day's chart arm cost and what it produced.
 *
 * Four counts and one division. Two gaps carry the whole story: reached against
 * asked is the check that runs before the model, drafted against published is
 * the pair of checks that run after it.
 *
 * `routerMinutes` and `minutesPerChart` are null rather than zero wherever the
 * number does not exist - a day whose route job never ran measured no time, and
 * a day with no chart has no per-chart cost. Zero would read as free.
 */
export interface ChartDay {
	date: string;
	reached: number;
	asked: number;
	drafted: number;
	published: number;
	routerMinutes: number | null;
	minutesPerChart: number | null;
}

/** One row per published day, from the day's own manifest and payload.
 *
 * Nothing here is stored as a rate. The manifest carries counts and one
 * millisecond total; the division happens at read time, so a ratio can never
 * disagree with the counts printed beside it.
 */
function chartDays(days: RunSummary[], charts: Map<string, number>): ChartDay[] {
	return days.map((day) => {
		const sum = (of: (run: RunRecord) => number) =>
			day.records.reduce((total, run) => total + of(run), 0);
		const timed = day.records.map((run) => run.routeMs).filter((ms): ms is number => ms !== null);
		const routerMinutes = timed.length === 0 ? null : timed.reduce((a, b) => a + b, 0) / 60_000;
		const published = charts.get(day.date) ?? 0;
		return {
			date: day.date,
			reached: sum((run) => run.routed + run.prefiltered),
			asked: sum((run) => run.routed),
			drafted: sum((run) => run.chartsDrafted),
			published,
			routerMinutes,
			minutesPerChart: routerMinutes === null || published === 0 ? null : routerMinutes / published
		};
	});
}

/** Null when nothing was timed. Zero is a measurement - a cheap stage really
 * does finish inside a millisecond clock's own resolution - so it can never
 * stand in for the absence of one.
 *
 * It takes a `Sample` rather than an array so that a hand-built list of
 * numbers, and any zero invented to fill an empty cell, has nowhere to land. */
function median(of: Sample): number | null {
	if (of.values.length === 0) return null;
	const sorted = [...of.values].sort((a, b) => a - b);
	const middle = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function measured(row: Record<string, string>, name: string): number | null {
	const raw = row[name];
	if (raw === undefined || raw === '') return null;
	const value = Number(raw);
	return Number.isFinite(value) ? value : null;
}

/** One column of one group of rows, and how many rows could have filled it.
 *
 * `timed` against `total` is the fact a bare array cannot carry: eight items
 * timed out of ten and ten out of ten arrive as the same list of numbers.
 */
interface Sample {
	values: number[];
	timed: number;
	total: number;
}

function sample(rows: Record<string, string>[], name: string): Sample {
	const values = rows
		.map((row) => measured(row, name))
		.filter((value): value is number => value !== null);
	return { values, timed: values.length, total: rows.length };
}

/** A sample reduced to what the chart draws: one median, and the two counts
 * that say whether the day was timed in full, in part, or not at all. */
function timing(of: Sample): StageTiming {
	return { ms: median(of), timed: of.timed, total: of.total };
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

function quantile(sorted: number[], fraction: number): number {
	if (sorted.length === 1) return sorted[0];
	const position = (sorted.length - 1) * fraction;
	const low = Math.floor(position);
	const high = Math.ceil(position);
	return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

function spread(values: number[]): RateSpread | null {
	if (values.length === 0) return null;
	const sorted = [...values].sort((a, b) => a - b);
	return {
		min: sorted[0],
		p25: quantile(sorted, 0.25),
		median: quantile(sorted, 0.5),
		p75: quantile(sorted, 0.75),
		max: sorted[sorted.length - 1]
	};
}

/** One item's two rates, or null where the runtime reported no timing.
 *
 * Cached prompt tokens are taken out of the read count. Leaving them in reports
 * a rate the machine never ran at: it did not read them.
 */
function itemRates(row: Record<string, string>): { read: number | null; write: number | null } {
	const prefillMs = measured(row, 'prefill_ms');
	const decodeMs = measured(row, 'decode_ms');
	const prompt = measured(row, 'input_tokens');
	const written = measured(row, 'output_tokens');
	const evaluated = prompt === null ? null : prompt - (measured(row, 'cached_tokens') ?? 0);
	return {
		read:
			prefillMs !== null && prefillMs > 0 && evaluated !== null && evaluated > 0
				? evaluated / (prefillMs / 1000)
				: null,
		write:
			decodeMs !== null && decodeMs > 0 && written !== null && written > 0
				? written / (decodeMs / 1000)
				: null
	};
}

function publicTelemetry(row: Record<string, string>) {
	return {
		date: row.date ?? '',
		run_id: row.run_id ?? '',
		item_id: row.item_id ?? '',
		vertical: row.vertical ?? '',
		source_id: row.source_id ?? '',
		stage: row.stage ?? '',
		outcome: row.outcome ?? '',
		code: row.code ?? '',
		source_words: measured(row, 'source_words'),
		summary_words: measured(row, 'summary_words')
	};
}

function compressionPoint(row: Record<string, string>): CompressionPoint | null {
	const sourceWords = Number(row.source_word_count ?? 0) || 0;
	const summaryWords = Number(row.summary_word_count ?? 0) || 0;
	if (sourceWords <= 0 || summaryWords <= 0) return null;
	return {
		date: row.date ?? '',
		item_id: row.item_id ?? '',
		source_words: sourceWords,
		summary_words: summaryWords,
		truncation_flagged: row.truncation_flagged === 'True' || row.truncation_flagged === 'true'
	};
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
	const console = consoleConfig();
	const summarize = summarizeConfig();

	const scoresByDate = byDate(rows);
	const itemHealthByDate = byDate(itemRows);
	const modelOnDate = modelByDate(rows);

	// A day is kept when something on it was timed. Judging it by its medians
	// would drop a day whose only measurement was a zero, which is the same
	// mistake one level up.
	const timingDays: TimingStats[] = [...itemHealthByDate.entries()]
		.map(([date, group]) => ({
			date,
			items: group.length,
			fetch: timing(sample(group, 'fetch_ms')),
			extract: timing(sample(group, 'extract_ms')),
			summarize: timing(sample(group, 'summarize_ms')),
			score: timing(sample(scoresByDate.get(date) ?? [], 'score_ms'))
		}))
		.filter((day) =>
			[day.fetch, day.extract, day.summarize, day.score].some((stage) => stage.timed > 0)
		)
		.sort((a, b) => b.date.localeCompare(a.date));

	// Two different statistics, both kept on purpose. The candle is the spread of
	// per-item rates, because the worker sorts short articles first and the two
	// ends of a day drift apart. The day figure is the sum of the parts, because
	// a rate is a ratio and averaging per-item rates weighs a release note like a
	// feature. Oldest first: the chart reads left to right.
	const throughputDays: ThroughputDay[] = [...itemHealthByDate.entries()]
		.map(([date, group]) => {
			const reads: number[] = [];
			const writes: number[] = [];
			const perRun = new Map<string, { read: number[]; write: number[] }>();
			let prefillMs = 0;
			let decodeMs = 0;
			let cached = 0;
			let prompt = 0;
			let written = 0;
			for (const row of group) {
				const rate = itemRates(row);
				if (rate.read === null && rate.write === null) continue;
				const bucket = perRun.get(row.run_id ?? '') ?? { read: [], write: [] };
				if (rate.read !== null) {
					reads.push(rate.read);
					bucket.read.push(rate.read);
				}
				if (rate.write !== null) {
					writes.push(rate.write);
					bucket.write.push(rate.write);
				}
				perRun.set(row.run_id ?? '', bucket);
				prefillMs += measured(row, 'prefill_ms') ?? 0;
				decodeMs += measured(row, 'decode_ms') ?? 0;
				cached += measured(row, 'cached_tokens') ?? 0;
				prompt += measured(row, 'input_tokens') ?? 0;
				written += measured(row, 'output_tokens') ?? 0;
			}
			const read = spread(reads);
			const write = spread(writes);
			if (read === null || write === null) return null;
			const evaluated = Math.max(prompt - cached, 0);
			return {
				date,
				items: Math.max(reads.length, writes.length),
				read,
				write,
				readTps: prefillMs > 0 ? evaluated / (prefillMs / 1000) : 0,
				writeTps: decodeMs > 0 ? written / (decodeMs / 1000) : 0,
				cacheHitPct: prompt > 0 ? (cached / prompt) * 100 : 0,
				model: modelOnDate.get(date) ?? null,
				runs: [...perRun.entries()]
					.map(([runId, bucket]) => ({
						runId,
						items: Math.max(bucket.read.length, bucket.write.length),
						read: spread(bucket.read)?.median ?? 0,
						write: spread(bucket.write)?.median ?? 0
					}))
					.sort((a, b) => a.runId.localeCompare(b.runId))
			};
		})
		.filter((day): day is ThroughputDay => day !== null)
		.sort((a, b) => a.date.localeCompare(b.date));

	const manifests = loadManifests();
	// The strip is a time axis, so it reads oldest to newest. The Runs table under
	// it still reads newest first, which is why this copies rather than reverses:
	// an in-place reverse would silently turn that table upside down too.
	const grid: DayColumn[] = [...manifests].reverse().map((day) => ({
		date: day.date,
		squares: day.records.map((run) => ({
			runId: run.runId,
			n: run.n,
			health: health(run, floorPct),
			label: describe(day.date, run)
		}))
	}));

	const results = feedResults();
	// Seeded to the window the viewport opens on, not to every committed month:
	// this list is inlined into the prerendered HTML, so an unbounded seed makes
	// the page grow for as long as the pipeline runs.
	const publicRows = telemetryRows(TELEMETRY_ROOT, console.default_window_days).rows.map(
		publicTelemetry
	);
	const compression = rows
		.map(compressionPoint)
		.filter((point): point is CompressionPoint => point !== null)
		.sort((a, b) => a.date.localeCompare(b.date));
	return {
		timingDays,
		throughputDays,
		// The explanation lives in docs/, which the site does not publish, so the
		// chart points at the repository rather than restating it in a caption.
		throughputReference: `${uiConfig().repo_url.replace(/\/+$/, '')}/blob/main/docs/architecture/summarize/throughput.md`,
		// Every fixed benchmark figure lives in the write-up and none of them is
		// copied onto this page: two machines and two workloads, so a gap between a
		// bench number and a run reads as a regression nobody measured.
		measurementsReference: `${uiConfig().repo_url.replace(/\/+$/, '')}/blob/main/docs/reference/measurements.md`,
		modelWork: modelWork(rows, itemRows),
		manifests,
		charts: chartDays(manifests, publishedCharts()),
		totalRows: rows.length,
		itemHealthRows: itemRows.length,
		grid,
		floorPct,
		quarantineAfter,
		feeds: trouble(results, quarantineAfter),
		feedsChecked: new Set(results.map((row) => row.feedId)).size,
		feedRuns: new Set(results.map((row) => row.runId)).size,
		telemetryRows: publicRows,
		telemetryMonths: telemetryMonths(),
		console,
		compression,
		summarizeBands: summarize.bands,
		today: new Date().toISOString().slice(0, 10)
	};
}
