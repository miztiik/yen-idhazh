<script lang="ts">
	import Panel from '$lib/components/Panel.svelte';
	import ScoreIntervals from '$lib/charts/d3/ScoreIntervals.svelte';
	import { scoreIntervals } from '$lib/charts/d3/scoreIntervals';
	import { chartWidth, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import { factsOf } from '$lib/charts/readout';
	import { drawOf, SCORE_MAX, SCORE_MIN, sliceParts } from '$lib/console/judge-draw';
	import { judgeCount, judgeDecimal, judgeDayAbsence, judgeNumber, judgeStatus, SAMPLE_STATUS } from '$lib/console/judge-observations';
	import type { Answer } from '$lib/console/voices/record';
	import type { LedgerReach, Row } from '$lib/data/ledger';
	import { longDate } from '$lib/format';
	import { numberFormatter } from '$lib/number-format';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';
	import { OUTCOME_STYLE } from './judge-trial-style';

	let { calendar, selected, rows, fit, answer, reach, knobs, chart, onPick, onRetry }: {
		calendar: readonly string[]; selected: string; rows: ReadonlyMap<string, Row>;
		fit: Row | null; answer: Answer; reach: LedgerReach; knobs: ConsoleConfig; chart: ChartConfig;
		onPick: (date: string) => void; onRetry: () => void;
	} = $props();

	let measured = $state<number | null>(null);
	let full = $state(false);
	const name = 'judge-draw-intervals';
	const frame = useChartFrame(() => chart);
	const value = (n: number) => judgeDecimal(n, chart.number_format);
	const number = $derived(numberFormatter(chart.number_format));
	const count = (n: number | null) => n === null ? 'Not recorded' : number(n, { exact: true });
	const score = (n: unknown) => {
		const reading = judgeNumber(n);
		return reading === null ? 'Not recorded' : value(reading);
	};
	const tokens = [OUTCOME_STYLE.yes.token, OUTCOME_STYLE.no.token, OUTCOME_STYLE.maybe.token, OUTCOME_STYLE.missing.token];
	const dates = $derived(calendar.map((date) => ({ date, ...drawOf(rows.get(date) ?? null) })));
	const chosen = $derived(dates.find(({ date }) => date === selected));
	const min = $derived(Math.min(...dates.flatMap(({ bounds, decided }) => [bounds?.lower, decided?.lower])
		.filter((n): n is number => n !== undefined)));
	const floor = $derived(full || !Number.isFinite(min) ? SCORE_MIN : min);
	const drawing = $derived(scoreIntervals(dates.map((day) => ({
		date: day.date, used: [day.bounds?.lower ?? null, day.bounds?.upper ?? null],
		decided: [day.decided?.lower ?? null, day.decided?.upper ?? null],
		slices: (day.slices ?? []).map((slice) => {
			const { yes, no, unclear, split, refused, missing } = sliceParts(slice);
			return { low: slice.low, high: slice.high, parts: [yes, no, unclear + split, refused + missing] };
		})
	})), frame(chartWidth(measured, knobs.chart_width), knobs.chart_height), floor, SCORE_MAX, chart.tick_density));
	const note = (date: string) => {
		const row = rows.get(date);
		return row ? judgeStatus(row.sample_status, SAMPLE_STATUS) : judgeDayAbsence(date, answer, reach);
	};
	const facts = $derived(dates.map((day) => factsOf(longDate(day.date), [
		{ label: 'Returned / drawn', value: `${count(day.returned)} / ${count(day.drawn)}` },
		{ label: 'Bounds used', value: day.bounds && `${value(day.bounds.lower)} to ${value(day.bounds.upper)}` },
		{ label: 'Bounds decided after the draw', value: day.decided && `${value(day.decided.lower)} to ${value(day.decided.upper)}` },
		{ label: 'Draw intervals', value: day.slices === null ? note(day.date) : count(day.slices.length) }
	], note(day.date))));
	const fitNotes = { not_enough_evidence: 'not enough evidence', fit_failed: 'fit failed',
		within_ignore_range: 'inside the hold range', waiting_for_second_night: 'waiting for a second night',
		widening_step: 'widening step', narrowing_step: 'narrowing step', far_gap_step: 'large-gap step',
		lowest_allowed: 'lowest allowed', highest_allowed: 'highest allowed', smallest_gap: 'smallest gap', none: 'none' } as const;
	const fitNote = (cell: Row[string] | undefined) => typeof cell === 'string' && Object.hasOwn(fitNotes, cell)
		? fitNotes[cell as keyof typeof fitNotes] : 'not recorded';
</script>

<Panel title="Draw ranges and bounds by date" heading="h3" wide>
	<div use:observeWidth={(width) => measured = width} data-panel-question="Where was the nightly draw and what came back?"
		data-model-rule="no" data-model-rule-name={name} data-model-rule-none="The draw does not compare summary settings.">
		<p data-lede>Each upright spans the saved score range. The crossbar grows with the draw size and is split by outcome.</p>
		<ul class="legend" aria-label="Interval plot legend">
			{#each ['yes', 'no', 'maybe', 'missing'] as part, index (part)}
				<li><span style:background="var({tokens[index]})" aria-hidden="true"></span>{['Agreed YES', 'Agreed NO', 'MAYBE: split or unclear', 'Refused or did not return'][index]}</li>
			{/each}
		</ul>
		<p data-comparison="Bounds used against bounds decided after the draw.">Dashed lower and solid upper lines are bounds used. Open diamonds are changes decided after the draw.</p>
		{#if drawing !== null}
			<label><input type="checkbox" bind:checked={full} /> Show full signed score scale</label>
			{#if floor > SCORE_MIN}<p>Zoomed to {value(floor)} through {value(SCORE_MAX)}. &lt; marks an interval that extends below the zoom.</p>{/if}
			<ScoreIntervals {drawing} {selected} {facts} {tokens} format={value} maxShare={chart.readout_max_share} {onPick} />
		{:else}
			<p>{note(selected)}</p>
		{/if}
		{#if answer !== 'pending' && answer.state === 'unreachable'}<button type="button" onclick={onRetry}>Retry draw history</button>{/if}
		{#if chosen?.slices?.length}
			<details>
				<summary>Exact intervals and counts for {longDate(selected)}</summary>
				<ul>
					{#each chosen.slices as slice (slice.low)}
						{@const parts = sliceParts(slice)}
						<li>{value(slice.low)} to {value(slice.high)}: {count(slice.drawn)} drawn;
							{count(parts.yes)} YES, {count(parts.no)} NO, {count(parts.unclear)} unclear,
							{count(parts.split)} split, {count(parts.refused)} refused, {count(parts.missing)} did not return.</li>
					{/each}
				</ul>
			</details>
		{/if}
		{#if fit}
			<details>
				<summary>Threshold fit and support for {longDate(selected)}</summary>
				<ul>
					{#each ['lower', 'upper'] as side (side)}
						<li>{side === 'lower' ? 'Lower' : 'Upper'} estimate: {score(fit[`${side}_estimate`])};
							{count(judgeCount(fit[`${side}_usable_pairs_used`]))} usable pairs over {count(judgeCount(fit[`${side}_nights_used`]))} digests.
							Hold: {fitNote(fit[`${side}_held_because`])}. Limit: {fitNote(fit[`${side}_move_limited_by`])}.</li>
					{/each}
				</ul>
			</details>
		{/if}
	</div>
</Panel>

<style>
	p { margin: 0 0 var(--space-2); }
	.legend { display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-4); list-style: none; padding: 0; }
	.legend span { display: inline-block; inline-size: var(--space-3); block-size: var(--space-3); margin-inline-end: var(--space-1); }
	label { display: flex; align-items: center; gap: var(--space-2); margin-block: var(--space-2); }
	details { margin-block-start: var(--space-3); }
</style>
