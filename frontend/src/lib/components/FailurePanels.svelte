<script lang="ts">
	/** Three stage panels, each answering "how often does this stage fail".
	 *
	 * The rate is printed in type as well as drawn. An SVG `<title>` does not
	 * fire on touch and does not survive the screenshot an operator pastes into
	 * an issue, so a chart whose only number is a tooltip has no number.
	 *
	 * The y domain is fixed at 0 to 100% and stays fixed. A rate over a known
	 * range is compared across panels and across days, so padding it to the
	 * drawn extent would break the comparison the panel exists for. Scaled to
	 * the window's own maximum, a 12% failure rate and a 90% one both filled the
	 * panel.
	 *
	 * A panel is the narrowest chart on the page - 163px measured at a 1057px
	 * window - and it used to declare a 360-unit `viewBox` into that space, so
	 * `font-size="10"` reached the screen at 4.5px. It draws in CSS pixels now,
	 * through the same frame as every other console chart.
	 */
	import { chartWidth, frame, linearAxis, MARGIN, observeWidth } from '$lib/charts/frame';
	import { failureSeries, type StageFailureSeries, type TelemetryRow } from '$lib/charts/series';
	import type { TimeWindow } from '$lib/charts/viewport';

	let {
		rows,
		window,
		minAttempts,
		height,
		width,
		selectedCode,
		onSelect
	}: {
		rows: TelemetryRow[];
		window: TimeWindow;
		minAttempts: number;
		/** The whole SVG, margins included. */
		height: number;
		/** The column the three panels share, until one has been measured. */
		width: number;
		selectedCode: string | null;
		onSelect: (code: string | null) => void;
	} = $props();

	/** The shared label column beside, and no tick row below: these panels label
	 * their window in type above the chart, so a date axis would say it twice. */
	const PANEL_MARGIN = { top: 8, right: 8, bottom: 8, left: MARGIN.left };

	/** The `gap-4` and `p-3` of the three-up row below, in pixels. */
	const ROW_GAP = 16;
	const PANEL_PADDING = 12;

	/** Nought to one. A rate is already on a known scale. */
	const DOMAIN = [0, 1];

	// One measurement for three panels: the grid gives every column the same
	// width at every breakpoint it has.
	let measured = $state<number | null>(null);

	const panelWidth = $derived(
		chartWidth(measured, Math.max(1, Math.round((width - ROW_GAP * 2) / 3) - PANEL_PADDING * 2))
	);
	const box = $derived(frame(panelWidth, height, PANEL_MARGIN));
	const axis = $derived(linearAxis(DOMAIN, [box.bottom, box.top]));

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
		return Math.max(1, box.bottom - axis.scale(day.rate));
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

	<!-- 380, not 320: the minimum is the TRACK, and each track spends padding and
	     a border before the chart inside it gets any. Measured 2026-08-29 at
	     1440px, a 320px minimum drew the plot at 298. -->
	<div class="auto-grid mt-4" style="--auto-grid-min: 380px" data-failure-panels>
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
					<div class="mt-3" use:observeWidth={(value) => (measured = value)}>
						<svg
							width={box.width}
							height={box.height}
							viewBox={`0 0 ${box.width} ${box.height}`}
							role="img"
							aria-label={`${entry.label} failure rate per day. ${headline(entry)}`}
							data-panel={entry.stage}
						>
							<line
								x1={box.left}
								x2={box.right}
								y1={box.bottom}
								y2={box.bottom}
								stroke="var(--color-rule)"
							/>
							<line
								x1={box.left}
								x2={box.left}
								y1={box.top}
								y2={box.bottom}
								stroke="var(--color-rule)"
							/>
							<text
								x={box.left - 4}
								y={box.top + 3.5}
								text-anchor="end"
								fill="var(--color-text-tertiary)"
								font-size="10"
							>
								{percent(axis.domain[1])}
							</text>
							<text
								x={box.left - 4}
								y={box.bottom + 3.5}
								text-anchor="end"
								fill="var(--color-text-tertiary)"
								font-size="10"
							>
								{percent(axis.domain[0])}
							</text>
							{#each entry.days as day, index (day.date)}
								{@const slot = box.innerWidth / entry.days.length}
								{@const h = barHeight(day)}
								{@const thin = day.attempts > 0 && day.attempts < minAttempts}
								<rect
									x={box.left + index * slot + 0.5}
									y={box.bottom - h}
									width={Math.max(1, slot - 1)}
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
					</div>
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
