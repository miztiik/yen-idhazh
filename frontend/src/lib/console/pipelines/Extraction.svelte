<script lang="ts">
	import { nativeExtraction } from './extraction';
	import KpiCard from '$lib/components/KpiCard.svelte';
	import RankedList from '$lib/components/RankedList.svelte';
	import { rankedList } from '$lib/charts/d3/rankedList';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { emptyState } from '$lib/charts/d3/empty';
	import { frame, MARGIN } from '$lib/charts/frame';
	import Reserved from '$lib/components/Reserved.svelte';
	import type { PanelState } from '../waiting';
	import type { Range } from '../queries/window';
	import type { ExtractionDay } from '$lib/charts/extraction-trend';
	import type { Row } from '$lib/data/ledger';
	import type { ModelRule } from '$lib/charts/d3/model-rule';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
	let { rows, evaluations, knobs, chart, rule, yieldDays, publishedShare, nativeState, evaluationsState, nativeWindow, evaluationsWindow }: {
		rows: Row[]; evaluations: Row[] | null; knobs: ConsoleConfig; chart: ChartConfig; rule: ModelRule;
		yieldDays: ExtractionDay[];
		publishedShare: { measuredDays: number; unusedPct: number | null; unused: number; chartablePublished: number };
		nativeState: PanelState; evaluationsState: PanelState;
		nativeWindow?: Range; evaluationsWindow?: Range;
	} = $props();
	const extraction = $derived(nativeExtraction(rows, evaluations));
	const classes = $derived(rankedList(extraction.classes.map((entry) => ({ label: entry.label, value: entry.count })), {}));
	const geometry = $derived(dateSeries([
		{ label: 'Enough figures to draw', token: '--chart-1', points: yieldDays.map((day) => ({ date: day.date, value: day.chartable })) },
		{ label: 'Published carrying a chart', token: '--chart-4', points: yieldDays.map((day) => ({ date: day.date, value: day.charted })) }
	], { frame: frame(knobs.chart_width, knobs.chart_height, MARGIN), density: chart.tick_density, valueTicks: 5, padding: 0.2, rule }));
	const noRule = { declined: 'one figure of the window, not a date axis' };
</script>
<div data-eval-panel="extraction">
	<p data-comparison="classes">Chartable articles against narrative and unclassified ones, beside recorded extraction flags.</p>
	{#if publishedShare.measuredDays === 0}
		<p data-extraction="none">The build-time published chart-share record is unavailable in this window.</p>
	{:else}
		<KpiCard label="Of those, published without one" rule={noRule} lede
			value={publishedShare.unusedPct === null ? 'Not measured' : `${publishedShare.unusedPct}%`}
			note="{publishedShare.unused} of {publishedShare.chartablePublished} chartable published articles" />
	{/if}
	<div data-extraction-source="native" data-panel-state={nativeState}>
	<Reserved record panelState={nativeState} height={knobs.chart_height} width={knobs.chart_width} name="extraction" label="Native extraction readings">
	<div class="auto-grid">
		<KpiCard label="Articles the extraction record names" value={String(extraction.articles)} rule={noRule} />
		<KpiCard label="Facts found" value={extraction.elementsFound === null ? 'Not measured' : String(extraction.elementsFound)} rule={noRule} note="over {extraction.elementsMeasured} measured articles" />
		<KpiCard label="Not prose" value={String(extraction.notProse)} rule={noRule} />
		<KpiCard label="Contaminated" value={String(extraction.contaminated)} rule={noRule} />
	</div>
	<p>{extraction.note}</p>
	{#if nativeWindow}<p data-extraction-record>Extraction record: {nativeWindow.from} through {nativeWindow.to}.</p>{/if}
	<RankedList geometry={classes} caption="Articles by element class and failed re-slice" maxText={classes === null ? 'not measured' : `${classes.max} articles`}
		unmeasuredNote="No extraction class was measured." emptyNote="No extraction class is recorded." />
	</Reserved>
	</div>
	<p data-extraction-provenance>The record does not identify which extraction checker ran or its version. A false flag is the record's default, not proof that an extraction check ran.</p>
	<div data-extraction-source="flags" data-panel-state={evaluationsState}>
	<Reserved record panelState={evaluationsState} height={knobs.chart_height} width={knobs.chart_width} name="extraction-suspect" label="Recorded extraction flags">
		<KpiCard label="Recorded flags for page furniture" value={extraction.suspect === null ? 'Record unavailable' : String(extraction.suspect)} rule={noRule}
			note={extraction.checked === null ? 'No recorded article count is available' : `of ${extraction.checked} distinct recorded articles; ${extraction.suspectUnknown} have no boolean flag`} />
		{#if extraction.suspect === 0 && extraction.checked !== null && extraction.checked > 0 && extraction.suspectUnknown === 0}
			<p data-nothing-fired>No recorded extraction flag is true in these days. This does not establish that the extraction checker ran.</p>
		{/if}
		{#if evaluationsWindow}<p data-extraction-evaluator-record>Flag record: {evaluationsWindow.from} through {evaluationsWindow.to}.</p>{/if}
		<p>Counts include articles that were not published. Later dated boolean flags replace earlier ones; a missing flag does not replace a recorded flag. Conflicting flags on the latest recorded day are unknown. Nothing acts on these numbers.</p>
	</Reserved>
	</div>
	<h3>Whether the yield is falling</h3>
	<DateSeries {geometry} empty={emptyState('quiet', 'No build-time day carries both yield counts.')}
		name="extraction-yield" label="Enough figures to draw and articles published with a chart, day by day"
		width={knobs.chart_width} height={knobs.chart_height} readout={geometry?.readout} readoutMaxShare={chart.readout_max_share} />
	<ul class="sr-only" data-extraction-trend-days-list>
		{#each yieldDays as day (day.date)}
			<li data-extraction-trend-day={day.date} data-extraction-trend-chartable={day.chartable} data-extraction-trend-charted={day.charted}>{day.date}: {day.chartable} enough figures, {day.charted} carrying a chart.</li>
		{/each}
	</ul>
</div>
