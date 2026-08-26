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
	 * The chart draws through `frame.ts` in CSS pixels, so `font-size="10"` is
	 * ten pixels on screen. Its domain is the drawn extent rather than zero to
	 * the fastest item: a candle says where a rate is, and zero belongs on an
	 * axis only where the length of the mark carries the number. Measured on the
	 * published console 2026-08-25, zero-anchored, the read whisker occupied
	 * 17.5% of the plot height and the middle-half box 3.7%.
	 */
	import { chartWidth, frame, linearAxis, observeWidth } from '$lib/charts/frame';
	import { axisLabels, type LabelAlign } from '$lib/charts/run-history';
	import type { ThroughputDay } from '$lib/charts/series';
	import { daysInWindow } from '$lib/charts/viewport';
	import { shortDate } from '$lib/format';

	let {
		days,
		height,
		width,
		reference
	}: { days: ThroughputDay[]; height: number; width: number; reference: string } = $props();

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

	const axis = $derived(axisLabels(calendar));
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

	const ANCHOR: Record<LabelAlign, 'start' | 'middle' | 'end'> = {
		start: 'start',
		centre: 'middle',
		end: 'end'
	};

	function x(index: number): number {
		return calendar.length === 1 ? (box.left + box.right) / 2 : box.left + pad + index * step;
	}

	function centre(index: number, key: SeriesKey): number {
		return x(index) + (key === 'read' ? -offset : offset);
	}

	function rate(value: number): string {
		return `${value.toFixed(2)} tok/s`;
	}

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

	function shift(now: number, before: number): string {
		if (before <= 0) return 'level';
		const pct = ((now - before) / before) * 100;
		return `${pct >= 0 ? 'up' : 'down'} ${Math.abs(pct).toFixed(0)}%`;
	}
</script>

<h3 class="mt-6 text-[0.9375rem] font-semibold text-text">Model tokens per second</h3>
<p class="mt-1 text-[0.8125rem] text-text-tertiary">
	<em>Read</em> is the model taking an article in, <em>write</em> is it producing the summary. Writing
	is slower because it goes one token at a time. Each candle is one day: the line spans the slowest
	and fastest item, the box is the middle half, and the tick is the median. The axis starts at the
	slowest rate drawn, not at zero. A wide candle is a mixed day, not a fault -
	<a href={reference} class="text-accent hover:underline" rel="noreferrer">why the spread is wide</a
	>.
</p>

<div class="mt-4 rounded-md border border-rule bg-surface p-3" data-throughput="chart">
	<!-- The measured element is this one, not the card: the card's padding and
	     border are not part of the width the chart draws into. -->
	<div use:observeWidth={(px) => (measured = px)}>
		<svg
			class="w-full"
			height={box.height}
			viewBox={`0 0 ${box.width} ${box.height}`}
			role="img"
			aria-label="Model tokens per second per day, oldest day on the left"
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

			{#each calendar as date, index (date)}
				{@const day = byDate.get(date)}
				{#if day}
					{#each drawn as series (series.key)}
						{@const band = day[series.key]}
						{@const cx = centre(index, series.key)}
						<g data-candle={series.key} data-date={date}>
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

			<!-- One day is still a candle - five order statistics is a shape - but a
			     single column cannot carry a cadence, so it says which day it is. -->
			{#if calendar.length === 1}
				<text
					x={(box.left + box.right) / 2}
					y={box.height - 6}
					text-anchor="middle"
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-throughput="day"
				>
					{shortDate(calendar[0])}
				</text>
			{:else}
				{#each axis as label (label.column)}
					<text
						x={x(label.column - 1)}
						y={box.height - 6}
						text-anchor={ANCHOR[label.align]}
						fill="var(--color-text-tertiary)"
						font-size="10"
					>
						{label.text}
					</text>
				{/each}
			{/if}
		</svg>
	</div>

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
				prompt reused
				<span class="tabular-nums text-text-secondary">{newest.cacheHitPct.toFixed(0)}%</span>
			</li>
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
