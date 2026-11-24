<script lang="ts">
	import Panel from '$lib/components/Panel.svelte';
	import DiagnosticGrid from '$lib/charts/d3/DiagnosticGrid.svelte';
	import { diagnosticGrid } from '$lib/charts/d3/diagnosticGrid';
	import PrecisionRecall from '$lib/charts/d3/PrecisionRecall.svelte';
	import { precisionRecall, type CutoffShape } from '$lib/charts/d3/precisionRecall';
	import { chartWidth, labelWidth, MARGIN, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import { factsOf } from '$lib/charts/readout';
	import { judgeCutoffSweep, judgeZoneMatrix, SCORE_ZONES, type CutoffReading } from '$lib/console/judge-cutoff-evidence';
	import { judgeScore } from '$lib/console/judge-draw';
	import { judgeDecimal, judgeNumber, judgeShare } from '$lib/console/judge-observations';
	import type { PairDay } from '$lib/console/judge-pair-evidence';
	import type { Row } from '$lib/data/ledger';
	import { longDate } from '$lib/format';
	import { numberFormatter } from '$lib/number-format';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';
	import { OUTCOME_STYLE } from './judge-trial-style';

	let { selected, day, status, detail, ranking, chart, knobs }: {
		selected: string; day: PairDay | undefined; status: string; detail: Row | null;
		ranking: Row | null; chart: ChartConfig; knobs: ConsoleConfig;
	} = $props();
	let measured = $state<number | null>(null);
	const frame = useChartFrame(() => chart);
	const box = $derived.by(() => {
		const width = chartWidth(measured, knobs.chart_width);
		const probe = frame(width, knobs.chart_height);
		return frame(width, knobs.chart_height, { ...MARGIN, left: labelWidth('100%', probe.labels) + probe.labels.fontSize });
	});

	const number = $derived(numberFormatter(chart.number_format));
	const exact = (n: number) => number(n, { exact: true });
	const score = (n: number) => judgeDecimal(n, chart.number_format);
	const percent = (n: number) => `${number(100 * n, { si: false })}%`;
	const reading = $derived(day?.state === 'ready' ? day : null);
	const sweep = $derived(reading === null ? null : judgeCutoffSweep(reading.pairs));
	const matrix = $derived(reading?.bounds ? judgeZoneMatrix(reading.pairs, reading.bounds) : null);
	const headings = SCORE_ZONES.map((key) => ({ label: key.toUpperCase(), tone: `var(${OUTCOME_STYLE[key].token})` }));
	const grid = $derived(matrix === null ? null : diagnosticGrid(headings, headings, SCORE_ZONES.map((judge) => {
		const n = SCORE_ZONES.reduce((sum, zone) => sum + matrix.matrix[judge][zone], 0);
		return SCORE_ZONES.map((zone) => {
			const count = matrix.matrix[judge][zone];
			const share = judgeShare(count, n, chart.number_format);
			return {
				text: exact(count), diagonal: judge === zone,
				paint: n > 0 ? `color-mix(in oklab, var(${OUTCOME_STYLE[judge].token}) calc(${100 * count / n}% * var(--chart-spread-mix)), var(--color-surface))` : null,
				facts: factsOf(`Judge ${judge.toUpperCase()} / score ${zone.toUpperCase()}`, [
					{ label: 'Count', value: exact(count) }, { label: 'Share of this judge outcome', value: share },
					{ label: 'Row support', value: exact(n) }
				], 'No pairs with this judge outcome.')
			};
		});
	})));
	const cutoffs = $derived(([
		{ shape: 'lower', label: 'Lower draw bound', glyph: '\u25bc', value: reading?.bounds?.lower ?? null },
		{ shape: 'upper', label: 'Upper draw bound', glyph: '\u25b2', value: reading?.bounds?.upper ?? null },
		{ shape: 'reporting', label: 'Reporting cutoff', glyph: '\u25a0', value: judgeScore(detail?.evaluated_cutoff) },
		{ shape: 'target', label: 'First cutoff reaching 90% recall', glyph: '\u25c6', value: judgeScore(ranking?.sample_recall_90_cutoff) }
	] as const).map(({ value, ...key }) => ({ ...key, value, reading: value !== null ? sweep?.atCutoff(value) ?? null : null })) satisfies
		{ shape: CutoffShape; label: string; glyph: string; value: number | null; reading: CutoffReading | null }[]);
	const available = $derived(cutoffs.flatMap(({ shape, label, reading }) => reading === null ? [] : [{ ...reading, shape, label }]));
	const graph = $derived(sweep === null ? null : precisionRecall(sweep.points, available, box, chart.tick_density));
	const cutoffFacts = (label: string, r: CutoffReading) => factsOf(label, [
		{ label: 'Precision', value: judgeShare(r.tp, r.tp + r.fp, chart.number_format) },
		{ label: 'Recall', value: judgeShare(r.tp, r.tp + r.fn, chart.number_format) },
		{ label: 'Matched YES', value: exact(r.tp) }, { label: 'Wrong matches', value: exact(r.fp) },
		{ label: 'Missed matches', value: exact(r.fn) }, { label: 'Matched NO', value: exact(r.tn) }
	], 'Not measurable at this cutoff.');
	const observations = $derived(sweep?.points.map((r) => cutoffFacts(`Cutoff ${score(r.cutoff)}`, r)) ?? []);
	const markers = $derived(available.map((r) => cutoffFacts(`${r.label}: ${score(r.cutoff)}`, r)));
	const metric = (cell: Row[string] | undefined, asPercent = false) => {
		const n = judgeNumber(cell);
		return n === null ? 'Not recorded' : asPercent ? percent(n) : number(n, { si: false });
	};
</script>

<Panel title="Judge and pipeline score decisions" heading="h3" wide>
	<div class="cutoff-layout" data-panel-question="Where do the score choices differ from the judge?"
		data-model-rule="no" data-model-rule-name="judge-cutoff-trial" data-model-rule-none="The cutoffs follow the saved scorer and judge."
		data-judge-digest={selected}>
		<p class="intro" data-lede>{longDate(selected)} UTC. These readings compare the recorded sample with judge answers, not human labels or published merges.</p>
		<section>
			<h4>Judge outcome vs pipeline score zone</h4>
			<p data-comparison="Two-order judge outcome against pipeline score zone.">Rows are judge outcomes. Columns are pipeline score zones.</p>
			{#if grid !== null && matrix !== null && reading?.bounds}
				<p>NO below {score(reading.bounds.lower)}; YES at or above {score(reading.bounds.upper)}; MAYBE between. Judge MAYBE includes
					{exact(matrix.unclear)} agreed UNCLEAR and {exact(matrix.split)} split. {exact(matrix.refused)} refused excluded.</p>
				<DiagnosticGrid drawing={grid} name="judge-score-matrix" label="Judge outcomes by pipeline score zone"
					corner="Judge / score" labels maxShare={chart.readout_max_share} />
			{:else}
				<p>{reading === null ? status : 'Not measured: the saved pair rows do not agree on the draw bounds.'}</p>
			{/if}
		</section>
		<section use:observeWidth={(width) => measured = width}>
			<h4>Precision vs recall</h4>
			<p>One digest, one dot per observed score cutoff. Recall runs across; precision runs up.</p>
			{#if sweep}
				<p>{exact(sweep.binary)} agreed YES or NO pairs; {exact(sweep.excluded)} others excluded.</p>
			{/if}
			{#if graph !== null}
				<PrecisionRecall drawing={graph} {observations} cutoffs={markers} {percent} maxShare={chart.readout_max_share} />
			{:else}
				<p>{sweep === null ? status : 'Not measured: no agreed YES answers for a recall comparison.'}</p>
			{/if}
			{#if sweep}
				<ul class="cutoff-key" aria-label="Named cutoff readings">
					{#each cutoffs as cutoff (cutoff.shape)}
						<li><span class="glyph" aria-hidden="true">{cutoff.glyph}</span> <strong>{cutoff.label}:</strong>
							{#if cutoff.value !== null}
								{score(cutoff.value)}.
								{#if cutoff.reading}
									Precision {judgeShare(cutoff.reading.tp, cutoff.reading.tp + cutoff.reading.fp, chart.number_format) ?? 'not measured'};
									recall {judgeShare(cutoff.reading.tp, cutoff.reading.tp + cutoff.reading.fn, chart.number_format) ?? 'not measured'}.
								{/if}
							{:else}Not recorded.{/if}</li>
					{/each}
				</ul>
				{#if ranking}
					<p>Average precision: {metric(ranking.sample_average_precision, true)}. F0.5: {metric(ranking.sample_f0_5)}.
						At the saved 90% recall cutoff: {metric(ranking.sample_precision_at_recall_90, true)} precision,
						{metric(ranking.sample_recall_at_recall_90_cutoff, true)} recall.</p>
				{/if}
			{/if}
		</section>
	</div>
</Panel>

<style>
	.cutoff-layout { display: grid; gap: var(--console-panel-gap); }
	.cutoff-layout section { min-inline-size: 0; }
	@media (min-width: 1024px) {
		.cutoff-layout { grid-template-columns: repeat(2, minmax(0, 1fr)); }
		.intro { grid-column: 1 / -1; }
	}
	p, h4 { margin: 0 0 var(--space-2); }
	.cutoff-key { padding-inline-start: 0; list-style: none; }
	.cutoff-key li { margin-block: var(--space-1); }
	.glyph { color: var(--chart-2); }
</style>
