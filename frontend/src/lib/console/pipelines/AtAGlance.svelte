<script lang="ts">
	import { atAGlance } from './at-a-glance';
	import KpiCard from '$lib/components/KpiCard.svelte';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import { pointerReadout, readoutMarks, readoutOf } from '$lib/charts/readout';
	import { shortDate } from '$lib/format';
	import type { ChartDay } from '$lib/server/chart-days';
	import type { TimeWindow } from '$lib/charts/viewport';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
	let { days, window, knobs, chart }: { days: ChartDay[]; window: TimeWindow; knobs: ConsoleConfig; chart: ChartConfig } = $props();
	const counts = $derived(atAGlance(days, window));
	const noRule = { declined: 'counts of what published, not how it was written' };
	let selected = $state<Record<string, number | null>>({ articles: null, visuals: null });
	const cards = $derived([
		{ label: 'Articles published', name: 'articles', strip: counts.articles },
		{ label: 'Visuals published', name: 'visuals', strip: counts.visuals }
	]);
	const measured = $derived(days.some((day) => day.date >= window.start && day.date <= window.end));
</script>
{#if !measured}
	<p data-empty="missing">The private published-day record is unavailable in this window.</p>
{:else}
	<div class="auto-grid" data-glance>
		{#each cards as card, index (card.name)}
			{#snippet trend()}
				{@const strip = card.strip}
				{@const readout = readoutOf({ type: 'dateSeries', columns: strip.bars.map((bar) => shortDate(bar.date)),
					series: [{ label: card.label, swatch: 'var(--chart-3)', values: strip.bars.map((bar) => bar.published), format: String }],
					notMeasured: 'No published day was measured.', resting: 'newest' })}
				<div data-readout-columns={readout.columns.length} data-model-rule="no"
					data-model-rule-none={noRule.declined}>
					<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
					<svg width="220" height="34" viewBox="0 0 220 34" role="img" tabindex="0" aria-label={card.label}
						data-chart="published-counts" data-chart-name="published-{card.name}"
						data-published-measure={card.name} data-published-total={strip.total} data-published-days={strip.bars.length}
						use:pointerReadout={{ marks: readoutMarks(strip.bars.map((bar) => (bar.x + bar.width / 2) * 220)), width: 220,
							onSelect: (at) => selected[card.name] = at }}>
						{#each strip.bars as bar (bar.date)}
							{@const height = bar.published === 0 ? 0 : Math.max(1, bar.height * 34)}
							<rect x={bar.x * 220} width={bar.width * 220} y={34 - height} {height} fill="var(--chart-3)"
								data-published-bar={bar.date} data-published={bar.published} />
						{/each}
					</svg>
					<ChartReadout {readout} at={selected[card.name]} name="published-{card.name}" maxShare={chart.readout_max_share} hint="" />
				</div>
			{/snippet}
			<KpiCard label={card.label} value={String(card.strip.total)} note={card.strip.bars.length === 1 ? 'in this one day' : `in these ${card.strip.bars.length} days`} lede={index === 0} rule={noRule} {trend} />
		{/each}
	</div>
{/if}
<p data-comparison="Articles published against visuals published over the same days.">Articles published against visuals published over the same days.</p>
<style>
	.auto-grid :global(.kpi) { background: var(--color-surface); }
	svg { inline-size: 100%; max-inline-size: 100%; block-size: auto; }
</style>
