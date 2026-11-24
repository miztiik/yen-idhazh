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
	import { DRAW_PARTS, OUTCOME_STYLE } from './judge-trial-style';

	let { calendar, selected, rows, fit, answer, reach, knobs, chart, contextShare, onPick, onRetry }: {
		calendar: readonly string[]; selected: string; rows: ReadonlyMap<string, Row>;
		fit: Row | null; answer: Answer; reach: LedgerReach; knobs: ConsoleConfig; chart: ChartConfig;
		contextShare: number | null;
		onPick: (date: string) => void; onRetry: () => void;
	} = $props();

	let measured = $state<number | null>(null);
	const name = 'judge-draw-intervals';
	const frame = useChartFrame(() => chart);
	const value = (n: number) => judgeDecimal(n, chart.number_format);
	const number = $derived(numberFormatter(chart.number_format));
	const count = (n: number | null) => n === null ? 'Not recorded' : number(n, { exact: true });
	const estimate = (n: unknown) => {
		const reading = judgeNumber(n);
		return reading === null ? 'Not recorded' : number(reading, { si: false });
	};
	const tokens = [OUTCOME_STYLE.yes.token, OUTCOME_STYLE.no.token, OUTCOME_STYLE.maybe.token, OUTCOME_STYLE.missing.token];
	const dates = $derived(calendar.map((date) => ({ date, ...drawOf(rows.get(date) ?? null) })));
	const chosen = $derived(dates.find(({ date }) => date === selected));
	const min = $derived(Math.min(...dates.flatMap(({ bounds, decided }) => [bounds?.lower, decided?.lower])
		.filter((n): n is number => n !== undefined)));
	const columns = $derived(DRAW_PARTS.filter((key) =>
		key === 'yes' || key === 'no' || chosen?.slices?.some((slice) => sliceParts(slice)[key] > 0)));
	const drawing = $derived(scoreIntervals(dates.map((day) => ({
		date: day.date, used: [day.bounds?.lower ?? null, day.bounds?.upper ?? null],
		decided: [day.decided?.lower ?? null, day.decided?.upper ?? null],
		slices: (day.slices ?? []).map((slice) => {
			const { yes, no, unclear, split, refused, missing } = sliceParts(slice);
			return { low: slice.low, high: slice.high, parts: [yes, no, unclear + split, refused + missing] };
		})
	})), frame(chartWidth(measured, knobs.chart_width), knobs.chart_height), SCORE_MIN, SCORE_MAX, chart.tick_density,
		contextShare !== null && Number.isFinite(min) ? { focus: min, share: contextShare } : null));
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
	const fitMetrics = [['Estimate', 'estimate'], ['Usable pairs', 'pairs'], ['Digests', 'digests'], ['Hold', 'held'], ['Limit', 'limit']] as const;
	const fitRows = $derived(fit === null ? [] : ['lower', 'upper'].map((side) => ({
		side: side === 'lower' ? 'Lower' : 'Upper',
		estimate: estimate(fit?.[`${side}_estimate`]),
		pairs: count(judgeCount(fit?.[`${side}_usable_pairs_used`])),
		digests: count(judgeCount(fit?.[`${side}_nights_used`])),
		held: fitNote(fit?.[`${side}_held_because`]),
		limit: fitNote(fit?.[`${side}_move_limited_by`])
	})));
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
			{#if drawing.axis.focus !== null}<p>Scores below {value(drawing.axis.focus)} use a compressed scale.</p>{/if}
			<ScoreIntervals {drawing} {selected} {facts} {tokens} format={value} maxShare={chart.readout_max_share} {onPick} />
		{:else}
			<p>{note(selected)}</p>
		{/if}
		{#if answer !== 'pending' && answer.state === 'unreachable'}<button type="button" onclick={onRetry}>Retry draw history</button>{/if}
		{#if chosen?.slices?.length}
			<details>
				<summary>Slice counts</summary>
				<div class="table-wrap">
					<table aria-label="Exact slice counts">
						<thead><tr><th scope="col">Score range</th><th scope="col">Drawn</th>
							{#each columns as key (key)}
								<th scope="col" style:color="var({OUTCOME_STYLE[key].token})">
									{key === 'missing' ? 'No return' : key === 'split' ? 'Split' : key.toUpperCase()}
								</th>
							{/each}
						</tr></thead>
						<tbody>
							{#each chosen.slices as slice (slice.low)}
								{@const parts = sliceParts(slice)}
								<tr><th scope="row">{value(slice.low)} to {value(slice.high)}</th><td>{count(slice.drawn)}</td>
									{#each columns as key (key)}<td>{count(parts[key])}</td>{/each}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</details>
		{/if}
		{#if fitRows.length}
			<details>
				<summary>Threshold fit</summary>
				<div class="table-wrap">
					<table aria-label="Threshold fit evidence">
						<thead><tr><th scope="col">Metric</th>{#each fitRows as row (row.side)}<th scope="col">{row.side}</th>{/each}</tr></thead>
						<tbody>
							{#each fitMetrics as [label, key] (key)}
								<tr><th scope="row">{label}</th>
									{#each fitRows as row (row.side)}
										<td>{row[key]}</td>
									{/each}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</details>
		{/if}
	</div>
</Panel>

<style>
	p { margin: 0 0 var(--space-2); }
	.legend { display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-4); list-style: none; padding: 0; }
	.legend span { display: inline-block; inline-size: var(--space-3); block-size: var(--space-3); margin-inline-end: var(--space-1); }
	details { margin-block-start: var(--space-3); }
	.table-wrap { overflow-x: auto; margin-block-start: var(--space-2); }
	table { border-collapse: collapse; font-size: var(--console-small-size); font-variant-numeric: tabular-nums; }
	th, td { padding: var(--space-1) var(--space-2); border-block-end: 1px solid var(--color-rule); }
	th[scope='row'] { text-align: start; white-space: nowrap; }
	td, th[scope='col'] { text-align: end; }
</style>
