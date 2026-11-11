<script lang="ts">
	/** Group one console question and its evidence on a neutral surface. */
	import type { Snippet } from 'svelte';

	let {
		title,
		id = null,
		note = null,
		tone = 'neutral',
		wide = false,
		heading = 'h2',
		verdict = false,
		actions = null,
		children
	}: {
		title: string;
		/** The id `console.panel_groups` places this panel under. It is what a
		 * check holds the page to: the title is prose, and a row that rewrites
		 * prose would otherwise move every address with it. */
		id?: string | null;
		note?: string | null;
		/** The hue of what the panel means, never of how important it looks. */
		tone?: 'neutral' | 'info' | 'good' | 'warn' | 'bad';
		/** Set where the content is a table or a chart that needs the full frame. */
		wide?: boolean;
		/** Which level the title takes. A panel under a group heading is an `h3`
		 * below that heading's `h2`, so the outline says what contains what
		 * instead of drawing every title at one weight. */
		heading?: 'h2' | 'h3';
		/** Set on the one panel that verdicts the rest of its route. It sits
		 * first, so an operator reads whether to trust the readings before he
		 * reads ten of them. */
		verdict?: boolean;
		/** Optional controls that act on the panel as a whole. */
		actions?: Snippet | null;
		children: Snippet;
	} = $props();
</script>

<section
	class="panel-block"
	data-console-panel={title}
	data-console-panel-id={id ?? undefined}
	data-tone={tone}
	data-panel-verdict={verdict ? 'route' : undefined}
	data-panel-question={verdict ? 'is it working' : undefined}
	class:wide
>
	<header class="panel-head">
		{#if heading === 'h3'}
			<h3 class="panel-title">{title}</h3>
		{:else}
			<h2 class="panel-title">{title}</h2>
		{/if}
		{#if actions}
			<div class="panel-actions">
				{@render actions()}
			</div>
		{/if}
		{#if note}<p class="panel-note">{note}</p>{/if}
	</header>
	<div class="panel-body">
		{@render children()}
	</div>
</section>

<style>
	.panel-block {
		min-inline-size: 0;
		margin-top: var(--console-panel-gap);
		padding: var(--console-panel-padding);
		border: 1px solid var(--color-rule);
		border-radius: var(--console-panel-radius);
		background: var(--color-surface);
		box-shadow: var(--shadow-sm);
	}

	.panel-head {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: start;
		gap: var(--console-control-gap) var(--console-panel-gap);
		margin-bottom: var(--console-panel-gap);
	}

	.panel-title {
		margin: 0;
		font-family: var(--font-display);
		font-size: var(--console-panel-title-size);
		line-height: var(--console-panel-title-leading);
		font-weight: var(--console-panel-title-weight);
		letter-spacing: var(--console-panel-title-tracking);
		color: var(--color-text);
	}

	.panel-note {
		margin: 0;
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
		color: var(--color-text-secondary);
		grid-column: 1 / -1;
	}

	.panel-actions {
		display: flex;
		flex-wrap: wrap;
		justify-content: flex-end;
		gap: var(--space-2);
	}

	@media (max-width: 1023px) {
		.panel-head {
			grid-template-columns: minmax(0, 1fr);
		}

		.panel-actions {
			justify-content: flex-start;
		}
	}

	.panel-block.wide, .panel-block[data-panel-verdict='route'] { grid-column: 1 / -1; }

	/* Under workbench chrome a panel is a region of one tool: no card of its
	   own, and its body fills whatever share of the window the page gives it. */
	:global([data-console-chrome='workbench']) .panel-block {
		display: grid;
		margin-top: 0;
		padding: 0;
		border: 0;
		border-radius: 0;
		box-shadow: none;
		background: transparent;
	}

	:global([data-console-chrome='workbench']) .panel-body {
		display: grid;
	}

	:global([data-console-chrome='workbench']) .panel-head {
		position: absolute;
		inline-size: 1px;
		block-size: 1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
	}

	:global([data-console-chrome='workbench']) .panel-body,
	:global([data-console-chrome='workbench']) .panel-block.wide .panel-body,
	:global([data-console-chrome='workbench']) .panel-block.wide .panel-body > :global(*) {
		margin-inline: 0;
		padding-inline: 0;
	}
</style>
