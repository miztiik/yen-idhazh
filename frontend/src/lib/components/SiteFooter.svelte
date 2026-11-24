<script lang="ts">
	/** Which shared destinations and local display control finish a page? */
	import Icon from '$lib/icons/Icon.svelte';
	import { base } from '$app/paths';
	import ThemeToggle from './ThemeToggle.svelte';

	let {
		repoUrl,
		operator,
		home,
		previousEdition = null
	}: { repoUrl: string; operator: boolean; home: boolean; previousEdition?: string | null } = $props();
</script>

{#snippet sourceCode()}
	<a href={repoUrl} target="_blank" rel="noopener noreferrer">Source code</a>
{/snippet}

<footer class="site-footer" class:operator data-site-footer>
	<nav class="footer-nav" aria-label="Site">
		{#if operator}
			<div class="footer-links">
				<a href="{base}/"><Icon id="previous-edition" size={14} /> <span>Back to digest</span></a>
				{@render sourceCode()}
			</div>
		{:else}
			<div class="footer-group">
				<h2>More editions</h2>
				<div class="footer-links edition-links">
					{#if previousEdition !== null}
						<a href="{base}/{previousEdition}/">
							<Icon id="previous-edition" size={14} /> <span>Previous edition</span>
						</a>
					{/if}
					<a href="{base}/archive/">
						<Icon id="archive" size={14} /> <span>{home ? 'Archive & search' : 'Archive'}</span>
					</a>
				</div>
			</div>
			<div class="footer-group">
				<h2>Project</h2>
				<div class="footer-links">
					<a href="{base}/console/">
						<Icon id="console" size={14} /> <span>Console</span>
					</a>
					{@render sourceCode()}
				</div>
			</div>
		{/if}
	</nav>
	{#if operator}<div class="footer-theme"><ThemeToggle /></div>{/if}
</footer>

<style>
	.site-footer {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2) var(--space-5);
		margin-block-start: var(--space-6);
		padding-block: var(--space-4);
		padding-inline: var(--story-text-inset) var(--story-card-padding);
		border-block-start: 1px solid var(--color-rule-strong);
		background: var(--color-surface-sunken);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
	}
	.site-footer.operator {
		flex: none;
		margin-block-start: var(--console-group-gap);
		padding-block: var(--console-panel-gap);
		padding-inline: var(--space-4);
	}
	.footer-theme { margin-inline-start: auto; }
	.footer-nav {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
		min-inline-size: 0;
	}
	.footer-group h2 {
		font-family: var(--font-display);
		font-size: var(--text-base);
		line-height: var(--leading-base);
		font-weight: 600;
	}
	.footer-links {
		display: flex;
		flex-wrap: wrap;
		column-gap: var(--space-4);
	}
	.footer-nav a {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		min-block-size: var(--space-7);
		color: var(--color-text-secondary);
	}
	.edition-links a { color: var(--color-accent); }
	.footer-nav a:hover {
		color: var(--color-accent-strong);
		text-decoration: underline;
	}
	/* Matches frame.breakpoints_px[0]; media queries cannot read CSS tokens. */
	@media (min-width: 640px) {
		.footer-nav {
			flex-direction: row;
			flex-wrap: wrap;
			gap: var(--space-3) var(--space-8);
		}
	}
</style>
