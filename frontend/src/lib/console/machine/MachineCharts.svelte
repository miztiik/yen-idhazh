<script lang="ts">
	import Panel from '$lib/components/Panel.svelte';
	import RankedList from '$lib/components/RankedList.svelte';
	import MachinePhases from './MachinePhases.svelte';
	import { rankedList } from '$lib/charts/d3/rankedList';
	import { formatNumber } from '$lib/number-format';
	import { SERIES_TOKENS } from '$lib/console/series-tokens';
	import { closestToMemory, slowerMachines } from './records';
	import type { Row } from '$lib/data/ledger';
	import type { ChartConfig } from '$lib/server/config';

	let { id, title, rows, hostRows = [], chart, knobs }: {
		id: string; title: string; rows: readonly Row[];
		hostRows?: readonly Row[];
		chart: ChartConfig; knobs: Readonly<Record<string, number>>;
	} = $props();
	const numberFormat = $derived(chart.number_format);
	const shown = (value: number) => formatNumber(value, numberFormat, { si: false });
	const count = (value: number) => formatNumber(value, numberFormat, { exact: true });
	const seconds = (value: number) => `${shown(value)} s`;
	const gibPlaces = 2;
	const memoryFormat = $derived(new Intl.NumberFormat(numberFormat.locale, { maximumFractionDigits: gibPlaces }));
	const gib = (value: number) => {
		const printed = memoryFormat.format(value);
		return value > 0 && printed === memoryFormat.format(0) ? `<${memoryFormat.format(10 ** -gibPlaces)} GiB` : `${printed} GiB`;
	};
	const declined = { declined: 'This compares records within one run or kind, not a change over days.' };
	const slower = $derived(slowerMachines(id === 'slower-machines' ? rows : []));
	const comparableKinds = $derived(slower.reading.filter((row) => (row.range?.count ?? 0) >= knobs.slower_machines_min_articles));
	const memoryReadings = $derived(id === 'closest-to-memory' ? closestToMemory(rows) : []);
	const closest = $derived(rankedList(memoryReadings.map((row) => ({ ...row, context: `${gib(row.capacity)} total` })), {
		max: knobs.closest_to_memory_rows, order: 'smallest-first', formatValue: gib,
		scaleFloor: memoryReadings.reduce((largest, row) => Math.max(largest, row.capacity), 0)
	}));
	const tightest = $derived(closest?.rows[0]);
	const readingLeader = $derived(comparableKinds.toSorted((a, b) => b.value - a.value)[0]);
	const phases = $derived([
		{ label: 'Prefill (reading the prompt)', tokens: slower.reference.freshInput, unit: 'fresh prompt tokens',
			rows: slower.reading, target: slower.typical.read, token: SERIES_TOKENS['reading-prompt'] },
		{ label: 'Decode (writing the reply)', tokens: slower.reference.output, unit: 'output tokens',
			rows: slower.writing, target: slower.typical.write, token: SERIES_TOKENS['writing-reply'] }
	]);
</script>

<Panel {id} {title} heading="h3">
	<div data-panel-question="is it working"
		data-model-rule-name={id}
		data-model-rule="no"
		data-model-rule-none={declined.declined}>
		{#if id === 'slower-machines'}
			<p class="lede" data-lede>{comparableKinds.length === 0 ? 'No CPU recorded enough comparable work.'
				: comparableKinds.length === 1 ? slower.reference.referenceRows === rows.length
					? 'Every article ran on one kind of machine.' : 'Only one kind of machine has enough comparable work.'
				: readingLeader && slower.typical.read !== null && slower.typical.read > 0
					? `Longest median prefill: ${shown(readingLeader.value / slower.typical.read)} times the reference`
					: 'No CPU recorded enough comparable prefill work.'}</p>
			<p data-comparison="Estimated seconds for the same workload by CPU">Estimated seconds for the same workload, adjusted against the reference CPU within each run.
				Each bar ends at the median (middle estimate). The solid line marks the 90th percentile: about 90% of estimates are at or below it.</p>
			{#if slower.reference.cpuModel !== null}<p><strong>Reference CPU:</strong> {slower.reference.cpuModel}</p>{/if}
			<div class="halves auto-grid">
				{#each phases as phase (phase.label)}
					{@const reference = `Reference CPU median for ${phase.tokens === null ? '' : count(phase.tokens)} ${phase.unit}`}
					{@const geometry = rankedList(phase.rows.map((row) => ({ ...row,
						context: row.range !== undefined && row.range.count >= knobs.slower_machines_min_articles
							? `${count(row.range.count)} articles; 90th percentile ${seconds(row.range.high)}` : undefined
					})), {
						max: knobs.fleet_top_kinds, minCount: knobs.slower_machines_min_articles, formatValue: seconds,
						rules: phase.target === null ? [] : [{ at: phase.target, label: reference }]
					})}
					<div>
						<h4>{phase.label}</h4>
						{#if geometry?.rows.some((row) => row.refused === null) && phase.target !== null}
							<p class="guide">Dashed line: {reference}, {seconds(phase.target)}.</p>
						{/if}
						<RankedList {geometry} caption={phase.label} maxText={seconds(geometry?.max ?? 0)} labelRules={false}
							token={phase.token} unmeasuredNote="No comparable timings." emptyNote="No comparable timings." />
					</div>
				{/each}
			</div>
			{#if slower.withoutReference > 0 || slower.reference.unqualified > 0}
				<p>{#if slower.withoutReference > 0}Runs excluded without reference timings: {count(slower.withoutReference)}. {/if}
					{#if slower.reference.unqualified > 0}Article rows without comparable timings or token counts: {count(slower.reference.unqualified)}.{/if}</p>
			{/if}
			<MachinePhases {rows} hosts={hostRows} {numberFormat} />
		{:else if id === 'closest-to-memory'}
			{#if tightest}<p class="lede" data-lede>{tightest.row.value} available at the lowest recorded point</p>{/if}
			<p data-comparison="Lowest recorded available memory per article">Least available first. The scale ends at the largest recorded machine capacity.</p>
			{#if closest !== null}
				<div class="memory-scale" role="group" aria-label="Available memory colour scale">
					<span>Less memory left</span>
					<span class="memory-gradient chart-bar" aria-hidden="true"></span>
					<span>More memory left</span>
				</div>
			{/if}
			<RankedList geometry={closest} caption="Lowest available memory per article" maxText={gib(closest?.max ?? 0)}
				unmeasuredNote="No article has a recorded available-memory reading and total."
				emptyNote="No article has a recorded available-memory reading and total.">
				{#snippet track(row)}
					<span class="memory-track" aria-hidden="true">
						<span class="memory-gradient chart-bar-stack" style:--chart-filled-width={row.percent}></span>
					</span>
				{/snippet}
			</RankedList>
		{/if}
	</div>
</Panel>

<style>
	.lede { font-size: var(--console-page-title-size); line-height: var(--console-page-title-leading); font-weight: var(--console-page-title-weight); }
	.halves > div { min-width: 0; }
	h4 { font-size: var(--console-body-size); line-height: var(--console-body-leading); margin-block: var(--console-control-gap); }
	.guide { color: var(--color-text-secondary); font-size: var(--console-small-size); line-height: var(--console-small-leading); }
	.memory-scale {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		margin-block: var(--space-2);
		color: var(--color-text-secondary);
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
	}
	.memory-scale .memory-gradient { flex: 1; min-inline-size: var(--space-6); }
	.memory-track {
		display: block;
		border-radius: var(--radius-full);
		background: var(--color-surface-sunken);
	}
	.memory-gradient {
		display: block;
		block-size: var(--space-3);
		background: linear-gradient(to right in oklch, var(--chart-memory-low), var(--chart-memory-high));
	}
</style>
