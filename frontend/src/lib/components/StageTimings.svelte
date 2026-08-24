<script lang="ts">
	/** Is it getting slower? That is the only question this section is asked.
	 *
	 * The block used to be one group of four bars per day. At a 30-day window
	 * that is about 150 rows and no trend at all, which answers the question by
	 * making the operator hold thirty numbers in their head.
	 *
	 * The x axis is the calendar, not the list of days that have rows. A day
	 * with no census breaks the line rather than closing the gap, because "no
	 * data" and "no time spent" are different facts.
	 */
	import { axisLabels, type LabelAlign } from '$lib/charts/run-history';
	import type { StageTimingDay } from '$lib/charts/series';
	import { daysInWindow } from '$lib/charts/viewport';

	let { days, height }: { days: StageTimingDay[]; height: number } = $props();

	const STAGES = [
		{ key: 'fetchMs', label: 'fetch', colour: 'var(--band-low)' },
		{ key: 'extractMs', label: 'extract', colour: 'var(--band-medium)' },
		{ key: 'summarizeMs', label: 'summarize', colour: 'var(--color-accent)' },
		{ key: 'scoreMs', label: 'score', colour: 'var(--band-high)' }
	] as const;

	/** Room for the seconds labels, so a line never starts on top of one. */
	const PLOT_LEFT = 34;
	const PLOT_RIGHT = 360;

	const ordered = $derived([...days].sort((a, b) => a.date.localeCompare(b.date)));
	const calendar = $derived(
		ordered.length === 0
			? []
			: daysInWindow({
					start: ordered[0].date,
					end: ordered[ordered.length - 1].date
				})
	);
	const byDate = $derived(new Map(ordered.map((day) => [day.date, day])));
	const step = $derived((PLOT_RIGHT - PLOT_LEFT) / Math.max(1, calendar.length - 1));
	const worst = $derived(
		Math.max(1, ...ordered.flatMap((day) => STAGES.map((stage) => day[stage.key])))
	);
	const axis = $derived(axisLabels(calendar));
	const newest = $derived(ordered[ordered.length - 1] ?? null);

	const ANCHOR: Record<LabelAlign, 'start' | 'middle' | 'end'> = {
		start: 'start',
		centre: 'middle',
		end: 'end'
	};

	function x(index: number): number {
		return calendar.length === 1 ? (PLOT_LEFT + PLOT_RIGHT) / 2 : PLOT_LEFT + index * step;
	}

	function y(ms: number): number {
		return height - (ms / worst) * height;
	}

	/** Each unbroken stretch of days that has a census, so an absent day is a
	 * gap and never a straight line drawn through nothing. */
	function runs(key: (typeof STAGES)[number]['key']): string[] {
		const paths: string[] = [];
		let current: string[] = [];
		calendar.forEach((date, index) => {
			const day = byDate.get(date);
			if (day) {
				current.push(`${x(index)},${y(day[key])}`);
			} else if (current.length > 0) {
				paths.push(current.join(' '));
				current = [];
			}
		});
		if (current.length > 0) paths.push(current.join(' '));
		return paths;
	}

	function seconds(ms: number): string {
		return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`;
	}
</script>

<h2 class="mt-10 text-[1.0625rem] font-semibold text-text">Median seconds per item, by stage</h2>
<p class="mt-1 text-[0.8125rem] text-text-tertiary">
	Median, not mean: one very slow host would otherwise describe the whole day. Only
	<em>summarize</em> moves when the model changes - the rest is the open web and our own extractor.
</p>

<div class="mt-4 rounded-md border border-rule bg-surface p-3" data-timing="chart">
	<svg
		class="w-full overflow-visible"
		height={height + 26}
		viewBox={`0 0 ${PLOT_RIGHT} ${height + 26}`}
		role="img"
		aria-label="Median seconds per item by stage, oldest day on the left"
	>
		<line x1={PLOT_LEFT} x2={PLOT_RIGHT} y1={height} y2={height} stroke="var(--color-rule)" />
		<line x1={PLOT_LEFT} x2={PLOT_LEFT} y1="0" y2={height} stroke="var(--color-rule)" />
		<text
			x={PLOT_LEFT - 4}
			y="9"
			text-anchor="end"
			fill="var(--color-text-tertiary)"
			font-size="10"
		>
			{seconds(worst)}
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

		{#each STAGES as stage (stage.key)}
			{#if calendar.length === 1}
				{@const only = byDate.get(calendar[0])}
				{#if only}
					<circle cx={x(0)} cy={y(only[stage.key])} r="3.5" fill={stage.colour} />
				{/if}
			{:else}
				{#each runs(stage.key) as path, index (`${stage.key}-${index}`)}
					<polyline
						points={path}
						fill="none"
						stroke={stage.colour}
						stroke-width="1.5"
						stroke-linejoin="round"
					/>
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
			{#each STAGES as stage (stage.key)}
				<li class="flex items-center gap-2" data-stage={stage.label}>
					<span class="size-3 shrink-0 rounded-sm" style="background: {stage.colour}"></span>
					{stage.label}
					<span class="tabular-nums text-text-secondary">{seconds(newest[stage.key])}</span>
				</li>
			{/each}
		</ul>
		<p class="mt-2 text-[0.75rem] text-text-tertiary">
			Values are the newest day on record, {newest.date}.
		</p>
	{/if}
</div>
