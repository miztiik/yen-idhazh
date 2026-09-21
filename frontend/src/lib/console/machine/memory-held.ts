/** What is holding the machine's memory, drawn so a reader can only add the
 * parts that really add up.
 *
 * The bar a reader first asks for - the model server, our python, the page
 * cache and what is free, side by side, summing to the machine - cannot be
 * drawn, and that is measured rather than feared. Stacking those four exceeds
 * the machine on **378 of 378 committed rows that carry the kernel reading,
 * by 1.21x at the narrowest and 1.87x at the widest, measured 2026-09-21 over
 * `state/item-health/`**. Two independent double-counts produce it. The weight
 * file is mapped rather than read in, so its pages are resident in the server
 * and counted in the page cache at the same moment. And what the kernel calls
 * available is mostly that same reclaimable page cache, so the page cache is
 * already inside the free part.
 *
 * So this draws two shapes, and says which one the reader is looking at.
 *
 * **Two segments that genuinely partition the machine**, on every row the
 * pipeline has committed: what the kernel says it could still hand out, and
 * what is held. Under the bar, the two process readings are brackets labelled
 * *at most*, both anchored at the bar's origin so they visibly overlap. A
 * reader cannot add two brackets that overlap, which is the whole point -
 * abutting slices would invite exactly the addition that produced the 1.87.
 *
 * **Four segments where the row carries the two anonymous readings.** Anonymous
 * memory is not file-backed, so it cannot double-count with the page cache and
 * the parts close. Those two columns landed with row #5 and no pipeline run has
 * written a day since, so every committed row is blank in them today and the
 * four-segment shape reaches a reader through the canary first.
 *
 * **The remainder is drawn with its sign.** Where the two own-memory readings
 * together exceed what the kernel says is held, that is two readings taken a
 * moment apart disagreeing, and the bar runs past the machine's edge to say so.
 * Clamping it to zero would delete the finding.
 */

import { gib } from '$lib/charts/machine';
import { percentOf } from '$lib/charts/rank';

/** One part of the bar. `bytes` is signed; `width` is never negative, because a
 * negative width is not a thing a browser can paint - the sign leaves the bar
 * and becomes the over-run beside it. */
export interface MemorySegment {
	key: 'free' | 'held' | 'server' | 'worker' | 'rest';
	/** Plain words, no column name. */
	label: string;
	bytes: number;
	/** The figure as a reader reads it. */
	figure: string;
	width: string;
}

/** A process reading, drawn from the bar's origin and labelled *at most*.
 *
 * It is an upper bound in two directions at once: it counts the mapped weight
 * pages the kernel can take back, and it counts pages shared with another
 * process in full. Two of them may not be added.
 */
export interface MemoryBracket {
	key: 'server' | 'worker';
	label: string;
	bytes: number;
	figure: string;
	width: string;
	/** True where the bracket runs past what the kernel calls held. Measured on
	 * **375 of 378 committed rows** for the model server, 2026-09-21: the
	 * bracket is mostly the mapped weight file, which is not memory the kernel
	 * had to find. */
	pastHeld: boolean;
}

/** The swap actually in use, ruled under the bar on its own scale.
 *
 * The machine's scale is the wrong one for it. Measured 2026-09-21 over the
 * 378 committed rows that carry the reading: a median of 60 KiB, a p90 of 61.1
 * MiB and a worst of 657.9 MiB against a 15.61 GiB machine, so on the bar's own
 * scale the median is four ten-thousandths of a percent and paints nothing. On
 * the swap file's scale the worst row is 21.4 percent, which is a mark.
 */
export interface MemorySwap {
	usedBytes: number;
	totalBytes: number;
	usedFigure: string;
	totalFigure: string;
	width: string;
	/** True where the reading is present and reads zero - a different fact from
	 * no reading at all. */
	none: boolean;
}

/** One day's tightest moment, and what the machine was holding at it. */
export interface MemoryDay {
	date: string;
	/** The item the reading is from. One row, so every segment comes from one
	 * moment rather than from an average of moments that never met. */
	itemId: string;
	/** Which of the two shapes the reader is looking at. */
	shape: 'four' | 'two';
	totalBytes: number;
	totalFigure: string;
	/** What the bar is drawn against: the machine, widened only where the parts
	 * run past it. */
	scaleBytes: number;
	/** Where the machine's own edge falls on that scale. `100%` unless the parts
	 * ran past it. */
	machineWidth: string;
	segments: MemorySegment[];
	brackets: MemoryBracket[];
	/** How far two brackets overlap, from the origin. Zero where only one of the
	 * two readings is present. */
	overlapBytes: number;
	overlapWidth: string;
	overlapFigure: string;
	/** Signed, and null in the two-segment shape where there is no remainder to
	 * compute. Negative is the disagreement. */
	restBytes: number | null;
	/** How far the parts ran past the machine. Zero where they did not. */
	overBytes: number;
	overFigure: string;
	swap: MemorySwap | null;
}

/** Every day the ledger can draw, and the date the reading begins. */
export interface MemoryHeldRecord {
	days: MemoryDay[];
	/** The first date any row carried the machine's own total, or null where no
	 * row ever did. The ledger reaches back further than this, and a reader who
	 * is not told that reads an empty stretch as a quiet machine. */
	firstDate: string | null;
	/** How many days of ledger were read to find them. */
	daysRead: number;
}

/** What one open span draws. */
export interface MemoryHeldView {
	days: MemoryDay[];
	fourShape: number;
	twoShape: number;
	firstDate: string | null;
	daysRead: number;
	empty: boolean;
}

/** A GiB figure is unreadable below about a hundredth of one, and the swap
 * median is four hundred times smaller than that. Format literals, not knobs. */
const BYTES_IN_MIB = 1024 * 1024;
const BYTES_IN_GIB = 1024 * 1024 * 1024;

/** Under a tenth of a GiB, say it in MiB. A reader who is told `0.00 GiB` has
 * been told nothing, and a swap of 60 KiB is not the same fact as no swap. */
function memoryFigure(bytes: number): string {
	const size = Math.abs(bytes);
	if (size >= BYTES_IN_GIB / 10) return gib(bytes);
	if (size >= BYTES_IN_MIB / 100) return `${(bytes / BYTES_IN_MIB).toFixed(2)} MiB`;
	return `${Math.round(bytes / 1024)} KiB`;
}

function numberCell(row: Record<string, string>, name: string): number | null {
	const text = (row[name] ?? '').trim();
	if (text === '') return null;
	const value = Number(text);
	return Number.isFinite(value) ? value : null;
}

function widthOn(bytes: number, scale: number): string {
	if (scale <= 0) return percentOf(0);
	return percentOf(Math.max(bytes, 0) / scale);
}

/** The tightest moment of a day: the row where the kernel had the least left to
 * hand out. That is the moment that decides whether the machine runs out, and
 * reading every segment off that one row is what keeps the arithmetic about a
 * single moment. A tie is broken on the item id so two builds of the same
 * ledger draw the same item. */
function tightestOf(rows: readonly Record<string, string>[]): Record<string, string> {
	return [...rows].sort((left, right) => {
		const gap = (numberCell(left, 'os_mem_available_bytes') ?? 0) -
			(numberCell(right, 'os_mem_available_bytes') ?? 0);
		if (gap !== 0) return gap;
		return (left.item_id ?? '').localeCompare(right.item_id ?? '');
	})[0];
}

function bracketsOf(
	row: Record<string, string>,
	heldBytes: number,
	scaleBytes: number
): { brackets: MemoryBracket[]; overlapBytes: number } {
	const readings: { key: 'server' | 'worker'; label: string; bytes: number | null }[] = [
		{ key: 'server', label: 'the model server, at most', bytes: numberCell(row, 'llama_rss_bytes') },
		{ key: 'worker', label: 'our own worker, at most', bytes: numberCell(row, 'python_rss_bytes') }
	];
	const brackets = readings
		.filter((reading): reading is { key: 'server' | 'worker'; label: string; bytes: number } =>
			reading.bytes !== null
		)
		.map((reading) => ({
			key: reading.key,
			label: reading.label,
			bytes: reading.bytes,
			figure: memoryFigure(reading.bytes),
			width: widthOn(reading.bytes, scaleBytes),
			pastHeld: reading.bytes > heldBytes
		}));
	// The overlap is what a reader would have added twice. Drawing it is what
	// makes "these two may not be added" something they can see rather than
	// something they are told.
	const overlapBytes = brackets.length === 2 ? Math.min(brackets[0].bytes, brackets[1].bytes) : 0;
	return { brackets, overlapBytes };
}

/** Every day the item ledger can draw a bar for.
 *
 * `health` is the item ledger, already bounded by the caller to the widest span
 * the window control offers (`CLAUDE.md` Guardrail #12). A day is drawable when one of
 * its rows carries both the machine's own total and what the kernel said was
 * available; nothing is inferred for a day that carries neither.
 */
export function memoryHeld(health: readonly Record<string, string>[]): MemoryHeldRecord {
	const byDay = new Map<string, Record<string, string>[]>();
	const allDays = new Set<string>();
	for (const row of health) {
		const date = (row.date ?? '').trim();
		if (date === '') continue;
		allDays.add(date);
		if (numberCell(row, 'os_mem_total_bytes') === null) continue;
		if (numberCell(row, 'os_mem_available_bytes') === null) continue;
		const held = byDay.get(date);
		if (held === undefined) byDay.set(date, [row]);
		else held.push(row);
	}

	const days: MemoryDay[] = [];
	for (const [date, rows] of [...byDay.entries()].sort((left, right) =>
		left[0].localeCompare(right[0])
	)) {
		const row = tightestOf(rows);
		const totalBytes = numberCell(row, 'os_mem_total_bytes') ?? 0;
		const availableBytes = numberCell(row, 'os_mem_available_bytes') ?? 0;
		const heldBytes = totalBytes - availableBytes;
		const serverAnon = numberCell(row, 'llama_rss_anon_bytes');
		const workerAnon = numberCell(row, 'python_rss_anon_bytes');
		const four = serverAnon !== null && workerAnon !== null;

		// The remainder carries its sign. Negative means the two own-memory
		// readings, taken at the end of the item, together exceed what the kernel
		// said was held a moment later. That is a disagreement between two
		// readings and it is drawn, never clamped.
		const restBytes = four ? heldBytes - (serverAnon as number) - (workerAnon as number) : null;
		const overBytes = restBytes !== null && restBytes < 0 ? -restBytes : 0;
		const scaleBytes = totalBytes + overBytes;

		const segments: MemorySegment[] = [
			{
				key: 'free',
				label: 'the kernel could still hand this out',
				bytes: availableBytes,
				figure: memoryFigure(availableBytes),
				width: widthOn(availableBytes, scaleBytes)
			}
		];
		if (four) {
			segments.push({
				key: 'server',
				label: "the model server's own memory",
				bytes: serverAnon as number,
				figure: memoryFigure(serverAnon as number),
				width: widthOn(serverAnon as number, scaleBytes)
			});
			segments.push({
				key: 'worker',
				label: "our own worker's memory",
				bytes: workerAnon as number,
				figure: memoryFigure(workerAnon as number),
				width: widthOn(workerAnon as number, scaleBytes)
			});
			segments.push({
				key: 'rest',
				label: 'everything else the machine is holding',
				bytes: restBytes as number,
				figure: memoryFigure(restBytes as number),
				width: widthOn(restBytes as number, scaleBytes)
			});
		} else {
			segments.push({
				key: 'held',
				label: 'held',
				bytes: heldBytes,
				figure: memoryFigure(heldBytes),
				width: widthOn(heldBytes, scaleBytes)
			});
		}

		const { brackets, overlapBytes } = bracketsOf(row, heldBytes, scaleBytes);
		const swapTotal = numberCell(row, 'os_swap_total_bytes');
		const swapFree = numberCell(row, 'os_swap_free_bytes');
		const swapUsed = swapTotal !== null && swapFree !== null ? swapTotal - swapFree : null;

		days.push({
			date,
			itemId: (row.item_id ?? '').trim(),
			shape: four ? 'four' : 'two',
			totalBytes,
			totalFigure: memoryFigure(totalBytes),
			scaleBytes,
			machineWidth: widthOn(totalBytes, scaleBytes),
			segments,
			brackets,
			overlapBytes,
			overlapWidth: widthOn(overlapBytes, scaleBytes),
			overlapFigure: memoryFigure(overlapBytes),
			restBytes,
			overBytes,
			overFigure: memoryFigure(overBytes),
			swap:
				swapTotal === null || swapUsed === null
					? null
					: {
							usedBytes: swapUsed,
							totalBytes: swapTotal,
							usedFigure: memoryFigure(swapUsed),
							totalFigure: memoryFigure(swapTotal),
							width: widthOn(swapUsed, swapTotal),
							none: swapUsed === 0
						}
		});
	}

	return {
		days,
		firstDate: days.length === 0 ? null : days[0].date,
		daysRead: allDays.size
	};
}

/** The days of that record the open span reaches.
 *
 * `start` and `end` are the span the window control has open, as the rest of
 * this route carries them. The counts are recomputed per span rather than
 * carried over, because a narrower span can hold a different mix of the two
 * shapes and a count taken at the widest would be about days the reader cannot
 * see.
 */
export function memoryHeldWithin(
	record: MemoryHeldRecord,
	start: string,
	end: string
): MemoryHeldView {
	const days = record.days.filter((day) => day.date >= start && day.date <= end);
	return {
		days,
		fourShape: days.filter((day) => day.shape === 'four').length,
		twoShape: days.filter((day) => day.shape === 'two').length,
		firstDate: record.firstDate,
		daysRead: record.daysRead,
		empty: days.length === 0
	};
}
