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
		DRIFT_STATUS, PROBABILITY_STATUS, judgeCanaries, judgeDecimal, judgeDriftBaseline, judgeNumber,
		judgeProbabilityEvidence, judgeStatus, psiInterpretation, psiNumber, type JudgeReading
	} from '$lib/console/judge-observations';
	import type { PanelState } from '$lib/console/waiting';
	import type { Row } from '$lib/data/ledger';
	import { longDate, plural } from '$lib/format';
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
	const probability = $derived(judgeProbabilityEvidence(detail?.judge_probability_evidence));
	const canaries = $derived(detail === null ? null : judgeCanaries(detail));
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
		<p class="intro" data-comparison="The full incoming score pool against its saved baseline.">
			Population Stability Index (PSI) compares the full pool of eligible pair scores, not just the judged sample.
		</p>
		<Reserved record panelState={historyState} {width} height={knobs.chart_height} {name} {label}>
			<DateSeries {geometry} empty={emptyState('quiet', 'No PSI reading is available in this window.')}
				{name} {label} {width} height={knobs.chart_height} {readout} readoutMaxShare={chart.readout_max_share}
				picked={picked} onPick={(index) => onPick(calendar[index]!)} restingNote=" (selected digest)"
				hint="Left and Right inspect dates. Click, tap or press Enter to select a digest for all three panels."
				hintOne="Click, tap or press Enter to select this digest." />
		</Reserved>
		<div class="drift-reading" data-judge-digest={selected}>
			<p data-lede><strong>{longDate(selected)}</strong> (UTC digest).
				{#if selectedPsi !== null}
					<strong>PSI {psi(selectedPsi)}</strong> &mdash; {interpretation(selectedPsi)}.
				{:else}
					{detail === null ? dayNote : judgeStatus(detail.score_drift_status, DRIFT_STATUS)}
				{/if}
			</p>
			<p>
				<strong>Rule of thumb.</strong> PSI below {lowGuide}: No significant drift.
				PSI from {lowGuide} through {highGuide}: Moderate drift (investigation needed).
				PSI above {highGuide}: Significant drift (retrain or re-calibrate).
				These are rules of thumb for changes in the incoming score mix. Verify quality before retraining or recalibrating.
				No alert is sent and nothing changes automatically.
			</p>
			{#if detail}
				{#if baseline}
					<p>Baseline: {exact(baseline.days)} of {exact(baseline.required)} source days
						{#if baseline.first && baseline.last}
							{baseline.first === baseline.last ? `on ${longDate(baseline.first)}` :
								`from ${longDate(baseline.first)} through ${longDate(baseline.last)}`}
						{/if}.
					</p>
				{/if}
				{#if selectedPsi !== null}
					<p>Binned Wasserstein: {measuredText(detail.score_wasserstein_distance)} score units.
						Binned KS: {measuredText(detail.score_ks_distance)} cumulative-share gap.</p>
				{/if}
			{:else if selectedPsi !== null}
				<p>{dayNote}</p>
			{/if}
		</div>
		{#if detail && canaries}
			<div class="selected-notes">
				<section aria-labelledby="judge-prior-fit">
					<h4 id="judge-prior-fit">How close were the prior probabilities to this judge?</h4>
					{#if detail.judge_probability_status === 'measured' && probability}
						<p>Probability Brier: <strong>{measuredText(detail.judge_probability_brier_score)}</strong>.
							Same-sample baseline Brier: {measuredText(detail.judge_probability_baseline_brier_score)}.
							Expected calibration error (ECE): {measuredText(detail.judge_probability_ece)} across {exact(probability.bins)} bins.</p>
						<p>{exact(probability.yes)} YES out of {exact(probability.pairs)} new agreed pairs in the fit's score range.
							The reference fit did not use these exact pairs.</p>
					{:else}
						<p>{judgeStatus(detail.judge_probability_status, PROBABILITY_STATUS)}</p>
					{/if}
					{#if probability}
						<p>Reference: {longDate(probability.date)} (digest), Council run <span class="run">{probability.run}</span>.</p>
					{/if}
				</section>
				<section aria-labelledby="judge-known-answers">
					<h4 id="judge-known-answers">What did the judge say on the known-answer pairs?</h4>
					{#if canaries.graded}
						<p><strong>{exact(canaries.matches)} of {exact(canaries.items.length)} expected pairs matched</strong> the saved agent-labelled key.</p>
						<p>Cohen's kappa:
							{#if canaries.kappa !== null && canaries.eligible !== null}
								{measuredText(canaries.kappa)} across {exact(canaries.eligible)} {plural(canaries.eligible, 'pair', 'pairs')}.
							{:else if canaries.eligible !== null && canaries.eligible < canaries.items.length}
								Not measured: only {exact(canaries.eligible)} of {exact(canaries.items.length)} pairs agreed in both orders.
							{:else if canaries.eligible === canaries.items.length}
								Not measured: the chance-adjusted denominator was zero.
							{:else}
								Not recorded.
							{/if}
						</p>
					{:else}
						<p>Not recorded: this digest has no saved expected key. Observed answers are not graded.</p>
					{/if}
					{#if canaries.items.length > 0}
						<ul class="known-answers">
							{#each canaries.items as item (item.id)}
								<li>
									<strong class="pair-id">{item.id}</strong>
									<span>{#if item.expected}Expected {item.expected} &middot; {/if}
										File order: {item.forward ?? 'no answer'} &middot; Swapped: {item.swapped ?? 'no answer'}</span>
									<span class="outcome">{item.outcome}</span>
								</li>
							{/each}
						</ul>
					{/if}
				</section>
			</div>
		{/if}
	</div>
</Panel>

<style>
	p, h4 { margin: 0; overflow-wrap: anywhere; }
	.intro { margin-block-end: var(--space-3); }
	.drift-reading { display: grid; gap: var(--space-2); margin-block-start: var(--space-3); }
	.selected-notes {
		display: grid;
		align-items: start;
		gap: var(--console-panel-gap) var(--space-6);
		margin-block-start: var(--console-panel-gap);
		padding-block-start: var(--console-panel-gap);
		border-block-start: 1px solid var(--color-rule);
	}
	.selected-notes section { display: grid; gap: var(--space-2); }
	@media (min-width: 1024px) { .selected-notes { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
	.known-answers { list-style: none; margin: 0; padding: 0; }
	.known-answers li {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-1) var(--space-3);
		padding-block: var(--space-2);
		border-block-start: 1px solid var(--color-rule);
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
		overflow-wrap: anywhere;
	}
	.outcome { margin-inline-start: auto; color: var(--color-text-secondary); }
</style>
