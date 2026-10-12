<script lang="ts">
	import StageTimings from '$lib/components/StageTimings.svelte';
	import { nativeStageTimings } from './stage-timings';
	import { finiteCell, nearestRank } from '../rates';
	import type { Row } from '$lib/data/ledger';
	import type { TimeWindow } from '$lib/charts/viewport';
	import type { ModelRule } from '$lib/charts/d3/model-rule';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
	let { rows, knobs, chart, window, rule }: {
		rows: Row[]; knobs: ConsoleConfig; chart: ChartConfig; window: TimeWindow; rule: ModelRule;
	} = $props();
	const days = $derived(nativeStageTimings(rows));
	const summarize = $derived(nearestRank(rows.flatMap((row) => {
		const value = finiteCell(row.summarize_ms);
		return value === null ? [] : [value];
	}), 0.5));
</script>
<p data-lede class="lede">{summarize === null ? 'No summarize clock was measured.' : `${(summarize / 1000).toFixed(2)} median summarize seconds.`}</p>
<p data-comparison="Summarize against fetch and extract.">Summarize against fetch and extract, with timed coverage kept beside each stage.</p>
<StageTimings {days} span={window} height={knobs.chart_height} width={knobs.chart_width}
	tickDensity={chart.tick_density} readoutMaxShare={chart.readout_max_share} {rule} />
<style>.lede { font-size: var(--text-2xl); }</style>
