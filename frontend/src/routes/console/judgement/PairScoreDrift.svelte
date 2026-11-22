<script lang="ts">
	import Panel from '$lib/components/Panel.svelte';
	import Reserved from '$lib/components/Reserved.svelte';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import { emptyState } from '$lib/charts/d3/empty';
	import { MARGIN, chartWidth, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import { readoutOf } from '$lib/charts/readout';
	import {
		DRIFT_STATUS, judgeDecimal, judgeDriftBaseline, judgeNumber, judgeStatus, psiInterpretation,
		psiNumber, type JudgeReading
	} from '$lib/console/judge-observations';
	import type { PanelState } from '$lib/console/waiting';
	import type { Row } from '$lib/data/ledger';
	import { longDate } from '$lib/format';
	import { numberFormatter } from '$lib/number-format';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';

	let { calendar, windowDays, readings, selected, detail, historyState, dayNote, noteFor, low, high, knobs, chart, onPick }: {
		calendar: readonly string[];
		windowDays: number;
		readings: ReadonlyMap<string, JudgeReading>;
		selected: string;
		detail: Row | null;
		historyState: PanelState;
		dayNote: string;
		noteFor: (date: string) => string;
		low: number;
		high: number;
		knobs: ConsoleConfig;
		chart: ChartConfig;
		onPick: (date: string) => void;
	} = $props();

	const name = 'pair-score-drift';
	const label = 'Population Stability Index by UTC digest date';
	const rule = { declined: 'Incoming scores do not compare summary settings.' };
	let measured = $state<number | null>(null);
	const frame = useChartFrame(() => chart);
	const width = $derived(chartWidth(measured, knobs.chart_width));
	const number = $derived(numberFormatter(chart.number_format));
	const exact = (value: number) => number(value, { exact: true });
	const psi = (value: number) => psiNumber(value, low, high, chart.number_format);
	const interpretation = (value: number) => psiInterpretation(value, low, high);
	const measuredText = (value: unknown) => {
		const n = judgeNumber(value);
		return n === null ? 'Not recorded' : number(n, { si: false });
	};
	const lowGuide = $derived(judgeDecimal(low, chart.number_format));
	const highGuide = $derived(judgeDecimal(high, chart.number_format));
	const points = $derived(calendar.map((date) => ({ date, value: judgeNumber(readings.get(date)?.cells.score_psi) })));
	const picked = $derived(calendar.indexOf(selected));
	const selectedPsi = $derived(points[picked]?.value ?? null);
	const baseline = $derived(judgeDriftBaseline(detail?.score_drift_baseline));
	const geometry = $derived(dateSeries([{ label: 'PSI', token: '--chart-measure', points }], {
		frame: frame(width, knobs.chart_height, MARGIN),
		density: chart.tick_density, valueTicks: 4, padding: 0.25,
		number_format: chart.number_format, rule,
		rules: [{ at: low, label: `${lowGuide} moderate starts` }, { at: high, label: `${highGuide} moderate ends` }]
	}));
	const readout = $derived(readoutOf({
		type: 'dateSeries', columns: calendar.map(longDate),
		series: [
			{ label: 'PSI', swatch: 'var(--chart-measure)', values: points.map((point) => point.value), format: psi },
			{ label: 'Interpretation', swatch: null, values: points.map((point) => point.value === null ? null : interpretation(point.value)), format: psi }
		],
		notMeasured: 'Not recorded.',
		notMeasuredAt: calendar.map((date) => date === selected && detail !== null
			? judgeStatus(detail.score_drift_status, DRIFT_STATUS) : readings.has(date) ? 'No PSI saved for this digest.' : noteFor(date)),
		resting: picked
	}));
</script>

<Panel id={name} title="Pair-score drift over time" heading="h3" wide>
	<div use:observeWidth={(next) => measured = next} data-windowed={name} data-window-days={windowDays}
		data-panel-question="How much did the mix of incoming pair scores change?"
		data-model-rule="no" data-model-rule-name={name} data-model-rule-none={rule.declined}>
		<div class="drift-reading" data-judge-digest={selected}>
			<p data-comparison="The full incoming score pool against its saved baseline.">
				Population Stability Index (PSI) compares the full pool of eligible pair scores, not just the judged sample.
			</p>
			<p data-lede><strong>{longDate(selected)}</strong> (UTC digest).
				{#if selectedPsi !== null}
					<strong>PSI {psi(selectedPsi)}</strong> &mdash; {interpretation(selectedPsi)}.
				{:else}
					{detail === null ? dayNote : judgeStatus(detail.score_drift_status, DRIFT_STATUS)}
				{/if}
			</p>
			{#if baseline}
				<p>Baseline: {exact(baseline.days)} of {exact(baseline.required)} source days{#if baseline.first && baseline.last}
					{baseline.first === baseline.last ? ` on ${longDate(baseline.first)}` :
						` from ${longDate(baseline.first)} through ${longDate(baseline.last)}`}{/if}.</p>
			{/if}
		</div>
		<Reserved record panelState={historyState} {width} height={knobs.chart_height} {name} {label}>
			<DateSeries {geometry} empty={emptyState('quiet', 'No PSI reading is available in this window.')}
				{name} {label} {width} height={knobs.chart_height} {readout} readoutMaxShare={chart.readout_max_share}
				picked={picked} onPick={(index) => onPick(calendar[index]!)} restingNote=" (selected digest)"
				hint="Left and Right inspect dates. Click, tap or press Enter to select a digest for the judge group."
				hintOne="Click, tap or press Enter to select this digest." />
		</Reserved>
		<div class="drift-notes">
			{#if selectedPsi !== null}
				{#if detail}
					<p>Binned Wasserstein: {measuredText(detail.score_wasserstein_distance)} score units.
						Binned KS: {measuredText(detail.score_ks_distance)} cumulative-share gap.</p>
				{:else}
					<p>{dayNote}</p>
				{/if}
			{/if}
			<p>
				<strong>Rule of thumb.</strong> PSI below {lowGuide}: No significant drift.
				PSI from {lowGuide} through {highGuide}: Moderate drift (investigation needed).
				PSI above {highGuide}: Significant drift (retrain or re-calibrate).
				These are rules of thumb for changes in the incoming score mix. Verify quality before retraining or recalibrating.
				No alert is sent and nothing changes automatically.
			</p>
		</div>
	</div>
</Panel>

<style>
	p { margin: 0; overflow-wrap: anywhere; }
	.drift-reading, .drift-notes { display: grid; gap: var(--space-2); }
	.drift-reading { margin-block-end: var(--space-3); }
	.drift-notes { margin-block-start: var(--space-3); }
</style>
