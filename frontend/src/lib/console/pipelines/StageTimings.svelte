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
	const modelChanges = $derived('changes' in rule ? rule.changes.map((change) => change.date) : []);
	const summarize = $derived(nearestRank(rows.flatMap((row) => {
		const value = finiteCell(row.summarize_ms);
		return value === null ? [] : [value];
	}), 0.5));
</script>
<p data-lede class="lede">{summarize === null ? 'No summarize clock was measured.' : `${(summarize / 1000).toFixed(2)} median summarize seconds.`}</p>
<p data-comparison="trend">Summarize against fetch and extract, with timed coverage kept beside each stage.</p>
{#if 'declined' in rule}
	<p data-contract-blocked="settings-rule">{rule.declined} The retained stage chart accepts only change dates and would call this “Nothing changed.” Its structured settings-rule input must be settled; the measured clocks remain below.</p>
	<details><summary>The measured stage clocks</summary>
		{#each days as day (day.date)}
			<p>{day.date}: summarize {day.summarize.ms === null ? 'not measured' : `${day.summarize.ms} ms`}, fetch {day.fetch.ms === null ? 'not measured' : `${day.fetch.ms} ms`}, extract {day.extract.ms === null ? 'not measured' : `${day.extract.ms} ms`}.</p>
		{/each}
	</details>
{:else}
	<StageTimings {days} span={window} height={knobs.chart_height} width={knobs.chart_width}
		tickDensity={chart.tick_density} readoutMaxShare={chart.readout_max_share} {modelChanges} />
	{#if rule.note}<p>{rule.note}</p>{/if}
	{#each rule.changes as change}<p data-settings-line={change.date}>{change.date}: {change.words}</p>{/each}
{/if}
<style>.lede { font-size: var(--text-2xl); }</style>
