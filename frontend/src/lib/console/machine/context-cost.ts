/** What the model's reading limit costs, from the item ledger's own rows.
 *
 * The limit bounds ONE call. A pipeline that makes several calls for one
 * article carries the earlier ones forward into the later prompt, so the
 * largest single call is the whole of what that article ever held open - and
 * adding the calls together reports a length the server never saw. Measured
 * 2026-09-21 over the 1,312 committed item rows that carry both figures, the
 * two differ by 1.92x at the middle row, which decides whether the limit looks
 * two fifths used or a fifth used.
 *
 * Nothing here is keyed to how many calls an article makes. A slot is measured
 * when the ledger filled it, the peak is the largest of whatever was filled,
 * and a config edit that changes the count changes no arithmetic on this page.
 */
import { quantile } from '$lib/charts/machine';
import type { DayReadout } from '$lib/charts/frame';
import { grouped } from '$lib/charts/series';

/** The call slots an item row can carry, in the order the stage fills them.
 *
 * A fact about the ledger's column names rather than a tunable: a row either
 * has these cells or it predates them. The peak is a maximum over the filled
 * ones, so a row that fills one and a row that fills both are both measured
 * and neither is counted.
 */
const CALL_SLOTS = ['label', 'summary'] as const;

/** One run's two ends: the ordinary article and the worst one. */
export interface ContextRun {
	runId: string;
	date: string;
	/** Item rows of the run that recorded both a limit and a call's tokens. */
	items: number;
	/** The configured percentile of those items' peaks, in tokens. */
	high: number | null;
	/** The largest of them, in tokens. */
	largest: number | null;
	/** Each as a share of the limit those rows ran under, whole percent. */
	highPct: number | null;
	largestPct: number | null;
}

/** How a decode stopped, and how often. The words are the server's. */
export interface StopReason {
	reason: string;
	calls: number;
}

/** What the limit cost over a span of days, and what it bought.
 *
 * Every figure is a share as well as a count, because a token total says
 * nothing without the limit beside it.
 */
export interface ContextSpan {
	/** Item rows read, and the ones that could be measured against a limit. */
	rowsRead: number;
	items: number;
	/** Every distinct limit the measured rows ran under, ascending. One value
	 * is the ordinary case; two means the setting moved inside the span, and a
	 * single token figure would then be about neither. */
	limits: number[];
	/** The middle item, the configured percentile and the worst, in tokens. */
	median: number | null;
	high: number | null;
	largest: number | null;
	/** The same three as shares of the limit, whole percent. */
	medianPct: number | null;
	highPct: number | null;
	largestPct: number | null;
	/** What the worst article left behind, whole percent. The headline: this
	 * much of the limit has never been used, not once, by anything. */
	unusedPct: number | null;
	/** How many times the limit is the middle article. One decimal, because the
	 * figure is a ratio of two measurements rather than a count. */
	timesMedian: number | null;
	/** The percentile the high mark was taken at, carried so the page prints
	 * the knob's value rather than a number typed into a template. */
	percentile: number;
	/** Every reason the server gave for stopping a decode, commonest first. */
	reasons: StopReason[];
	/** Calls that stopped because they ran out of room. */
	cutOff: number;
	/** Calls that reported any reason at all. */
	calls: number;
}

export interface ContextCost {
	/** Oldest first, so the newest run is the last mark on the chart. */
	runs: ContextRun[];
	/** The same rows read as one figure each. Carried apart from the rows
	 * because a span needs the scalars and the chart needs the rows, and one
	 * document holds one copy of each rather than four copies of both. */
	span: ContextSpan;
}

export interface ContextOptions {
	/** Which percentile the second mark is taken at - `console.context_high_percentile`. */
	percentile: number;
	/** The word the server uses for a decode that ran out of room -
	 * `console.context_cut_off_reason`. */
	cutOffReason: string;
}

function cell(value: string | undefined): number | null {
	if (value === undefined || value === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

/** The largest single call this row put in the limit, and the limit it ran under.
 *
 * Null where the row recorded no limit or filled no call slot. A row that
 * recorded a total across its calls and no split is not measurable here: a
 * total is not a length anything ever held.
 */
function peakOf(row: Record<string, string>): { peak: number; limit: number } | null {
	const limit = cell(row.n_ctx_configured);
	if (limit === null || limit <= 0) return null;
	let peak: number | null = null;
	for (const slot of CALL_SLOTS) {
		const prompt = cell(row[`${slot}_input_tokens`]);
		const wrote = cell(row[`${slot}_output_tokens`]);
		if (prompt === null || wrote === null) continue;
		peak = Math.max(peak ?? 0, prompt + wrote);
	}
	return peak === null ? null : { peak, limit };
}

/** A share of a limit as whole percent. Null where either side is unknown. */
function sharePct(part: number | null, limit: number | null): number | null {
	if (part === null || limit === null || limit <= 0) return null;
	return Math.round((part / limit) * 100);
}

/** The two ends of a set of peaks, at the configured percentile and at the top. */
function endsOf(peaks: number[], percentile: number): { high: number; largest: number } | null {
	if (peaks.length === 0) return null;
	const sorted = [...peaks].sort((left, right) => left - right);
	return {
		// Whole tokens. The interpolation gives a fraction of one, and a fraction
		// of a token is finer than anything this is printed at.
		high: Math.round(quantile(sorted, percentile / 100)),
		largest: sorted[sorted.length - 1]
	};
}

/** What the limit cost, over the rows handed in.
 *
 * One derivation behind both halves of the panel. The span figures and the
 * run marks come out of one call, so the sentence under the chart and the
 * marks on it cannot be two answers to one question.
 */
export function contextCost(
	health: readonly Record<string, string>[],
	options: ContextOptions
): ContextCost {
	const peaks: number[] = [];
	const limits = new Set<number>();
	const byRun = new Map<string, { date: string; peaks: number[]; limits: Set<number> }>();
	const reasons = new Map<string, number>();

	for (const row of health) {
		for (const slot of CALL_SLOTS) {
			const reason = row[`${slot}_finish_reason`] ?? '';
			if (reason !== '') reasons.set(reason, (reasons.get(reason) ?? 0) + 1);
		}
		// A run gets a column as soon as the ledger names it, measured or not. A
		// run that recorded nothing is a run nobody can ask about once it is
		// dropped, and the whole panel is about the worst run in the span - so an
		// absence is drawn as an absence rather than left out of the axis.
		const runId = row.run_id ?? '';
		if (runId === '') continue;
		const bucket = byRun.get(runId) ?? {
			date: row.date ?? '',
			peaks: [] as number[],
			limits: new Set<number>()
		};
		byRun.set(runId, bucket);
		const measured = peakOf(row);
		if (measured === null) continue;
		peaks.push(measured.peak);
		limits.add(measured.limit);
		bucket.peaks.push(measured.peak);
		bucket.limits.add(measured.limit);
	}

	// A share is unitless, so it pools across a limit that moved; a token figure
	// does not. Where the span holds one limit the two agree, and where it holds
	// two the shares are still one answer and the token figures are named as the
	// limits they belong to.
	const oneLimit = limits.size === 1 ? [...limits][0] : null;
	const ends = endsOf(peaks, options.percentile);
	const sorted = [...peaks].sort((left, right) => left - right);
	const median = sorted.length === 0 ? null : Math.round(quantile(sorted, 0.5));
	const largestPct = sharePct(ends?.largest ?? null, oneLimit);

	// Run ids are `<date>-<n>`, so a plain string sort orders a day's runs and
	// orders the days too.
	const runs: ContextRun[] = [...byRun.keys()].sort().map((runId) => {
		const bucket = byRun.get(runId) as { date: string; peaks: number[]; limits: Set<number> };
		const runEnds = endsOf(bucket.peaks, options.percentile);
		const runLimit = bucket.limits.size === 1 ? [...bucket.limits][0] : null;
		return {
			runId,
			date: bucket.date,
			items: bucket.peaks.length,
			high: runEnds?.high ?? null,
			largest: runEnds?.largest ?? null,
			highPct: sharePct(runEnds?.high ?? null, runLimit),
			largestPct: sharePct(runEnds?.largest ?? null, runLimit)
		};
	});

	const calls = [...reasons.values()].reduce((total, count) => total + count, 0);
	return {
		runs,
		span: {
			rowsRead: health.length,
			items: peaks.length,
			limits: [...limits].sort((left, right) => left - right),
			median,
			high: ends?.high ?? null,
			largest: ends?.largest ?? null,
			medianPct: sharePct(median, oneLimit),
			highPct: sharePct(ends?.high ?? null, oneLimit),
			largestPct,
			unusedPct: largestPct === null ? null : 100 - largestPct,
			// One decimal: the ratio answers "how many times over", and a second
			// decimal on a ratio of two measured counts is precision nobody measured.
			timesMedian:
				median === null || median <= 0 || oneLimit === null
					? null
					: Math.round((oneLimit / median) * 10) / 10,
			percentile: options.percentile,
			reasons: [...reasons.entries()]
				.map(([reason, count]) => ({ reason, calls: count }))
				.sort(
					(left, right) => right.calls - left.calls || left.reason.localeCompare(right.reason)
				),
			cutOff: reasons.get(options.cutOffReason) ?? 0,
			calls
		}
	};
}

/** Everything one run's two marks print, for the strip under the chart. */
export function contextColumns(
	runs: readonly ContextRun[],
	limit: number | null,
	percentile: number
): DayReadout[] {
	const of = (value: number | null, pct: number | null): string => {
		if (value === null) return '-';
		const share = pct === null || limit === null ? '' : ` - ${pct}% of ${grouped(limit)}`;
		return `${grouped(value)} tokens${share}`;
	};
	return runs.map((run) => ({
		x: 0,
		date: run.runId,
		rows: [
			{
				label: 'The longest article',
				value: of(run.largest, run.largestPct),
				colour: 'var(--chart-1)'
			},
			{
				label: highLabel(percentile),
				value: of(run.high, run.highPct),
				colour: 'var(--chart-3)'
			},
			{ label: 'Articles measured', value: `${run.items}`, colour: '' }
		]
	}));
}

/** The high mark in words, at whatever percentile the config set.
 *
 * `p99` is a subsystem term (CLAUDE.md section 0b). A reader who has never met
 * one still knows what "all but the longest 1 in 100" means, and the sentence
 * survives the knob moving to 95 or to 90.
 */
export function highLabel(percentile: number): string {
	const rest = Math.round((100 - percentile) * 100) / 100;
	return `All but the longest ${rest} in 100`;
}
