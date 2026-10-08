<script lang="ts">
	/** A chart with nothing to draw, at the height the chart would have taken.
	 *
	 * **The box is the chart's height in every state**, so a panel does not
	 * move when its rows resolve into a nothing. A wait is the reserved box,
	 * shimmer and all, and says nothing, because a panel with rows on the way
	 * that printed a sentence would be wrong in a second. Every other nothing
	 * is a box of the same height carrying the one sentence `waiting.ts` wrote
	 * for it, so a quiet window, a real gap, a floor missed and a failed fetch
	 * are four different pictures. Only the failure takes a hue.
	 */
	import Reserved from '$lib/components/Reserved.svelte';
	import type { EmptyDrawing } from './empty';

	let {
		drawing,
		height,
		width,
		name,
		label
	}: {
		drawing: EmptyDrawing;
		/** The drawn height of the chart this stands in for. */
		height: number;
		/** The width the chart is authored at, for the reserved frame's viewBox. */
		width: number;
		/** A key for a test or a smoke to find this box by. */
		name: string;
		/** What the chart is, for anyone who cannot see it. */
		label: string;
	} = $props();
</script>

<!-- The reserved box never draws its children while it waits. -->
{#snippet nothing()}{/snippet}

{#if drawing.shimmer}
	<Reserved panelState="loading" {height} {width} {name} {label} children={nothing} />
{:else}
	<div
		class="empty"
		data-empty={name}
		data-empty-state={drawing.kind}
		data-tone={drawing.tone}
		style="block-size: {height}px"
	>
		<p class="empty-sentence">{drawing.sentence}</p>
	</div>
{/if}

<style>
	.empty {
		display: grid;
		place-items: center;
		box-sizing: border-box;
		inline-size: 100%;
		padding-inline: var(--space-4);
		overflow: hidden;
		border-radius: var(--radius-md);
	}

	/* A failed fetch is the one nothing that is a fault. */
	.empty[data-tone='warn'] {
		background: var(--tint-warn);
	}

	.empty-sentence {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
		text-align: center;
		/* A centred sentence that wraps leaves its last word alone on a phone
		   unless its lines are evened out. */
		text-wrap: balance;
	}
</style>
