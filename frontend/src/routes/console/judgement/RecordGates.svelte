<script lang="ts">
	/** What the record still needs before a line may be fitted at all, and which
	 * days it actually folded.
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
	import { daysBetween, type TimeWindow } from '$lib/charts/viewport';
	import Panel from '$lib/components/Panel.svelte';
	import TargetBar from '$lib/components/TargetBar.svelte';
	import { grouped } from '$lib/charts/series';
	import { foldDays, gateNeeds, silentTail, type JudgeDay } from '$lib/console/merge-line';

	let {
		days,
		dates,
		gates,
		viewport
	}: {
		days: JudgeDay[];
		/** Every date the window spans, including the ones nothing recorded. */
		dates: string[];
		gates: { minimumNegatives: number; minimumDays: number; minimumAboveLine: number };
		viewport: TimeWindow;
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
	const squares = $derived(foldDays(spanned, drawn, met));
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
</script>

<Panel
	title="What the record still needs"
	note="Three counts have to be reached before the line may move at all. The squares are one a day: what the record did with that day."
>
	<div
		data-windowed="record-gates"
		data-window-days={windowDays}
		data-gates-met={met ? 'yes' : 'no'}
		data-readout-none="three values against three thresholds, and all six are already in words"
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

		<div class="strip" data-fold-strip data-fold-squares={squares.length}>
			{#each squares as square (square.date)}
				<span
					class="square"
					style={`background: ${fill(square.state)}`}
					data-fold-day={square.date}
					data-fold-state={square.state}
					title={square.title}
				><span class="sr-only">{square.title}</span></span>
			{/each}
		</div>

		<p class="gates-note">
			{#if newest === null}
				<span data-gates-state="empty"
					>Nothing has been judged yet. The three bars are what the record needs before a
					line may be fitted at all.</span
				>
			{:else if !met}
				<span data-gates-state="filling"
					>The record has {grouped(needs[0].value)} of the {grouped(needs[0].target)} readings
					it needs, {needs[1].value} of {needs[1].target} days, and {grouped(needs[2].value)} of
					{grouped(needs[2].target)} pairs above the line.</span
				>
			{:else if silent > 0}
				<span data-gates-state="stale"
					>Nothing has been folded for {silent}
					{silent === 1 ? 'day' : 'days'}.</span
				>
			{:else}
				<span data-gates-state="met"
					>The record has what it needs. These three bars stay so a record that empties is
					visible.</span
				>
			{/if}
			{#if fitted > 0}
				<span data-fold-fitted={fitted}
					>A line was fitted on {fitted} of these {windowDays} days.</span
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

	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}

	.gates-note {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
</style>
