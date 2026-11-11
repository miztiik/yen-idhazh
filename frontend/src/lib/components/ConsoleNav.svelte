<script lang="ts">
	/** Labelled route and group navigation stays beside the evidence on a wide screen. */
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import type { ConsoleRoute, RouteId } from '$lib/console/band';

	let { routes, active, groups = [], worst = null }: {
		routes: ConsoleRoute[];
		active: RouteId;
		groups?: readonly { id: string; title: string }[];
		worst?: RouteId | null;
	} = $props();
	let expanded = $state(true);
	let wide = $state(false);
	let rail = $state<HTMLElement | null>(null);
	onMount(() => {
		let initialized = false;
		const sync = () => {
			if (rail === null) return;
			const next = getComputedStyle(rail).position === 'sticky';
			if (!initialized || next !== wide) {
				wide = next;
				expanded = next;
				initialized = true;
			}
		};
		sync();
		window.addEventListener('resize', sync);
		return () => window.removeEventListener('resize', sync);
	});
	function closeMenu() { if (!wide) expanded = false; }
</script>

<aside class="console-rail" data-console-rail bind:this={rail}>
	<details class="rail-menu" bind:open={expanded}>
		<summary>Console menu</summary>
		<nav aria-label="Console sections" data-console-nav>
			<ul class="routes">
				{#each routes as route (route.id)}
					<li>
						<a class="route-link" href="{base}{route.href}" title={route.description}
							aria-current={route.id === active ? 'page' : undefined}
							data-console-tab={route.id} data-console-tab-active={route.id === active ? 'true' : null}
							onclick={closeMenu}>
							<span>{route.label}</span>
							{#if route.worst || route.id === worst}
								<small class="route-state">
									{#if route.id === worst}<span data-console-tab-worst-mark>Worst{route.worst ? ':' : ''}</span>{/if}
									{#if route.worst}<span data-console-tab-worst={route.id}>{route.worst}</span>{/if}
								</small>
							{/if}
						</a>
						{#if route.id === active && groups.length > 0}
							<nav class="group-links" aria-label="On this page" data-console-contents>
								<ul>
									{#each groups as group (group.id)}
										<li><a href="#{group.id}" data-console-contents-link={group.id} onclick={closeMenu}>{group.title}</a></li>
									{/each}
								</ul>
							</nav>
						{/if}
					</li>
				{/each}
			</ul>
		</nav>
	</details>
</aside>

<style>
	.console-rail { min-inline-size: 0; }
	.rail-menu {
		padding: var(--console-control-padding-block);
		border: 1px solid var(--color-rule);
		border-radius: var(--console-control-radius);
		background: var(--color-surface);
	}
	summary {
		min-block-size: var(--console-control-min-height);
		padding: var(--console-control-padding-block) var(--console-control-padding-inline);
		align-content: center;
		color: var(--color-text);
		font-size: var(--console-control-size);
		line-height: var(--console-control-leading);
		font-weight: var(--console-control-weight);
		cursor: pointer;
	}
	ul { list-style: none; margin: 0; padding: 0; }
	.routes { display: grid; gap: var(--console-rail-gap); }
	.route-link {
		display: flex;
		flex-direction: column;
		justify-content: center;
		min-block-size: var(--console-control-min-height);
		padding: var(--console-control-padding-block) var(--console-control-padding-inline);
		border: 1px solid transparent;
		border-radius: var(--console-control-radius);
		color: var(--color-text-secondary);
		font-size: var(--console-control-size);
		line-height: var(--console-control-leading);
		font-weight: var(--console-control-weight);
		letter-spacing: var(--console-control-tracking);
		text-decoration: none;
		overflow-wrap: anywhere;
	}
	.route-link:hover { background: var(--color-surface-sunken); color: var(--color-accent-strong); }
	.route-link[aria-current='page'] { background: var(--console-selected); border-color: var(--color-accent); color: var(--color-text); }
	.route-state {
		display: flex;
		flex-wrap: wrap;
		gap: var(--console-control-padding-block);
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
		font-weight: var(--console-small-weight);
		color: var(--color-text-secondary);
	}
	.group-links { margin-block: var(--console-rail-gap); padding-inline: var(--console-control-padding-inline); }
	.group-links ul { display: grid; gap: var(--console-control-padding-block); }
	.group-links a {
		display: block;
		padding-block: var(--console-control-padding-block);
		color: var(--color-text-secondary);
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
	}
	.group-links a:hover { color: var(--color-accent-strong); text-decoration: underline; }
	@media (min-width: 1024px) {
		.console-rail {
			position: sticky;
			inset-block-start: var(--console-rail-padding);
			max-block-size: calc(100dvh - 2 * var(--console-rail-padding));
			overflow-y: auto;
			overscroll-behavior-y: contain;
			scrollbar-width: thin;
		}
		.rail-menu { padding: var(--console-rail-padding); background: var(--color-surface-sunken); }
		summary { display: none; }
	}
</style>
