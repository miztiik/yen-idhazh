<script lang="ts">
	/** Three stage panels, each answering "how often does this stage fail".
	 *
	 * The rate is printed in type as well as drawn. An SVG `<title>` does not
	 * fire on touch and does not survive the screenshot an operator pastes into
	 * an issue, so a chart whose only number is a tooltip has no number.
	 *
	 * The y domain is fixed at 0 to 100%. Scaled to the window's own maximum, a
	 * single day in view normalised its bar to itself, so a 12% failure rate and
	 * a 90% one both filled the panel.
	 */
	import { failureSeries, type StageFailureSeries, type TelemetryRow } from '$lib/charts/series';
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

	/** Room for the y labels, so a bar never starts on top of "100%". */
	const PLOT_LEFT = 30;
	const PLOT_RIGHT = 360;

	const series = $derived(failureSeries(rows, window));
	const codes = $derived(
		[
			...new Set(
				series
					.flatMap((entry) => entry.days.flatMap((day) => Object.keys(day.codes)))
					.filter(Boolean)
			)
		].sort()
	);
	const anyThin = $derived(
		series.some((entry) => entry.days.some((day) => day.attempts > 0 && day.attempts < minAttempts))
	);

	function totals(entry: StageFailureSeries): { attempts: number; failures: number } {
		return entry.days.reduce(
			(sum, day) => ({
				attempts: sum.attempts + day.attempts,
				failures: sum.failures + day.failures
			}),
			{ attempts: 0, failures: 0 }
		);
	}

	function percent(rate: number): string {
		const pct = rate * 100;
		if (pct > 0 && pct < 1) return '<1%';
		return `${Math.round(pct)}%`;
	}

	/** The whole panel in one sentence, which is what gets read and screenshotted. */
	function headline(entry: StageFailureSeries): string {
		const { attempts, failures } = totals(entry);
		if (attempts === 0) return 'No rows in this window.';
		return `${percent(failures / attempts)} failed, ${failures} of ${attempts}.`;
	}

	function barHeight(day: StageFailureSeries['days'][number]): number {
		if (day.rate === null || day.rate === 0) return 0;
		return Math.max(1, day.rate * height);
	}
</script>

<section>
	<div class="flex flex-wrap items-baseline justify-between gap-3">
		<div>
			<h2 class="text-[1.0625rem] font-semibold text-text">Failure rate</h2>
			<p class="mt-1 text-[0.8125rem] text-text-tertiary">
				Three stage panels, one bar per day, on a fixed 0 to 100% scale.
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
					<p class="mt-1 text-[0.875rem] text-text-secondary" data-panel-rate={entry.stage}>
						{headline(entry)}
					</p>
					<p class="mt-0.5 text-[0.75rem] text-text-tertiary">{window.start} to {window.end}</p>
				</div>
				<!-- A chart of one value is a rectangle. The sentence above is the panel. -->
				{#if entry.days.length > 1}
					<svg
						class="mt-3 w-full overflow-visible"
						height={height + 26}
						viewBox={`0 0 ${PLOT_RIGHT} ${height + 26}`}
						role="img"
						aria-label={`${entry.label} failure rate per day. ${headline(entry)}`}
						data-panel={entry.stage}
					>
						<line x1={PLOT_LEFT} x2={PLOT_RIGHT} y1={height} y2={height} stroke="var(--color-rule)" />
						<line x1={PLOT_LEFT} x2={PLOT_LEFT} y1="0" y2={height} stroke="var(--color-rule)" />
						<line
							x1={PLOT_LEFT}
							x2={PLOT_RIGHT}
							y1={height / 2}
							y2={height / 2}
							stroke="var(--color-rule)"
							stroke-dasharray="2 4"
						/>
						<text
							x={PLOT_LEFT - 4}
							y="9"
							text-anchor="end"
							fill="var(--color-text-tertiary)"
							font-size="10"
						>
							100%
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
						{#each entry.days as day, index (day.date)}
							{@const width = (PLOT_RIGHT - PLOT_LEFT) / entry.days.length}
							{@const x = PLOT_LEFT + index * width + 1}
							{@const h = barHeight(day)}
							{@const thin = day.attempts > 0 && day.attempts < minAttempts}
							<rect
								x={x}
								y={height - h}
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
					</svg>
				{/if}
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
								title={selectedCode === code ? `Stop filtering by ${code}` : `Show only ${code}`}
								aria-label={selectedCode === code ? `Stop filtering by ${code}` : `Show only ${code}`}
								aria-pressed={selectedCode === code}
								onclick={() => onSelect(selectedCode === code ? null : code)}
							>
								{code} {count}
							</button>
						{/if}
					{/each}
				</div>
			</div>
		{/each}
	</div>

	{#if anyThin}
		<p class="mt-2 text-[0.75rem] text-text-tertiary">
			Dashed days had fewer than {minAttempts} attempts.
		</p>
	{/if}
</section>
