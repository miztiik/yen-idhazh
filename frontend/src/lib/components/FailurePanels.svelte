<script lang="ts">
	/** One chart: how often each stage fails, against the volume it was measured
	 * on.
	 *
	 * It was three panels, one per stage, each carrying a sentence and a row of
	 * bars on a fixed 0 to 100% scale. Two things were wrong with that. The
	 * split cost every panel its width - three at 492px on a 1600px frame, with
	 * two text nodes each - and a rate on its own cannot be acted on: a stage
	 * that failed both of the two items it was given drew the same full bar as
	 * an outage.
	 *
	 * The columns are the day's items, split by where each one stopped, so the
	 * height of a column IS the volume. The lines are each stage's failure
	 * share, on a right-hand axis fixed at 0 to 100% - fixed because a rate over
	 * a known range is compared across stages and across days, and scaling it to
	 * the window's own maximum made a 12% rate and a 90% one the same height.
	 *
	 * Every rate is printed in type as well as drawn, with its denominator in
	 * the same sentence. An SVG `<title>` does not fire on touch and does not
	 * survive the screenshot an operator pastes into an issue, so a chart whose
	 * only number is a tooltip has no number.
	 *
	 * A stage under `console.min_attempts_for_rate` prints its counts and no
	 * rate at all, and its line breaks rather than drawing a share nobody
	 * measured. The same knob decides the source-cut table's share, so two
	 * shares on one page cannot disagree about when a denominator is too thin.
	 */
	import {
		chartWidth,
		frame,
		linearAxis,
		observeWidth,
		pointerReadout,
		readoutMarks,
		type DayReadout
	} from '$lib/charts/frame';
	import ChartReadout from './ChartReadout.svelte';
	import { failureLoad, type FailurePoint, type FailureStage } from '$lib/charts/glance';
	import { failureSeries, grouped, type TelemetryRow } from '$lib/charts/series';
	import { daysBetween, type TimeWindow } from '$lib/charts/viewport';

	let {
		rows,
		window,
		minAttempts,
		height,
		width,
		selectedCode,
		onSelect,
		readoutMaxShare = 0.33
	}: {
		rows: TelemetryRow[];
		window: TimeWindow;
		minAttempts: number;
		/** The whole SVG, margins included. */
		height: number;
		/** The column, until the element has been measured. */
		width: number;
		selectedCode: string | null;
		onSelect: (code: string | null) => void;
		/** `chart.readout_max_share`. */
		readoutMaxShare?: number;
	} = $props();

	/** Room on the right for the percent axis this chart added, on the left for
	 * an item count that reaches four digits, and above for the two axis titles -
	 * a chart with two y scales has to say which is which. */
	const CHART_MARGIN = { top: 26, right: 46, bottom: 26, left: 42 };

	/** Nought to one. A rate is already on a known scale, so the axis is fixed
	 * and stays fixed. */
	const RATE_TICKS = [0, 0.25, 0.5, 0.75, 1];

	/** As many date labels as fit without overlapping at the narrowest window
	 * this chart is drawn in. */
	const DATE_LABELS = 6;

	let measured = $state<number | null>(null);

	const windowDays = $derived(daysBetween(window.start, window.end));
	const series = $derived(failureSeries(rows, window));
	const load = $derived(failureLoad(series, minAttempts));

	const box = $derived(frame(chartWidth(measured, width), height, CHART_MARGIN));
	const volume = $derived(linearAxis([0, load.peak], [box.bottom, box.top]));
	// A count of items has no half. A domain of two draws ticks at 0.5, and a
	// console cell never prints a decimal.
	const volumeTicks = $derived(volume.ticks.filter((tick) => Number.isInteger(tick)));
	const slot = $derived(box.innerWidth / Math.max(1, load.columns.length));
	const barWidth = $derived(Math.max(1, Math.min(26, slot - 2)));

	const codes = $derived(
		[...new Set(series.flatMap((s) => s.days.flatMap((d) => Object.keys(d.codes))))]
			.filter(Boolean)
			.map((code) => ({
				code,
				count: series.reduce(
					(total, s) => total + s.days.reduce((sum, d) => sum + (d.codes[code] ?? 0), 0),
					0
				)
			}))
			.filter((entry) => entry.count > 0)
			.sort((a, b) => b.count - a.count || a.code.localeCompare(b.code))
	);

	const anyLowSample = $derived(load.stages.some((stage) => stage.lowSample));
	// The band only draws where the run listed an item it never fetched, so the
	// key only names it there. A legend entry for a band nobody can see is a
	// reader hunting the chart for something that is not on it.
	const anySkipped = $derived(
		load.columns.some((column) => column.bands.some((band) => band.key === 'skipped'))
	);

	function centre(index: number): number {
		return box.left + index * slot + slot / 2;
	}

	function rateY(rate: number): number {
		return box.bottom - rate * box.innerHeight;
	}

	/** Whole percent, and `<1%` where a real measurement rounds away. A `0%`
	 * there would say the stage never failed. */
	function percent(rate: number): string {
		const pct = rate * 100;
		if (pct > 0 && pct < 1) return '<1%';
		return `${Math.round(pct)}%`;
	}

	/** The whole stage in one sentence: what failed, and what it is out of.
	 *
	 * Never a bare percentage. A share with no denominator beside it invites a
	 * trend that is not there, which is the defect this row exists to fix.
	 */
	function sentence(stage: FailureStage): string {
		if (stage.reached === 0) {
			return `Nothing reached this stage in these ${windowDays} days.`;
		}
		if (stage.rate === null) {
			return `${grouped(stage.failures)} failed of the ${grouped(stage.reached)} that reached it. Too few to give a rate - ${minAttempts} needed.`;
		}
		return `${percent(stage.rate)} failed, ${grouped(stage.failures)} of the ${grouped(stage.reached)} that reached it.`;
	}

	/** The line, broken wherever the rate is unknown.
	 *
	 * A run of one point is a dot rather than a line, and the marks below draw
	 * every point, so nothing is lost by keeping segments to two or more here.
	 */
	function segments(points: readonly FailurePoint[]): string[] {
		const runs: string[][] = [];
		let current: string[] = [];
		points.forEach((point, index) => {
			if (point.rate === null) {
				if (current.length > 1) runs.push(current);
				current = [];
				return;
			}
			current.push(`${centre(index)},${rateY(point.rate)}`);
		});
		if (current.length > 1) runs.push(current);
		return runs.map((run) => run.join(' '));
	}

	/** Which days get a date under them. The first and the last always, so the
	 * span of the chart can be read off the chart. */
	function labelled(index: number): boolean {
		const step = Math.max(1, Math.ceil(load.columns.length / DATE_LABELS));
		return index === 0 || index === load.columns.length - 1 || index % step === 0;
	}

	function below(index: number, band: number): number {
		return load.columns[index].bands
			.slice(0, band)
			.reduce((sum, entry) => sum + entry.value, 0);
	}

	function bandTop(index: number, band: number): number {
		return volume.scale(below(index, band) + load.columns[index].bands[band].value);
	}

	function bandHeight(index: number, band: number): number {
		const start = below(index, band);
		const end = start + load.columns[index].bands[band].value;
		return Math.max(1, volume.scale(start) - volume.scale(end));
	}

	function bandTitle(index: number, band: number): string {
		const column = load.columns[index];
		const entry = column.bands[band];
		const what =
			entry.key === 'finished'
				? 'finished'
				: entry.key === 'skipped'
					? 'were never fetched'
					: `failed at ${entry.label}`;
		return `${column.date}: ${grouped(entry.value)} of ${grouped(column.planned)} ${what}`;
	}

	const headline = $derived(
		load.empty
			? `No item was planned in these ${windowDays} days.`
			: `Failure rate against volume, ${windowDays} days. ${load.stages
					.map((stage) => `${stage.label}: ${sentence(stage)}`)
					.join(' ')}`
	);

	/** The column a pointer or an arrow key has picked. */
	let selected = $state<number | null>(null);

	/** Where the day's items stopped, and every stage's rate, at one column. Two
	 * quantities on two axes is the shape where reading them together by eye is
	 * hardest, and it is the whole reason both are drawn. */
	const columns = $derived<DayReadout[]>(
		load.columns.map((column, index) => ({
			x: centre(index),
			date: column.date,
			rows: [
				...column.bands.map((band) => ({
					label: band.key === 'finished' ? 'Finished' : band.label,
					value: grouped(band.value),
					colour: `var(${band.token})`
				})),
				...load.stages.map((stage) => ({
					label: `${stage.label} rate`,
					value:
						stage.points[index]?.rate == null ? 'too few' : percent(stage.points[index].rate ?? 0),
					colour: `var(${stage.token})`
				}))
			]
		}))
	);
	const marks = $derived(readoutMarks(columns));
	const at = $derived(selected ?? (columns.length === 0 ? null : columns.length - 1));
	const readout = $derived(at === null ? null : (columns[at] ?? null));
	const guide = $derived(selected === null ? null : (columns[selected]?.x ?? null));
</script>

<section
	data-failure-panels
	data-windowed="failure-rate"
	data-window-days={windowDays}
	aria-label="Failure rate against volume, over {windowDays} days"
>
	<div class="flex flex-wrap items-baseline justify-between gap-3">
		<div>
			<h2 class="text-[1.0625rem] font-semibold text-text">Failure rate against volume</h2>
			<p class="mt-1 text-[0.8125rem] text-text-tertiary">
				Columns are the day's items, split by where each one stopped. Lines are each stage's failure
				share on the right axis, so a high rate on a short column reads as the thin sample it is.
			</p>
		</div>
		{#if selectedCode}
			<button
				type="button"
				class="min-h-11 rounded-full border border-rule px-3 py-1 text-[0.75rem] text-text-secondary"
				onclick={() => onSelect(null)}
			>
				Clear {selectedCode}
			</button>
		{/if}
	</div>

	{#if load.empty}
		<p class="mt-4 text-[0.9375rem] text-text-secondary" data-failure-empty>
			No item was planned in these {windowDays} days, so there is no rate to give and no volume to
			give it against.
		</p>
	{:else}
		<!-- A figure, because the frame oracle scans `figure svg` for a chart drawn
		     too narrow to read a value off - and the three panels this replaced are
		     what that bound was written against. Outside a figure the new chart
		     would leave the check with nothing to measure. -->
		<figure
			class="mt-4"
			data-readout-columns={columns.length}
			use:observeWidth={(value) => (measured = value)}
		>
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<svg
				class="focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
				width={box.width}
				height={box.height}
				viewBox={`0 0 ${box.width} ${box.height}`}
				role="img"
				tabindex="0"
				aria-label={headline}
				data-failure-chart
				use:pointerReadout={{
					marks,
					width: box.width,
					onSelect: (index) => (selected = index)
				}}
			>
				{#if guide !== null}
					<line
						x1={guide}
						x2={guide}
						y1={box.top}
						y2={box.bottom}
						stroke="var(--color-text-tertiary)"
						stroke-opacity="0.5"
						data-failure-chart="guide"
					/>
				{/if}
				<text x="0" y="11" fill="var(--color-text-tertiary)" font-size="11">Items</text>
				<text
					x={box.width}
					y="11"
					text-anchor="end"
					fill="var(--color-text-tertiary)"
					font-size="11">Failure rate</text
				>

				{#each volumeTicks as tick (tick)}
					<line
						x1={box.left}
						x2={box.right}
						y1={volume.scale(tick)}
						y2={volume.scale(tick)}
						stroke="var(--chart-grid)"
					/>
					<text
						x={box.left - 5}
						y={volume.scale(tick) + 3.5}
						text-anchor="end"
						fill="var(--color-text-tertiary)"
						font-size="10">{grouped(tick)}</text
					>
				{/each}

				{#each RATE_TICKS as tick (tick)}
					<text
						x={box.right + 5}
						y={rateY(tick) + 3.5}
						text-anchor="start"
						fill="var(--color-text-tertiary)"
						font-size="10">{Math.round(tick * 100)}%</text
					>
				{/each}

				<line x1={box.left} x2={box.left} y1={box.top} y2={box.bottom} stroke="var(--chart-axis)" />
				<line
					x1={box.right}
					x2={box.right}
					y1={box.top}
					y2={box.bottom}
					stroke="var(--chart-axis)"
				/>
				<line
					x1={box.left}
					x2={box.right}
					y1={box.bottom}
					y2={box.bottom}
					stroke="var(--chart-axis)"
				/>

				{#each load.columns as column, index (column.date)}
					{#each column.bands as band, position (band.key)}
						<rect
							x={centre(index) - barWidth / 2}
							y={bandTop(index, position)}
							width={barWidth}
							height={bandHeight(index, position)}
							fill="var({band.token})"
							data-band={band.key}
						>
							<title>{bandTitle(index, position)}</title>
						</rect>
					{/each}
					{#if labelled(index)}
						<text
							x={centre(index)}
							y={box.bottom + 14}
							text-anchor="middle"
							fill="var(--color-text-tertiary)"
							font-size="10">{column.date.slice(5)}</text
						>
					{/if}
				{/each}

				{#each load.stages as stage (stage.stage)}
					{#each segments(stage.points) as points (points)}
						<polyline
							{points}
							fill="none"
							stroke="var({stage.token})"
							stroke-width="1.5"
							data-rate-line={stage.stage}
						/>
					{/each}
					{#each stage.points as point, index (point.date)}
						{#if point.rate !== null}
							<circle
								cx={centre(index)}
								cy={rateY(point.rate)}
								r="2"
								fill="var({stage.token})"
								data-rate-mark={stage.stage}
							>
								<title
									>{point.date}: {stage.label} failed {percent(point.rate)} of the {grouped(
										point.reached
									)} that reached it</title
								>
							</circle>
						{/if}
					{/each}
				{/each}
			</svg>
			<!-- Below the plot, never over it, and the same strip every chart on
			     this console prints - see `ChartReadout.svelte` for the rules. -->
			<ChartReadout
				{readout}
				name="failure-rate"
				maxShare={readoutMaxShare}
				resting={selected === null}
				restingNote=", the newest day"
				hint="Point at a day to read where its items stopped and every stage's rate. Left and Right step through the days, Escape returns to the newest."
			/>
			<figcaption class="mt-2 text-[0.75rem] text-text-tertiary" data-failure-key>
				The grey ground under each column is the work that finished{#if anySkipped}, and the slate
					band on top of it is what the run listed and never fetched{/if}. The three coloured bands
				are the failures, in the colours the stages carry below.
			</figcaption>
		</figure>

		<ul class="mt-3 grid gap-2 sm:grid-cols-3" data-failure-readout>
			{#each load.stages as stage (stage.stage)}
				<li
					class="rounded-md border border-rule bg-surface p-3"
					data-failure-stage={stage.stage}
					data-stage-reached={stage.reached}
					data-stage-failed={stage.failures}
					data-stage-low-sample={stage.rate === null ? 'true' : 'false'}
				>
					<h3 class="flex items-center gap-2 text-[0.875rem] font-semibold text-text">
						<span
							class="inline-block h-2.5 w-2.5 rounded-full"
							style="background: var({stage.token})"
							aria-hidden="true"
						></span>
						{stage.label}
					</h3>
					<p class="mt-1 text-[0.875rem] text-text-secondary" data-panel-rate={stage.stage}>
						{sentence(stage)}
					</p>
				</li>
			{/each}
		</ul>

		{#if codes.length > 0}
			<div class="mt-3 flex flex-wrap gap-2">
				{#each codes as entry (entry.code)}
					<button
						type="button"
						class="min-h-11 rounded-full border px-3 py-1 text-[0.6875rem]"
						class:border-accent={selectedCode === entry.code}
						class:border-rule={selectedCode !== entry.code}
						class:text-accent={selectedCode === entry.code}
						class:text-text-secondary={selectedCode !== entry.code}
						aria-label={selectedCode === entry.code
							? `Stop filtering by ${entry.code}`
							: `Show only ${entry.code}`}
						aria-pressed={selectedCode === entry.code}
						onclick={() => onSelect(selectedCode === entry.code ? null : entry.code)}
					>
						{entry.code}
						{entry.count}
					</button>
				{/each}
			</div>
		{/if}

		{#if anyLowSample}
			<p class="mt-2 text-[0.75rem] text-text-tertiary" data-failure-low-sample>
				A stage fewer than {minAttempts} items reached prints its counts and no rate, and its line
				stops there.
			</p>
		{/if}
	{/if}
</section>
