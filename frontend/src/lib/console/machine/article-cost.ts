/** What one article costs the machine, taken off the item ledger a row at a time.
 *
 * A run total divided by the item count cannot disagree with the run total, so
 * it checks nothing. Every figure here is measured per article and then read as
 * a range, which is the only shape that can say a change to the prompt, the
 * model or the item count was worth its price before the run that pays it.
 *
 * Three costs, three instruments, and they are not interchangeable. Processor
 * time is the share the kernel says was busy, multiplied by the processors the
 * machine record names and by the clock the item ran for. Model time is the
 * server's own accounting of reading the prompt and writing the reply. Added
 * memory is the rise in the model server's resident memory between one item of
 * a shard and the next, which is a step and not a level.
 *
 * Nothing here is keyed to how many calls an article makes. The model figure is
 * a total over whatever calls the item made, and a config edit that changes the
 * count changes no arithmetic on this page.
 */
import { quantile } from '$lib/charts/machine';
import { percentOf } from '$lib/charts/rank';

/** Milliseconds to seconds, and hundredths to a fraction. Format literals: the
 * ledger writes milliseconds and whole percent, and neither is a setting. */
const MS_PER_SECOND = 1000;
const PER_CENT = 100;

/** Seconds in an hour, for the sentence that says what a runner-hour supplies.
 * A processor-second is only readable against the hour that produces it. */
const SECONDS_PER_HOUR = 3600;

/** One cost read across the articles that recorded it.
 *
 * A range and not a mean. Two articles of one run can differ by an order of
 * magnitude, and a mean of that reports neither end - which is the whole reason
 * this panel exists rather than a single number on a card.
 */
export interface CostFigure {
	/** The cheapest article that recorded this cost. */
	low: number | null;
	/** The middle one. What a further article is likeliest to cost. */
	mid: number | null;
	/** The dearest one. What the worst article cost. */
	high: number | null;
	/** Articles that produced a figure. */
	from: number;
	/** Articles that carried what the item ledger needs for it. Larger than
	 * `from` only where a second instrument was also needed and was missing. */
	outOf: number;
}

/** The three costs of one article, over one span of days. */
export interface ArticleCost {
	/** Item rows the span holds, measured or not. */
	rowsRead: number;
	/** Busy processor time one article used, in processor-seconds. */
	processorSeconds: CostFigure;
	/** Every distinct processor count the measured articles ran on, ascending.
	 * Empty where no machine record named one, which is what makes the
	 * processor figure a dash rather than a guess. */
	processors: number[];
	/** Reading the prompt and writing the reply, in seconds, summed over
	 * whatever calls the item made. */
	modelSeconds: CostFigure;
	/** What the model server's resident memory did from one item to the next,
	 * in bytes. Negative where the item gave memory back. */
	addedBytes: CostFigure;
	/** Shards those steps were taken inside. A step is never taken across two
	 * shards: a fresh shard starts a fresh model server, so the difference
	 * would be a restart rather than an article. */
	shards: number;
}

/** What the join to the machine record needs, and nothing else.
 *
 * Structural rather than the whole fingerprint row, so a fixture can state a
 * machine in four fields and a run whose record names no processor count is a
 * case a test can write.
 */
export interface MachineProcessors {
	date: string;
	run_id: string;
	shard: number;
	/** Logical processors, which is what the kernel's busy share is taken over.
	 * Null where the record reached the machine but named no count. */
	threads: number | null;
}

function cell(value: string | undefined): number | null {
	if (value === undefined || value === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

/** The run and shard an item ran on, which is what a machine record is keyed by. */
function shardKey(date: string, runId: string, shard: number | string): string {
	return `${date}|${runId}|${shard}`;
}

function figureOf(values: readonly number[], outOf: number): CostFigure {
	if (values.length === 0) return { low: null, mid: null, high: null, from: 0, outOf };
	const sorted = [...values].sort((left, right) => left - right);
	return {
		low: sorted[0],
		mid: quantile(sorted, 0.5),
		high: sorted[sorted.length - 1],
		from: sorted.length,
		outOf
	};
}

/** The processors each shard ran on, for the shards the machine record reached.
 *
 * A record that named no count is absent here rather than present as a zero: a
 * missing count and a count of none are different facts, and only the first one
 * is true of this ledger.
 */
function processorsByShard(hosts: readonly MachineProcessors[]): Map<string, number> {
	const found = new Map<string, number>();
	for (const host of hosts) {
		if (host.threads === null || host.threads <= 0) continue;
		found.set(shardKey(host.date, host.run_id, host.shard), host.threads);
	}
	return found;
}

/** Busy processor time one article used, in processor-seconds.
 *
 * `cpu_busy_pct` is a share of every logical processor the machine has, because
 * the kernel counts the whole machine on one line. Multiplying the share by the
 * processors and by the item's own clock turns three readings into the one
 * quantity a runner-hour is sold in.
 *
 * Counted as offered where the item ledger recorded both a busy share and a
 * clock, and as measured only where a machine record also named the processors.
 * The gap between the two is the count of articles this cannot be worked out
 * for, which is the number the panel prints rather than hides.
 */
function processorTime(
	health: readonly Record<string, string>[],
	hosts: readonly MachineProcessors[]
): { figure: CostFigure; processors: number[] } {
	const byShard = processorsByShard(hosts);
	const seconds: number[] = [];
	const counts = new Set<number>();
	let offered = 0;
	for (const row of health) {
		const busyPct = cell(row.cpu_busy_pct);
		const totalMs = cell(row.item_total_ms);
		if (busyPct === null || totalMs === null || totalMs <= 0) continue;
		offered += 1;
		const processors = byShard.get(shardKey(row.date ?? '', row.run_id ?? '', row.shard ?? ''));
		if (processors === undefined) continue;
		counts.add(processors);
		seconds.push((busyPct / PER_CENT) * processors * (totalMs / MS_PER_SECOND));
	}
	return {
		figure: figureOf(seconds, offered),
		processors: [...counts].sort((left, right) => left - right)
	};
}

/** Reading the prompt and writing the reply, in seconds.
 *
 * The server's own accounting, and a total over whatever calls the item made -
 * the stage sums its calls into these two cells before the row is written. It
 * is the smaller half of the item clock, and the difference between the two is
 * what the panel exists to make visible.
 */
function modelTime(health: readonly Record<string, string>[]): CostFigure {
	const seconds: number[] = [];
	for (const row of health) {
		const prefill = cell(row.prefill_ms);
		const decode = cell(row.decode_ms);
		if (prefill === null || decode === null) continue;
		seconds.push((prefill + decode) / MS_PER_SECOND);
	}
	return figureOf(seconds, seconds.length);
}

/** What the model server's resident memory did from one item to the next.
 *
 * A step between neighbours of one shard, never a level: the level answers what
 * the server holds, and the question here is what one more article adds to it.
 * Neighbours only, so a gap in the ledger never becomes a rise that no single
 * article caused, and inside one shard only, because a new shard starts a new
 * server and the first reading of it is a restart rather than an article.
 */
function addedMemory(health: readonly Record<string, string>[]): {
	figure: CostFigure;
	shards: number;
} {
	const byShard = new Map<string, { index: number; rss: number }[]>();
	for (const row of health) {
		const index = cell(row.item_index);
		const rss = cell(row.llama_rss_bytes);
		if (index === null || rss === null) continue;
		const key = shardKey(row.date ?? '', row.run_id ?? '', row.shard ?? '');
		const held = byShard.get(key);
		if (held === undefined) byShard.set(key, [{ index, rss }]);
		else held.push({ index, rss });
	}
	const rises: number[] = [];
	let shards = 0;
	for (const items of byShard.values()) {
		const sorted = [...items].sort((left, right) => left.index - right.index);
		let stepped = false;
		for (let at = 1; at < sorted.length; at += 1) {
			if (sorted[at].index !== sorted[at - 1].index + 1) continue;
			rises.push(sorted[at].rss - sorted[at - 1].rss);
			stepped = true;
		}
		if (stepped) shards += 1;
	}
	return { figure: figureOf(rises, rises.length), shards };
}

/** The three costs of one article, over the rows and machine records handed in.
 *
 * Pure. It reaches no disk and holds no window of its own - the caller decides
 * which days these rows came from, so one span and the next are the same
 * arithmetic over different rows.
 */
export function articleCost(
	health: readonly Record<string, string>[],
	hosts: readonly MachineProcessors[]
): ArticleCost {
	const processor = processorTime(health, hosts);
	const memory = addedMemory(health);
	return {
		rowsRead: health.length,
		processorSeconds: processor.figure,
		processors: processor.processors,
		modelSeconds: modelTime(health),
		addedBytes: memory.figure,
		shards: memory.shards
	};
}

/** What one runner-hour supplies, in processor-seconds, on the processors named.
 *
 * Null where no processor count was named, which is the same absence that makes
 * the processor figure a dash: neither number can be stated without the other.
 * Where the span ran on more than one size of machine the hour is quoted on the
 * smallest, because that is the one a cost has to fit inside.
 */
export function runnerHourSeconds(processors: readonly number[]): number | null {
	if (processors.length === 0) return null;
	return Math.min(...processors) * SECONDS_PER_HOUR;
}

/** A figure drawn on a track whose domain always holds zero.
 *
 * Zero is on the track because added memory goes below it - an article that
 * gives memory back is a real reading, and a track running from the lowest
 * value would hide the sign by putting the giving-back end at the left edge
 * exactly where the smallest rise would sit.
 */
export interface CostTrack {
	drawn: boolean;
	/** The band's near end, as a CSS length. */
	start: string;
	/** The band's length, as a CSS length. */
	length: string;
	/** Where the middle article stands, as a CSS length. */
	at: string;
	/** Where zero stands, as a CSS length. */
	zero: string;
	/** What the two ends of the whole track stand for. */
	floor: number;
	ceiling: number;
}

/** One cost as a band between its two ends, with the middle article marked.
 *
 * `width` is the drawing width in pixels, which is what decides whether a band
 * a person can see was drawn at all - a span every article agreed on is a
 * printed figure and a mark, never a line too thin to find.
 */
export function costTrack(figure: CostFigure, width: number): CostTrack | null {
	if (figure.low === null || figure.high === null || figure.mid === null) return null;
	const floor = Math.min(0, figure.low);
	const ceiling = Math.max(0, figure.high);
	const reach = ceiling - floor;
	const along = (value: number) => (reach <= 0 ? 0 : (value - floor) / reach);
	const length = Math.max(0, along(figure.high) - along(figure.low));
	return {
		drawn: length * width >= 1,
		start: percentOf(along(figure.low)),
		length: percentOf(length),
		at: percentOf(along(figure.mid)),
		zero: percentOf(along(0)),
		floor,
		ceiling
	};
}
