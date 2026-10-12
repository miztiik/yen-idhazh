<script lang="ts">
	import { base } from '$app/paths';
	import TimeHistogram from '$lib/components/TimeHistogram.svelte';
	import { nativeItemCost } from './item-cost';
	import { SERIES_TOKENS } from '../series-tokens';
	import type { Row } from '$lib/data/ledger';
	import type { ConsoleConfig, ChartConfig } from '$lib/server/config';
	let { rows, knobs, chart }: { rows: Row[]; knobs: ConsoleConfig; chart: ChartConfig } = $props();
	const cost = $derived(nativeItemCost(rows));
</script>

<p data-lede data-item-cost-lead data-item-cost-rows={cost.rows} class="lede">
	{cost.writing === null ? 'No summary-writing clock was measured.' : `${(cost.writing.median / 1000).toFixed(2)} seconds to write one summary.`}
</p>
<p data-comparison="Writing one summary against reading one prompt.">Writing one summary against reading one prompt; their distributions share one time axis.</p>
<p>{cost.writeCostRatio === null ? 'The two per-token costs cannot yet be compared.' : `Writing a token cost ${cost.writeCostRatio.toFixed(1)} times reading one.`}</p>
{#each [{ times: cost.reading, name: 'item-reading', subject: 'Seconds to read one prompt', verb: 'read', noun: 'prompt', nouns: 'prompts', token: SERIES_TOKENS['reading-prompt'] },
	{ times: cost.writing, name: 'item-writing', subject: 'Seconds to write one summary', verb: 'written', noun: 'summary', nouns: 'summaries', token: SERIES_TOKENS['writing-reply'] }] as part (part.name)}
	<div class={part.name}>
		{#if part.times === null}
			<p data-item-cost={part.name}>No {part.noun} clock was measured.</p>
		{:else if part.times.n < knobs.min_attempts_for_rate}
			<p>{part.times.n} clocks were measured; {knobs.min_attempts_for_rate} are needed for a distribution.</p>
		{:else}
			<TimeHistogram times={part.times} name={part.name} subject={part.subject} verb={part.verb} noun={part.noun} nouns={part.nouns}
				noRuleReason="one distribution of the window, not a date axis" barToken={part.token}
				width={knobs.chart_width} height={knobs.chart_height} readoutMaxShare={chart.readout_max_share} domain={cost.domain} />
		{/if}
	</div>
{/each}
<p class="note" data-item-cost-pairs>
	Reading: {cost.readPairs} paired clocks and fresh-token counts; writing: {cost.writePairs} paired clocks and output counts.
	{cost.unknownCache} prompts have no recorded cache count and are not treated as read whole.
	Prompt reuse is on <a href="{base}/console/machine/">Hardware</a>.
</p>
<style>
	.lede { font-size: var(--text-2xl); font-variant-numeric: tabular-nums; }
	.note { font-size: var(--text-sm); color: var(--color-text-secondary); }
</style>
