<script lang="ts">
	import Panel from '$lib/components/Panel.svelte';
	import DiagnosticGrid from '$lib/charts/d3/DiagnosticGrid.svelte';
	import { diagnosticGrid, type GridDiagnostic } from '$lib/charts/d3/diagnosticGrid';
	import { factsOf } from '$lib/charts/readout';
	import { countBandOutcomes, judgeEntropy, MAX_ENTROPY_BITS, outcomeTotal, PAIR_OUTCOMES,
		type PairDay, type ScoreBand } from '$lib/console/judge-pair-evidence';
	import { judgeDecimal, judgeShare } from '$lib/console/judge-observations';
	import { dayMonth, longDate } from '$lib/format';
	import { numberFormatter } from '$lib/number-format';
	import type { ChartConfig } from '$lib/server/config';
	import { OUTCOME_STYLE } from './judge-trial-style';

	let { dates, bands, days, selected, status, thin, chart, noteFor, onPick }: {
		dates: readonly string[]; bands: readonly ScoreBand[]; days: ReadonlyMap<string, PairDay>; selected: string;
		status: string | null; thin: number; chart: ChartConfig;
		noteFor: (date: string) => string; onPick: (date: string) => void;
	} = $props();

	const views = [
		{ key: 'yes', title: 'Agreed YES by date and score', note: 'Share of recorded pairs that both orders called the same story.' },
		{ key: 'no', title: 'Agreed NO by date and score', note: 'Share of recorded pairs that both orders called different stories.' },
		{ key: 'split', title: 'Split answers by date and score', note: 'Share of recorded pairs whose two valid answers differed.' },
		{ key: 'entropy', title: 'Answer entropy by date and score', note: 'Spread across YES, MAYBE and NO among pairs with two valid answers. MAYBE includes split and agreed UNCLEAR.' }
	] as const;
	const number = $derived(numberFormatter(chart.number_format));
	const exact = (n: number) => number(n, { exact: true });
	const bandText = (band: ScoreBand) =>
		`${judgeDecimal(band.low, chart.number_format)} to ${judgeDecimal(band.high, chart.number_format)}`;
	const rows = $derived(bands.map((band) => ({ label: bandText(band) })).reverse());
	const columns = $derived(dates.map((date, index) => {
		const day = days.get(date);
		const previous = days.get(dates[index - 1]);
		const stamp = day?.state === 'ready' ? day.settings : null;
		const priorStamp = previous?.state === 'ready' ? previous.settings : null;
		const change = stamp !== null && priorStamp !== null && stamp !== priorStamp;
		return { label: dayMonth(date), title: `${longDate(date)}${change ? ' (settings changed)' : ''}`,
			change, chosen: date === selected };
	}));
	const counts = $derived(dates.map((date) => {
		const day = days.get(date);
		return day?.state === 'ready' ? countBandOutcomes(day.pairs, bands) : null;
	}));
	const heatmaps = $derived(views.map((view) => {
		const cells = bands.map((band, bin) => dates.map((date, at): GridDiagnostic => {
			const countsAt = counts[at]?.[bin];
			const n = countsAt ? outcomeTotal(countsAt) : 0;
			const heading = `${longDate(date)} (UTC), scores ${bandText(band)}`;
			if (!countsAt || n === 0) return { paint: null, facts: factsOf(heading, [],
				countsAt ? 'No recorded pairs in this band.' : noteFor(date)) };
			const valid = n - countsAt.refused;
			const entropy = judgeEntropy(countsAt);
			const fraction = view.key === 'entropy' ? null : countsAt[view.key] / n;
			const paint = view.key === 'entropy'
				? entropy === null ? null : `color-mix(in oklab, var(--chart-change) ${100 * entropy / MAX_ENTROPY_BITS}%, var(--chart-measure))`
				: `color-mix(in oklab, var(${OUTCOME_STYLE[view.key].token}) ${100 * (fraction ?? 0)}%, var(--chart-grid))`;
			const day = days.get(date);
			return { paint, facts: factsOf(heading, [
				{ label: 'Recorded pairs', value: `${exact(n)}${n < thin ? ' (thin sample)' : ''}` },
				...PAIR_OUTCOMES.map((key) => ({ label: OUTCOME_STYLE[key].label,
					value: `${exact(countsAt[key])} (${judgeShare(countsAt[key], n, chart.number_format)})` })),
				...(view.key !== 'entropy' ? [] : [
					{ label: 'MAYBE', value: valid === 0 ? null : `${judgeShare(countsAt.unclear + countsAt.split, valid, chart.number_format)} of ${exact(valid)} pairs with two valid answers` },
					{ label: 'Entropy', value: entropy === null ? null : `${number(entropy, { si: false })} bits` }
				]),
				...(day?.state === 'ready' && day.settings === null ? [{ label: 'Settings', value: 'Mixed or not recorded' }] : [])
			], 'No classified evidence.') };
		})).reverse();
		return { ...view, drawing: diagnosticGrid(rows, columns, cells, Math.max(0, dates.indexOf(selected))) };
	}));
</script>

<Panel title="Judge outcomes over time" heading="h3" wide>
	<div data-panel-question="Which scores and dates had repeatable verdicts?" data-model-rule="no"
		data-model-rule-name="judge-verdict-heatmaps" data-model-rule-none="The annotations describe recorded judge and scorer settings.">
		<p data-lede>These heatmaps count recorded verdicts, not every pair drawn or the full score pool. Hatched cells have no evidence for the plotted measure.</p>
		{#if status}
			<p>{status}</p>
		{:else if dates.length}
			<p data-comparison="Recorded scores and outcomes compared on fixed bands over UTC dates.">
				{longDate(dates[0])} to {longDate(dates[dates.length - 1])} UTC. * marks a recorded settings change from the previous day.
			</p>
			{#each heatmaps as view (view.key)}
				{#if view.drawing !== null}
					<section>
						<h4>{view.title}</h4>
						<p>{view.note}</p>
						{#if view.key === 'entropy'}
							<div class="key"><span>0 bits</span><span class="ramp" style:--from="var(--chart-measure)" style:--to="var(--chart-change)" aria-hidden="true"></span><span>{number(MAX_ENTROPY_BITS, { si: false })} bits at an even three-way mix</span></div>
							<p>A band of only MAYBE also has zero entropy. Changes in this chart are not proof of judge drift.</p>
						{:else}
							<div class="key"><span>0%</span><span class="ramp" style:--from="var(--chart-grid)" style:--to="var({OUTCOME_STYLE[view.key].token})" aria-hidden="true"></span><span>100%</span></div>
						{/if}
						<DiagnosticGrid drawing={view.drawing} name={`judge-${view.key}-heatmap`} label={view.title}
							corner="Score band" maxShare={chart.readout_max_share} onPick={(index) => onPick(dates[index])} />
					</section>
				{/if}
			{/each}
		{/if}
	</div>
</Panel>

<style>
	p, h4 { margin: 0 0 var(--space-2); }
	section { margin-block-start: var(--console-panel-gap); }
	.key { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); color: var(--color-text-secondary); font-size: var(--console-small-size); }
	.ramp { inline-size: var(--space-8); block-size: var(--space-2); background: linear-gradient(90deg, var(--from), var(--to)); }
</style>
