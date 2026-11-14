<script lang="ts">
	/** Compare mean phase time per article by CPU and reported L3 cache. */
	import type { Row } from '$lib/data/ledger';
	import { formatNumber, type NumberFormatConfig } from '$lib/number-format';
	import RankedList from '$lib/components/RankedList.svelte';
	import { rankedList } from '$lib/charts/d3/rankedList';
	import { SERIES_TOKENS } from '$lib/console/series-tokens';
	import { machinePhases } from '$lib/console/machine/machine-phases';

	let { rows, hosts, numberFormat }: {
		rows: readonly Row[]; hosts: readonly Row[]; numberFormat: NumberFormatConfig;
	} = $props();
	/** A MiB is a binary unit, independent of display preferences. */
	const BYTES_PER_MIB = 1024 * 1024;
	const work = $derived(machinePhases(rows, hosts));
	const print = (value: number) => formatNumber(value, numberFormat, { si: false });
	const count = (value: number) => formatNumber(value, numberFormat, { exact: true });
	const reading = SERIES_TOKENS['reading-prompt'];
	const writing = SERIES_TOKENS['writing-reply'];
	const byKey = $derived(new Map(work.machines.map((machine) => [machine.key, machine])));
	const label = (machine: (typeof work.machines)[number]) => {
		const cpu = machine.cpuModels.length === 0 ? 'CPU not recorded'
			: `${machine.cpuModels.length > 1 ? 'CPU readings disagree: ' : ''}${machine.cpuModels.join(', ')}`;
		const cache = machine.l3CacheBytes.length === 0 ? 'L3 not recorded'
			: `${machine.l3CacheBytes.length > 1 ? 'L3 readings disagree: ' : 'L3 '}${machine.l3CacheBytes.map((bytes) => `${print(bytes / BYTES_PER_MIB)} MiB`).join(', ')}`;
		return `${cpu}; ${cache}`;
	};
	const comparison = $derived(rankedList(work.machines.map((machine) => ({
		label: machine.key, value: machine.total,
		context: `${count(machine.articles)} ${machine.articles === 1 ? 'article' : 'articles'}; ${count(machine.shards)} ${machine.shards === 1 ? 'shard' : 'shards'}`,
		segments: [
			{ label: 'Prefill', value: machine.prefill, token: reading },
			{ label: 'Decode', value: machine.decode, token: writing }
		]
	})), {}));
	const geometry = $derived(comparison === null ? null : {
		...comparison,
		rows: comparison.rows.map((row) => ({
			...row, row: { ...row.row, label: label(byKey.get(row.key)!), value: `${print(row.value)} s/article` }
		}))
	});
</script>

<section class="machine-phases" data-machine-phases aria-label="Mean prefill and decode by CPU and L3">
	<h4>Prefill and decode by CPU and L3</h4>
	<p>One bar per CPU and reported L3: mean measured seconds per article, split into prefill and decode. Phase shares use total measured time; rates divide total phase tokens by total phase seconds.</p>
	<p>Article lengths still differ; the normalized comparisons above answer which CPU is faster. L3 comes from each shard's host, never its CPU name. This is model-processing time, not elapsed job time.</p>
	<RankedList {geometry} caption="Mean prefill and decode by CPU and L3" hover={false}
		maxText={`${print(comparison?.max ?? 0)} seconds per article`}
		emptyNote="No article has a recorded shard identity and complete positive phase timings."
		unmeasuredNote="Phase timings were not recorded.">
		{#snippet trend(row)}
			{@const machine = byKey.get(row.key)}
			{#if machine}
				<span class="phase-reading" style:color="var({reading})">
					<strong>Prefill {print(machine.prefillShare)}%</strong> - {print(machine.prefill)} s/article - {print(machine.prefillTps)} tokens/s
				</span>
				<span class="phase-reading" style:color="var({writing})">
					<strong>Decode {print(100 - machine.prefillShare)}%</strong> - {print(machine.decode)} s/article - {print(machine.decodeTps)} tokens/s
				</span>
			{/if}
		{/snippet}
	</RankedList>
	{#if work.excluded > 0}
		<p>{count(work.excluded)} rows lack a shard identity or complete positive phase timings; excluded, not counted as zero.</p>
	{/if}
</section>

<style>
	.machine-phases { margin-block-start: var(--console-group-gap); }
	h4 { font-size: var(--console-panel-title-size); line-height: var(--console-panel-title-leading); margin-block: 0 var(--console-control-gap); }
	.phase-reading { display: block; overflow-wrap: anywhere; }
</style>
