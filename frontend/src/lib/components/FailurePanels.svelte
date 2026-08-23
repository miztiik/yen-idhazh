<script lang="ts">
	import {
		failureSeries,
		type StageFailureSeries,
		type TelemetryRow
	} from '$lib/charts/series';
	import type { TimeWindow } from '$lib/charts/viewport';

	let {
		rows,
		window,
		minAttempts,
		height,
		selectedCode,
		onSelect
	}: {
		rows: TelemetryRow[];
		window: TimeWindow;
		minAttempts: number;
		height: number;
		selectedCode: string | null;
		onSelect: (code: string | null) => void;
	} = $props();

	const series = $derived(failureSeries(rows, window));
	const maxRate = $derived(Math.max(0.01, ...series.flatMap((entry) => entry.days.map((day) => day.rate ?? 0))));
	const codes = $derived(
		[
			...new Set(
				series.flatMap((entry) => entry.days.flatMap((day) => Object.keys(day.codes))).filter(Boolean)
			)
		].sort()
	);

	function top(day: StageFailureSeries['days'][number]): number {
		if (day.rate === null) return height;
		return height - (day.rate / maxRate) * height;
	}

	function barHeight(day: StageFailureSeries['days'][number]): number {
		if (day.rate === null) return 0;
		return Math.max(1, height - top(day));
	}
</script>

<section>
	<div class="flex flex-wrap items-baseline justify-between gap-3">
		<div>
			<h2 class="text-[1.0625rem] font-semibold text-text">Failure rate</h2>
			<p class="mt-1 text-[0.8125rem] text-text-tertiary">
				Three stage panels. The rate is primary; the title gives failures over attempts.
			</p>
		</div>
		{#if selectedCode}
			<button
				type="button"
				class="rounded-full border border-rule px-3 py-1 text-[0.75rem] text-text-secondary"
				onclick={() => onSelect(null)}
			>
				Clear {selectedCode}
			</button>
		{/if}
	</div>

	<div class="mt-4 grid gap-4 sm:grid-cols-3" data-failure-panels>
		{#each series as entry (entry.stage)}
			<div class="rounded-md border border-rule bg-surface p-3">
				<div>
					<h3 class="text-[0.875rem] font-semibold text-text">{entry.label}</h3>
					<p class="mt-1 text-[0.75rem] text-text-tertiary">{window.start} to {window.end}</p>
				</div>
				<svg
					class="mt-3 w-full overflow-visible"
					height={height + 26}
					viewBox={`0 0 360 ${height + 26}`}
					role="img"
					aria-label={`${entry.label} failures`}
					data-panel={entry.stage}
				>
					<line x1="0" x2="360" y1={height} y2={height} stroke="var(--color-rule)" />
					<line x1="0" x2="0" y1="0" y2={height} stroke="var(--color-rule)" />
					{#if entry.days.every((day) => day.attempts === 0)}
						<line
							x1="0"
							x2="360"
							y1={height / 2}
							y2={height / 2}
							stroke="var(--color-text-tertiary)"
							stroke-dasharray="4 4"
						/>
						<text x="8" y={height / 2 - 8} fill="var(--color-text-tertiary)" font-size="12">
							No rows in this window
						</text>
					{:else}
						{#each entry.days as day, index (day.date)}
							{@const width = 360 / Math.max(1, entry.days.length)}
							{@const x = index * width + 1}
							{@const h = barHeight(day)}
							{@const y = height - h}
							{@const thin = day.attempts > 0 && day.attempts < minAttempts}
							<rect
								x={x}
								y={y}
								width={Math.max(1, width - 2)}
								height={h}
								fill={day.failures > 0 ? 'var(--band-low)' : 'var(--color-text)'}
								fill-opacity={day.failures > 0 ? 0.9 : 0.25}
								stroke={thin ? 'var(--color-text)' : 'none'}
								stroke-dasharray={thin ? '3 2' : undefined}
							>
								<title>{day.date}: {day.failures}/{day.attempts} failed</title>
							</rect>
						{/each}
					{/if}
				</svg>
				<div class="mt-2 flex flex-wrap gap-2">
					{#each codes as code (code)}
						{@const count = entry.days.reduce((total, day) => total + (day.codes[code] ?? 0), 0)}
						{#if count > 0}
							<button
								type="button"
								class="rounded-full border px-2 py-1 text-[0.6875rem]"
								class:border-accent={selectedCode === code}
								class:border-rule={selectedCode !== code}
								class:text-accent={selectedCode === code}
								class:text-text-secondary={selectedCode !== code}
								onclick={() => onSelect(code)}
							>
								{code} {count}
							</button>
						{/if}
					{/each}
				</div>
			</div>
		{/each}
	</div>
</section>
