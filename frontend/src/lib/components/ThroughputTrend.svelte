<script lang="ts">
	/** Did the model get faster, and did its spread change?
	 *
	 * A single number a day cannot answer the second half. A worker sorts its
	 * articles by prompt band and summarises the short ones first, so within one
	 * run the slowest item is several times slower than the fastest. That spread
	 * is a property of the day's article mix, not a fault, and a model swap moves
	 * the whole candle rather than one number.
	 *
	 * Whisker is fastest to slowest item, box is the middle half, the tick is the
	 * median. Cached prompt tokens are already out of the read rate.
	 *
	 * The axis, the marks and the readout follow the same contract as the stage
	 * timing trend directly above it on the page: a date per column thinned to
	 * `chart.tick_density` with both ends kept, a mark on every plotted point,
	 * one column guide under the pointer, and a readout in a fixed strip below
	 * the plot rather than a box over it. Two charts stacked on one page that
	 * hover differently cost the reader a second guess.
	 *
	 * The chart draws through `frame.ts` in CSS pixels, so `font-size="10"` is
	 * ten pixels on screen. Its domain is the drawn extent rather than zero to
	 * the fastest item: a candle says where a rate is, and zero belongs on an
	 * axis only where the length of the mark carries the number. Measured on the
	 * published console 2026-08-25, zero-anchored, the read whisker occupied
	 * 17.5% of the plot height and the middle-half box 3.7%.
	 */
	import {
		chartWidth,
		dayColumnX,
		dayTicks,
		frame,
		linearAxis,
		observeWidth,
		pointerReadout,
		readoutMarks,
		type DayReadout
	} from '$lib/charts/frame';
	import ChartReadout from './ChartReadout.svelte';
	import type { ThroughputDay } from '$lib/charts/series';
	import { daysInWindow } from '$lib/charts/viewport';
	import { shortDate } from '$lib/format';

	let {
		days,
		height,
		width,
		reference,
		tickDensity,
		readoutMaxShare
	}: {
		days: ThroughputDay[];
		height: number;
		width: number;
		reference: string;
		tickDensity: number;
		readoutMaxShare: number;
	} = $props();

	const SERIES = [
		{ key: 'read', label: 'read', colour: 'var(--color-accent)' },
		{ key: 'write', label: 'write', colour: 'var(--color-text)' }
	] as const;

	type SeriesKey = (typeof SERIES)[number]['key'];

	/** Thin enough that 60 days do not overlap into a smear, thick enough that
	 * the middle-half box still reads as a box. */
	const CANDLE_MIN = 2;
	const CANDLE_MAX = 6;

	/** The width the chart occupies, once a browser has measured it. Null on the
	 * server, where the knob is the width. */
	let measured = $state<number | null>(null);
	let selected = $state<number | null>(null);

	const ordered = $derived([...days].sort((a, b) => a.date.localeCompare(b.date)));
	const calendar = $derived(
		ordered.length === 0
			? []
			: daysInWindow({ start: ordered[0].date, end: ordered[ordered.length - 1].date })
	);
	const byDate = $derived(new Map(ordered.map((day) => [day.date, day])));
	const box = $derived(frame(chartWidth(measured, width), height));

	/** A series with nothing in the window draws nothing, and takes its axis, its
	 * ticks and its legend entry with it. */
	const drawn = $derived(
		SERIES.filter((series) =>
			ordered.some((day) => Number.isFinite(day[series.key].max) && day[series.key].max > 0)
		)
	);
	const rates = $derived(
		ordered.flatMap((day) => drawn.flatMap((series) => [day[series.key].min, day[series.key].max]))
	);
	const y = $derived(linearAxis(rates, [box.bottom, box.top], { zero: false }));

	const axis = $derived(dayTicks(calendar, tickDensity));
	const newest = $derived(ordered[ordered.length - 1] ?? null);
	const previous = $derived(ordered.length > 1 ? ordered[ordered.length - 2] : null);

	/** The two newest days ran on models the ledger names, and they differ.
	 *
	 * A percent shift across that boundary would read as the swap's doing, and
	 * nothing committed says it was: the articles changed too. An unknown model
	 * ends the comparison rather than inventing a swap. */
	const swapped = $derived(
		newest !== null &&
			previous !== null &&
			newest.model !== null &&
			previous.model !== null &&
			newest.model !== previous.model
	);

	const column = $derived(new Map(calendar.map((date, index) => [date, index])));

	/** Every boundary in the window where the model changed, not just the newest.
	 *
	 * Drawn so a step in the trend can be attributed to a swap rather than
	 * guessed at. Consecutive days that RAN, so a gap in the calendar does not
	 * invent a swap; an unnamed model on either side ends the comparison the
	 * same way the verdict sentence does. */
	const swaps = $derived(
		ordered.flatMap((day, index) => {
			if (index === 0) return [];
			const before = ordered[index - 1];
			if (day.model === null || before.model === null || day.model === before.model) return [];
			const at = column.get(day.date);
			if (at === undefined) return [];
			return [{ date: day.date, at, from: before.model, to: day.model }];
		})
	);

	/** Candles thin as the window widens. */
	const candle = $derived(
		Math.max(
			CANDLE_MIN,
			Math.min(CANDLE_MAX, (box.innerWidth / Math.max(1, calendar.length - 1)) * 0.34)
		)
	);
	const offset = $derived(candle * 0.62);
	/** Half a pair of candles, so the oldest and the newest day sit inside the
	 * plot rather than straddling its edge. */
	const pad = $derived(Math.min(offset + candle / 2, box.innerWidth / 2));
	const step = $derived((box.innerWidth - pad * 2) / Math.max(1, calendar.length - 1));

	function x(index: number): number {
		return dayColumnX(index, calendar.length, box, pad);
	}

	function centre(index: number, key: SeriesKey): number {
		return x(index) + (key === 'read' ? -offset : offset);
	}

	function rate(value: number): string {
		return `${value.toFixed(2)} tok/s`;
	}

	/** The long form: everything about one day and one series, including which
	 * run moved. It is the mark's accessible name, where length costs nothing. */
	function caption(day: ThroughputDay, key: SeriesKey): string {
		const band = day[key];
		const runs = day.runs
			.map((run) => `${run.runId} ${(key === 'read' ? run.read : run.write).toFixed(2)}`)
			.join(', ');
		return (
			`${day.date} ${key}: median ${rate(band.median)}, ` +
			`middle half ${band.p25.toFixed(2)} to ${band.p75.toFixed(2)}, ` +
			`slowest ${band.min.toFixed(2)}, fastest ${band.max.toFixed(2)} over ${day.items} items. ` +
			`Run medians: ${runs}.`
		);
	}

	/** The short form: the day's rate and its extent, sized to sit on one line
	 * inside a readout capped at `chart.readout_max_share` of the plot.
	 *
	 * The readout carried `caption()` verbatim until 2026-08-30, on the rule that
	 * one day gets one sentence. The cap ends that: `caption()` closes with a run
	 * list that grows with the day's run count, so it is the one clause here with
	 * no bound, and four wrapped lines of it under the plot is not a readout. The
	 * `<title>` keeps every word, including the middle half the box already
	 * draws, and the run count stays in the verdict line under the legend.
	 *
	 * The series name is the strip's own row label, so it is not repeated here.
	 */
	function readoutLine(day: ThroughputDay, key: SeriesKey): string {
		const band = day[key];
		return `${band.median.toFixed(2)} (${band.min.toFixed(2)}-${band.max.toFixed(2)})`;
	}

	function shift(now: number, before: number): string {
		if (before <= 0) return 'level';
		const pct = ((now - before) / before) * 100;
		return `${pct >= 0 ? 'up' : 'down'} ${Math.abs(pct).toFixed(0)}%`;
	}

	/** One column per day in the window, whether or not that day ran.
	 *
	 * Per day rather than per candle, because the two series of one day are the
	 * same measurement of the same articles and a reader stepping right means
	 * the next day. Every series is printed at once, so comparing read against
	 * write costs no second hover. A day that ran nothing still gets a column,
	 * or an arrow key would step over it without saying so.
	 */
	const columns = $derived<DayReadout[]>(
		calendar.map((date, index) => {
			const day = byDate.get(date);
			return {
				x: x(index),
				date: shortDate(date),
				rows:
					day === undefined
						? [{ label: 'nothing ran', value: '', colour: '' }]
						: drawn.map((series) => ({
								label: series.label,
								value: readoutLine(day, series.key),
								colour: series.colour
							}))
			};
		})
	);
	const marks = $derived(readoutMarks(columns));
	/** The strip opens on the newest day, so it is never blank and never shifts
	 * the page as it fills. */
	const resting = $derived(columns.length === 0 ? null : columns[columns.length - 1]);
	const readout = $derived(selected === null ? resting : (columns[selected] ?? resting));
	const guide = $derived(selected === null ? null : (columns[selected]?.x ?? null));

	/** The span, said once, for a reader who cannot see the axis. The axis used
	 * to carry this as a single string and no per-day label at all. */
	const span = $derived(
		calendar.length === 0
			? ''
			: calendar.length === 1
				? shortDate(calendar[0])
				: `${shortDate(calendar[0])} to ${shortDate(calendar[calendar.length - 1])}`
	);
</script>

<h3 class="mt-6 text-[0.9375rem] font-semibold text-text">Model tokens per second</h3>

{#if ordered.length === 0}
	<!-- Said in words, not left blank. The timing trend directly above says so
	     when it has nothing; a chart that simply vanishes beside one that
	     explains itself reads as a chart that broke. -->
	<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-throughput="empty">
		We measured nothing in this window. Widen the window to look further back.
	</p>
{:else}
	<p class="mt-1 text-[0.8125rem] text-text-tertiary">
		<em>Read</em> is the model taking an article in, <em>write</em> is it producing the summary. Write
		is slower because it goes one token at a time. Each candle is one day: the line spans the slowest
		and fastest item, the box is the middle half, and the tick is the median. The axis starts at the
		slowest rate drawn, not at zero. A wide candle is a mixed day, not a fault -
		<a href={reference} class="text-accent hover:underline" rel="noreferrer">why the range is wide</a
		>.
	</p>

	<div class="relative mt-4 rounded-md border border-rule bg-surface p-3" data-throughput="chart">
		<!-- The measured element is this one, not the card: the card's padding and
		     border are not part of the width the chart draws into. -->
		<div use:observeWidth={(px) => (measured = px)}>
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<svg
				class="w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
				height={box.height}
				viewBox={`0 0 ${box.width} ${box.height}`}
				role="img"
				tabindex="0"
				aria-label={`Model tokens per second per day, ${span}, oldest day on the left`}
				data-throughput-days={calendar.length}
				data-throughput-first={calendar[0] ?? ''}
				data-throughput-last={calendar[calendar.length - 1] ?? ''}
				use:pointerReadout={{
					marks,
					width: box.width,
					onSelect: (index) => (selected = index)
				}}
			>
				{#if drawn.length > 0}
					<line
						x1={box.left}
						x2={box.right}
						y1={box.bottom}
						y2={box.bottom}
						stroke="var(--color-rule)"
					/>
					<line x1={box.left} x2={box.left} y1={box.top} y2={box.bottom} stroke="var(--color-rule)" />
					{#each y.ticks as tick (tick)}
						<text
							x={box.left - 4}
							y={y.scale(tick) + 3}
							text-anchor="end"
							fill="var(--color-text-tertiary)"
							font-size="10"
							data-throughput-tick={tick}
						>
							{tick}
						</text>
					{/each}
				{/if}

				<!-- The day the model changed, drawn on the boundary between the two
				     days rather than through either one's candles. A step in the trend
				     either lines up with a rule or it does not, which is the whole of
				     what this mark is for. -->
				{#each swaps as swap (swap.date)}
					<line
						x1={Math.max(box.left, x(swap.at) - step / 2)}
						x2={Math.max(box.left, x(swap.at) - step / 2)}
						y1={box.top}
						y2={box.bottom}
						stroke="var(--color-text-tertiary)"
						stroke-width="1"
						stroke-dasharray="3 3"
						data-throughput-swap={swap.date}
					>
						<title>{`Model changed from ${swap.from} to ${swap.to} on ${swap.date}.`}</title>
					</line>
				{/each}

				<!-- The column under the pointer, marked across both series, so a
				     comparison between read and write is read off one line. -->
				{#if guide !== null}
					<line
						x1={guide}
						x2={guide}
						y1={box.top}
						y2={box.bottom}
						stroke="var(--color-text-tertiary)"
						stroke-opacity="0.5"
						data-throughput="guide"
					/>
				{/if}

				{#each calendar as date, index (date)}
					{@const day = byDate.get(date)}
					{#if day}
						{#each drawn as series (series.key)}
							{@const band = day[series.key]}
							{@const cx = centre(index, series.key)}
							<g data-candle={series.key} data-date={date} data-model={day.model ?? ''}>
								<title>{caption(day, series.key)}</title>
								<line
									x1={cx}
									x2={cx}
									y1={y.scale(band.max)}
									y2={y.scale(band.min)}
									stroke={series.colour}
									stroke-width="1"
								/>
								<rect
									x={cx - candle / 2}
									y={y.scale(band.p75)}
									width={candle}
									height={Math.max(1, y.scale(band.p25) - y.scale(band.p75))}
									fill={series.colour}
									opacity="0.55"
								/>
								<line
									x1={cx - candle / 2 - 1}
									x2={cx + candle / 2 + 1}
									y1={y.scale(band.median)}
									y2={y.scale(band.median)}
									stroke={series.colour}
									stroke-width="1.5"
								/>
							</g>
						{/each}
					{/if}
				{/each}

				<!-- A date per column, thinned to `tickDensity` with both ends kept. It
				     used to be one span string for the whole axis, which left a spike
				     sitting between two dates it could equally have belonged to. -->
				{#each axis as label (label.index)}
					<text
						x={x(label.index)}
						y={box.bottom + 14}
						text-anchor={label.anchor}
						fill="var(--color-text-tertiary)"
						font-size="10"
						data-throughput-label={label.date}
					>
						{label.text}
					</text>
				{/each}
			</svg>
		</div>

		{#if readout}
			<!-- Below the plot, never over it, and the same strip every chart on this
			     console prints - see `ChartReadout.svelte` for the rules it holds. -->
			<ChartReadout
				{readout}
				name="throughput"
				maxShare={readoutMaxShare}
				resting={selected === null}
				restingNote=", the newest day"
				hint="Point at a day to read it. Left and Right step through the days, Escape returns to the newest."
			/>
		{/if}

		{#if newest}
			<ul class="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-[0.75rem] text-text-tertiary">
				{#each drawn as series (series.key)}
					<li class="flex items-center gap-2" data-series={series.label}>
						<span class="size-3 shrink-0 rounded-sm" style="background: {series.colour}"></span>
						{series.label}
						<span class="tabular-nums text-text-secondary">
							{rate(series.key === 'read' ? newest.readTps : newest.writeTps)}
						</span>
					</li>
				{/each}
				<!-- A cache statistic, not a series. Drawn as a line against a second y
				     axis until 2026-08-25, which invited a reader to correlate it with a
				     rate it shares no unit with. -->
				<li class="flex items-center gap-2" data-series="reused">
					prompt tokens reused
					<span class="tabular-nums text-text-secondary">{newest.cacheHitPct.toFixed(0)}%</span>
				</li>
				<!-- Only where a rule was actually drawn. A key to a mark that is not on
				     the chart is a reader looking for something that is not there. -->
				{#if swaps.length > 0}
					<li class="flex items-center gap-2" data-series="swap">
						<span
							class="h-0 w-3 shrink-0 border-t border-dashed border-text-tertiary"
							aria-hidden="true"
						></span>
						model changed
					</li>
				{/if}
			</ul>
			<p class="mt-2 text-[0.75rem] text-text-tertiary" data-throughput="verdict">
				{newest.date}, over the whole day: read {rate(newest.readTps)}, write {rate(newest.writeTps)},
				from {newest.items}
				{newest.items === 1 ? 'item' : 'items'} across {newest.runs.length}
				{newest.runs.length === 1 ? 'run' : 'runs'}.
					{#if swapped}
						<span data-throughput="swap"
							>{previous?.date} ran on {previous?.model} and this day ran on {newest.model}, so the
							two are not compared.</span
						>
					{:else if previous}
					Read is {shift(newest.readTps, previous.readTps)} and write is {shift(
						newest.writeTps,
						previous.writeTps
					)} on {previous.date}.
				{:else}
					One day so far. A second day gives it something to move against.
				{/if}
			</p>
		{/if}
	</div>
{/if}
