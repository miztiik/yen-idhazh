<script lang="ts">
	/** A section of the console, in the one shape they all take.
	 *
	 * The console used to be headings and tables on bare background, which meant
	 * an operator's eye had nothing to group by and every section had the same
	 * weight as every other. A panel gives a section an edge, so "this belongs
	 * together" is drawn rather than inferred from proximity.
	 *
	 * Tint and elevation only. No display face, no gradient, no illustration -
	 * the operator surface is instrumentation, and a chart that looks like a
	 * poster is harder to read, not easier.
	 */
	import type { Snippet } from 'svelte';

	let {
		title,
		note = null,
		tone = 'neutral',
		wide = false,
		children
	}: {
		title: string;
		note?: string | null;
		/** The hue of what the panel means, never of how important it looks. */
		tone?: 'neutral' | 'info' | 'good' | 'warn' | 'bad';
		/** Set where the content is a table or a chart that needs the full frame. */
		wide?: boolean;
		children: Snippet;
	} = $props();
</script>

<section class="panel-block" data-console-panel={title} data-tone={tone} class:wide>
	<header class="panel-head">
		<h2 class="panel-title">{title}</h2>
		{#if note}<p class="panel-note">{note}</p>{/if}
	</header>
	<div class="panel-body">
		{@render children()}
	</div>
</section>

<style>
	.panel-block {
		margin-top: var(--space-6);
		padding: var(--space-5);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
		box-shadow: var(--shadow-sm);
	}

	.panel-block[data-tone='info'] {
		background: var(--tint-info);
	}
	.panel-block[data-tone='good'] {
		background: var(--tint-good);
	}
	.panel-block[data-tone='warn'] {
		background: var(--tint-warn);
	}
	.panel-block[data-tone='bad'] {
		background: var(--tint-bad);
	}

	.panel-head {
		margin-bottom: var(--space-3);
	}

	.panel-title {
		margin: 0;
		font-size: var(--text-lg);
		font-weight: 600;
		color: var(--color-text);
	}

	.panel-note {
		margin: var(--space-1) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}

	/* A wide panel still has an edge; it just does not pad its content away from
	   it, so a table can use the frame the row-4 work gave the page. */
	.panel-block.wide .panel-body {
		margin-inline: calc(var(--space-5) * -1);
	}

	.panel-block.wide .panel-body > :global(*) {
		padding-inline: var(--space-5);
	}
</style>
