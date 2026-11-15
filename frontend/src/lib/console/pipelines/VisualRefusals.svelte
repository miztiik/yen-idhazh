<script lang="ts">
	/** Draw every recorded refusal reason over the same UTC calendar and count scale. */
	import { refusalLines } from '$lib/console/pipelines/visual-refusals';
	import { attemptNotes } from '$lib/console/pipelines/attempt-notes';
	import type { VisualAttemptDay } from '$lib/console/pipelines/visual-attempts';
	import type { RecordRead } from '$lib/console/recording';
	import type { TimeWindow } from '$lib/charts/viewport';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { emptyState } from '$lib/charts/d3/empty';
	import { MARGIN, chartWidth, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import { useNumberFormat } from '$lib/number-format-context';
	import { grouped } from '$lib/charts/series';
	import { shortDate } from '$lib/format';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';

	let { days, read, window, knobs, chart }: {
		days: VisualAttemptDay[]; read: RecordRead; window: TimeWindow; knobs: ConsoleConfig; chart: ChartConfig;
	} = $props();
	const numberFormat = useNumberFormat();
	const frame = useChartFrame(() => chart);
	let measured = $state<Record<string, number>>({});
	const evidence = $derived(attemptNotes(read, window));
	const lines = $derived(refusalLines(days, read, window, numberFormat));
	const maximum = $derived(Math.max(1, ...lines.flatMap((line) => line.series.points.map((point) => point.value ?? 0))));
	const rule = { declined: 'Visual plan checks do not record summary-setting changes.' };
</script>

<div data-visual-attempt-view="refusals" data-record-incomplete={evidence.state !== 'read' || evidence.notes.length > 0 ? '' : undefined}>
	{#if evidence.state === 'read' && days.length > 0}
		<p data-source-window data-range-from={window.start} data-range-to={window.end}>Packed visual attempts: {shortDate(window.start)}{window.start === window.end ? '' : ` - ${shortDate(window.end)}`} UTC.</p>
	{/if}
	<p>Counts of the first failed plan check recorded on each UTC day, including plans later written. These are not failed articles or counts of all omitted visuals.</p>
	<p data-comparison="Each recorded reason has a daily line on the same UTC dates and count scale.">Each recorded reason has a daily line on the same UTC dates and count scale. A gap is not zero.</p>
	{#each evidence.notes as note}<p data-record-note>{note}</p>{/each}
	{#if evidence.state === 'read'}
		{#if lines.length === 0}
			<p data-empty={evidence.notes.length > 0 ? 'incomplete' : 'quiet'}>No visual attempt is recorded in this window.</p>
		{:else}
			<div class="auto-grid refusal-lines">
				{#each lines as line, index (line.reason)}
					{@const key = line.reason ?? ''}
					{@const width = chartWidth(measured[key] ?? null, knobs.chart_width)}
					{@const geometry = dateSeries([line.series], {
						frame: frame(width, knobs.chart_height, MARGIN), density: chart.tick_density,
						valueTicks: Math.min(5, maximum), padding: 0.2, rule, number_format: numberFormat, domain: [0, maximum]
					})}
					<section class="refusal-line" data-refusal-reason={line.reason ?? undefined}
						use:observeWidth={(width) => measured = { ...measured, [key]: width }}>
						<h3>{line.label}</h3>
						<DateSeries {geometry} empty={emptyState('missing', 'No complete daily failed-check count is available.')}
							name="visual-refusals-{index}" label="{line.label}, recorded attempts per UTC day"
							{width} height={knobs.chart_height} readout={line.readout} readoutMaxShare={chart.readout_max_share}
							restingNote=", the newest recorded day" />
						{#if geometry === null}
							{#each days.filter((day) => day.date >= window.start && day.date <= window.end) as day (day.date)}
								<p>{day.date} UTC: {grouped(day.attempts, numberFormat)} recorded {day.attempts === 1 ? 'attempt' : 'attempts'}; the failed-check count is unknown.</p>
							{/each}
						{/if}
					</section>
				{/each}
			</div>
		{/if}
	{/if}
</div>

<style>
	.refusal-lines { margin-block-start: var(--space-5); gap: var(--space-6); }
	.refusal-line { min-inline-size: 0; }
	h3 { margin-block: 0 var(--space-2); overflow-wrap: anywhere; }
</style>
