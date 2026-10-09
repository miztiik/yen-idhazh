/** What the readout strip under a console chart prints, and which of its
 * columns a pointer, a key or a tap has picked.
 *
 * One module, because the strip used to be composed by every chart that had
 * one and hinted at by a native tooltip on every chart that did not. A chart
 * hands this module its columns and series and gets back the one shape
 * `ChartReadout.svelte` prints; it never builds a strip of its own.
 *
 * **Every chart on the console says what it hovers, in markup.** A chart that
 * shares a column between its marks carries `data-readout-columns` on the
 * element holding both the plot and the strip, and the strip is the only key it
 * draws. A chart whose hover describes one thing at a time - a row, a tile, an
 * item - carries `data-readout-records`. A chart with nothing to show beyond
 * what it already prints carries `data-readout-none` with the reason in words
 * and who agreed it. "This chart has no hover" is a decision somebody took, and
 * an undeclared chart looks exactly like one where the strip was forgotten, so
 * `console-readout.spec.ts` fails on a chart that declares none of the three.
 */

/** One reading as a chart hands it over. A number is formatted by its series;
 * a string is a word with no number behind it, printed as written; null is a
 * reading nobody took, and the strip prints the not-measured word for it. */
export type ReadoutValue = number | string | null;

/** A line that belongs to one column only, printed after that column's series:
 * a run of that day, or the day the summarizer's settings moved. */
export interface ReadoutLine {
	label: string;
	value: string;
	/** The colour the line's mark is drawn in, or null where nothing on the plot
	 * is its mark. */
	swatch: string | null;
}

/** One series as a chart hands it to `readoutOf`. */
export interface ReadoutInputSeries {
	/** At most 24 characters: a label that wraps turns one entry into two. */
	label: string;
	/** The colour the chart draws the series in, so the strip is the key. */
	swatch: string | null;
	/** One reading per column, in draw order. */
	values: readonly ReadoutValue[];
	/** This series' own number-to-text, so a count and a share sit in one
	 * strip. It is told the column, so a cell built from two numbers - three of
	 * twelve published - can read its second one. */
	format: (value: number, column: number) => string;
	/** One constant printed once beside the label, never per column. */
	note?: string;
}

/** Which column the strip shows while nobody has picked one.
 *
 * `newest` is the newest column with a reading, `last` the last column drawn
 * whatever it holds, `first` the first. A number is a column the panel's own
 * sentence names - the worst day its finding reports. */
export type ReadoutResting = 'newest' | 'first' | 'last' | number;

/** What a column chart hands the builder. Only the column types call this;
 * a chart whose hover is one record at a time calls `factsOf`. */
export interface ReadoutInput {
	type: 'dateSeries' | 'distribution' | 'tileStrip';
	/** The label of each hoverable column, in draw order and reader spelling. */
	columns: readonly string[];
	series: readonly ReadoutInputSeries[];
	/** Lines that belong to one column each, and the sentence a column with none
	 * of them prints - left out where a column without one says nothing. */
	events?: { lines: readonly (readonly ReadoutLine[])[]; none?: string };
	/** From the same vocabulary as the panel's empty state. */
	notMeasured: string;
	/** One column's own reason it holds no reading, where that differs from
	 * `notMeasured` - a chart whose empty columns are not all empty for the
	 * same cause. Null at a column falls back to `notMeasured`; omit the whole
	 * array where every column shares one reason. */
	notMeasuredAt?: readonly (string | null)[];
	resting: ReadoutResting;
}

/** One entry of the strip. */
export interface ReadoutSeries {
	label: string;
	swatch: string | null;
	/** One per column; null prints the not-measured word. */
	values: (string | null)[];
	note?: string;
}

/** The column shape, for a chart with a shared column across its series. */
export interface Readout {
	columns: string[];
	series: ReadoutSeries[];
	/** One list a column, each printed after that column's series. */
	events: ReadoutLine[][];
	/** Printed on a column with no event line; empty where it says nothing. */
	eventsNone: string;
	/** Printed once, in place of the series, on a column nothing measured - and
	 * in place of a single missing reading on a column that measured the rest. */
	notMeasured: string;
	/** Each column's own reason, where it differs from `notMeasured`; null
	 * wherever a chart does not distinguish its empty columns. */
	notMeasuredAt: (string | null)[];
	/** The column shown while nobody has picked one. */
	resting: number;
	/** The sentence for a chart with no column at all, or null. */
	empty: string | null;
}

/** One fact as a record chart hands it to `factsOf`. */
export interface FactInput {
	label: string;
	value: ReadoutValue;
	/** Required for a number: each fact formats its own, so a record can print
	 * a count and a share side by side. */
	format?: (value: number) => string;
	/** The colour this fact is drawn in on the chart, where it has one. */
	swatch?: string | null;
}

/** One fact of a record, ready to print. */
export interface ReadoutFact {
	label: string;
	/** Null prints the record's not-measured word. */
	value: string | null;
	swatch: string | null;
	/** The characters the widest reading of this fact needs across the chart's
	 * records, so stepping from one record to the next does not reflow the
	 * strip. Set by `recordsOf`. */
	reserve?: number;
}

/** The record shape, for a chart whose hover describes one thing - a row, a
 * tile, an item - rather than one column across its series. */
export interface ReadoutFacts {
	subject: string;
	facts: ReadoutFact[];
	notMeasured: string;
	empty: string | null;
}

/** A string that stands in for a missing reading. A strip that prints a dash or
 * nothing for a day nobody measured reads as a broken hover, and a zero there
 * would be a lie; null is how a chart says it, so the strip can say it in
 * words. */
function placeholder(value: string): boolean {
	const bare = value.trim();
	return bare === '' || bare === '-';
}

function printed(
	value: ReadoutValue,
	format: ((value: number) => string) | undefined,
	where: string
): string | null {
	if (value === null) return null;
	if (typeof value === 'number') {
		if (format === undefined) throw new Error(`${where} is a number with no format to print it`);
		return format(value);
	}
	if (placeholder(value)) {
		throw new Error(
			`${where} prints "${value}" for a missing reading; hand null so the strip prints the not-measured word`
		);
	}
	return value;
}

function restingColumn(input: ReadoutInput): number {
	const count = input.columns.length;
	if (count === 0) return 0;
	const rule = input.resting;
	if (typeof rule === 'number') return Math.min(count - 1, Math.max(0, Math.round(rule)));
	if (rule === 'first') return 0;
	if (rule === 'last') return count - 1;
	for (let column = count - 1; column >= 0; column -= 1) {
		if (input.series.some((one) => one.values[column] !== null)) return column;
	}
	return count - 1;
}

/** The strip of a column chart, from its columns and its series.
 *
 * A series with no reading in any column has no entry: a key for a series the
 * window never measured is a claim the data does not support. Every series is
 * checked against the column count, because a strip built from a list of a
 * different length prints one day's numbers under another day's heading.
 */
export function readoutOf(input: ReadoutInput): Readout {
	const count = input.columns.length;
	for (const one of input.series) {
		if (one.values.length !== count) {
			throw new Error(
				`readout series "${one.label}" has ${one.values.length} readings for ${count} columns`
			);
		}
	}
	const lines = input.events?.lines ?? [];
	if (input.events !== undefined && lines.length !== count) {
		throw new Error(`readout events have ${lines.length} columns for ${count}`);
	}
	if (input.notMeasuredAt !== undefined && input.notMeasuredAt.length !== count) {
		throw new Error(`readout notMeasuredAt has ${input.notMeasuredAt.length} reasons for ${count} columns`);
	}
	return {
		columns: [...input.columns],
		series: input.series
			.filter((one) => one.values.some((value) => value !== null))
			.map((one) => ({
				label: one.label,
				swatch: one.swatch,
				values: one.values.map((value, column) =>
					printed(value, (number) => one.format(number, column), `"${one.label}" at column ${column}`)
				),
				...(one.note === undefined ? {} : { note: one.note })
			})),
		events: input.columns.map((_, column) => [...(lines[column] ?? [])]),
		eventsNone: input.events?.none ?? '',
		notMeasured: input.notMeasured,
		notMeasuredAt: input.columns.map((_, column) => input.notMeasuredAt?.[column] ?? null),
		resting: restingColumn(input),
		empty: count === 0 ? input.notMeasured : null
	};
}

/** One record of a record chart, from its facts. */
export function factsOf(
	subject: string,
	facts: readonly FactInput[],
	notMeasured: string
): ReadoutFacts {
	return {
		subject,
		facts: facts.map((fact) => ({
			label: fact.label,
			value: printed(fact.value, fact.format, `"${fact.label}" of ${subject}`),
			swatch: fact.swatch ?? null
		})),
		notMeasured,
		empty: facts.length === 0 ? notMeasured : null
	};
}

/** A record chart's records, each fact keeping room for the widest reading any
 * record gives it, so stepping from one record to the next does not reflow the
 * strip or change the panel's height. */
export function recordsOf(records: readonly ReadoutFacts[]): ReadoutFacts[] {
	const widest = new Map<string, number>();
	for (const record of records) {
		for (const fact of record.facts) {
			const length = (fact.value ?? record.notMeasured).length;
			widest.set(fact.label, Math.max(widest.get(fact.label) ?? 0, length));
		}
	}
	return records.map((record) => ({
		...record,
		facts: record.facts.map((fact) => ({ ...fact, reserve: widest.get(fact.label) ?? 0 }))
	}));
}

/** How wide the readout strip under a plot may be, as an inline style.
 *
 * The strip sits below the plot, so it cannot cover a mark whatever its width.
 * `share` is `chart.readout_max_share`, a share of the plot rather than a pixel
 * count so the cap holds at every window width.
 */
export function readoutCapStyle(share: number): string {
	const capped = Math.min(1, Math.max(0, share));
	return `max-width: ${(capped * 100).toFixed(2)}%`;
}

/** One mark a readout can land on: where it sits.
 *
 * It carried a second field, `lines`, holding one preformatted sentence per
 * series on the premise that the action would read them out. Nothing ever did:
 * `ChartReadout.svelte` is the live region and prints the strip straight.
 */
export interface ReadoutMark {
	/** The mark's x in the chart's own pixels. The hit rule is nearest by x. */
	x: number;
}

/** The action's marks: where each column of the strip sits.
 *
 * The strip and the action are built from one list of columns, so the column a
 * pointer lands on and the column the strip prints cannot be two different ones.
 */
export function readoutMarks(xs: readonly number[]): ReadoutMark[] {
	return xs.map((x) => ({ x }));
}

/** How far a mark may sit from an evenly spaced one and still count as evenly
 * spaced, as a share of one step.
 *
 * `dayColumns` computes `left + (index * (right - left)) / (columns - 1)`, so
 * two neighbouring columns come out a bit or two of a double apart rather than
 * exactly one step apart. A millionth of a step admits that and admits nothing
 * else: over the widest axis this ships, 366 columns, the arithmetic below can
 * then be out by at most a thousandth of a column, and it checks a whole column
 * either side of its own answer.
 */
const EVEN_SPACING_SLACK = 1e-6;

/** How a set of marks lies along x, which decides how a pointer is answered. */
export type MarkSpacing = 'even' | 'ordered' | 'scan';

/** Which of the three rules a set of marks gets, and the rule itself. */
export interface ColumnLookup {
	/** `even` where the marks are evenly spaced, so a column is one division;
	 * `ordered` where they only ascend, so it is a binary search; `scan` where
	 * they do neither. Published so a test can say which rule ran, rather than
	 * only that the answer came out right - an implementation that quietly
	 * walked every mark every time would pass a parity test in silence. */
	rule: MarkSpacing;
	/** The column a pointer at this x means, or null where there are none. */
	at: (x: number) => number | null;
}

function spacingOf(xs: readonly number[]): MarkSpacing {
	for (let index = 0; index < xs.length; index += 1) {
		// A mark that is not a real number, or one sitting before the mark before
		// it, is outside what either fast rule can promise. Neither happens on a
		// console chart and both are cheap to hand back to the walk.
		if (!Number.isFinite(xs[index])) return 'scan';
		if (index > 0 && xs[index] < xs[index - 1]) return 'scan';
	}
	if (xs.length < 2) return 'ordered';
	const first = xs[0];
	const step = (xs[xs.length - 1] - first) / (xs.length - 1);
	// Every mark at one x, which is what an engine-drawn chart holds before it
	// is given its real shares. The search answers it.
	if (!(step > 0)) return 'ordered';
	const slack = step * EVEN_SPACING_SLACK;
	for (let index = 1; index < xs.length - 1; index += 1) {
		if (Math.abs(xs[index] - (first + index * step)) > slack) return 'ordered';
	}
	return 'even';
}

/** The first mark at or past `x`, looking only at the first `to` of them. */
function firstAtOrPast(xs: readonly number[], x: number, to: number): number {
	let low = 0;
	let high = to;
	while (low < high) {
		const middle = (low + high) >> 1;
		if (xs[middle] < x) low = middle + 1;
		else high = middle;
	}
	return low;
}

/** Which column a pointer at an x means, worked out once for one set of marks.
 *
 * The walk this replaces measured every mark on every `pointermove`, so a chart
 * with a column a day over a ninety-day window did ninety subtractions to
 * answer a question a dragging thumb asks many times a second, and it did them
 * again for a move that did not change the answer. The layout is settled once
 * instead, when the marks change:
 *
 * - **Evenly spaced** - every day chart on the console, because `dayColumns`
 *   and `bandShares` both divide the plot evenly. The column is then one
 *   division, and only its two neighbours are measured to settle a pointer
 *   sitting on a boundary.
 * - **Ascending but not evenly spaced** - a chart placing its columns by a
 *   value rather than by a count, and any strip whose marks share an x. A
 *   binary search finds the first mark at or past the pointer and measures the
 *   pair around it.
 * - **Neither** - the walk, unchanged. Nothing on the console produces this,
 *   and a rule that guessed here would be a rule nobody could check.
 *
 * All three answer the same, including the tie: where two marks are the same
 * distance away the lower index wins, because the strip prints one column and
 * a chart with two runs of one day at one x needs the pointer and the strip to
 * agree which. `frame.spec.ts` holds every rule to the walk, at every mark,
 * every midpoint and every duplicate.
 */
export function nearestColumn(marks: readonly ReadoutMark[]): ColumnLookup {
	const xs = marks.map((mark) => mark.x);
	const count = xs.length;
	const rule = spacingOf(xs);

	/** The nearest of a run of candidates, lowest index on a tie. The walk's own
	 * comparison, so a fast rule that narrows the field cannot change the pick. */
	const best = (x: number, from: number, to: number): number => {
		let at = from;
		let gap = Math.abs(xs[from] - x);
		for (let index = from + 1; index <= to; index += 1) {
			const distance = Math.abs(xs[index] - x);
			if (distance < gap) {
				gap = distance;
				at = index;
			}
		}
		return at;
	};

	if (count === 0) return { rule, at: () => null };

	if (rule === 'even') {
		const first = xs[0];
		const step = (xs[count - 1] - first) / (count - 1);
		return {
			rule,
			at: (x: number) => {
				// The walk keeps its first candidate against every distance it cannot
				// beat, so an x that is not a number picks the first column.
				if (!Number.isFinite(x)) return 0;
				// `ceil(t - 0.5)` is the nearest column with an exact halfway point
				// sent down, which is the walk's tie rule.
				const guess = Math.ceil((x - first) / step - 0.5);
				const near = Math.min(count - 1, Math.max(0, guess));
				return best(x, Math.max(0, near - 1), Math.min(count - 1, near + 1));
			}
		};
	}

	if (rule === 'ordered') {
		return {
			rule,
			at: (x: number) => {
				if (!Number.isFinite(x)) return 0;
				const past = firstAtOrPast(xs, x, count);
				if (past === 0) return 0;
				// A second search rather than a walk back over the duplicates: a strip
				// whose marks all share an x is the case that would make that walk the
				// whole array again.
				const firstOf = (index: number) => firstAtOrPast(xs, xs[index], index + 1);
				if (past === count) return firstOf(count - 1);
				return xs[past] - x < x - xs[past - 1] ? past : firstOf(past - 1);
			}
		};
	}

	return { rule, at: (x: number) => best(x, 0, count - 1) };
}

export interface ReadoutOptions {
	marks: ReadoutMark[];
	/** The width the chart drew at, so a client x can be scaled into chart
	 * pixels even in the frame before the resize observer has reported. */
	width: number;
	/** Which mark is selected now, or null for none. */
	onSelect: (index: number | null) => void;
	/** The mark a second figure has picked, where two figures share one pick.
	 * It is taken as this figure's own position without being reported back, so
	 * an arrow key steps on from the day the reader is on rather than from the
	 * day this figure last saw. Left out, the action keeps its own position. */
	selected?: number | null;
	/** Told of a deliberate pick - a step key, or a tap or click that finished -
	 * and never of a hover or the start of a touch. A figure that scrolls another
	 * into view does it here, so a page scroll that starts on the chart cannot
	 * drag the other figure along with it. */
	onPick?: (index: number) => void;
}

/** Report which column the reader is pointing at, or has stepped to.
 *
 * A Svelte action, so a chart writes `use:pointerReadout={...}` and never reads
 * the DOM itself. One `pointermove` and `pointerdown` stream covers mouse, pen
 * and touch, which a native tooltip never did: a tooltip needs a hover, so on a
 * phone the numbers in it did not exist.
 *
 * The `<svg>` itself takes the focus, not its marks. A tab stop per point is a
 * trap on a plot that draws two and a half thousand of them. An engine-drawn
 * chart hands its wrapping element instead: the engine owns everything inside
 * it and swaps the prerendered SVG out on hydration, so an action bound to the
 * SVG would come away with the markup it was attached to.
 */
export function pointerReadout(
	node: SVGSVGElement | HTMLElement,
	options: ReadoutOptions
): { update: (next: ReadoutOptions) => void; destroy: () => void } {
	let current = options;
	let at: number | null = options.selected ?? null;
	let column = nearestColumn(options.marks);

	const select = (next: number | null) => {
		if (next === at) return;
		at = next;
		current.onSelect(next);
	};

	/** Nearest mark by x, never by straight-line distance. Two articles of the
	 * same length sit on top of each other, and a reader pointing at a column
	 * means the column rather than whichever of them is nearer the pointer. */
	const nearest = (clientX: number): number | null => {
		if (current.marks.length === 0) return null;
		const rect = node.getBoundingClientRect();
		if (rect.width === 0) return null;
		return column.at(((clientX - rect.left) * current.width) / rect.width);
	};

	const track = (event: PointerEvent) => select(nearest(event.clientX));

	/** A touch ends the moment the thumb lifts, and a lift raises this event.
	 * Clearing there would blank the readout before it could be read, so only a
	 * mouse leaving the plot clears it. */
	const leave = (event: PointerEvent) => {
		if (event.pointerType === 'mouse') select(null);
	};

	const enter = () => {
		if (at === null && current.marks.length > 0) select(0);
	};

	const away = () => select(null);

	/** A press that lifted where it landed. A touch that turned into a page
	 * scroll is cancelled and never gets here, which is the whole difference
	 * between a tap and the start of a touch. */
	const tap = (event: MouseEvent) => {
		const index = nearest(event.clientX);
		if (index === null) return;
		select(index);
		current.onPick?.(index);
	};

	const step = (event: KeyboardEvent) => {
		const last = current.marks.length - 1;
		if (last < 0) return;
		const from = at ?? 0;
		if (event.key === 'ArrowLeft') select(Math.max(0, from - 1));
		else if (event.key === 'ArrowRight') select(Math.min(last, from + 1));
		else if (event.key === 'Home') select(0);
		else if (event.key === 'End') select(last);
		else if (event.key === 'Escape') select(null);
		else return;
		event.preventDefault();
		// The chart consumed the key. The compression scatter sits inside the
		// viewport control, which pans on the same two arrows - left unstopped,
		// one step through the marks also moved the window under them and left
		// the readout pointing at a mark that had gone.
		event.stopPropagation();
		if (at !== null) current.onPick?.(at);
	};

	// One list, attached and removed from the same entries, so the two halves
	// cannot drift. The node is an `<svg>` on a hand-written chart and a `<div>`
	// on an engine-drawn one; a union of two element types has two incompatible
	// `addEventListener` overload sets, so the listeners go on the base
	// interface both of them implement.
	const events: EventTarget = node;
	const bound: [string, EventListener][] = [
		['pointermove', track as EventListener],
		['pointerdown', track as EventListener],
		['pointerleave', leave as EventListener],
		['focusin', enter],
		['focusout', away],
		['keydown', step as EventListener],
		['click', tap as EventListener]
	];
	for (const [type, handler] of bound) events.addEventListener(type, handler);

	return {
		update(next: ReadoutOptions) {
			// The layout of the marks is settled here rather than on every pointer
			// move, which is the whole of what this action costs a dragging thumb.
			if (next.marks !== current.marks) column = nearestColumn(next.marks);
			current = next;
			// Another figure moved the shared pick. Take it as this figure's own,
			// silently: reporting it back would be the pick answering itself.
			if (next.selected !== undefined) at = next.selected;
			// The window moved, so the mark this index named may be gone. Holding
			// the index would print one article's numbers under another's mark.
			if (at !== null && at > next.marks.length - 1) select(null);
		},
		destroy() {
			for (const [type, handler] of bound) events.removeEventListener(type, handler);
		}
	};
}

export interface ColumnPickOptions {
	marks: ReadoutMark[];
	/** The width the chart drew at, as `pointerReadout` takes it. */
	width: number;
	/** The column the strip shows now, which Enter picks. */
	showing: number | null;
	onPick: (index: number) => void;
}

/** Tell a chart which column a click or Enter chose, for a chart that opens
 * something on a pick - a list of what that column holds.
 *
 * Beside `pointerReadout` rather than inside it, because a hover and a step key
 * only move the strip, and a pick is a deliberate act a reader takes once. A
 * click picks the column nearest the pointer by the same rule the strip uses;
 * Enter picks the column the strip is showing.
 */
export function columnPick(
	node: SVGSVGElement | HTMLElement,
	options: ColumnPickOptions
): { update: (next: ColumnPickOptions) => void; destroy: () => void } {
	let current = options;
	let column = nearestColumn(options.marks);

	const click = (event: MouseEvent) => {
		const rect = node.getBoundingClientRect();
		if (rect.width === 0) return;
		const index = column.at(((event.clientX - rect.left) * current.width) / rect.width);
		if (index !== null) current.onPick(index);
	};

	const key = (event: KeyboardEvent) => {
		if (event.key !== 'Enter' || current.showing === null) return;
		event.preventDefault();
		current.onPick(current.showing);
	};

	const events: EventTarget = node;
	events.addEventListener('click', click as EventListener);
	events.addEventListener('keydown', key as EventListener);
	return {
		update(next: ColumnPickOptions) {
			if (next.marks !== current.marks) column = nearestColumn(next.marks);
			current = next;
		},
		destroy() {
			events.removeEventListener('click', click as EventListener);
			events.removeEventListener('keydown', key as EventListener);
		}
	};
}

/** Which arrow keys step the marks of a chart drawn as elements.
 *
 * `row` is one line of marks - tiles along a date, bars along a strip - and
 * Left and Right step it. `list` is one mark a line, and Up and Down step it.
 * A number is a grid that many marks wide: Left and Right step along a line,
 * Up and Down move a whole line. Keys the layout has no use for are left to
 * the page, which scrolls on them. */
export type MarkWalk = 'row' | 'list' | number;

export interface MarkReadoutOptions {
	/** How many marks carry `data-readout-at`, numbered in reading order. */
	count: number;
	walk: MarkWalk;
	/** Which mark is selected now, or null for the resting one. */
	onSelect: (index: number | null) => void;
	/** The mark picked elsewhere, taken as this chart's own position. */
	selected?: number | null;
}

/** Report which mark of a chart of records - a tile, a square, a row - the
 * reader is pointing at, has stepped to or has tapped.
 *
 * A chart whose marks share a column answers a pointer by the nearest column.
 * A chart of records answers by the mark under the pointer, because its marks
 * wrap onto several lines or stack down a list, and nearest by x would pick a
 * mark on the wrong line. It may be drawn in HTML or in SVG. Every
 * mark carries `data-readout-at` with its index; the element the action is on
 * is the chart's one tab stop, never a stop per mark. A tap sets a mark and it
 * stays set; a mouse leaving, Escape, or focus leaving the chart returns the
 * strip to rest.
 */
export function markReadout(
	node: HTMLElement | SVGElement,
	options: MarkReadoutOptions
): { update: (next: MarkReadoutOptions) => void; destroy: () => void } {
	let current = options;
	let at: number | null = options.selected ?? null;

	const select = (next: number | null) => {
		if (next === at) return;
		at = next;
		current.onSelect(next);
	};

	const markOf = (target: EventTarget | null): number | null => {
		if (!(target instanceof Element)) return null;
		const mark = target.closest('[data-readout-at]');
		if (mark === null || !node.contains(mark)) return null;
		const index = Number(mark.getAttribute('data-readout-at'));
		return Number.isInteger(index) && index >= 0 && index < current.count ? index : null;
	};

	const track = (event: PointerEvent) => {
		const index = markOf(event.target);
		if (index !== null) select(index);
	};

	/** Only a mouse leaving clears: a lifted thumb raises the same event, and
	 * clearing there would blank the strip before it could be read. */
	const leave = (event: PointerEvent) => {
		if (event.pointerType === 'mouse') select(null);
	};

	const enter = () => {
		if (at === null && current.count > 0) select(0);
	};

	const away = (event: FocusEvent) => {
		if (event.relatedTarget instanceof Node && node.contains(event.relatedTarget)) return;
		select(null);
	};

	const step = (event: KeyboardEvent) => {
		const last = current.count - 1;
		if (last < 0) return;
		const from = at ?? 0;
		const walk = current.walk;
		const across = walk !== 'list';
		const down = walk === 'list' ? 1 : typeof walk === 'number' ? walk : 0;
		let next: number | null;
		if (across && event.key === 'ArrowLeft') next = Math.max(0, from - 1);
		else if (across && event.key === 'ArrowRight') next = Math.min(last, from + 1);
		else if (down > 0 && event.key === 'ArrowUp') next = from - down >= 0 ? from - down : from;
		else if (down > 0 && event.key === 'ArrowDown') next = from + down <= last ? from + down : from;
		else if (event.key === 'Home') next = 0;
		else if (event.key === 'End') next = last;
		else if (event.key === 'Escape') next = null;
		else return;
		event.preventDefault();
		event.stopPropagation();
		select(next);
	};

	const events: EventTarget = node;
	const bound: [string, EventListener][] = [
		['pointermove', track as EventListener],
		['pointerdown', track as EventListener],
		['pointerleave', leave as EventListener],
		['focusin', enter],
		['focusout', away as EventListener],
		['keydown', step as EventListener],
		['click', track as EventListener]
	];
	for (const [type, handler] of bound) events.addEventListener(type, handler);

	return {
		update(next: MarkReadoutOptions) {
			current = next;
			if (next.selected !== undefined) at = next.selected;
			if (at !== null && at > next.count - 1) select(null);
		},
		destroy() {
			for (const [type, handler] of bound) events.removeEventListener(type, handler);
		}
	};
}

/** One pick on a chart of lines stacked a row each: which line, and which of
 * its columns. */
export interface GridPick {
	row: number;
	column: number;
}

/** Where a key moves a pick on a chart of lines stacked a row each - a ledger
 * that draws one line a row, every line one column a day.
 *
 * The keys follow the layout: Up and Down move to the line above or below and
 * keep the day, Left and Right step along the line, Home and End jump to its
 * ends, and Escape returns to rest, which is null. A key the layout has no use
 * for is undefined, and is left to the page, which scrolls on it. The chart is
 * one tab stop for all of its lines; the pointer picks a line by the line it is
 * on and a column by x, through each line's own `pointerReadout`.
 */
export function gridStep(
	key: string,
	from: GridPick,
	rows: number,
	columns: number
): GridPick | null | undefined {
	if (rows < 1 || columns < 1) return undefined;
	const row = Math.min(rows - 1, Math.max(0, from.row));
	const column = Math.min(columns - 1, Math.max(0, from.column));
	if (key === 'ArrowUp') return { row: Math.max(0, row - 1), column };
	if (key === 'ArrowDown') return { row: Math.min(rows - 1, row + 1), column };
	if (key === 'ArrowLeft') return { row, column: Math.max(0, column - 1) };
	if (key === 'ArrowRight') return { row, column: Math.min(columns - 1, column + 1) };
	if (key === 'Home') return { row, column: 0 };
	if (key === 'End') return { row, column: columns - 1 };
	if (key === 'Escape') return null;
	return undefined;
}
