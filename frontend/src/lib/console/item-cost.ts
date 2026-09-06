import { distribution, quantile, type Distribution } from '../charts/series';

/** What one item cost the model, over one window of the published projection.
 *
 * Four cells of the projection are behind everything here - the two model
 * clocks and the three token counts - and they are per item, which is the grain
 * nothing else on the console has. The Hardware route pools the same quantities
 * per run and per shard out of the server's own counters, and a run total
 * cannot say that one article in nine got nothing from the cache.
 *
 * It is a pure reduction over rows the caller already read, so it runs in Node
 * without a browser and the spec can re-derive every figure from the committed
 * projection and compare.
 */

/** The days a reduction covers. Named rather than a bare pair, because a start
 * and an end without a count is a span nobody can check against the control. */
export interface CostWindow {
	start: string;
	end: string;
	days: number;
}

/** Every figure the cost section draws, for one window.
 *
 * **Every count here is a denominator of its own.** An item that failed before
 * the model saw it has no clock and no token count; an item that failed before
 * the fetch has neither of those and no stage clock either. Measured 2026-09-05
 * over the committed projection, that is 6,104 rows with the model's clocks
 * against 8,300 rows in all - so one "items" figure would be wrong for at least
 * one column of this section whichever row set it counted.
 */
export interface ItemCost {
	days: number;
	start: string;
	end: string;
	/** Projection rows the window holds, of every kind. The widest denominator,
	 * and the one that says how much of the window this section is silent about. */
	rows: number;
	/** Rows carrying both of the model's own clocks. */
	timed: number;
	/** Days inside the window that recorded a model clock at all. */
	timedDays: number;
	/** How long the model spent reading the prompt, one entry per item. */
	reading: Distribution | null;
	/** How long it spent writing the summary, one entry per item. */
	writing: Distribution | null;
	/** Items carrying a prompt token count. The denominator for every token
	 * figure below, and not the same number as `timed`. */
	counted: number;
	/** The middle item's prompt, in tokens, cached part included. */
	promptTokens: number | null;
	/** The middle item's summary, in tokens. */
	writtenTokens: number | null;
	/** Prompt tokens the model actually read, summed over the window. */
	readTokens: number;
	/** Prompt tokens it did not have to read again, summed over the window. */
	reusedTokens: number;
	/** Reused over every prompt token the window needed, whole percent. Null
	 * where the window needed none. */
	reusedPct: number | null;
	/** The middle item's own share, whole percent. It is not `reusedPct`: one is
	 * a share of the window's tokens and the other is the middle of a list of
	 * shares, and on a window holding one very long article they disagree. */
	itemReusedPct: number | null;
	/** The middle item's reused count, and the largest any item got.
	 *
	 * These two are the reason the share is not drawn as a trend. Measured
	 * 2026-09-05 the middle item reused 922 tokens and the widest 941, over a
	 * spread of 6,104 items - so the share moves because the prompt moves.
	 */
	reusedMedian: number | null;
	reusedWidest: number | null;
	/** Items whose prompt was read whole. Zero reuse is a measurement, so these
	 * are counted rather than left out. */
	readWhole: number;
	/** Milliseconds one prompt token costs to read. Summed and then divided,
	 * never a mean of per-item rates: averaging ratios weighs a release note
	 * like a feature. */
	msPerReadToken: number | null;
	/** Milliseconds one written token costs, the same way. */
	msPerWrittenToken: number | null;
	/** How many times a written token costs what a read one does. Null unless
	 * both rates are known - a ratio against an absent rate is not a ratio. */
	writeCostRatio: number | null;
}

/** An empty cell is absent, never zero. The rule the whole projection is read
 * by: a stage that did not run measured nothing, and a stage that finished
 * inside the clock's own resolution measured zero. */
function cell(row: Record<string, string>, name: string): number | null {
	const raw = row[name];
	if (raw === undefined || raw === '') return null;
	const value = Number(raw);
	return Number.isFinite(value) ? value : null;
}

function within(
	rows: readonly Record<string, string>[],
	window: CostWindow
): Record<string, string>[] {
	return rows.filter((row) => {
		const date = row.date ?? '';
		return date >= window.start && date <= window.end;
	});
}

/** The middle value, as a whole number.
 *
 * Every caller is a count of tokens or a whole percent, and no console cell
 * prints a decimal. It matters here rather than at the far end: over an even
 * number of items the middle is the mean of two, so a real window of 6,104
 * items printed `1,687.5 tokens` while the seven-item canary printed a whole
 * number and no test could see it.
 */
function middle(values: readonly number[]): number | null {
	if (values.length === 0) return null;
	return Math.round(quantile([...values].sort((a, b) => a - b), 0.5));
}

/** A share as whole percent, or null where the denominator is nothing.
 *
 * Whole percent because no console cell prints a decimal, and because `0.518`
 * is a number an operator has to convert before it means anything.
 */
function sharePct(part: number, whole: number): number | null {
	return whole > 0 ? Math.round((part / whole) * 100) : null;
}

/** What one item cost, over the rows of one window.
 *
 * The rows are the published projection as it was read, cell by cell, so the
 * two clocks and the three counts keep the emptiness the writer gave them.
 */
export function itemCost(rows: readonly Record<string, string>[], window: CostWindow): ItemCost {
	const inWindow = within(rows, window);

	const readMs: number[] = [];
	const writeMs: number[] = [];
	const prompts: number[] = [];
	const written: number[] = [];
	const reused: number[] = [];
	const itemShares: number[] = [];
	const timedDays = new Set<string>();
	let timed = 0;
	let counted = 0;
	let readTokens = 0;
	let reusedTokens = 0;
	let readWhole = 0;
	// The two rates are pooled over the items that carry both halves of them, so
	// a millisecond total and a token total always describe the same items.
	let readPairMs = 0;
	let readPairTokens = 0;
	let writePairMs = 0;
	let writePairTokens = 0;

	for (const row of inWindow) {
		const prefill = cell(row, 'prefill_ms');
		const decode = cell(row, 'decode_ms');
		const input = cell(row, 'input_tokens');
		const output = cell(row, 'output_tokens');
		const cached = cell(row, 'cached_tokens');

		if (prefill !== null) readMs.push(prefill);
		if (decode !== null) writeMs.push(decode);
		if (prefill !== null && decode !== null) {
			timed += 1;
			timedDays.add(row.date ?? '');
		}

		if (input !== null) {
			counted += 1;
			prompts.push(input);
			// Cached tokens are taken out of the read count. Leaving them in reports
			// a rate the machine never ran at: it did not read them.
			const read = Math.max(0, input - (cached ?? 0));
			readTokens += read;
			if (cached !== null) {
				reusedTokens += cached;
				reused.push(cached);
				if (cached === 0) readWhole += 1;
				const share = sharePct(cached, input);
				if (share !== null) itemShares.push(share);
			}
			if (prefill !== null) {
				readPairMs += prefill;
				readPairTokens += read;
			}
		}
		if (output !== null) {
			written.push(output);
			if (decode !== null) {
				writePairMs += decode;
				writePairTokens += output;
			}
		}
	}

	const msPerReadToken = readPairTokens > 0 ? readPairMs / readPairTokens : null;
	const msPerWrittenToken = writePairTokens > 0 ? writePairMs / writePairTokens : null;

	return {
		days: window.days,
		start: window.start,
		end: window.end,
		rows: inWindow.length,
		timed,
		timedDays: timedDays.size,
		reading: distribution(readMs),
		writing: distribution(writeMs),
		counted,
		promptTokens: middle(prompts),
		writtenTokens: middle(written),
		readTokens,
		reusedTokens,
		reusedPct: sharePct(reusedTokens, readTokens + reusedTokens),
		itemReusedPct: middle(itemShares),
		reusedMedian: middle(reused),
		reusedWidest: reused.length === 0 ? null : Math.max(...reused),
		readWhole,
		msPerReadToken,
		msPerWrittenToken,
		writeCostRatio:
			msPerReadToken === null || msPerWrittenToken === null || msPerReadToken <= 0
				? null
				: msPerWrittenToken / msPerReadToken
	};
}
