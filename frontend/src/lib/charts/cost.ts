/** The counterfactual price of each day's work and the running total.
 *
 * Never a bill: the native chart states the rate and currency beside the value.
 * Both readings come from one pass over the same qualified runs.
 */
import { costOf, type CostRate, type RunWork } from './machine';

export interface CostDay {
	date: string;
	/** What reading this day's prompts would have cost at the rate handed in. */
	read: number;
	/** What writing this day's answers would have cost. */
	written: number;
	total: number;
	/** This day and every day before it in the window. The line's points. */
	running: number;
	/** Items that reported both token counts. The denominator, printed. */
	items: number;
}

export interface CostShapes {
	/** Oldest first. One day's price, one point of the running line. */
	days: CostDay[];
	/** The last point of the line, which is what the whole window cost. */
	runningTotal: number;
}

/** A day that ran twice is one day's work, at the operator's current rate.
 *
 * Nothing is cached against the rate: a typed price is a multiplication away,
 * and a cache keyed on a number a person is typing would go stale.
 */
export function costOverDays(
	runs: readonly RunWork[],
	rate: CostRate
): CostShapes {
	const byDate = new Map<string, { input: number; output: number; items: number }>();
	for (const run of runs) {
		const date = run.date;
		if (date === '') continue;
		const bucket = byDate.get(date) ?? { input: 0, output: 0, items: 0 };
		bucket.input += run.input;
		bucket.output += run.output;
		bucket.items += run.items;
		byDate.set(date, bucket);
	}

	let running = 0;
	const days: CostDay[] = [...byDate.entries()]
		.sort(([left], [right]) => left.localeCompare(right))
		.map(([date, bucket]) => {
			const read = costOf({ input: bucket.input, output: 0 }, rate);
			const written = costOf({ input: 0, output: bucket.output }, rate);
			const total = read + written;
			running += total;
			return { date, read, written, total, running, items: bucket.items };
		});

	return {
		days,
		runningTotal: days.at(-1)?.running ?? 0
	};
}
