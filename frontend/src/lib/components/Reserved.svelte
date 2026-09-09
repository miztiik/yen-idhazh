<script lang="ts">
	/** The room a console panel takes, drawn before it has anything to put in it.
	 *
	 * **One box, five states, one height.** The box is exactly `height` tall
	 * whether it is waiting, quiet, gapped or refused, so nothing under it moves
	 * between the first frame and the settled page. That is the oracle this
	 * component exists to satisfy, and it is why the sentence a state prints sits
	 * INSIDE the reserved box rather than under it - a note under it would add
	 * its own height and shift the page the moment a state resolved.
	 *
	 * What it draws while waiting is the axis frame and the tick marks, and no
	 * numbers (`$lib/charts/skeleton`). A plain grey rectangle would keep the
	 * room and say nothing about what is coming.
	 *
	 * There is no spinner. A spinner suits one wait, a blank page and a person
	 * who cannot act; the console has a dozen waits and an operator who can act
	 * from the first frame (Susan, owner decision D3).
	 */
	import type { Snippet } from 'svelte';
	import { skeletonFrame } from '$lib/charts/skeleton';
	import type { PanelState } from '$lib/console/waiting';

	let {
		panelState: state,
		height,
		width,
		name,
		label,
		children
	}: {
		/** Named `panelState` rather than `state` because a prop called `state`
		 * shadows the `$state` rune inside the component that takes it, and the
		 * error that produces names a store rather than the shadowing. */
		panelState: PanelState;
		/** The drawn height of the panel's chart - `console.chart_height`. The
		 * reserved box is exactly this, in every state it is in. */
		height: number;
		/** The width the chart is authored at - `console.chart_width`. It sets the
		 * SVG's viewBox, so the frame scales with the column rather than being
		 * measured in a browser that has not run yet. */
		width: number;
		/** A key for a test or a smoke to find this box by. */
		name: string;
		/** What the panel is, for anyone who cannot see it. */
		label: string;
		children: Snippet;
	} = $props();

	const skeleton = $derived(skeletonFrame(width, height));
	/** Warn only where something failed. */
	const tone = $derived(state === 'unreachable' ? 'warn' : 'neutral');
	/** The box takes over for exactly two states, and the rule is one sentence:
	 * **it appears where the panel's own words would be false.**
	 *
	 * A panel with rows on the way that printed "nothing is on record" would be
	 * wrong for the next second; a panel whose month did not arrive and printed
	 * the same thing would be wrong outright. Those are `loading` and
	 * `unreachable`. An empty window and a real gap are the other way round - the
	 * panel's own sentence is TRUE and more precise than anything a general box
	 * could write, so it keeps it, and which of the two it is gets said once for
	 * the whole page beside the control that governs the window.
	 *
	 * The box itself carries no words for the same reason: a dozen panels each
	 * repeating one page-level fact is a dozen announcements of one thing.
	 */
	const passthrough = $derived(state !== 'loading' && state !== 'unreachable');
</script>

{#if passthrough}
	{@render children()}
{:else}
	<div
		class="reserved"
		data-reserved={name}
		data-panel-state={state}
		data-tone={tone}
		style="block-size: {height}px"
		role="img"
		aria-label={state === 'loading'
			? `${label} - waiting for its rows`
			: `${label} - its rows did not arrive, and the sentence above the panels says which months`}
		aria-busy={state === 'loading'}
	>
		<!-- The frame, and only the frame. Ticks are marks; a tick LABEL needs a
		     value, and there is no value here. -->
		<svg
			class="reserved-frame"
			viewBox="0 0 {width} {height}"
			preserveAspectRatio="none"
			aria-hidden="true"
			focusable="false"
			data-reserved-frame={name}
			data-reserved-ticks={skeleton.xTicks.length}
		>
			<line
				x1={skeleton.box.left}
				y1={skeleton.box.top}
				x2={skeleton.box.left}
				y2={skeleton.box.bottom}
				stroke="var(--chart-axis)"
				stroke-width="1"
			/>
			<line
				x1={skeleton.box.left}
				y1={skeleton.box.bottom}
				x2={skeleton.box.right}
				y2={skeleton.box.bottom}
				stroke="var(--chart-axis)"
				stroke-width="1"
			/>
			{#each skeleton.xTicks as at (at)}
				<line
					x1={at}
					y1={skeleton.box.bottom}
					x2={at}
					y2={skeleton.box.bottom + 4}
					stroke="var(--chart-axis)"
					stroke-width="1"
				/>
			{/each}
			{#each skeleton.yTicks as at (at)}
				<line
					x1={skeleton.box.left - 4}
					y1={at}
					x2={skeleton.box.left}
					y2={at}
					stroke="var(--chart-axis)"
					stroke-width="1"
				/>
			{/each}
		</svg>

		{#if state === 'loading'}
			<!-- The marks that stand where the data will be, inside the same plot
			     the SVG drew. They carry the `loading` state class, so the sweep is
			     switched on by an ancestor and every block on the page moves in one
			     phase (app.css). -->
			<div
				class="reserved-plot"
				aria-hidden="true"
				style="top: {skeleton.inset.top}; right: {skeleton.inset.right}; bottom: {skeleton.inset
					.bottom}; left: {skeleton.inset.left}"
			>
				{#each skeleton.bars as bar, index (index)}
					<span class="loading reserved-bar" style="block-size: {(bar * 100).toFixed(2)}%"></span>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<style>
	/* No tint of its own. The axis frame is the only thing this box says, and a
	   tint under it costs exactly that: measured 2026-09-09 over the committed
	   token values, `--chart-axis` reads 2.76:1 dark and 2.38:1 light on a tinted
	   box, against 3.2:1 and 2.58:1 on the panel itself - which is where every
	   real chart on this page draws its axis. So the waiting frame is exactly as
	   legible as the chart it stands in for, neither louder nor quieter. */
	.reserved {
		position: relative;
		inline-size: 100%;
		border-radius: var(--radius-md);
	}

	/* A failed fetch is the only one of the four that is a fault, so it is the
	   only one that takes a hue. A quiet window and a real gap are normal, and a
	   page that tints normal things like faults teaches its operator to stop
	   reading the tint. */
	.reserved[data-tone='warn'] {
		background: var(--tint-warn);
	}

	.reserved-frame {
		position: absolute;
		inset: 0;
		inline-size: 100%;
		block-size: 100%;
	}

	.reserved-plot {
		position: absolute;
		display: flex;
		align-items: flex-end;
		gap: 1.6%;
	}

	.reserved-bar {
		flex: 1 1 0;
		min-inline-size: 1px;
		align-self: flex-end;
	}
</style>
