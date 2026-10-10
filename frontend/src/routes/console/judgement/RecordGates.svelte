<script lang="ts">
	/** What the record still needs before a line may be fitted at all, and which
	 * days it actually counted.
	 *
	 * Three target bars, one per gate, and a square a day underneath.
	 *
	 * **The bars are not deleted when the gates clear.** They become where
	 * staleness fires. They are the record's newest row on or before the window's
	 * last day, so a window with no row leaves them standing; only a record that
	 * empties - because a weight moved and the fit archived it - or never held a
	 * row draws them at zero.
	 *
	 * **A held day while the gates are unfilled is not a warning.** It is the
	 * design working. The warning fill arrives on the day a hold stops being
	 * expected, so the colour still means something when it does.
	 */
	import { targetMarks } from '$lib/charts/targetbar';
	import { markReadout, readoutOf } from '$lib/charts/readout';
	import { daysBetween, type TimeWindow } from '$lib/charts/viewport';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import { shortDate } from '$lib/format';
	import TargetBar from '$lib/components/TargetBar.svelte';
	import { grouped } from '$lib/charts/series';
	import {
		countedDays,
		describeEarlierRow,
		findNewestRow,
		gateNeeds,
		silentTail,
		type JudgeDay
	} from '$lib/console/merge-line';
	import { countDays, nameSpan } from '$lib/console/span-words';

	let {
		days: inputDays,
		evidence = [],
		dates,
		gates,
		viewport,
		readoutMaxShare
	}: {
		days: JudgeDay[] | null;
		evidence?: string[];
		/** Every date the window spans, including the ones nothing recorded. */
		dates: string[];
		gates: { minimumNegatives: number; minimumDays: number; minimumAboveLine: number };
		viewport: TimeWindow;
		/** `chart.readout_max_share`. */
		readoutMaxShare: number;
	} = $props();

	const windowDays = $derived(daysBetween(viewport.start, viewport.end));
	const days = $derived(inputDays ?? []);
	const drawn = $derived(
		days.filter((day) => day.date >= viewport.start && day.date <= viewport.end)
	);
	const spanned = $derived(
		dates.filter((date) => date >= viewport.start && date <= viewport.end)
	);
	/** The record is cumulative, so its newest row on or before the window's last
	 * day is what it holds then, whether or not the window holds a row. */
	const standing = $derived(findNewestRow(days, viewport.end));
	/** The newest row inside the window, which the note's state reads. */
	const newest = $derived(drawn.length === 0 ? null : drawn[drawn.length - 1]);
	const needs = $derived(gateNeeds(standing, gates));
	const met = $derived(needs.every((need) => need.value >= need.target));
	const squares = $derived(countedDays(spanned, drawn, met));
	const silent = $derived(silentTail(squares));
	const fitted = $derived(squares.filter((square) => square.state === 'fitted').length);

	/** One categorical fill a state, and every square carries a sentence as well,
	 * so a reader who cannot tell two hues apart still has the answer. */
	function fill(state: string): string {
		switch (state) {
			case 'fitted':
				return 'var(--fill-high)';
			case 'held':
				return 'var(--fill-medium)';
			case 'filling':
				return 'var(--chart-1)';
			default:
				return 'var(--color-surface-sunken)';
		}
	}

	/** The day a pointer, a key or a tap has picked, or null for the newest. */
	let picked = $state<number | null>(null);

	/** One square a day, printed in words with the fill it is drawn in. It rests
	 * on the newest day, which is what the record holds now. */
	const readout = $derived(
		readoutOf({
			type: 'tileStrip',
			columns: squares.map((square) => shortDate(square.date)),
			series: [
				{
					label: 'The record',
					swatch: null,
					values: squares.map((square) => square.said),
					format: (value: number) => String(value)
				}
			],
			events: {
				lines: squares.map((square) => [
					{ label: 'Square', value: square.state, swatch: fill(square.state) }
				])
			},
			notMeasured: 'no judge row was returned for this day.',
			resting: 'last'
		})
	);
</script>

<Panel
	id="record-gates"
	title="What the record still needs"
	note={`Three counts have to be reached before the line may move at all. ${windowDays === 1 ? `The square is what the record did with ${nameSpan(windowDays)}.` : 'The squares are one a day: what the record did with that day.'}`}
>
	<div
		data-windowed="record-gates"
		data-panel-question="Does the record hold enough evidence to move the line?"
		data-model-rule="no"
		data-model-rule-none="the judge's record, not how summaries are written"
		data-window-days={windowDays}
		data-gates-met={standing === null ? undefined : met ? 'yes' : 'no'}
		data-readout-none={inputDays === null
			? 'the gate counts are unavailable, so there is no day to read; agreed with Susan'
			: undefined}
	>
		<p class="comparison" data-comparison="Each gate's recorded count against the count it needs.">
			Each gate's recorded count against the count it needs.
		</p>
		{#each evidence as note}<p data-evidence-note>{note}</p>{/each}
		{#if inputDays === null}
			<p class="lede" data-lede data-empty="missing">The record's gate counts are unavailable for {nameSpan(windowDays)}.</p>
		{:else}
		<p class="lede" data-lede>
			{standing === null ? 'No gate counts were returned for this window.' : `${needs.filter((need) => need.value >= need.target).length} of ${needs.length} gates passed`}
		</p>
		{#if standing !== null}
		<div class="bars">
			{#each needs as need (need.label)}
				<TargetBar
					marks={targetMarks(need.value, need.target, 'higher-is-better')}
					label={need.label}
					valueText={grouped(need.value)}
					targetText={need.targetText}
					emptyNote="Nothing has been judged yet."
					tone="policy"
				/>
			{/each}
		</div>
		{/if}

		<!-- The squares wrap onto several lines, so a pointer reads the square
		     under it rather than the nearest one across; one tab stop for all. -->
		<div
			data-readout-columns={squares.length > 0 ? squares.length : undefined}
			data-readout-none={squares.length > 0
				? undefined
				: 'the window spans no day, so there is no square to read; agreed with Susan'}
		>
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<div
				class="strip"
				data-chart-type="tileStrip"
				data-counted-strip
				data-counted-squares={squares.length}
				tabindex="0"
				role="group"
				aria-label={windowDays === 1
					? `What the record did with ${nameSpan(windowDays)}.`
					: 'What the record did with each day. Left and Right read a day, Escape returns to the newest.'}
				use:markReadout={{
					count: squares.length,
					walk: 'row',
					onSelect: (index) => (picked = index),
					selected: picked
				}}
			>
				{#each squares as square, index (square.date)}
					<span
						class="square"
						style={`background: ${fill(square.state)}`}
						role="img"
						aria-label={square.title}
						data-readout-at={index}
						data-readout-picked={picked === index ? 'yes' : undefined}
						data-counted-day={square.date}
						data-counted-state={square.state}
					></span>
				{/each}
			</div>
			{#if squares.length > 0}
				<ChartReadout
					{readout}
					at={picked}
					name="record-gates"
					maxShare={readoutMaxShare}
					restingNote=", the newest day"
					hint="Point at a square to read its day. Left and Right step through the days, Escape returns to the newest."
				/>
			{/if}
		</div>

		<p class="gates-note" data-gates-note>
			{#if newest === null && standing !== null}
				<!-- The bars stand on a row before the window, so the note names its
				     day: a reader has to know they are not this window's. -->
				<span data-gates-state="earlier">{describeEarlierRow(standing, windowDays)}</span>
			{:else if newest === null}
				<span data-gates-state="empty"
					>No gate counts were returned for {nameSpan(windowDays)}. The record needs readings,
					days counted and pairs above the line before a line may be fitted.</span
				>
			{:else}
				{#if !met}
					<span data-gates-state="filling"
						>The record has {grouped(needs[0].value)} readings, {countDays(needs[1].value)}, and
						{grouped(needs[2].value)} pairs above the line; it needs at least
						{grouped(needs[0].target)} readings, {countDays(needs[1].target)}, and
						{grouped(needs[2].target)} pairs above the line.</span
					>
				{:else if silent > 0}
					<span data-gates-state="stale">No judge row was returned for the latest {countDays(silent)}.</span>
				{:else}
					<span data-gates-state="met"
						>The record has what it needs. These three bars stay so a record that empties is
						visible.</span
					>
				{/if}
				<!-- Printed in every state with a row, so the window's days are named
				     whether or not a line was fitted on one of them. -->
				<span data-counted-fitted={fitted}
					>{fitted > 0
						? `A line was fitted on ${fitted} of ${countDays(windowDays)}.`
						: `No fitted line was returned for ${nameSpan(windowDays)}.`}</span
				>
			{/if}
		</p>
		{/if}
	</div>
</Panel>

<style>
	.lede {
		margin: 0 0 var(--space-3);
		font-size: var(--text-xl);
		line-height: var(--leading-xl);
		color: var(--color-text);
	}
	.comparison {
		margin: 0 0 var(--space-3);
		font-size: var(--text-sm);
		color: var(--color-text-secondary);
	}
	.bars {
		display: grid;
		gap: var(--space-3);
	}

	/* One row that wraps rather than one that scrolls: the widest preset is 91
	   squares, and a strip a reader has to drag is a strip nobody reads. */
	.strip {
		display: flex;
		flex-wrap: wrap;
		gap: 2px;
		margin-top: var(--space-4);
	}

	.square {
		width: 10px;
		height: 10px;
		border-radius: 2px;
	}

	.gates-note {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
	/* The day the strip below is reading. */
	.square[data-readout-picked] {
		outline: 2px solid var(--color-focus);
		outline-offset: 1px;
	}

	.strip:focus-visible {
		outline: 2px solid var(--color-focus);
		outline-offset: 3px;
	}
</style>
