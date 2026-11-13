<script lang="ts">
	import type { Row } from '../../data/ledger';
	import type { Range } from '../queries/window';
	import type { ModelRule } from '../../charts/d3/model-rule';
	import type { ChartConfig, ConsoleConfig, SummaryBand } from '../../server/config';
	import Series from './Series.svelte';
	import ThroughputTrend from '../../components/ThroughputTrend.svelte';
	import TimeCost from '../TimeCost.svelte';
	import ItemCost from './ItemCost.svelte';
	import RunLengths from '../../components/RunLengths.svelte';
	import RankedList from '../../components/RankedList.svelte';
	import { modelThroughput } from './model-throughput';
	import { callEnding } from './call-ending';
	import { faithfulness } from './faithfulness';
	import { sourceDoubts } from './source-doubts';
	import { summaryLength } from './summary-length';
	import { RECORDED } from '../eval-instruments';
	import { rankedList } from '../../charts/d3/rankedList';
	import { rank } from '../../charts/rank';
	import { median } from './rows';
	import { completeModelRule } from './model-rule';
	import { useNumberFormat } from '$lib/number-format-context';
	import { formatNumber } from '$lib/number-format';

	let { id, rows, range, rule, chart, knobs, bands, thresholds, throughputReference }: {
		id: string; rows: readonly Row[][]; range: Range; rule: ModelRule; chart: ChartConfig;
		knobs: ConsoleConfig; bands: readonly SummaryBand[]; thresholds: { high: number; low: number };
		throughputReference: string;
	} = $props();
	const numberFormat = useNumberFormat();
	const window = $derived({ start: range.from, end: range.to, days: range.days });
	const throughputs = $derived(id === 'model-throughput' ? modelThroughput(rows[0], window) : []);
	const endings = $derived(id === 'call-ending' ? callEnding(rows[0]) : null);
	const scores = $derived(id === 'faithfulness' ? faithfulness(rows[0], thresholds, { step: knobs.faithfulness_axis_step, floorMax: knobs.faithfulness_axis_floor_max }, numberFormat) : null);
	const sources = $derived(id === 'source-doubts' ? sourceDoubts(rows[0], rows[1], window, { limit: knobs.doubt_rows, minForShare: knobs.min_attempts_for_rate }) : null);
	const lengths = $derived(id === 'summary-length' ? summaryLength(rows[0], bands) : []);
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
{:else if endings !== null}
	<p data-lede>{endings.calls === 0 ? 'Call endings were not measured.' : `${endings.length} calls cut off at the length limit, out of ${endings.calls} recorded endings`}</p>
	<p data-comparison="calls cut off against calls that ended on their own">Calls cut off at the length limit against calls that ended on their own. Each call has one ending.</p>
	<Series series={endings.series} {rule} {chart} name="call-ending" stacked />
	{#if endings.calls > 0 && endings.length === 0}<p>No call was cut off at the length limit in these {range.days} days.</p>{/if}
{:else if scores !== null}
	<div data-eval-panel="faithfulness" data-match-floor={scores.floor}>
	<p data-lede>{scores.days.at(-1)?.matchMid == null ? 'Faithfulness was not measured.' : `${scores.days.at(-1)?.matchMid}% median faithfulness`}</p>
	<p data-comparison="each day's median against its middle half">Each day's median against its middle half.</p>
	<Series series={scores.series} {rule} {chart} name="faithfulness" rules={scores.rules} domain={[scores.floor, 100]} />
	<p>{scores.wider}</p>
	<p data-model-match-rule>These scores are banded on the site's agreed thresholds.</p>
	<p data-model-match-intro>{thresholds.high}% clears the high band and {thresholds.low}% clears the middle band. A line crosses the plot at each one the days on it reach.</p>
	<table data-match-days data-model-match-days={range.days}><caption>Faithfulness, in whole percent.</caption><thead><tr><th>Day</th><th>Lower quarter</th><th>Median</th><th>Upper quarter</th></tr></thead>
		<tbody>{#each scores.days as day}<tr data-match-day={day.date} data-match-mid={day.matchMid} data-match-low={day.matchLow} data-match-high={day.matchHigh} data-match-checked={day.matched}><th>{day.date}</th><td>{day.matchLow}</td><td>{day.matchMid}</td><td>{day.matchHigh}</td></tr>{/each}</tbody>
	</table>
	</div>
{:else if sources !== null}
	<p data-lede>{sources.rows.length === 0 ? (sources.unattributed > 0 ? 'No scored summary could be joined to a source.' : `The checker doubted no source in these ${range.days} days.`) :
		sources.rows[0].sharePct === null ? 'The top source has too few summaries to draw a share.' : `${sources.rows[0].sharePct}% of the top source's summaries were doubted`}</p>
	<p data-comparison="each source's doubted share against all sources' share">Each source's doubted share against all sources' share.</p>
	<div data-eval-panel="source-doubts" data-model-doubt data-model-doubt-days={range.days}
		data-model-doubt-from={range.from} data-model-doubt-to={range.to}
		data-model-rule="no" data-model-rule-name="source-doubts" data-model-rule-none="A source ranking pools the selected window, so a change has no dated position.">
		<p data-model-doubt-rule>The order is the count and never the share.</p>
		<p data-model-doubt-intro>The checker counted sources {range.days === 1 ? 'over this one day' : `over these ${range.days} days`}. For example, 2 doubted of 3 is a larger share but a smaller count than 40 of 400.</p>
		<div data-model-doubt-list>
		<RankedList caption="Which sources the checker doubts" geometry={sources.geometry} maxText="100 percent"
			measured={sources.sources > 0} unmeasuredNote="No source could be joined to these scores." emptyNote="The checker doubted no source in this window.">
			{#snippet trend(row)}
				{@const source = sources.rows.find((s) => s.sourceId === row.key)}
				{#if source}
					<p><span data-doubt-count="not-sure" data-doubt-n={source.notSure}>{source.notSure} marked "not sure"</span>;
						<span data-doubt-count="unsupported" data-doubt-n={source.unsupportedNumbers}>{source.unsupportedNumbers} with numbers not in the article</span>;
						<span data-doubt-count="hedge" data-doubt-n={source.hedgeDropped}>{source.hedgeDropped} with "maybe" told as fact</span>.</p>
					<p>{RECORDED.find((i) => i.id === 'evidential_density')?.label}: <span data-instrument="evidential_density">{source.evidential === null ? 'not measured' : `${formatNumber(source.evidential, numberFormat, { si: false })} per 1,000 words`}</span>.</p>
					<p>{RECORDED.find((i) => i.id === 'speculative_density')?.label}: <span data-instrument="speculative_density">{source.speculative === null ? 'not measured' : `${formatNumber(source.speculative, numberFormat, { si: false })} per 1,000 words`}</span>.</p>
				{/if}
			{/snippet}
		</RankedList>
		</div>
		{#if sources.unattributed > 0}<p data-model-doubt-unattributed>{sources.unattributed} scored summaries could not be traced to a source. They are counted in neither list.</p>{/if}
		<p>{sources.moreSources} more sources had {sources.moreDoubted} doubted summaries.</p>
		{#each RECORDED.filter((i) => ['evidential_density', 'speculative_density'].includes(i.id)) as instrument}<p>{instrument.label}: {instrument.note}</p>{/each}
		<p>Nothing acts on these numbers.</p>
	</div>
{:else if id === 'score-cost'}
	<TimeCost {id} rows={rows[0]} {range} {chart} />
{:else if id === 'summary-length'}
	<p data-lede>{median(lengths.map((run) => run.median)) ?? 'not measured'} median words per run</p>
	<p data-comparison="each run's middle length against its shortest and longest">Each run's middle length against its shortest and longest.</p>
	<div data-eval-panel="summary-length">
		<RunLengths runs={lengths} width={chart.width_px} height={chart.height_px} tickDensity={chart.tick_density} readoutMaxShare={chart.readout_max_share} rule={lengthRule} />
		<table><caption>{RECORDED.find((i) => i.id === 'compression')?.label}</caption><thead><tr><th>Run</th><th>Median compression</th></tr></thead>
			<tbody>{#each lengths as run}<tr data-run-compression={run.runId}><th>{run.runId}</th><td data-instrument="compression">{run.compression === null ? 'not measured' : `${Math.round(run.compression * 100)}%`}</td></tr>{/each}</tbody>
		</table>
		<p>{RECORDED.find((i) => i.id === 'compression')?.note}</p><p>Nothing acts on these numbers.</p>
		{#if 'changes' in lengthRule && lengthRule.note !== null}<p data-model-rule-empty={lengthRule.changes.length ? undefined : 'summary-length'} data-model-rule-unread="summary-length">{lengthRule.note}</p>{/if}
	</div>
{/if}
