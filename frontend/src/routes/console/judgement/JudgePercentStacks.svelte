<script lang="ts">
	import PartsOfOne from '$lib/charts/d3/PartsOfOne.svelte';
	import { partsOfOne } from '$lib/charts/d3/partsOfOne';
	import { factsOf } from '$lib/charts/readout';
	import { sliceParts } from '$lib/console/judge-draw';
	import { judgeDecimal, judgeShare, type SliceOutcome } from '$lib/console/judge-observations';
	import { numberFormatter } from '$lib/number-format';
	import type { ChartConfig } from '$lib/server/config';
	import { DRAW_PARTS, OUTCOME_STYLE } from './judge-trial-style';

	let { slices, chart, width, height, thin }: {
		slices: readonly SliceOutcome[]; chart: ChartConfig; width: number; height: number; thin: number;
	} = $props();
	const number = $derived(numberFormatter(chart.number_format));
	const labelFor = (low: number, high: number) => `${judgeDecimal(low, chart.number_format)} to ${judgeDecimal(high, chart.number_format)}`;
	const rows = $derived(slices.flatMap((slice, index) => {
		const prior = slices[index - 1];
		const band = { label: labelFor(slice.low, slice.high), slice };
		return prior && prior.high < slice.low
			? [{ label: labelFor(prior.high, slice.low), slice: null }, band] : [band];
	}));
	const settings = DRAW_PARTS.map((part) => OUTCOME_STYLE[part]);
	const geometry = $derived(partsOfOne(rows.map(({ label, slice }) => ({
		label,
		parts: slice === null ? [] : DRAW_PARTS.map((part) => ({
			label: OUTCOME_STYLE[part].label, value: sliceParts(slice)[part] / slice.drawn
		}))
	})), { order: settings.map(({ label }) => label), tokens: settings.map(({ token }) => token) }));
	const readout = $derived(rows.map(({ label, slice }) => factsOf(label,
		slice === null ? [] : [
			{ label: 'Pairs drawn', value: number(slice.drawn, { exact: true }) },
			...DRAW_PARTS.map((part) => {
				const n = sliceParts(slice)[part];
				const style = OUTCOME_STYLE[part];
				return {
					label: style.label, value: `${number(n, { exact: true })} of ${number(slice.drawn, { exact: true })} (${judgeShare(n, slice.drawn, chart.number_format)})`,
					swatch: `var(${style.token})`
				};
			})
		], 'Not drawn.')));
</script>

<div class="stack-ends" aria-hidden="true"><span>0%</span><span>100%</span></div>
<ul class="stack-key" aria-label="Score range outcomes">
	{#each settings as { label, token } (label)}
		<li><span style:background="var({token})" aria-hidden="true"></span>{label}</li>
	{/each}
</ul>
<PartsOfOne {geometry} {readout} empty={null} name="judge-percent-stacks" label="Share of drawn pairs by answer and score range"
	{width} {height} readoutMaxShare={chart.readout_max_share} separateSegments showTotal={false}>
	{#snippet rowTotal(index)}
		{@const slice = rows[index].slice}
		{#if slice === null}
			Not drawn
		{:else}
			{number(slice.drawn, { exact: true })} drawn{slice.drawn < thin ? ' (thin)' : ''}
		{/if}
	{/snippet}
</PartsOfOne>

<style>
	.stack-ends, .stack-key {
		display: flex;
		color: var(--color-text-secondary);
		font-size: var(--console-small-size);
		margin-block-end: var(--space-2);
	}
	.stack-ends { justify-content: space-between; }
	.stack-key { flex-wrap: wrap; padding: 0; gap: var(--space-1) var(--space-3); list-style: none; }
	.stack-key span { display: inline-block; inline-size: var(--space-3); block-size: var(--space-3); margin-inline-end: var(--space-1); }
</style>
