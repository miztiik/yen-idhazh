<script lang="ts">
	import Panel from '$lib/components/Panel.svelte';
	import Reserved from '$lib/components/Reserved.svelte';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import { emptyState } from '$lib/charts/d3/empty';
	import type { ModelRule } from '$lib/charts/d3/model-rule';
	import { MARGIN, chartWidth, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import { readoutOf } from '$lib/charts/readout';
	import { drawCoverageByOutcome } from '$lib/console/judge-draw';
	import { judgeCoverage, judgeNumber, judgeShare, judgeSlices, judgeStatus, SAMPLE_STATUS, type JudgeReading } from '$lib/console/judge-observations';
	import type { PanelState } from '$lib/console/waiting';
	import type { Row } from '$lib/data/ledger';
	import { longDate } from '$lib/format';
	import { numberFormatter } from '$lib/number-format';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';
	import { OUTCOME_STYLE } from './judge-trial-style';

	let { calendar, windowDays, readings, selected, detail, trialDraws = null, historyState, rule, dayNote, noteFor, knobs, chart, onPick }: {
		calendar: readonly string[];
		windowDays: number;
		readings: ReadonlyMap<string, JudgeReading>;
		selected: string;
		detail: Row | null;
		trialDraws?: ReadonlyMap<string, Row> | null;
		historyState: PanelState;
		rule: ModelRule;
		dayNote: string;
		noteFor: (date: string) => string;
		knobs: ConsoleConfig;
		chart: ChartConfig;
		onPick: (date: string) => void;
	} = $props();

	const name = 'judge-coverage';
	const label = 'Daily counts of pairs drawn and returned';
	const legacyParts = [
		{ label: 'Agreed YES or NO', token: '--chart-4', part: 'binary' },
		{ label: 'Other returned', token: '--chart-3', part: 'other' },
		{ label: 'Did not return', token: '--chart-8', part: 'lost' }
	] as const;
	const outcomeParts = ['yes', 'no', 'maybe', 'refused', 'unclassified', 'missing'] as const;
	let measured = $state<number | null>(null);
	const frame = useChartFrame(() => chart);
	const width = $derived(chartWidth(measured, knobs.chart_width));
	const number = $derived(numberFormatter(chart.number_format));
	const exact = (value: number) => number(value, { exact: true });
	const countText = (value: number | null) => value === null ? 'Not recorded' : exact(value);
	const counts = $derived(calendar.map((date) => {
		const reading = readings.get(date);
		return reading === undefined ? null : judgeCoverage(reading.cells);
	}));
	const picked = $derived(calendar.indexOf(selected));
	const chosen = $derived(counts[picked] ?? null);
	const outcomes = $derived(trialDraws === null ? null : calendar.map((date) => {
		const reading = readings.get(date);
		return reading ? drawCoverageByOutcome(reading.cells, trialDraws?.get(date) ?? (date === selected ? detail : null)) : null;
	}));
	const series = $derived(outcomes === null ? legacyParts.map(({ label, token, part }, index) => ({
		label, token, values: counts.map((day) => day?.[part] ?? null), drawn: counts.map((day) => day?.stack?.[index] ?? null)
	})) : outcomeParts.map((part) => {
		const values = outcomes.map((day) => day?.[part] ?? null);
		return { ...OUTCOME_STYLE[part], values, drawn: values };
	}));
	const geometry = $derived(dateSeries(series.map(({ label, token, drawn }) => ({
		label, token, points: calendar.map((date, day) => ({ date, value: drawn[day] }))
	})), {
		frame: frame(width, knobs.chart_height, MARGIN),
		stacked: true, density: chart.tick_density, valueTicks: 4, padding: 0.25,
		number_format: chart.number_format, rule
	}));
	const readout = $derived(readoutOf({
		type: 'dateSeries', columns: calendar.map(longDate),
		series: [
			{
				label: 'Returned of drawn', swatch: null,
				values: counts.map((day) => {
					if (day?.returned != null && day.drawn != null) return `${exact(day.returned)} of ${exact(day.drawn)}`;
					return day?.drawn == null ? null : `Returns not measured; ${exact(day.drawn)} drawn`;
				}),
				format: exact
			},
			...series.map(({ label, token, values }) => ({
				label, swatch: `var(${token})`, values, format: exact
			}))
		],
		notMeasured: 'Not measured.',
		notMeasuredAt: calendar.map((date) => readings.has(date) ? 'Not recorded or not measured on this digest.' : noteFor(date)),
		resting: picked
	}));

	const slices = $derived(judgeSlices(detail?.slice_outcomes));
	const sample = $derived(slices?.reduce((sums, slice) => ({
		unclear: sums.unclear + slice.unclear, split: sums.split + slice.split, refused: sums.refused + slice.refused
	}), { unclear: 0, split: 0, refused: 0 }) ?? null);
	const reported = $derived(judgeNumber(detail?.runners_reported));
	const expected = $derived(judgeNumber(detail?.runners_expected));
	const valid = $derived(judgeNumber(detail?.pairs_valid));
	const agreed = $derived(judgeNumber(detail?.pairs_agreed));
	const dealt = $derived(judgeNumber(detail?.pairs_dealt));
	const returnShare = $derived(judgeShare(chosen?.returned ?? null, chosen?.drawn ?? null, chart.number_format));
	const share = (value: unknown) => {
		const fraction = judgeNumber(value);
		return fraction === null ? 'Not measured' : `${number(100 * fraction, { si: false })}%`;
	};
</script>

<Panel id={name} title="Pairs drawn and returned" heading="h3" wide>
	<div use:observeWidth={(next) => measured = next} data-windowed={name} data-window-days={windowDays}
		data-panel-question="How many drawn pairs did the judge return?"
		data-judge-digest={selected}>
		<div class="judge-summary">
			<p data-lede>
				{#if chosen?.returned != null && chosen.drawn !== null}
					<strong>{exact(chosen.returned)} of {exact(chosen.drawn)} returned</strong>{returnShare === null ? '' : ` (${returnShare})`}.
				{:else if chosen?.drawn != null}
					<strong>{exact(chosen.drawn)} drawn.</strong> {detail ? judgeStatus(detail.sample_status, SAMPLE_STATUS) : dayNote}
				{:else}
					<strong>{longDate(selected)}:</strong> {detail ? judgeStatus(detail.sample_status, SAMPLE_STATUS) : dayNote}
				{/if}
				{#if chosen?.binary != null} {exact(chosen.binary)} agreed YES or NO.{/if}
				{#if reported !== null && expected !== null} {exact(reported)} of {exact(expected)} runners reported.{/if}
			</p>
			<p data-comparison="Pairs returned against pairs drawn.">
				Each column shows the draw split by what came back.
				{#if trialDraws !== null}MAYBE includes split and agreed UNCLEAR, not refusals.{/if}
			</p>
		</div>
		<Reserved record panelState={historyState} {width} height={knobs.chart_height} {name} {label}>
			<DateSeries {geometry} empty={emptyState('quiet', 'No complete draw and return stacks were measured in this window.')}
				{name} {label} {width} height={knobs.chart_height} {readout} readoutMaxShare={chart.readout_max_share}
				picked={picked} onPick={(index) => onPick(calendar[index]!)} restingNote=" (selected digest)"
				hint="Left and Right inspect dates. Click, tap or press Enter to select a digest for the judge group."
				hintOne="Click, tap or press Enter to select this digest." />
		</Reserved>
		{#if detail}
			<div class="judge-reading">
				{#if sample && chosen?.binary != null && chosen.returned !== null}
					{@const usable = chosen.binary + sample.unclear}
					<p>Sample usability: {exact(usable)} of {exact(chosen.returned)} returned pairs agreed YES, NO or UNCLEAR.
						{exact(sample.unclear)} UNCLEAR, {exact(sample.split)} split across orders and {exact(sample.refused)} refused.
						{#if chosen.lost !== null} {exact(chosen.lost)} drawn pairs did not return.{/if}</p>
				{/if}
				<p>
					Reporting runners: {countText(dealt)} dealt; {countText(agreed)} of {countText(valid)} pairs with two valid answers
					agreed in both orders. Disagreement: {share(detail.disagreement_rate)} of valid pairs. UNCLEAR:
					{share(detail.unclear_rate)} of agreed pairs. {countText(judgeNumber(detail.pairs_refused))} refused,
					{countText(judgeNumber(detail.pairs_unreadable))} unreadable and
					{countText(judgeNumber(detail.pairs_abandoned))} lost to the deadline.
				</p>
			</div>
		{:else if chosen?.returned != null}
			<p class="judge-reading">{dayNote}</p>
		{/if}
	</div>
</Panel>

<style>
	.judge-summary {
		display: grid;
		gap: var(--space-2);
		margin-block-end: var(--space-3);
	}
	.judge-reading { display: grid; gap: var(--space-2); margin-block-start: var(--space-3); }
	p { margin: 0; overflow-wrap: anywhere; }
</style>
