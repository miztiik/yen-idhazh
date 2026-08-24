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
	 */
	import { axisLabels, type LabelAlign } from '$lib/charts/run-history';
	import type { ThroughputDay } from '$lib/charts/series';
	import { daysInWindow } from '$lib/charts/viewport';

	let {
		days,
		height,
		reference
	}: { days: ThroughputDay[]; height: number; reference: string } = $props();

	const SERIES = [
		{ key: 'read', label: 'read', colour: 'var(--color-accent)' },
		{ key: 'write', label: 'write', colour: 'var(--color-text)' }
	] as const;

	/** Room for the tokens-per-second labels on the left and the percentage on
	 * the right, so a candle never lands on top of one. */
	const PLOT_LEFT = 30;
	const PLOT_RIGHT = 330;
	const CANVAS = 360;

	const ordered = $derived([...days].sort((a, b) => a.date.localeCompare(b.date)));
	const calendar = $derived(
		ordered.length === 0
			? []
			: daysInWindow({ start: ordered[0].date, end: ordered[ordered.length - 1].date })
	);
	const byDate = $derived(new Map(ordered.map((day) => [day.date, day])));
	const step = $derived((PLOT_RIGHT - PLOT_LEFT) / Math.max(1, calendar.length - 1));
	const fastest = $derived(Math.max(1, ...ordered.flatMap((day) => [day.read.max, day.write.max])));
	const axis = $derived(axisLabels(calendar));
	const newest = $derived(ordered[ordered.length - 1] ?? null);
	const previous = $derived(ordered.length > 1 ? ordered[ordered.length - 2] : null);

	/** Candles thin as the window widens, so 60 days do not overlap into a smear. */
	const width = $derived(Math.max(2, Math.min(6, step * 0.34)));
	const offset = $derived(width * 0.62);

	const ANCHOR: Record<LabelAlign, 'start' | 'middle' | 'end'> = {
		start: 'start',
		centre: 'middle',
		end: 'end'
	};

	function x(index: number): number {
		return calendar.length === 1 ? (PLOT_LEFT + PLOT_RIGHT) / 2 : PLOT_LEFT + index * step;
	}

	function y(tps: number): number {
		return height - (tps / fastest) * height;
	}

	function centre(index: number, key: (typeof SERIES)[number]['key']): number {
		return x(index) + (key === 'read' ? -offset : offset);
	}

	/** Each unbroken stretch of days that has a census. An absent day breaks the
	 * line rather than drawing through nothing - no data and no reuse are
	 * different facts. */
	const reuseRuns = $derived.by(() => {
		const paths: string[] = [];
		let current: string[] = [];
		calendar.forEach((date, index) => {
			const day = byDate.get(date);
			if (day) {
				current.push(`${x(index)},${height - (day.cacheHitPct / 100) * height}`);
			} else if (current.length > 0) {
				paths.push(current.join(' '));
				current = [];
			}
		});
		if (current.length > 0) paths.push(current.join(' '));
		return paths;
	});

	function rate(value: number): string {
		return `${value.toFixed(2)} tok/s`;
	}

	function caption(day: ThroughputDay, key: (typeof SERIES)[number]['key']): string {
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

<h2 class="mt-10 text-[1.0625rem] font-semibold text-text">Model tokens per second</h2>
<p class="mt-1 text-[0.8125rem] text-text-tertiary">
	<em>Read</em> is the model taking an article in, <em>write</em> is it producing the summary. Writing
	is slower because it goes one token at a time. Each candle is one day: the line spans the slowest
	and fastest item, the box is the middle half, and the tick is the median. A wide candle is a mixed
	day, not a fault -
	<a href={reference} class="text-accent hover:underline" rel="noreferrer">why the spread is wide</a
	>.
</p>

<div class="mt-4 rounded-md border border-rule bg-surface p-3" data-throughput="chart">
	<svg
		class="w-full overflow-visible"
		height={height + 26}
		viewBox={`0 0 ${CANVAS} ${height + 26}`}
		role="img"
		aria-label="Model tokens per second per day, oldest day on the left"
	>
		<line x1={PLOT_LEFT} x2={PLOT_RIGHT} y1={height} y2={height} stroke="var(--color-rule)" />
		<line x1={PLOT_LEFT} x2={PLOT_LEFT} y1="0" y2={height} stroke="var(--color-rule)" />
		<line x1={PLOT_RIGHT} x2={PLOT_RIGHT} y1="0" y2={height} stroke="var(--color-rule)" />
		<text x={PLOT_LEFT - 4} y="9" text-anchor="end" fill="var(--color-text-tertiary)" font-size="10">
			{fastest.toFixed(0)}
		</text>
		<text
			x={PLOT_LEFT - 4}
			y={height}
			text-anchor="end"
			fill="var(--color-text-tertiary)"
			font-size="10"
		>
			0
		</text>
		<text x={PLOT_RIGHT + 4} y="9" fill="var(--color-text-tertiary)" font-size="10">100%</text>
		<text x={PLOT_RIGHT + 4} y={height} fill="var(--color-text-tertiary)" font-size="10">0</text>

		{#each reuseRuns as path, index (`reuse-${index}`)}
			<polyline
				points={path}
				fill="none"
				stroke="var(--color-text-tertiary)"
				stroke-width="1"
				stroke-dasharray="2 3"
			/>
		{/each}

		{#each calendar as date, index (date)}
			{@const day = byDate.get(date)}
			{#if day}
				{#each SERIES as series (series.key)}
					{@const band = day[series.key]}
					{@const cx = centre(index, series.key)}
					<g data-candle={series.key} data-date={date}>
						<title>{caption(day, series.key)}</title>
						<line
							x1={cx}
							x2={cx}
							y1={y(band.max)}
							y2={y(band.min)}
							stroke={series.colour}
							stroke-width="1"
						/>
						<rect
							x={cx - width / 2}
							y={y(band.p75)}
							width={width}
							height={Math.max(1, y(band.p25) - y(band.p75))}
							fill={series.colour}
							opacity="0.55"
						/>
						<line
							x1={cx - width / 2 - 1}
							x2={cx + width / 2 + 1}
							y1={y(band.median)}
							y2={y(band.median)}
							stroke={series.colour}
							stroke-width="1.5"
						/>
					</g>
				{/each}
			{/if}
		{/each}

		{#each axis as label (label.column)}
			<text
				x={x(label.column - 1)}
				y={height + 16}
				text-anchor={ANCHOR[label.align]}
				fill="var(--color-text-tertiary)"
				font-size="10"
			>
				{label.text}
			</text>
		{/each}
	</svg>

	{#if newest}
		<ul class="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-[0.75rem] text-text-tertiary">
			{#each SERIES as series (series.key)}
				<li class="flex items-center gap-2" data-series={series.label}>
					<span class="size-3 shrink-0 rounded-sm" style="background: {series.colour}"></span>
					{series.label}
					<span class="tabular-nums text-text-secondary">
						{rate(series.key === 'read' ? newest.readTps : newest.writeTps)}
					</span>
				</li>
			{/each}
			<li class="flex items-center gap-2" data-series="reused">
				<span class="h-0 w-3 shrink-0 border-t border-dashed border-text-tertiary"></span>
				prompt reused
				<span class="tabular-nums text-text-secondary">{newest.cacheHitPct.toFixed(0)}%</span>
			</li>
		</ul>
		<p class="mt-2 text-[0.75rem] text-text-tertiary" data-throughput="verdict">
			{newest.date}, over the whole day: read {rate(newest.readTps)}, write {rate(newest.writeTps)},
			from {newest.items}
			{newest.items === 1 ? 'item' : 'items'} across {newest.runs.length}
			{newest.runs.length === 1 ? 'run' : 'runs'}.
			{#if previous}
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
