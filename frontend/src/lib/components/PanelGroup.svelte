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
	 *
	 * A titled group is also a place to jump to. Its id is the group's own, so the
	 * console's `On this page` row links straight to it, and a `Top` link beside
	 * the heading goes back to the head of the console. Both are plain anchors,
	 * so they work with no script at every width.
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
	<section class="panel-group" {id} data-console-group={id} data-console-group-panels={panels}>
		<h2 class="group-title">{title}</h2>
		<a class="group-top" href="#console-top" data-console-group-top>Top</a>
		{@render children()}
	</section>
{/if}

<style>
	/* No border, no tint and no card. The panels inside already carry an edge
	   each, and a box around three boxes is the nesting that makes a console
	   read as a form. What separates one group from the next is space and one
	   heavier line of type. */
	.panel-group {
		position: relative;
		margin-top: var(--space-8);
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
		font-size: var(--text-xl);
		line-height: var(--leading-xl);
		font-weight: 600;
		letter-spacing: -0.011em;
		color: var(--color-text);
	}

	/* On the heading's line at its trailing end, and in the console's link style. */
	.group-top {
		position: absolute;
		inset-block-start: 0;
		inset-inline-end: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-xl);
		color: var(--color-accent);
	}

	.group-top:hover {
		text-decoration: underline;
	}
</style>
