<script lang="ts">
	/** Show the recorded room left after summary prompts, before the model replies. */
	import Panel from '$lib/components/Panel.svelte';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import Distribution from '$lib/charts/d3/Distribution.svelte';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import { distribution } from '$lib/charts/d3/distribution';
	import { emptyState } from '$lib/charts/d3/empty';
	import { spreadPaint } from '$lib/charts/d3/spread-paint';
	import { AXIS_LABEL_GAP_PX, MARGIN, chartWidth, labelWidth, observeWidth } from '$lib/charts/frame';
	import { useChartFrame, useChartLabels } from '$lib/charts/label-context';
	import { readoutOf } from '$lib/charts/readout';
	import { daysInWindow } from '$lib/charts/viewport';
	import { shortDate } from '$lib/format';
	import { formatNumber } from '$lib/number-format';
	import {
		CONTEXT_CAPACITY_TOKEN, CONTEXT_PROMPT_TOKEN, summaryContext, summaryContextSeries,
		type ContextDay
	} from './summary-context';
	import type { Range } from '$lib/console/queries/window';
	import type { Row } from '$lib/data/ledger';
	import type { ChartConfig } from '$lib/server/config';

	let { title, rows, range, chart, windowDays, minValues }: {
		title: string; rows: readonly Row[]; range: Range; chart: ChartConfig; windowDays: number; minValues: number;
	} = $props();
	let measuredWidth = $state<number | null>(null);
	let inspect = $state(false);
	const frame = useChartFrame(() => chart);
	const labels = useChartLabels();
	const width = $derived(chartWidth(measuredWidth, chart.width_px));
	const box = $derived(frame(width, chart.height_px));
	const detailBox = $derived(frame(width, chart.height_px, {
		...MARGIN, right: Math.ceil(labelWidth('100%', labels()) + AXIS_LABEL_GAP_PX)
	}));
	const reading = $derived(summaryContext(rows, daysInWindow({ start: range.from, end: range.to })));
	const numberFormat = $derived(chart.number_format);
	const count = (value: number) => formatNumber(value, numberFormat, { exact: true });
	const tokens = (value: number) => `${count(value)} tokens`;
	const room = (value: number) => value < 0 ? `${tokens(-value)} over capacity` : tokens(value);
	const matched = (measured: number, recorded: number) => `${count(measured)} of ${count(recorded)}`;
	const rule = { declined: 'Slot capacities come from the settings on the summary prompt records.' };
	const geometry = $derived(dateSeries(summaryContextSeries(reading.days), {
		frame: box, density: chart.tick_density, valueTicks: chart.tick_density,
		padding: 0, number_format: numberFormat, rule
	}));
	const separate = 'Shown separately';
	function readingAt(day: ContextDay, key: 'capacity' | 'used' | 'room') {
		return day.slots.length > 1 ? separate : day.slots[0]?.[key] ?? null;
	}
	const readout = $derived(readoutOf({
		type: 'dateSeries', columns: reading.days.map(({ date }) => `${shortDate(date)} UTC`),
		series: [
			{ label: 'Slot capacity', swatch: `var(${CONTEXT_CAPACITY_TOKEN})`, note: 'dashed',
				values: reading.days.map((day) => readingAt(day, 'capacity')), format: tokens },
			{ label: 'Prompt used (p90)', swatch: `var(${CONTEXT_PROMPT_TOKEN})`, note: 'solid',
				values: reading.days.map((day) => readingAt(day, 'used')), format: tokens },
			{ label: 'Room before reply', swatch: spreadPaint(CONTEXT_PROMPT_TOKEN),
				values: reading.days.map((day) => readingAt(day, 'room')), format: room },
			{ label: 'Matched prompts', swatch: null,
				values: reading.days.map((day) => day.recorded ? matched(day.measured, day.recorded) : null), format: count }
		],
		events: { lines: reading.days.map(({ slots }) => slots.length < 2 ? [] : slots.map((slot) => ({
			label: `${tokens(slot.capacity)} per slot`,
			value: `${tokens(slot.used)} used at p90; ${slot.room < 0 ? room(slot.room) : `${room(slot.room)} left`}; ${count(slot.measured)} matched`,
			swatch: null
		}))) },
		notMeasured: 'No summary prompt recorded.',
		notMeasuredAt: reading.days.map((day) => day.recorded > 0 && day.measured === 0 ? 'Slot size not recorded.' : null),
		resting: 'last'
	}));
	const history = $derived(inspect ? distribution(reading.prompts, {
		frame: detailBox, minValues, valueTicks: chart.tick_density, scale: 'log', number_format: numberFormat
	}) : null);
</script>

<div data-windowed="machine-context" data-window-days={windowDays}>
	<Panel id="context-headroom" {title} heading="h3">
		<div data-panel-question="is it working" use:observeWidth={(px) => (measuredWidth = px)}>
			{#if reading.peak}
				<p class="lede" data-lede>Largest measured prompt share: {formatNumber(100 * reading.peak.share, numberFormat, { si: false })}% of its slot</p>
				<p>{tokens(reading.peak.used)} used out of {tokens(reading.peak.capacity)}.</p>
			{:else}
				<p class="lede" data-lede>No comparable summary prompts.</p>
			{/if}
			<p data-context-coverage>{matched(reading.measured, reading.prompts.length)} recorded summary prompts have a slot size.</p>
			<p data-comparison="Summary prompts against their own configured slots">About 90% of matched prompts are at or below the
				daily reading (p90). Shading shows the room left before the reply, not whether text was cut.</p>
			{#if reading.days.some(({ slots }) => slots.length > 1)}
				<p>Days with more than one slot size show separate dots. Select the day to read each comparison.</p>
			{/if}
			<DateSeries {geometry} {readout} empty={emptyState('quiet', 'No summary prompts have a recorded slot size in this window.')}
				name="summary-context" label="Summary prompt use and configured slot capacity, in tokens per call by UTC day"
				{width} height={box.height} readoutMaxShare={chart.readout_max_share} />
			<details bind:open={inspect} class="inspection">
				<summary>Token counts and extraction cuts</summary>
				<p>{reading.cut === 0 ? 'No extraction cut was recorded in this window.'
					: `${count(reading.cut)} article ${reading.cut === 1 ? 'attempt records' : 'attempts record'} an extraction cut before the prompt.`}</p>
				<p>Positive summary prompt counts, including those without a slot size.</p>
				{#if inspect}
					<Distribution geometry={history} empty={emptyState('quiet', 'Too few recorded summary prompts to draw a distribution.')}
						name="context-summary" label="Summary prompt tokens, logarithmic scale" {width}
						height={detailBox.height} readoutMaxShare={chart.readout_max_share} />
				{/if}
			</details>
		</div>
	</Panel>
</div>

<style>
	.lede { font-size: var(--console-page-title-size); line-height: var(--console-page-title-leading); font-weight: var(--console-page-title-weight); }
	.inspection { margin-block-start: var(--console-control-gap); border-block-start: 1px solid var(--color-rule); }
	.inspection summary {
		min-block-size: var(--console-control-min-height);
		align-content: center;
		color: var(--color-accent);
		cursor: pointer;
	}
</style>
