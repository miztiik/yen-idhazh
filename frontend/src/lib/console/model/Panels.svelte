<script lang="ts">
	import type { Row } from '../../data/ledger';
	import type { Range } from '../queries/window';
	import type { ModelRule } from '../../charts/d3/model-rule';
	import type { ChartConfig, ConsoleConfig } from '../../server/config';
	import Series from './Series.svelte';
	import ThroughputTrend from '../../components/ThroughputTrend.svelte';
	import TimeCost from '../TimeCost.svelte';
	import ItemCost from './ItemCost.svelte';
	import CallCutoffs from './CallCutoffs.svelte';
	import RunLengths from '../../components/RunLengths.svelte';
	import { modelThroughput } from './model-throughput';
	import { faithfulness } from './faithfulness';
	import { summaryLength } from './summary-length';
	import { median } from './rows';
	import { completeModelRule } from './model-rule';
	import { useNumberFormat } from '$lib/number-format-context';
	import { formatNumber } from '$lib/number-format';

	let { id, rows, range, rule, chart, knobs, thresholds, throughputReference }: {
		id: string; rows: readonly Row[][]; range: Range; rule: ModelRule; chart: ChartConfig;
		knobs: ConsoleConfig; thresholds: { high: number; low: number };
		throughputReference: string;
	} = $props();
	const numberFormat = useNumberFormat();
	const window = $derived({ start: range.from, end: range.to, days: range.days });
	const throughputs = $derived(id === 'model-throughput' ? modelThroughput(rows[0], window) : []);
	const scores = $derived(id === 'faithfulness' ? faithfulness(rows[0], thresholds, { step: knobs.faithfulness_axis_step, floorMax: knobs.faithfulness_axis_floor_max }, numberFormat) : null);
	const lengths = $derived(id === 'summary-length' ? summaryLength(rows[0]) : []);
	const lengthRule = $derived(completeModelRule(rule, lengths.map((run) => run.date)));
	const speedRule = $derived(completeModelRule(rule, throughputs.map((day) => day.date)));
</script>

{#if id === 'model-throughput'}
	<p data-lede>{throughputs.at(-1) === undefined ? 'not measured' : formatNumber(throughputs.at(-1)!.write.median, numberFormat, { si: false })} tokens per second on the newest day</p>
	<p data-comparison="each day's rate against the window's median">Each day's rate against the window's median.</p>
	<ThroughputTrend days={throughputs} height={chart.height_px} width={chart.width_px} reference={throughputReference}
		tickDensity={chart.tick_density} readoutMaxShare={chart.readout_max_share} windowDays={range.days} rule={speedRule} />
{:else if id === 'item-cost'}
	<ItemCost rows={rows[0]} {knobs} {chart} />
{:else if id === 'call-ending'}
	<CallCutoffs rows={rows[0]} {range} {rule} {chart} />
{:else if scores !== null}
	<div data-eval-panel="faithfulness" data-match-floor={scores.floor}>
	<p data-lede>{scores.days.at(-1)?.matchMid == null ? 'Faithfulness was not measured.' : `${scores.days.at(-1)?.matchMid}% median faithfulness`}</p>
	<p data-comparison="each day's median (p50) against its interquartile range (p25-p75)">Each day's median (p50) against its interquartile range (p25-p75): the span holding the middle half of that day's scores.</p>
	<Series series={scores.series} {rule} {chart} name="faithfulness" rules={scores.rules} domain={[scores.floor, 100]} />
	{#if scores.wider !== null}<p>{scores.wider}</p>{/if}
	<p data-model-match-note>For a flagged summary: Automated check found a possible mismatch. Read the original.</p>
	</div>
{:else if id === 'score-cost'}
	<TimeCost {id} rows={rows[0]} {range} {chart} />
{:else if id === 'summary-length'}
	<p data-lede>{median(lengths.map((run) => run.median)) ?? 'not measured'} median words per run</p>
	<p data-comparison="each run's median (p50) length against its shortest and longest">Each run's median (p50) length against its shortest and longest.</p>
	<div data-eval-panel="summary-length">
		<RunLengths runs={lengths} width={chart.width_px} height={chart.height_px} tickDensity={chart.tick_density} readoutMaxShare={chart.readout_max_share} rule={lengthRule} />
		{#if 'changes' in lengthRule && lengthRule.note !== null}<p data-model-rule-empty={lengthRule.changes.length ? undefined : 'summary-length'} data-model-rule-unread="summary-length">{lengthRule.note}</p>{/if}
	</div>
{/if}
