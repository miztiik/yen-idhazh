<script lang="ts">
	import Panel from '$lib/components/Panel.svelte';
	import RankedList from '$lib/components/RankedList.svelte';
	import Distribution from '$lib/charts/d3/Distribution.svelte';
	import MachinePhases from './MachinePhases.svelte';
	import { rankedList } from '$lib/charts/d3/rankedList';
	import { distribution } from '$lib/charts/d3/distribution';
	import { emptyState } from '$lib/charts/d3/empty';
	import { AXIS_LABEL_GAP_PX, chartWidth, labelWidth, MARGIN, observeWidth } from '$lib/charts/frame';
	import { useChartFrame, useChartLabels } from '$lib/charts/label-context';
	import { formatNumber } from '$lib/number-format';
	import { nameSpan } from '$lib/console/span-words';
	import { closestToMemory, contextReadings, slowerMachines } from './records';
	import type { Row } from '$lib/data/ledger';
	import type { ChartConfig } from '$lib/server/config';

	let { id, title, rows, hostRows = [], chart, knobs, windowDays }: {
		id: string; title: string; rows: readonly Row[];
		hostRows?: readonly Row[];
		chart: ChartConfig; knobs: Readonly<Record<string, number>>; windowDays: number;
	} = $props();
	const numberFormat = $derived(chart.number_format);
	const frame = useChartFrame(() => chart);
	const labels = useChartLabels();
	let width = $state<number | null>(null);
	const contextBox = $derived(frame(chartWidth(width, chart.width_px), chart.height_px,
		{ ...MARGIN, right: Math.ceil(labelWidth('100%', labels()) + AXIS_LABEL_GAP_PX) }));
	const declined = { declined: 'This compares records within one run or kind, not a change over days.' };
	const slower = $derived(slowerMachines(id === 'slower-machines' ? rows : []));
	const comparableKinds = $derived(new Set([...slower.reading, ...slower.writing]
		.filter((row) => (row.range?.count ?? 0) >= knobs.slower_machines_min_articles).map((row) => row.label)));
	const memoryReadings = $derived(closestToMemory(rows));
	const closest = $derived(rankedList(memoryReadings, { max: knobs.closest_to_memory_rows }));
	const tightest = $derived([...memoryReadings].sort((a, b) => b.value - a.value || a.label.localeCompare(b.label))[0]);
	const readingLeader = $derived([...slower.reading].filter((row) => (row.range?.count ?? 0) >= knobs.slower_machines_min_articles)
		.sort((a, b) => b.value - a.value)[0]);
	const comparison = $derived(id === 'slower-machines' ? "Each machine kind's typical time against the reference machine's"
		: id === 'closest-to-memory' ? "Memory held at each article's lowest point against the machine's total"
		: 'Each prompt against the reading limit');
	const context = $derived(contextReadings(rows));
	const contextDomain = $derived([
		Math.min(1, ...context.label, ...context.summary, ...context.rules.map((one) => one.at)),
		Math.max(10, ...context.label, ...context.summary, ...context.rules.map((one) => one.at))
	] as [number, number]);
</script>

<div data-windowed={{ 'context-headroom': 'machine-context' }[id]}
	data-window-days={windowDays}>
<Panel {id} {title} heading="h3" note={`Read from the published record when you open this page - over ${nameSpan(windowDays)}.`}>
	<div data-panel-question="is it working"
		data-model-rule-name={id}
		data-model-rule="no"
		data-model-rule-none={declined.declined}>
		<p data-comparison={comparison}>{comparison}.</p>
		{#if id === 'slower-machines'}
			<p class="lede" data-lede>{comparableKinds.size === 0 ? 'No machine recorded enough comparable work.'
				: comparableKinds.size === 1 ? slower.reference.referenceRows === rows.length
					? 'Every article ran on one kind of machine.' : 'Only one kind of machine has enough comparable work.'
				: readingLeader && slower.typical.read !== null && slower.typical.read > 0
					? `${readingLeader.label} took ${formatNumber(readingLeader.value / slower.typical.read, numberFormat, { si: false })} times ${slower.reference.cpuModel}'s typical reading time.`
					: 'No machine recorded enough comparable reading work.'}</p>
			<div class="halves auto-grid">
				{#each ['reading', 'writing'] as kind}
					{@const readings = kind === 'reading' ? slower.reading : slower.writing}
					{@const target = kind === 'reading' ? slower.typical.read : slower.typical.write}
					{@const geometry = rankedList(readings, { max: knobs.fleet_top_kinds, minCount: knobs.slower_machines_min_articles,
						rules: target === null ? [] : [{ at: target, label: slower.reference.cpuModel ?? 'Reference machine' }] })}
					<div>
					<h4>{kind === 'reading' ? 'Prefill' : 'Decode'} - median (p50), notch p90</h4>
					<RankedList {geometry} caption={kind === 'reading' ? 'Prefill' : 'Decode'} maxText={`${geometry === null ? '0' : formatNumber(geometry.max, numberFormat, { si: false })} seconds`} fitRuleLabels
						unmeasuredNote="No comparable reading." emptyNote="No comparable reading." />
					</div>
				{/each}
			</div>
			<p>{slower.withoutReference} runs had no reference-machine reading. {slower.reference.unqualified} articles lacked a comparable reading.</p>
			<MachinePhases {rows} hosts={hostRows} {numberFormat} />
		{:else if id === 'closest-to-memory'}
			<p class="lede" data-lede>{tightest?.ends
				? `The tightest article left ${formatNumber(tightest.ends.end - tightest.value, numberFormat, { si: false })} GiB of the machine's ${formatNumber(tightest.ends.end, numberFormat, { si: false })} GiB free.`
				: 'No article recorded available memory.'}</p>
			<RankedList geometry={closest} caption="Memory held against machine memory" maxText={`${closest === null ? '0' : formatNumber(closest.max, numberFormat, { si: false })} GiB`}
				unmeasuredNote="Memory was not recorded." emptyNote="Memory was not recorded." />
		{:else if id === 'context-headroom'}
			<p class="lede" data-lede>{context.limits.length
				? `${formatNumber(100 * Math.max(0, ...context.label, ...context.summary) / context.limits[0], numberFormat, { si: false })} percent of the smallest reading limit for the largest prompt.`
				: 'No request-slot limit was recorded.'}</p>
			{#if context.limits.length}<p>{context.limits[0]} tokens per request slot, at the smallest recorded limit.</p>{/if}
			<div class="halves auto-grid">
				{#each ['label', 'summary'] as call}
					<div use:observeWidth={(px) => (width = px)}><Distribution geometry={distribution(call === 'label' ? context.label : context.summary, {
						frame: contextBox, minValues: knobs.context_min_values, valueTicks: 4, scale: 'log', domain: contextDomain, rules: context.rules,
						number_format: numberFormat
					})} empty={emptyState('quiet', 'Too few positive request readings to draw a distribution.')}
						name={`context-${call}`} label={`${call} request tokens, logarithmic scale`} width={contextBox.width} height={contextBox.height} readoutMaxShare={chart.readout_max_share} /></div>
				{/each}
			</div>
			<p>{context.cut ? `${context.cut} articles were cut.` : 'No article was cut in this window.'}
				{context.limits.length > 1 ? ` Other request-slot limits: ${context.limits.slice(1).join(', ')} tokens.` : ''}</p>
		{/if}
	</div>
</Panel>
</div>

<style>
	.lede { font-size: var(--console-page-title-size); line-height: var(--console-page-title-leading); font-weight: var(--console-page-title-weight); }
	.halves > div { min-width: 0; }
	h4 { font-size: var(--console-body-size); line-height: var(--console-body-leading); margin-block: var(--console-control-gap); }
</style>
