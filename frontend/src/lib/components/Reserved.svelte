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
	import { STATE_WORDS, type PanelState } from '$lib/console/waiting';

	let {
		panelState: state,
		height,
		width,
		name,
		label,
		record = false,
		children
	}: {
		/** Named `panelState` rather than `state` because a prop called `state`
		 * shadows the `$state` rune inside the component that takes it, and the
		 * error that produces names an auto-subscription rather than the
		 * shadowing. */
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
		/** Ledger callers own their state words; month-based callers keep their old treatment until migration. */
		record?: boolean;
		children: Snippet;
	} = $props();

	const skeleton = $derived(skeletonFrame(width, height));
	/** Warn only where something failed. */
	const tone = $derived(state === 'unreachable' ? 'warn' : 'neutral');
	/** Month callers retain their own settled words. Ledger callers use the
	 * shared words inside this frame; loading never prints an answer. */
	const settledWord = $derived(record && (state === 'quiet' || state === 'missing' || state === 'unreachable') ? STATE_WORDS[state] : null);
	const passthrough = $derived(state !== 'loading' && state !== 'unreachable' && settledWord === null);
</script>

{#if passthrough}
	{@render children()}
{:else}
	<div
		class="reserved"
		class:loading={record && state === 'loading'}
		data-reserved={name}
		data-panel-state={state}
		data-tone={tone}
		style="block-size: {height}px"
		role="img"
		aria-label={state === 'loading'
			? `${label} - waiting for its rows`
			: settledWord === null ? `${label} - its rows did not arrive, and the sentence above the panels says which months` : `${label} - ${settledWord}`}
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

		{#if settledWord !== null}
			<p class="record-state">{settledWord}</p>
		{:else if state === 'loading' && !record}
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
	.record-state {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		margin: 0;
		padding-inline: var(--space-4);
		color: var(--color-text-secondary);
		font-size: var(--text-sm);
		text-align: center;
	}
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

	.reserved.loading {
		background-color: transparent;
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
