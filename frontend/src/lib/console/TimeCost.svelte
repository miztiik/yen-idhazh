<script lang="ts">
	import type { Row } from '../data/ledger';
	import type { Range } from './queries/window';
	import type { ChartConfig } from '../server/config';
	import TimeHistogram from '../components/TimeHistogram.svelte';
	import { cost } from './model/cost';
	import { SERIES_TOKENS } from './series-tokens';
	import { grouped as formatGrouped } from '../charts/series';
	import { useNumberFormat } from '../number-format-context';
	import { formatNumber } from '../number-format';
	import { nameSpan } from './span-words';

	let { id, rows, range, chart }: {
		id: 'write-cost' | 'score-cost'; rows: readonly Row[]; range: Range; chart: ChartConfig;
	} = $props();
	const numberFormat = useNumberFormat();
	const grouped = (value: number) => formatGrouped(value, numberFormat);
	const times = $derived(cost(rows, id === 'write-cost' ? 'summarize_ms' : 'score_ms'));
</script>

<p data-lede class="lede">{times.times === null ? 'not measured' : formatNumber(times.times.median / 1000, numberFormat, { si: false })} median seconds</p>
<p data-comparison="each time band's count against the share done by then">Each time band's count against the share done by then.</p>
{#if times.times !== null}
	<figure data-eval-panel={id} data-chart={id}>
		<TimeHistogram times={times.times} name={id === 'write-cost' ? 'write-times' : 'score-cost'}
			subject={id === 'write-cost' ? 'seconds to write one summary' : 'seconds to check one summary'}
			verb={id === 'write-cost' ? 'written' : 'checked'} noRuleReason="One distribution pools the window, so a setting change has no date on this axis."
			width={chart.width_px} height={chart.height_px} readoutMaxShare={chart.readout_max_share}
			barToken={id === 'write-cost' ? SERIES_TOKENS['summary-call'] : SERIES_TOKENS.checking} />
	</figure>
{:else}<p data-model-rule="no" data-model-rule-name={id} data-model-rule-none="One distribution pools the window, so a setting change has no date on this axis." data-readout-none="No measured clock readings were available.">No positive clock reading was recorded in this window.</p>{/if}
<p data-write-times={id === 'write-cost' ? 'readout' : undefined} data-score-cost={id === 'score-cost' ? 'readout' : undefined}>
	{times.times === null ? 'No measured summaries' : `${grouped(times.times.n)} summaries`} in {nameSpan(range.days)}.
	Median <span data-score-cost={id === 'score-cost' ? 'median' : undefined}>{times.times === null ? 'not measured' : Math.round(times.times.median / 1000) === 0 ? '<1 s' : `${Math.round(times.times.median / 1000)} s`}</span>;
	95th <span data-score-cost={id === 'score-cost' ? 'p95' : undefined}>{times.times === null ? 'not measured' : Math.round(times.times.p95 / 1000) === 0 ? '<1 s' : `${Math.round(times.times.p95 / 1000)} s`}</span>.
	{times.untimed} rows had no measured clock.
	{#if id === 'score-cost'}The checker runs after the model has finished; this clock is not part of the model's writing time.{/if}
</p>

<style>
	.lede { font-size: var(--text-xl); line-height: var(--leading-xl); font-weight: var(--console-value-weight); }
</style>
