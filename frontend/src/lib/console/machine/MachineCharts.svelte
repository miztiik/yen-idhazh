<script lang="ts">
	import Panel from '$lib/components/Panel.svelte';
	import RateControl from '$lib/components/RateControl.svelte';
	import RankedList from '$lib/components/RankedList.svelte';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import Distribution from '$lib/charts/d3/Distribution.svelte';
	import { rankedList } from '$lib/charts/d3/rankedList';
	import { dateSeries, type SeriesInput } from '$lib/charts/d3/dateSeries';
	import { distribution } from '$lib/charts/d3/distribution';
	import { emptyState } from '$lib/charts/d3/empty';
	import { AXIS_LABEL_GAP_PX, chartWidth, frame, labelWidth, MARGIN, observeWidth } from '$lib/charts/frame';
	import { clockAgreement, clocksChart, readAgainstWritten, workSeries, money, type CostRate } from '$lib/charts/machine';
	import { costOverDays } from '$lib/charts/cost';
	import { settingsRules } from '$lib/console/settings-moved';
	import { nameSpan } from '$lib/console/span-words';
	import { shortDate } from '$lib/format';
	import { closestToMemory, contextReadings, labelHeldMedian, reuseChecks, reuseSeries, slowestArticles, slowerMachines, textRows } from './records';
	import type { ConsoleShell } from '$lib/console/band';
	import type { Row } from '$lib/data/ledger';
	import type { ChartConfig } from '$lib/server/config';
	import type { MachineRun as CounterRun } from './counters';

	let { id, title, rows, newest = null, newestRunId = null, chart, shell, start, end, knobs, rate, windowDays }: {
		id: string; title: string; rows: readonly Row[];
		newest?: CounterRun | null; newestRunId?: string | null; chart: ChartConfig; shell: ConsoleShell;
		start: string; end: string; knobs: Readonly<Record<string, number>>; rate: CostRate; windowDays: number;
	} = $props();
	let width = $state<number | null>(null);
	const box = $derived(frame(chartWidth(width, chart.width_px), chart.height_px));
	const contextBox = $derived(frame(chartWidth(width, chart.width_px), chart.height_px,
		{ ...MARGIN, right: Math.ceil(labelWidth('100%') + AXIS_LABEL_GAP_PX) }));
	const declined = { declined: 'This compares records within one run or kind, not a change over days.' };
	const rule = $derived(settingsRules(shell, { from: start, to: end }, 'none'));
	const work = $derived(readAgainstWritten(textRows(rows)));
	const slower = $derived(slowerMachines(rows));
	const comparableKinds = $derived(new Set([...slower.reading, ...slower.writing]
		.filter((row) => (row.range?.count ?? 0) >= knobs.slower_machines_min_articles).map((row) => row.label)));
	const slowest = $derived(slowestArticles(rows));
	const memoryReadings = $derived(closestToMemory(rows));
	const closest = $derived(rankedList(memoryReadings, { max: knobs.closest_to_memory_rows }));
	const tightest = $derived([...memoryReadings].sort((a, b) => b.value - a.value || a.label.localeCompare(b.label))[0]);
	const clocks = $derived(clockAgreement(newest, textRows(rows), knobs.clocks_agree_within_pct));
	const gaps = $derived(clocks.pairs.flatMap((pair) => pair.gapPct === null ? [] : [pair.gapPct]));
	const widestGap = $derived(gaps.length ? Math.max(...gaps) : null);
	const readingLeader = $derived([...slower.reading].filter((row) => (row.range?.count ?? 0) >= knobs.slower_machines_min_articles)
		.sort((a, b) => b.value - a.value)[0]);
	const reuseMedian = $derived(labelHeldMedian(rows));
	const comparison = $derived(id === 'counterfactual-cost' ? "Each day's counterfactual cost against the running total"
		: id === 'two-clocks' ? "Each shard's gap against the tolerance"
		: id === 'slower-machines' ? "Each machine kind's typical time against the reference machine's"
		: id === 'slowest-articles' ? "Each article's longest stage against its other stages"
		: id === 'closest-to-memory' ? "Memory held at each article's lowest point against the machine's total"
		: id === 'context-headroom' ? 'Each prompt against the reading limit'
		: id === 'prompt-reuse' ? 'Text held for the label call against text the summary call reads fresh'
		: 'Tokens read against tokens written');
	const clockRows = $derived(clocksChart(clocks.pairs, knobs.clocks_agree_within_pct));
	const context = $derived(contextReadings(rows));
	const contextDomain = $derived([
		Math.min(1, ...context.label, ...context.summary, ...context.rules.map((one) => one.at)),
		Math.max(10, ...context.label, ...context.summary, ...context.rules.map((one) => one.at))
	] as [number, number]);
	// The operator owns these values after mount; the configured price only starts the control.
	// svelte-ignore state_referenced_locally
	let inputPrice = $state(rate.inputPerMillion);
	// svelte-ignore state_referenced_locally
	let outputPrice = $state(rate.outputPerMillion);
	let rateSource = $state<'configured' | 'yours'>('configured');
	const prices = $derived({ ...rate, inputPerMillion: inputPrice, outputPerMillion: outputPrice });
	const cost = $derived(costOverDays(work.runs, prices));
	const priced = $derived({
		input: cost.days.reduce((sum, day) => sum + day.read, 0),
		output: cost.days.reduce((sum, day) => sum + day.written, 0),
		items: cost.days.reduce((sum, day) => sum + day.items, 0)
	});
	const series = $derived.by((): SeriesInput[] => {
		if (id === 'prompt-reuse') return reuseSeries(rows);
		if (id === 'counterfactual-cost') return [{ label: `Running counterfactual total, ${rate.currency}`, token: '--chart-1',
			points: cost.days.map((day) => ({ date: day.date, value: day.running })) }];
		return workSeries(work.runs, 'tokens');
	});
	const drawing = $derived(dateSeries(series, { frame: box, density: chart.tick_density, valueTicks: 4, padding: 0.2, rule }));
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

<div data-windowed={{ 'context-headroom': 'machine-context', 'prompt-reuse': 'machine-prompt-reuse',
	'read-against-written': 'machine-tokens', 'counterfactual-cost': 'machine-cost' }[id]}
	data-window-days={windowDays}
	data-cost-running-total={id === 'counterfactual-cost' ? cost.runningTotal : undefined}>
<Panel {id} {title} heading="h3" verdict={id === 'two-clocks'} note={id === 'slowest-articles'
	? `Queue wait sits outside elapsed time - one article of the newest run ${slowest.run ?? 'not recorded'}.`
	: id === 'two-clocks' ? `Two independent instruments, never two copies of one counter - one shard of the newest run ${newestRunId ?? newest?.runId ?? 'not recorded'}.`
	: `Read from the published record when you open this page - over ${nameSpan(windowDays)}.`}>
	<div data-panel-question="is it working"
		data-model-rule-name={['prompt-reuse', 'read-against-written', 'counterfactual-cost'].includes(id) ? undefined : id}
		data-model-rule={['prompt-reuse', 'read-against-written', 'counterfactual-cost'].includes(id) ? undefined : 'no'}
		data-model-rule-none={['prompt-reuse', 'read-against-written', 'counterfactual-cost'].includes(id) ? undefined : declined.declined}>
		<p data-comparison={comparison}>{comparison}.</p>
		{#if id === 'two-clocks'}
			<p class="lede" data-lede>{widestGap === null ? 'Neither instrument recorded a comparison.'
				: clocks.disagreeing === 0 && gaps.length === clocks.pairs.length &&
					newest?.shards !== null && newest?.reported.length === newest?.shards
					? `Every shard's two clocks agreed within ${knobs.clocks_agree_within_pct} percent in the newest run.`
					: `${widestGap.toFixed(2)} percent was the widest gap between the two clocks.`}</p>
			<RankedList geometry={clockRows} caption="The two clocks" maxText={`${clockRows?.max.toFixed(1) ?? '0'}% apart`} fitRuleLabels
				unmeasuredNote="One instrument recorded nothing." emptyNote="One instrument recorded nothing." />
			{#each clocks.pairs as pair (pair.label)}
				<p data-clock-pair={pair.label} data-clock-gap={pair.gapPct?.toFixed(2) ?? ''} data-clock-agrees={pair.agrees === null ? 'unknown' : String(pair.agrees)}>
					{pair.label}: {pair.gapPct === null ? 'one instrument recorded nothing' : `${pair.gapPct.toFixed(2)}% apart`}.
				</p>
			{/each}
			{#if newest}<p data-planned-shards>{newest.shards === null ? 'The planned shard count was not recorded.'
				: `${newest.reported.length} of ${newest.shards} planned shards recorded work.`}</p>{/if}
		{:else if id === 'slower-machines'}
			<p class="lede" data-lede>{comparableKinds.size === 0 ? 'No machine recorded enough comparable work.'
				: comparableKinds.size === 1 ? slower.reference.referenceRows === rows.length
					? 'Every article ran on one kind of machine.' : 'Only one kind of machine has enough comparable work.'
				: readingLeader && slower.typical.read !== null && slower.typical.read > 0
					? `${readingLeader.label} took ${(readingLeader.value / slower.typical.read).toFixed(2)} times ${slower.reference.cpuModel}'s typical reading time.`
					: 'No machine recorded enough comparable reading work.'}</p>
			<div class="halves">
				{#each ['reading', 'writing'] as kind}
					{@const readings = kind === 'reading' ? slower.reading : slower.writing}
					{@const target = kind === 'reading' ? slower.typical.read : slower.typical.write}
					{@const geometry = rankedList(readings, { max: knobs.fleet_top_kinds, minCount: knobs.slower_machines_min_articles,
						rules: target === null ? [] : [{ at: target, label: slower.reference.cpuModel ?? 'Reference machine' }] })}
					<RankedList {geometry} caption={kind === 'reading' ? 'Reading' : 'Writing'} maxText={`${geometry?.max.toFixed(2) ?? '0'} seconds`} fitRuleLabels
						unmeasuredNote="No comparable reading." emptyNote="No comparable reading." />
				{/each}
			</div>
			<p>{slower.withoutReference} runs had no reference-machine reading. {slower.reference.unqualified} articles lacked a comparable reading.</p>
		{:else if id === 'slowest-articles'}
			{@const geometry = rankedList(slowest.rows, { max: knobs.slowest_articles_rows })}
			<p class="lede" data-lede>{geometry?.rows.length ? `${geometry.rows[0].value.toFixed(1)} seconds for the slowest article.` : 'No article recorded elapsed time.'}</p>
			<RankedList {geometry} caption="Longest articles" maxText={`${geometry?.max.toFixed(1) ?? '0'} seconds`}
				unmeasuredNote="No elapsed time recorded." emptyNote="No elapsed time recorded." />
			<p>{slowest.unmeasured} articles did not record elapsed time.</p>
		{:else if id === 'closest-to-memory'}
			<p class="lede" data-lede>{tightest?.ends
				? `The tightest article left ${(tightest.ends.end - tightest.value).toFixed(2)} GiB of the machine's ${tightest.ends.end.toFixed(2)} GiB free.`
				: 'No article recorded available memory.'}</p>
			<RankedList geometry={closest} caption="Memory held against machine memory" maxText={`${closest?.max.toFixed(2) ?? '0'} GiB`}
				unmeasuredNote="Memory was not recorded." emptyNote="Memory was not recorded." />
		{:else if id === 'context-headroom'}
			<p class="lede" data-lede>{context.limits.length
				? `${(100 * Math.max(0, ...context.label, ...context.summary) / context.limits[0]).toFixed(1)} percent of the smallest reading limit for the largest prompt.`
				: 'No request-slot limit was recorded.'}</p>
			{#if context.limits.length}<p>{context.limits[0]} tokens per request slot, at the smallest recorded limit.</p>{/if}
			<div class="halves">
				{#each ['label', 'summary'] as call}
					<div use:observeWidth={(px) => (width = px)}><Distribution geometry={distribution(call === 'label' ? context.label : context.summary, {
						frame: contextBox, minValues: knobs.context_min_values, valueTicks: 4, scale: 'log', domain: contextDomain, rules: context.rules
					})} empty={emptyState('quiet', 'Too few positive request readings to draw a distribution.')}
						name={`context-${call}`} label={`${call} request tokens, logarithmic scale`} width={contextBox.width} height={contextBox.height} readoutMaxShare={chart.readout_max_share} /></div>
				{/each}
			</div>
			<p>{context.cut ? `${context.cut} articles were cut.` : 'No article was cut in this window.'}
				{context.limits.length > 1 ? ` Other request-slot limits: ${context.limits.slice(1).join(', ')} tokens.` : ''}</p>
		{:else}
			<p class="lede" data-lede>{id === 'counterfactual-cost'
				? `${cost.runningTotal.toFixed(4)} ${rate.currency}, counterfactual, never a bill.`
				: id === 'prompt-reuse' ? reuseMedian === null ? 'No label request recorded held text.' : `${reuseMedian.toFixed(0)} tokens held for the middle label request.`
					: work.runs.length && work.runs.reduce((sum, run) => sum + run.output, 0) > 0
						? `${(work.runs.reduce((sum, run) => sum + run.input, 0) / work.runs.reduce((sum, run) => sum + run.output, 0)).toFixed(2)} tokens read for each token written.`
						: 'No run recorded both token counts.'}</p>
			{#if id === 'counterfactual-cost'}
				<RateControl configured={rate} bind:inputRate={inputPrice} bind:outputRate={outputPrice} bind:source={rateSource} />
				<dl class="costs" data-cost-figures data-cost-source={rateSource}>
					<div data-cost="input"><dt>Reading the prompts</dt><dd>{money(priced.input, rate.currency, 2)}</dd></div>
					<div data-cost="output"><dt>Writing the answers</dt><dd>{money(priced.output, rate.currency, 2)}</dd></div>
					<div data-cost="total"><dt>This window</dt><dd>{money(cost.runningTotal, rate.currency, 2)}</dd></div>
					<div data-cost="per-article"><dt>An article, out of {priced.items}</dt><dd>{priced.items ? money(cost.runningTotal / priced.items, rate.currency, 4) : 'Not recorded'}</dd></div>
				</dl>
			{/if}
			<div use:observeWidth={(px) => (width = px)}><DateSeries geometry={drawing}
				readout={drawing === null ? null : { ...drawing.readout, columns: drawing.dates.map(shortDate) }}
				empty={emptyState('quiet', 'Nothing recorded for this comparison.')}
				name={id} label={title} width={box.width} height={box.height} readoutMaxShare={chart.readout_max_share} /></div>
			{#if ruleNote}<p data-model-rule-empty={id}>{ruleNote}</p>{/if}
			{#if id === 'prompt-reuse'}{#each reuse as check}<p>{check.call}: our pooled held share {check.ours?.toFixed(1) ?? 'not recorded'}%;
				server's middle held share {check.server?.toFixed(1) ?? 'not recorded'}%; {check.count} complete article readings.</p>{/each}{/if}
		{/if}
	</div>
</Panel>
</div>

<style>
	.lede { font-size: var(--text-xl); line-height: var(--leading-tight); font-weight: 600; }
	.halves { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-4); }
	.halves > div { min-width: 0; }
	.costs { display: flex; flex-wrap: wrap; gap: var(--space-4); }
	.costs dd { margin: 0; font-weight: 600; font-variant-numeric: tabular-nums; }
	@media (max-width: 48rem) { .halves { grid-template-columns: minmax(0, 1fr); } }
</style>
