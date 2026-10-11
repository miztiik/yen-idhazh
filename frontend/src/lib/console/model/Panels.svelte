<script lang="ts">
	import type { Row } from '../../data/ledger';
	import type { Range } from '../queries/window';
	import type { ModelRule } from '../../charts/d3/model-rule';
	import type { ChartConfig, ConsoleConfig, SummaryBand } from '../../server/config';
	import Series from './Series.svelte';
	import ThroughputTrend from '../../components/ThroughputTrend.svelte';
	import TimeHistogram from '../../components/TimeHistogram.svelte';
	import FailureList from '../../components/FailureList.svelte';
	import RunLengths from '../../components/RunLengths.svelte';
	import SwapDots from '../../components/SwapDots.svelte';
	import RankedList from '../../components/RankedList.svelte';
	import { failureRuleRows } from '../failure-rules';
	import { modelThroughput } from './model-throughput';
	import { callEnding } from './call-ending';
	import { faithfulness } from './faithfulness';
	import { sourceDoubts } from './source-doubts';
	import { cost } from './cost';
	import { summaryLength } from './summary-length';
	import { modelChange } from './model-change';
	import { RECORDED } from '../eval-instruments';
	import { rankedList } from '../../charts/d3/rankedList';
	import { rank } from '../../charts/rank';
	import { SERIES_TOKENS } from '../series-tokens';
	import { median } from './rows';
	import { refusingRule, MODEL_STAGES } from './refusing-rule';
	import { completeModelRule } from './model-rule';
	import { grouped } from '../../charts/series';
	import { nameSpan } from '../span-words';

	let { id, rows, range, rule, chart, knobs, bands, thresholds, throughputReference }: {
		id: string; rows: readonly Row[][]; range: Range; rule: ModelRule; chart: ChartConfig;
		knobs: ConsoleConfig; bands: readonly SummaryBand[]; thresholds: { high: number; low: number };
		throughputReference: string;
	} = $props();
	const window = $derived({ start: range.from, end: range.to, days: range.days });
	const throughputs = $derived(id === 'model-throughput' ? modelThroughput(rows[0], window) : []);
	const endings = $derived(id === 'call-ending' ? callEnding(rows[0]) : null);
	const scores = $derived(id === 'faithfulness' ? faithfulness(rows[0], thresholds, { step: knobs.faithfulness_axis_step, floorMax: knobs.faithfulness_axis_floor_max }) : null);
	const sources = $derived(id === 'source-doubts' ? sourceDoubts(rows[0], rows[1], window, { limit: knobs.doubt_rows, minForShare: knobs.min_attempts_for_rate }) : null);
	const times = $derived(id === 'write-cost' || id === 'score-cost' ? cost(rows[0], id === 'write-cost' ? 'summarize_ms' : 'score_ms') : null);
	const lengths = $derived(id === 'summary-length' ? summaryLength(rows[0], bands) : []);
	const swap = $derived(id === 'model-change' ? modelChange(rows[0], rows[1], bands, knobs.min_attempts_for_rate) : null);
	const refusals = $derived(id === 'refusing-rule' ? refusingRule(rows[0], window) : null);
	const lengthRule = $derived(completeModelRule(rule, lengths.map((run) => run.date)));
	const speedRule = $derived(completeModelRule(rule, throughputs.map((day) => day.date)));
</script>

{#if id === 'model-throughput'}
	<p data-lede>{throughputs.at(-1)?.write.median.toFixed(2) ?? 'not measured'} tokens per second on the newest day</p>
	<p data-comparison="each day's rate against the window's median">Each day's rate against the window's median.</p>
	<ThroughputTrend days={throughputs} height={chart.height_px} width={chart.width_px} reference={throughputReference}
		tickDensity={chart.tick_density} readoutMaxShare={chart.readout_max_share} windowDays={range.days} rule={speedRule} />
{:else if endings !== null}
	<p data-lede>{endings.calls === 0 ? 'Call endings were not measured.' : `${endings.length} calls cut off at the length limit, out of ${endings.calls} recorded endings`}</p>
	<p data-comparison="calls cut off against calls that ended on their own">Calls cut off at the length limit against calls that ended on their own. Each call has one ending.</p>
	<Series series={endings.series} {rule} {chart} name="call-ending" stacked />
	{#if endings.calls > 0 && endings.length === 0}<p>No call was cut off at the length limit in these {range.days} days.</p>{/if}
{:else if refusals !== null}
	<p data-lede>{refusals.top === undefined ? 'No named rule refused a model reply.' : `${refusals.top.label}: ${refusals.top.count} refusals`} at summarization</p>
	<p data-comparison="the rule that refused most against every other rule">The rule that refused most against every other rule.</p>
	<div data-model-rule="no" data-model-rule-none="A ranking pools the window and has no dated change position.">
		<FailureList ranking={refusals.ranking} stages={{ options: [...MODEL_STAGES], chosen: 'summarize' }}
			{window} selectedCode={null} max={knobs.failure_list_max} sourceMax={knobs.source_rows} readoutMaxShare={chart.readout_max_share} />
	</div>
	{#if refusals.failed === 0}<p>No rule refused a model reply in these {range.days} days.</p>{/if}
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
		data-model-rule="no" data-model-rule-none="A source ranking pools the selected window, so a change has no dated position.">
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
					<p>{RECORDED.find((i) => i.id === 'evidential_density')?.label}: <span data-instrument="evidential_density">{source.evidential === null ? 'not measured' : `${source.evidential.toFixed(1)} per 1,000 words`}</span>.</p>
					<p>{RECORDED.find((i) => i.id === 'speculative_density')?.label}: <span data-instrument="speculative_density">{source.speculative === null ? 'not measured' : `${source.speculative.toFixed(1)} per 1,000 words`}</span>.</p>
				{/if}
			{/snippet}
		</RankedList>
		</div>
		{#if sources.unattributed > 0}<p data-model-doubt-unattributed>{sources.unattributed} scored summaries could not be traced to a source. They are counted in neither list.</p>{/if}
		<p>{sources.moreSources} more sources had {sources.moreDoubted} doubted summaries.</p>
		{#each RECORDED.filter((i) => ['evidential_density', 'speculative_density'].includes(i.id)) as instrument}<p>{instrument.label}: {instrument.note}</p>{/each}
		<p>Nothing acts on these numbers.</p>
	</div>
{:else if times !== null}
	<p data-lede>{times.times === null ? 'not measured' : (times.times.median / 1000).toFixed(2)} median seconds</p>
	<p data-comparison="each time band's count against the share done by then">Each time band's count against the share done by then.</p>
	{#if times.times !== null}
		<div data-eval-panel={id}>
			<TimeHistogram times={times.times} name={id === 'write-cost' ? 'write-times' : 'score-cost'}
				subject={id === 'write-cost' ? 'seconds to write one summary' : 'seconds to check one summary'}
				verb={id === 'write-cost' ? 'written' : 'checked'} noRuleReason="One distribution pools the window, so a setting change has no date on this axis."
				width={chart.width_px} height={chart.height_px} readoutMaxShare={chart.readout_max_share}
				barToken={id === 'write-cost' ? SERIES_TOKENS['summary-call'] : SERIES_TOKENS.checking} />
		</div>
	{:else}<p data-model-rule="no" data-model-rule-none="One distribution pools the window, so a setting change has no date on this axis." data-readout-none="No measured clock readings were available.">No positive clock reading was recorded in this window.</p>{/if}
	<p data-write-times={id === 'write-cost' ? 'readout' : undefined} data-score-cost={id === 'score-cost' ? 'readout' : undefined}>
		{times.times === null ? 'No measured summaries' : `${grouped(times.times.n)} summaries`} in {nameSpan(range.days)}.
		Median <span data-score-cost={id === 'score-cost' ? 'median' : undefined}>{times.times === null ? 'not measured' : Math.round(times.times.median / 1000) === 0 ? '<1 s' : `${Math.round(times.times.median / 1000)} s`}</span>;
		95th <span data-score-cost={id === 'score-cost' ? 'p95' : undefined}>{times.times === null ? 'not measured' : Math.round(times.times.p95 / 1000) === 0 ? '<1 s' : `${Math.round(times.times.p95 / 1000)} s`}</span>.
		{times.untimed} rows had no measured clock.
		{#if id === 'score-cost'}The checker runs after the model has finished; this clock is not part of the model's writing time.{/if}
	</p>
{:else if id === 'summary-length'}
	<p data-lede>{median(lengths.map((run) => run.median)) ?? 'not measured'} median words per run</p>
	<p data-comparison="each run's middle length against its shortest and longest">Each run's middle length against its shortest and longest.</p>
	<div data-eval-panel="summary-length">
		<RunLengths runs={lengths} width={chart.width_px} height={chart.height_px} tickDensity={chart.tick_density} readoutMaxShare={chart.readout_max_share} rule={lengthRule} />
		<table><caption>{RECORDED.find((i) => i.id === 'compression')?.label}</caption><thead><tr><th>Run</th><th>Median compression</th></tr></thead>
			<tbody>{#each lengths as run}<tr data-run-compression={run.runId}><th>{run.runId}</th><td data-instrument="compression">{run.compression === null ? 'not measured' : `${Math.round(run.compression * 100)}%`}</td></tr>{/each}</tbody>
		</table>
		<p>{RECORDED.find((i) => i.id === 'compression')?.note}</p><p>Nothing acts on these numbers.</p>
		{#if 'changes' in lengthRule && lengthRule.note !== null}<p data-model-rule-empty={lengthRule.changes.length ? undefined : 'summary-length'}>{lengthRule.note}</p>{/if}
	</div>
{:else if id === 'model-change'}
	<p data-lede>{swap === null ? 'The published record holds no model change to compare.' : swap.lede}</p>
	<p data-comparison="scores after the change against scores before it">Scores after the change against scores before it. Different article populations do not establish a cause.</p>
	<div data-model-rule="no" data-model-rule-none="This panel compares the two sides of the model change itself." data-readout-none={swap === null || !swap.enough ? 'There are no comparable measured populations to draw.' : undefined}>
		{#if swap !== null}<p>The change on {swap.at}, from {swap.before.model} to {swap.after.model}; {swap.before.articles} summaries before and {swap.after.articles} after.</p>
			{#if swap.enough}<SwapDots {swap} width={chart.width_px} readoutMaxShare={chart.readout_max_share} />
			{:else}<p>Only {Math.min(swap.before.articles, swap.after.articles)} of the {knobs.min_attempts_for_rate} summaries this chart needs are on its smaller side, so it is not drawn.</p>{/if}
		{/if}
	</div>
{/if}
