<script lang="ts">
	/** Which shared destinations and local display control finish a page? */
	import Icon from '$lib/icons/Icon.svelte';
	import { base } from '$app/paths';
	import ThemeToggle from './ThemeToggle.svelte';

	let {
		repoUrl,
		showTheme = false,
		home = false,
		previousEdition = null
	}: { repoUrl: string; showTheme?: boolean; home?: boolean; previousEdition?: string | null } = $props();
</script>

<footer class="site-footer mt-16 border-t border-rule pt-8 pb-12 text-sm text-text-tertiary" class:home data-site-footer>
	<div class="footer-row">
		<nav class="footer-nav" aria-label="Site">
			<div class="edition-links">
				{#if previousEdition !== null}
					<a href="{base}/{previousEdition}/">
						<Icon id="previous-edition" size={14} /> <span>Previous edition</span>
					</a>
				{/if}
				<a href="{base}/archive/">
					<Icon id="archive" size={14} /> <span>{home ? 'Archive & search' : 'Archive'}</span>
				</a>
			</div>
			<div class="site-links">
				<a href="{base}/console/">
					<Icon id="console" size={14} /> <span>Console</span>
				</a>
				<a href={repoUrl} target="_blank" rel="noopener noreferrer">Source code</a>
			</div>
		</nav>
		{#if showTheme}<div class="footer-theme"><ThemeToggle /></div>{/if}
	</div>
</footer>

<style>
	.footer-row { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-4); }
	.footer-theme { margin-inline-start: auto; }
	.footer-nav { display: flex; flex-wrap: wrap; gap: var(--space-4); }
	.edition-links, .site-links { display: contents; }
	.footer-nav a {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		color: var(--color-accent);
	}
	.footer-nav a:hover { text-decoration: underline; }
	.site-footer.home {
		margin-block-start: var(--space-5);
		padding-block: var(--space-2) var(--space-4);
	}
	.home .footer-nav { display: block; }
	.home :is(.edition-links, .site-links) { display: flex; flex-wrap: wrap; column-gap: var(--space-4); }
	.home .footer-nav a { min-block-size: calc(var(--space-6) + var(--space-3)); }
	.home .site-links a:not(:hover) { color: var(--color-text-secondary); }
	:global(.frame:has([data-surface='operator'])) .site-footer {
		flex: none;
		margin-block-start: var(--console-group-gap);
		padding-block: var(--console-panel-gap) var(--console-group-gap);
	}
</style>
