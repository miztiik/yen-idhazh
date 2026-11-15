<script lang="ts">
	/** Return to the real page top without covering readings or footer controls. */
	import { onMount } from 'svelte';
	import Icon from '$lib/icons/Icon.svelte';
	import { prefersReducedMotion } from '$lib/charts/d3/motion';

	let {
		heading = null,
		reading = false
	}: { heading?: HTMLHeadingElement | null; reading?: boolean } = $props();
	let brandVisible = $state(true);
	let footerVisible = $state(false);
	let footerHeight = $state(0);
	const shown = $derived(!brandVisible);
	function goTop() {
		const target = heading ?? document.querySelector<HTMLElement>('[data-surface="reading"] h1')
			?? document.querySelector<HTMLElement>('[data-site-header] a');
		if (target !== null) {
			target.setAttribute('tabindex', '-1');
			target.focus({ preventScroll: true });
		}
		const motionOff = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--dur-base')) === 0;
		window.scrollTo({ top: 0, behavior: motionOff || prefersReducedMotion() ? 'instant' : 'smooth' });
	}
	onMount(() => {
		const brand = document.querySelector('[data-site-header]');
		const footer = document.querySelector('[data-site-footer]');
		const observer = new IntersectionObserver((entries) => {
			for (const entry of entries) {
				if (entry.target === brand) brandVisible = entry.isIntersecting;
				if (entry.target === footer) footerVisible = entry.isIntersecting;
			}
		});
		if (brand !== null) observer.observe(brand);
		const size = new ResizeObserver(() => { footerHeight = footer?.getBoundingClientRect().height ?? 0; });
		if (footer !== null) {
			observer.observe(footer);
			size.observe(footer);
		}
		return () => { observer.disconnect(); size.disconnect(); };
	});
</script>

<span class="top-slot" class:reader={reading}>
	{#if shown}
		<button type="button" class="back-to-top" aria-label="Back to top" title="Back to top" onclick={goTop}
			data-console-top={reading ? undefined : ''} data-reader-top={reading ? '' : undefined}
			style:--console-footer-room="{footerVisible ? footerHeight : 0}px">
			{#if reading}<Icon id="go-top" size={24} />{:else}<Icon id="sort-ascending" /><span>Top</span>{/if}
		</button>
	{/if}
</span>

<style>
	.top-slot { display: block; inline-size: var(--console-control-min-height); }
	.back-to-top {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: var(--console-control-gap);
		min-inline-size: var(--console-control-min-height);
		min-block-size: var(--console-control-min-height);
		padding-inline: var(--console-control-gap);
		border: 1px solid var(--color-rule-strong);
		border-radius: var(--console-control-radius);
		background: var(--color-surface-raised);
		box-shadow: var(--shadow-md);
		color: var(--color-accent);
		font-size: var(--console-control-size);
		line-height: var(--console-control-leading);
	}
	.back-to-top span { display: none; }
	@media (min-width: 1024px) {
		.top-slot { inline-size: 0; }
		.back-to-top {
			position: fixed;
			inset-block-end: calc(var(--console-panel-gap) + var(--console-footer-room) + env(safe-area-inset-bottom));
			inset-inline-start: calc(var(--gutter) + env(safe-area-inset-left));
			padding-inline: var(--console-control-padding-inline);
		}
		.back-to-top span { display: inline; }
	}
	.reader { inline-size: 0; }
	.reader .back-to-top {
		position: fixed;
		z-index: 1;
		inset-block-end: calc(var(--space-5) + var(--console-footer-room) + env(safe-area-inset-bottom));
		inset-inline-start: auto;
		inset-inline-end: calc(var(--gutter) + env(safe-area-inset-right));
		inline-size: var(--space-7);
		block-size: var(--space-7);
		min-inline-size: var(--space-7);
		min-block-size: var(--space-7);
		padding: 0;
		border-radius: var(--radius-full);
		cursor: pointer;
		transition: background var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard);
	}
	.reader .back-to-top:hover {
		background: var(--tint-accent);
		border-color: var(--color-accent);
	}
</style>
