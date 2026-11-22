<script lang="ts">
	import Panel from '$lib/components/Panel.svelte';
	import Reserved from '$lib/components/Reserved.svelte';
	import PartsOfOne from '$lib/charts/d3/PartsOfOne.svelte';
	import { partsOfOne } from '$lib/charts/d3/partsOfOne';
	import { emptyState } from '$lib/charts/d3/empty';
	import { factsOf } from '$lib/charts/readout';
	import { judgeCutoff, judgeDecimal, judgeNumber, judgeShare, judgeSlices, judgeStatus, SAMPLE_STATUS } from '$lib/console/judge-observations';
	import type { PanelState } from '$lib/console/waiting';
	import type { Row } from '$lib/data/ledger';
	import { longDate } from '$lib/format';
	import { numberFormatter } from '$lib/number-format';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';

	let { selected, detail, detailState, dayNote, thin, knobs, chart }: {
		selected: string;
		detail: Row | null;
		detailState: PanelState;
		dayNote: string;
		thin: number;
		knobs: ConsoleConfig;
		chart: ChartConfig;
	} = $props();

	const name = 'judge-score-ranges';
	const label = 'Drawn score ranges and counts by answer';
	const rule = 'Drawn score ranges do not compare summary settings.';
	const order = ['YES', 'NO', 'Other returned', 'Did not return'] as const;
	const tokens = ['--chart-1', '--chart-2', '--chart-3', '--chart-8'] as const;
	const number = $derived(numberFormatter(chart.number_format));
	const exact = (value: number) => number(value, { exact: true });
	const decimal = (value: number) => judgeDecimal(value, chart.number_format);
	const score = (value: unknown) => {
		const n = judgeNumber(value);
		return n === null ? 'Not recorded' : decimal(n);
	};
	const slices = $derived(judgeSlices(detail?.slice_outcomes));
	const rows = $derived((slices ?? []).map((slice, index, drawn) => {
		const other = slice.unclear + slice.split + slice.refused;
		const sent = slice.yes + slice.no + other;
		const previous = drawn[index - 1];
		return {
			label: `${decimal(slice.low)} to ${decimal(slice.high)}`,
			wholeRangeLost: sent === 0,
			before: previous !== undefined && previous.high < slice.low ? `${decimal(previous.high)} to ${decimal(slice.low)}` : null,
			yes: slice.yes,
			no: slice.no,
			parts: [slice.yes, slice.no, other, slice.drawn - sent].map((value, i) => ({ label: order[i]!, value }))
		};
	}));
	const geometry = $derived(partsOfOne(rows, { order, tokens }));
	const readout = $derived(rows.map((row) => factsOf(row.label, row.parts.map((part, index) => ({
		...part, format: exact, swatch: `var(${tokens[index]})`
	})), 'Not measured.')));
	const cutoff = $derived(detail === null ? null : judgeCutoff(detail));
	const sampleNote = $derived(detail === null ? dayNote : slices?.length === 0
		? 'No pairs were drawn for this digest.' : judgeStatus(detail.sample_status, SAMPLE_STATUS));

	function rate(value: unknown, divisor: number | null, empty: string, population = ''): string {
		const n = judgeNumber(value);
		if (n === null || divisor === null || divisor === 0) return `Not measured: ${empty}`;
		return `${number(100 * n, { si: false })}% of ${exact(divisor)}${population ? ` ${population}` : ''}`;
	}

	function brier(value: unknown, divisor: number | null): string {
		const n = judgeNumber(value);
		return n === null || divisor === null || divisor === 0 ? 'Not measured: no agreed YES or NO answers'
			: `${number(n, { si: false })} across ${exact(divisor)} pairs`;
	}
</script>

<Panel id={name} title="Judge answers and cutoff agreement" heading="h3" wide>
	<div data-judge-digest={selected} data-panel-question="How did the judge answer within the ranges that were drawn?"
		data-model-rule="no" data-model-rule-name={name} data-model-rule-none={rule}>
		<p class="digest" data-lede><strong>{longDate(selected)}</strong> (UTC digest)</p>
		{#if detail && cutoff}
			<section class="cutoffs">
				<h4>Cutoff agreement with the judge</h4>
				<p>These compare score decisions with agreed YES or NO answers. Neither cutoff is the publication floor.
					Hard-decision Brier is the fraction of decisions that disagreed.</p>
				{#if cutoff.binary !== null}
					<p>{exact(cutoff.binary)} pairs with agreed YES or NO.
						{#if cutoff.binary < thin} Thin sample: fewer than {exact(thin)} such pairs.{/if}</p>
					<dl>
						<div>
							<dt>Reporting cutoff: {score(detail.evaluated_cutoff)}</dt>
							<dd>{exact(cutoff.tp!)} matched YES; {exact(cutoff.tn!)} matched NO.</dd>
							<dd>{exact(cutoff.fp!)} wrong matches (judge NO); {exact(cutoff.fn!)} missed matches (judge YES).</dd>
							<dd>Precision: {rate(detail.sample_precision, cutoff.predicted, 'no pairs at or above the cutoff', 'predicted YES')}.</dd>
							<dd>Recall: {rate(detail.sample_recall, cutoff.judgeYes, 'the judge agreed YES on no pairs', 'judge YES')}.</dd>
							<dd>Hard-decision Brier: {brier(detail.cutoff_brier_score, cutoff.binary)}.</dd>
						</div>
						<div>
							<dt>Upper bound used for the draw: {score(detail.upper_threshold_before)}</dt>
							<dd>Wrong-match share: {rate(detail.upper_cutoff_false_match_share, judgeNumber(detail.upper_cutoff_sample_size),
								'no agreed YES or NO pairs at or above this bound')}.</dd>
							<dd>Hard-decision Brier: {brier(detail.upper_cutoff_brier_score, cutoff.binary)}.</dd>
						</div>
					</dl>
				{:else}
					<p>{sampleNote} Upper bound used for the draw: {score(detail.upper_threshold_before)}.</p>
				{/if}
			</section>
		{/if}
		<p data-comparison="Agreed YES against agreed NO in each score range.">
			All bars use the same pair-count scale. Only drawn ranges are listed.
		</p>
		<Reserved record panelState={detailState} width={knobs.chart_width} height={knobs.chart_height} {name} {label}>
			<PartsOfOne {geometry} empty={emptyState('quiet', sampleNote)}
				{name} {label} width={knobs.chart_width} height={knobs.chart_height} {readout}
				readoutMaxShare={chart.readout_max_share} separateSegments>
				{#snippet rowNote(index)}
					{@const row = rows[index]!}
					<p>
						<strong>{exact(row.yes)} YES</strong> / <strong>{exact(row.no)} NO</strong>.
						{#if row.yes + row.no > 0}
							YES: {exact(row.yes)} of {exact(row.yes + row.no)} ({judgeShare(row.yes, row.yes + row.no, chart.number_format)}).
						{:else}
							No agreed YES or NO.
						{/if}
						{#if row.wholeRangeLost} None of the drawn pairs in this range returned.{/if}
						{#if row.before} Nothing was drawn in the gap from {row.before}.{/if}
					</p>
				{/snippet}
			</PartsOfOne>
		</Reserved>
	</div>
</Panel>

<style>
	p, h4, dl, dd { margin: 0; overflow-wrap: anywhere; }
	.digest { margin-block-end: var(--space-2); }
	[data-comparison] { margin-block-end: var(--space-3); }
	.cutoffs {
		display: grid;
		gap: var(--space-2);
		margin-block-end: var(--console-panel-gap);
		padding-block-end: var(--console-panel-gap);
		border-block-end: 1px solid var(--color-rule);
	}
	dl {
		display: grid;
		gap: var(--space-3) var(--space-6);
	}
	@media (min-width: 1024px) { dl { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
	dt { font-weight: var(--console-panel-title-weight); }
</style>
