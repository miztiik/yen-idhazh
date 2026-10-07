<script lang="ts">
	/** What the record still needs before a line may be fitted at all, and which
	 * days it actually counted.
	 *
	 * Three target bars, one per gate, and a square a day underneath.
	 *
	 * **The bars are not deleted when the gates clear.** They become where
	 * staleness fires. A record that empties - because a weight moved and the fit
	 * archived it - drops all three bars back towards zero, and this is the one
	 * picture that says so.
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
	import { countedDays, gateNeeds, silentTail, type JudgeDay } from '$lib/console/merge-line';
	import { countDays, nameSpan } from '$lib/console/span-words';

	let {
		days,
		dates,
		gates,
		viewport,
		readoutMaxShare
	}: {
		days: JudgeDay[];
		/** Every date the window spans, including the ones nothing recorded. */
		dates: string[];
		gates: { minimumNegatives: number; minimumDays: number; minimumAboveLine: number };
		viewport: TimeWindow;
		/** `chart.readout_max_share`. */
		readoutMaxShare: number;
	} = $props();

	const windowDays = $derived(daysBetween(viewport.start, viewport.end));
	const drawn = $derived(
		days.filter((day) => day.date >= viewport.start && day.date <= viewport.end)
	);
	const spanned = $derived(
		dates.filter((date) => date >= viewport.start && date <= viewport.end)
	);
	/** The record is cumulative, so the newest row is what it holds now. */
	const newest = $derived(drawn.length === 0 ? null : drawn[drawn.length - 1]);
	const needs = $derived(gateNeeds(newest, gates));
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
			notMeasured: 'no run recorded anything.',
			resting: 'last'
		})
	);
</script>

<Panel
	title="What the record still needs"
	note="Three counts have to be reached before the line may move at all. The squares are one a day: what the record did with that day."
>
	<div
		data-windowed="record-gates"
		data-window-days={windowDays}
		data-gates-met={met ? 'yes' : 'no'}
	>
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
				data-counted-strip
				data-counted-squares={squares.length}
				tabindex="0"
				role="group"
				aria-label="What the record did with each day. Left and Right read a day, Escape returns to the newest."
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
			{#if newest === null}
				<span data-gates-state="empty"
					>Nothing was judged in {nameSpan(windowDays)}. The three bars are what the record needs
					before a line may be fitted at all.</span
				>
			{:else}
				{#if !met}
					<span data-gates-state="filling"
						>The record has {grouped(needs[0].value)} of the {grouped(needs[0].target)} readings
						it needs, {needs[1].value} of {needs[1].target} days, and {grouped(needs[2].value)} of
						{grouped(needs[2].target)} pairs above the line.</span
					>
				{:else if silent > 0}
					<span data-gates-state="stale">Nothing has been counted for {countDays(silent)}.</span>
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
						: `No line was fitted in ${nameSpan(windowDays)}.`}</span
				>
			{/if}
		</p>
	</div>
</Panel>

<style>
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
