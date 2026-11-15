<script lang="ts">
	import { atAGlance } from '$lib/console/pipelines/at-a-glance';
	import KpiCard from '$lib/components/KpiCard.svelte';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import { pointerReadout, readoutMarks, readoutOf } from '$lib/charts/readout';
	import { AXIS_LABEL_GAP_PX, chartWidth, dayTicks, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import { shortDate } from '$lib/format';
	import type { ChartDay } from '$lib/server/chart-days';
	import type { TimeWindow } from '$lib/charts/viewport';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
	let { days, publishedItems, window, knobs, chart }: {
		days: ChartDay[]; publishedItems: Readonly<Record<string, number>>; window: TimeWindow; knobs: ConsoleConfig; chart: ChartConfig;
	} = $props();
	const counts = $derived(atAGlance(days, window, publishedItems));
	const noRule = { declined: 'counts of what published, not how it was written' };
	const frameFor = useChartFrame(() => chart);
	let selected = $state<Record<string, number | null>>({ articles: null, visuals: null });
	let widths = $state<Record<string, number>>({});
	const cards = $derived([
		{ label: 'Articles published', name: 'articles', strip: counts.articles },
		{ label: 'Visuals published', name: 'visuals', strip: counts.visuals }
	]);
	const measured = $derived(counts.articles.bars.some((bar) => bar.measured));
</script>
{#if !measured}
	<p data-empty="missing">The private published-day record is unavailable in this window.</p>
{:else}
	<div class="auto-grid" data-glance data-range-from={window.start} data-range-to={window.end}>
		{#each cards as card, index (card.name)}
			{#snippet trend()}
				{@const strip = card.strip}
				{@const width = chartWidth(widths[card.name] ?? null, knobs.chart_width)}
				{@const plotHeight = chart.sparkline_height_px}
				{@const box = frameFor(width, plotHeight)}
				{@const height = plotHeight + box.margin.bottom}
				{@const columns = strip.bars.map((bar) => (bar.x + bar.width / 2) * width)}
				{@const ticks = dayTicks(strip.bars.map((bar) => bar.date),
					{ density: chart.tick_density, columns, bounds: [0, width], labels: box.labels })}
				{@const readout = readoutOf({ type: 'dateSeries', columns: strip.bars.map((bar) => shortDate(bar.date)),
					series: [{ label: card.label, swatch: null, values: strip.bars.map((bar) => bar.measured ? bar.published : null), format: String }],
					notMeasured: 'No published-day record', resting: 'newest' })}
				<div data-readout-columns={readout.columns.length} use:observeWidth={(width) => widths = { ...widths, [card.name]: width }}>
					<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
					<svg {width} {height} viewBox="0 0 {width} {height}" role="img" tabindex="0" aria-label="{card.label}, UTC dates"
						data-chart="published-counts" data-chart-name="published-{card.name}"
						data-published-measure={card.name} data-published-total={strip.total} data-published-days={strip.bars.length}
						use:pointerReadout={{ marks: readoutMarks(columns), width,
							hover: { name: `published-${card.name}`, readout },
							onSelect: (at) => selected[card.name] = at }}>
						{#each strip.bars as bar (bar.date)}
							{@const barHeight = bar.published === 0 ? 0 : Math.max(1, bar.height * plotHeight)}
							<rect x={bar.x * width} width={bar.width * width} y={plotHeight - barHeight} height={barHeight} fill="var(--chart-1)"
								data-published-bar={bar.date} data-published={bar.published} />
						{/each}
						{#each ticks as tick (tick.index)}
							<line x1={columns[tick.index]} x2={columns[tick.index]} y1={plotHeight}
								y2={plotHeight + AXIS_LABEL_GAP_PX / 2} stroke="var(--chart-axis)" />
							{#if tick.text}
								<text x={columns[tick.index]} y={plotHeight + AXIS_LABEL_GAP_PX / 2 + box.labels.fontSize}
									text-anchor={tick.anchor} font-size={box.labels.fontSize}
									fill="var(--color-text-tertiary)" data-day-axis={tick.date}>{tick.text}</text>
							{/if}
						{/each}
					</svg>
					<ChartReadout {readout} at={selected[card.name]} name="published-{card.name}" maxShare={chart.readout_max_share} compact hint="" />
				</div>
			{/snippet}
			<KpiCard label={card.label} value={String(card.strip.total)} lede={index === 0} rule={noRule} {trend} />
		{/each}
	</div>
{/if}
<style>
	.auto-grid :global(.kpi) { background: var(--color-surface); }
	svg { inline-size: 100%; max-inline-size: 100%; block-size: auto; }
	text { font-family: var(--font-data); letter-spacing: var(--console-small-tracking); }
</style>
