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
		sentence = '',
		action = null,
		onRetry = null,
		children
	}: {
		/** Named `panelState` rather than `state` because a prop called `state`
		 * shadows the `$state` rune inside the component that takes it, and the
		 * error that produces names a store rather than the shadowing. */
		panelState: PanelState;
		/** The drawn height of the panel's chart - `console.chart_height`. The
		 * reserved box is exactly this, in every state. */
		height: number;
		/** The width the chart is authored at - `console.chart_width`. It sets the
		 * SVG's viewBox, so the frame scales with the column rather than being
		 * measured in a browser that has not run yet. */
		width: number;
		/** A key for a test or a smoke to find this box by. */
		name: string;
		/** What the panel is, for anyone who cannot see it. */
		label: string;
		/** What is true, in one sentence. Empty while loading: the wait is said
		 * once for the whole page by the window control, and a dozen panels each
		 * announcing their own would be a dozen announcements of one fact. */
		sentence?: string;
		/** The retry's label, where there is something to retry. */
		action?: string | null;
		onRetry?: (() => void) | null;
		children: Snippet;
	} = $props();

	const skeleton = $derived(skeletonFrame(width, height));
	/** Warn only where something failed. A real gap and an empty window are
	 * normal, and a page that tints them like a fault teaches an operator to
	 * ignore the tint. */
	const tone = $derived(state === 'unreachable' ? 'warn' : 'neutral');
</script>

{#if state === 'ready'}
	{@render children()}
{:else}
	<div
		class="reserved"
		data-reserved={name}
		data-panel-state={state}
		data-tone={tone}
		style="block-size: {height}px"
		role="img"
		aria-label={state === 'loading' ? `${label} - waiting for its rows` : `${label} - ${sentence}`}
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
		{:else}
			<!-- Over the frame, not under it. A note under the box would add its own
			     height, and the whole point of the box is that its height never
			     changes. -->
			<div class="reserved-say">
				<p class="reserved-note" data-reserved-note={name}>{sentence}</p>
				{#if action !== null && onRetry !== null}
					<button
						type="button"
						class="reserved-retry"
						data-reserved-retry={name}
						onclick={onRetry}>{action}</button
					>
				{/if}
			</div>
		{/if}
	</div>
{/if}

<style>
	.reserved {
		position: relative;
		inline-size: 100%;
		border-radius: var(--radius-md);
		background: var(--tint-neutral);
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

	.reserved-say {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--space-3);
		padding: var(--space-4);
		text-align: center;
	}

	.reserved-note {
		max-inline-size: 46ch;
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	/* Scoped to this panel and to the month it names. Nothing else on the page
	   moves when it is pressed. */
	.reserved-retry {
		min-block-size: 2.75rem;
		padding: 0 var(--space-4);
		border: 1px solid var(--color-rule-strong);
		border-radius: var(--radius-full);
		background: var(--color-surface);
		font-size: var(--text-sm);
		color: var(--color-text);
		cursor: pointer;
	}

	.reserved-retry:hover {
		border-color: var(--color-accent);
	}
</style>
