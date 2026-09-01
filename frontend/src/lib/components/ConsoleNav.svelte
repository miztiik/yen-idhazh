<script lang="ts">
	/** Where an operator can go, and what is worst on each route before he goes.
	 *
	 * Directly under the page title and above the band since 2026-08-31. Chrome
	 * above content is the one ordering a reader never has to learn, and the
	 * band's worst fact links into this strip - which a phone reader could not
	 * find 337px below it.
	 *
	 * Real anchors, one per prerendered route. Not tabs holding hidden panels:
	 * a tab strip that switches with script is a page that says nothing with
	 * script off, and every panel it hides still ships in the document.
	 *
	 * Every label carries its own worst state, computed at build time. Without
	 * it a route is where a metric goes to die - nobody opens a page to find out
	 * whether it was worth opening.
	 */
	import { base } from '$app/paths';
	import type { ConsoleRoute, RouteId } from '$lib/server/console-shell';

	let { routes, active }: { routes: ConsoleRoute[]; active: RouteId } = $props();
</script>

<nav class="console-nav" aria-label="Console sections" data-console-nav>
	<ul class="tabs">
		{#each routes as route (route.id)}
			<li class="tab-slot">
				<a
					class="tab"
					href="{base}{route.href}"
					title={route.description}
					aria-current={route.id === active ? 'page' : undefined}
					data-console-tab={route.id}
					data-console-tab-active={route.id === active ? 'true' : null}
				>
					<span class="tab-head">
						<span class="tab-label">{route.label}</span>
						{#if route.worst}
							<!-- No health colour, ever. Green, amber and red on a label
							     would say a route is failing, and a route is a noun. -->
							<span class="tab-worst" data-console-tab-worst={route.id}>{route.worst}</span>
						{/if}
					</span>
					<span class="tab-line">{route.description}</span>
				</a>
			</li>
		{/each}
	</ul>
</nav>

<style>
	.console-nav {
		margin-top: var(--space-4);
		border-block-end: 1px solid var(--color-rule);
	}

	.tabs {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.tab-slot {
		flex: 1 1 14rem;
		min-inline-size: 0;
	}

	/* The whole block is the target, not the word at the top of it. The touch
	   target is the 2.75rem floor, so the padding pays for looks and not for
	   reach - and three stacked tabs above the band on a phone is where every
	   pixel of it is charged three times. */
	.tab {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-block-size: 2.75rem;
		padding: var(--space-2) var(--space-3);
		border-radius: var(--radius-md) var(--radius-md) 0 0;
		/* Reserved on every tab, so the active one does not push the strip down
		   by three pixels when the operator moves between routes. */
		border-block-end: 3px solid transparent;
		color: var(--color-text-secondary);
		text-decoration: none;
	}

	.tab:hover {
		background: var(--color-surface);
	}

	/* The one thing that differs between routes: a 3px rule from the categorical
	   ramp. Categorical because it names a place and passes no verdict. */
	.tab[aria-current='page'] {
		border-block-end-color: var(--chart-1);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.tab-head {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-2);
	}

	.tab-label {
		font-size: var(--text-base);
		line-height: var(--leading-base);
		font-weight: 600;
	}

	.tab-worst {
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-secondary);
	}

	.tab-line {
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
	}
</style>
