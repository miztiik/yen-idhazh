<script lang="ts">
	/** One named question on a console route, and the panels that answer it.
	 *
	 * The Hardware route was fifteen panels down one column, every title at one
	 * weight, and an operator's eye had nothing to land on first. A group gives
	 * that column three stops, each one a question the panels under it share -
	 * so a reader who wants the run that just finished stops reading at the
	 * second heading.
	 *
	 * An empty title draws no heading and no element at all. A route that wants
	 * an order without a grouping - Pipelines - says so by leaving the title
	 * empty, and gets exactly the flat siblings it had before, in the order its
	 * config names.
	 */
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

{#if title === ''}
	{@render children()}
{:else}
	<section class="panel-group" data-console-group={id} data-console-group-panels={panels}>
		<h2 class="group-title">{title}</h2>
		{@render children()}
	</section>
{/if}

<style>
	/* No border, no tint and no card. The panels inside already carry an edge
	   each, and a box around three boxes is the nesting that makes a console
	   read as a form. What separates one group from the next is space and one
	   heavier line of type. */
	.panel-group {
		margin-top: var(--space-8);
	}

	/* A step up from the panel titles under it, which is the whole job: at one
	   size the heading is a fourteenth sibling rather than the thing that
	   groups the other thirteen. */
	.group-title {
		margin: 0 0 var(--space-2);
		padding-bottom: var(--space-2);
		border-bottom: 1px solid var(--color-rule);
		font-size: var(--text-xl);
		line-height: var(--leading-xl);
		font-weight: 600;
		letter-spacing: -0.011em;
		color: var(--color-text);
	}
</style>
