<script lang="ts">
	/** Keep a configured panel order, with an optional heading and group anchor. */
	import type { Snippet } from 'svelte';

	let {
		id,
		title,
		panels,
		children
	}: {
		id: string;
		title: string;
		/** How many panels the config put in this group. Drawn as an attribute so
		 * a check can hold the DOM to what the config declared rather than to
		 * whatever happened to render. */
		panels: number;
		children: Snippet;
	} = $props();
</script>

<section class="panel-group" {id} data-console-group={title ? id : undefined} data-console-group-panels={panels}>
	{#if title !== ''}
		<h2 class="group-title">{title}</h2>
		<a class="group-top" href="#console-top" data-console-group-top>Top</a>
	{/if}
	<div class="panel-grid">{@render children()}</div>
</section>

<style>
	/* No border, no tint and no card. The panels inside already carry an edge
	   each, and a box around three boxes is the nesting that makes a console
	   read as a form. What separates one group from the next is space and one
	   heavier line of type. */
	.panel-group {
		position: relative;
		margin-top: var(--console-group-gap);
	}
	.panel-grid { display: grid; gap: var(--console-panel-gap); min-inline-size: 0; }
	.panel-grid > :global(*) { min-inline-size: 0; }
	.panel-grid :global(.panel-block) { margin-top: 0; }
	@media (min-width: 1400px) {
		.panel-grid { grid-template-columns: repeat(var(--console-columns-wide), minmax(0, 1fr)); }
		.panel-grid > :global(:has([data-panel-verdict='route'])),
		.panel-grid > :global(:has(.panel-block.wide)) { grid-column: 1 / -1; }
	}

	/* A step up from the panel titles under it, which is the whole job: at one
	   size the heading is a fourteenth sibling rather than the thing that
	   groups the other thirteen. The room at its end is where the `Top` link
	   sits, on the heading's own line. */
	.group-title {
		margin: 0 0 var(--space-2);
		padding-bottom: var(--space-2);
		padding-inline-end: var(--space-8);
		border-bottom: 1px solid var(--color-rule);
		font-family: var(--font-display);
		font-size: var(--console-panel-title-size);
		line-height: var(--console-panel-title-leading);
		font-weight: var(--console-panel-title-weight);
		letter-spacing: var(--console-panel-title-tracking);
		color: var(--color-text);
	}

	/* On the heading's line at its trailing end, and in the console's link style. */
	.group-top {
		position: absolute;
		inset-block-start: 0;
		inset-inline-end: 0;
		font-size: var(--text-sm);
		line-height: var(--console-panel-title-leading);
		color: var(--color-accent);
	}

	.group-top:hover {
		text-decoration: underline;
	}
	@media (max-width: 1023px) {
		.panel-group:first-of-type { margin-block-start: var(--console-control-gap); }
		.group-title { margin-block-end: var(--console-control-padding-block); padding-block-end: var(--console-control-padding-block); }
	}
</style>
