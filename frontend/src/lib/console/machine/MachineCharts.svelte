<script lang="ts">
	import Panel from '$lib/components/Panel.svelte';
	import RankedList from '$lib/components/RankedList.svelte';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import Distribution from '$lib/charts/d3/Distribution.svelte';
	import { rankedList } from '$lib/charts/d3/rankedList';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import { distribution } from '$lib/charts/d3/distribution';
	import { emptyState } from '$lib/charts/d3/empty';
	import { AXIS_LABEL_GAP_PX, chartWidth, labelWidth, MARGIN, observeWidth } from '$lib/charts/frame';
	import { useChartFrame, useChartLabels } from '$lib/charts/label-context';
	import { clockAgreement, clocksChart } from '$lib/charts/machine';
	import { formatNumber } from '$lib/number-format';
	import { settingsRules } from '$lib/console/settings-moved';
	import { nameSpan } from '$lib/console/span-words';
	import { shortDate } from '$lib/format';
	import { closestToMemory, contextReadings, labelHeldMedian, reuseChecks, reuseSeries, slowerMachines, textRows } from './records';
	import type { ConsoleShell } from '$lib/console/band';
	import type { Row } from '$lib/data/ledger';
	import type { ChartConfig } from '$lib/server/config';
	import type { MachineRun as CounterRun } from './counters';

	let { id, title, rows, newest = null, newestRunId = null, chart, shell, start, end, knobs, windowDays }: {
		id: string; title: string; rows: readonly Row[];
		newest?: CounterRun | null; newestRunId?: string | null; chart: ChartConfig; shell: ConsoleShell;
		start: string; end: string; knobs: Readonly<Record<string, number>>; windowDays: number;
	} = $props();
	const numberFormat = $derived(chart.number_format);
	const frame = useChartFrame(() => chart);
	const labels = useChartLabels();
	let width = $state<number | null>(null);
	const box = $derived(frame(chartWidth(width, chart.width_px), chart.height_px));
	const contextBox = $derived(frame(chartWidth(width, chart.width_px), chart.height_px,
		{ ...MARGIN, right: Math.ceil(labelWidth('100%', labels()) + AXIS_LABEL_GAP_PX) }));
	const declined = { declined: 'This compares records within one run or kind, not a change over days.' };
	const rule = $derived(settingsRules(shell, { from: start, to: end }, 'none'));
	const slower = $derived(slowerMachines(rows));
	const comparableKinds = $derived(new Set([...slower.reading, ...slower.writing]
		.filter((row) => (row.range?.count ?? 0) >= knobs.slower_machines_min_articles).map((row) => row.label)));
	const memoryReadings = $derived(closestToMemory(rows));
	const closest = $derived(rankedList(memoryReadings, { max: knobs.closest_to_memory_rows }));
	const tightest = $derived([...memoryReadings].sort((a, b) => b.value - a.value || a.label.localeCompare(b.label))[0]);
	const clocks = $derived(clockAgreement(newest, textRows(rows), knobs.clocks_agree_within_pct));
	const gaps = $derived(clocks.pairs.flatMap((pair) => pair.gapPct === null ? [] : [pair.gapPct]));
	const widestGap = $derived(gaps.length ? Math.max(...gaps) : null);
	const readingLeader = $derived([...slower.reading].filter((row) => (row.range?.count ?? 0) >= knobs.slower_machines_min_articles)
		.sort((a, b) => b.value - a.value)[0]);
	const reuseMedian = $derived(labelHeldMedian(rows));
	const comparison = $derived(id === 'two-clocks' ? "Each shard's gap against the tolerance"
		: id === 'slower-machines' ? "Each machine kind's typical time against the reference machine's"
		: id === 'closest-to-memory' ? "Memory held at each article's lowest point against the machine's total"
		: id === 'context-headroom' ? 'Each prompt against the reading limit'
		: 'Text held for the label call against text the summary call reads fresh');
	const clockRows = $derived(clocksChart(clocks.pairs, knobs.clocks_agree_within_pct, numberFormat));
	const context = $derived(contextReadings(rows));
	const contextDomain = $derived([
		Math.min(1, ...context.label, ...context.summary, ...context.rules.map((one) => one.at)),
		Math.max(10, ...context.label, ...context.summary, ...context.rules.map((one) => one.at))
	] as [number, number]);
	const series = $derived(reuseSeries(rows));
	const drawing = $derived(dateSeries(series, {
		frame: box,
		density: chart.tick_density,
		valueTicks: 4,
		padding: 0.2,
		rule,
		number_format: numberFormat
	}));
	const ruleNote = $derived.by(() => {
		if (!('changes' in rule)) return rule.declined;
		const dates = new Set(series.flatMap((one) => one.points.map((point) => point.date)));
		const undrawn = rule.changes.filter((change) => !dates.has(change.date));
		return [rule.note, ...undrawn.map((change) =>
			`${change.words} (${change.date}), but this chart has no measured column on that day; a comparison across it crosses an undrawn settings change.`)]
			.filter(Boolean).join(' ');
	});
	const reuse = $derived(reuseChecks(rows));
</script>

<div data-windowed={{ 'context-headroom': 'machine-context', 'prompt-reuse': 'machine-prompt-reuse' }[id]}
	data-window-days={windowDays}>
<Panel {id} {title} heading="h3" verdict={id === 'two-clocks'} note={id === 'two-clocks' ? `Newest run ${newestRunId ?? newest?.runId ?? 'not recorded'}, by shard.`
	: `Read from the published record when you open this page - over ${nameSpan(windowDays)}.`}>
	<div data-panel-question="is it working"
		data-model-rule-name={id === 'prompt-reuse' ? undefined : id}
		data-model-rule={id === 'prompt-reuse' ? undefined : 'no'}
		data-model-rule-none={id === 'prompt-reuse' ? undefined : declined.declined}>
		{#if id !== 'two-clocks'}<p data-comparison={comparison}>{comparison}.</p>{/if}
		{#if id === 'two-clocks'}
			<p class="lede" data-lede data-comparison={comparison}>{widestGap === null ? 'Neither instrument recorded a comparison.'
				: `${formatNumber(widestGap, numberFormat, { si: false })}% max gap; ${formatNumber(knobs.clocks_agree_within_pct, numberFormat, { si: false })}% allowed.`}</p>
				<RankedList geometry={clockRows} caption="The two clocks" maxText={`${clockRows === null ? '0' : formatNumber(clockRows.max, numberFormat, { si: false })}% apart`} fitRuleLabels
				unmeasuredNote="One instrument recorded nothing." emptyNote="One instrument recorded nothing." />
			{#each clocks.pairs as pair (pair.label)}
				<p data-clock-pair={pair.label} data-clock-gap={pair.gapPct?.toFixed(2) ?? ''} data-clock-agrees={pair.agrees === null ? 'unknown' : String(pair.agrees)}>
					{pair.label}: {pair.gapPct === null ? 'one instrument recorded nothing' : `${formatNumber(pair.gapPct, numberFormat, { si: false })}% apart`}.
				</p>
			{/each}
			{#if newest}<p data-planned-shards>{newest.shards === null ? 'The planned shard count was not recorded.'
				: `${newest.reported.length} of ${newest.shards} planned shards recorded work.`}</p>{/if}
		{:else if id === 'slower-machines'}
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
					<RankedList {geometry} caption={kind === 'reading' ? 'Reading' : 'Writing'} maxText={`${geometry === null ? '0' : formatNumber(geometry.max, numberFormat, { si: false })} seconds`} fitRuleLabels
						unmeasuredNote="No comparable reading." emptyNote="No comparable reading." />
				{/each}
			</div>
			<p>{slower.withoutReference} runs had no reference-machine reading. {slower.reference.unqualified} articles lacked a comparable reading.</p>
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
		{:else}
			<p class="lede" data-lede>{reuseMedian === null ? 'No label request recorded held text.' : `${formatNumber(reuseMedian, numberFormat)} tokens held for the middle label request.`}</p>
			<div use:observeWidth={(px) => (width = px)}><DateSeries geometry={drawing}
				readout={drawing === null ? null : { ...drawing.readout, columns: drawing.dates.map(shortDate) }}
				empty={emptyState('quiet', 'Nothing recorded for this comparison.')}
				name={id} label={title} width={box.width} height={box.height} readoutMaxShare={chart.readout_max_share} /></div>
			{#if ruleNote}<p data-model-rule-empty={id}>{ruleNote}</p>{/if}
			{#each reuse as check}<p>{check.call}: our pooled held share {check.ours === null ? 'not recorded' : formatNumber(check.ours, numberFormat, { si: false })}%;
				server's middle held share {check.server === null ? 'not recorded' : formatNumber(check.server, numberFormat, { si: false })}%; {formatNumber(check.count, numberFormat, { exact: true, si: false })} complete article readings.</p>{/each}
		{/if}
	</div>
</Panel>
</div>

<style>
	.lede { font-size: var(--console-page-title-size); line-height: var(--console-page-title-leading); font-weight: var(--console-page-title-weight); }
	.halves > div { min-width: 0; }
</style>
