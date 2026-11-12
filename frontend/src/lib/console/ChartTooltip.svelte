<script lang="ts">
	/** Show one viewport-fitted hover reading without replacing keyboard or touch access. */
	import { onMount } from 'svelte';
	import { CHART_HOVER_EVENT, hoverPosition, type ChartHover } from '$lib/charts/readout-hover';

	let { enabled }: { enabled: boolean } = $props();
	let active = $state.raw<Extract<ChartHover, { reading: object }> | null>(null);
	let tooltip = $state<HTMLElement | null>(null);
	let size = $state({ width: 0, height: 0, gap: 0 });
	let viewport = $state({ width: 0, height: 0 });
	const position = $derived(active === null ? { left: 0, top: 0 } : hoverPosition(active, size, viewport, size.gap));
	const clear = () => { active = null; };

	onMount(() => {
		const hover = (event: Event) => {
			if (!(event instanceof CustomEvent) || !enabled) return;
			const detail: ChartHover = event.detail;
			if (!detail.source.closest('[data-surface="operator"]')) return;
			if (detail.reading === null) {
				if (active?.source === detail.source) clear();
			} else {
				viewport = { width: window.innerWidth, height: window.innerHeight };
				active = detail;
			}
		};
		const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') clear(); };
		document.addEventListener(CHART_HOVER_EVENT, hover);
		document.addEventListener('keydown', escape);
		document.addEventListener('focusin', clear);
		window.addEventListener('scroll', clear, true);
		window.addEventListener('resize', clear);
		return () => {
			document.removeEventListener(CHART_HOVER_EVENT, hover);
			document.removeEventListener('keydown', escape);
			document.removeEventListener('focusin', clear);
			window.removeEventListener('scroll', clear, true);
			window.removeEventListener('resize', clear);
		};
	});

	$effect(() => {
		if (!enabled) clear();
	});
	$effect(() => {
		if (tooltip === null) return;
		const node = tooltip;
		node.showPopover();
		const measure = () => {
			const rect = node.getBoundingClientRect();
			size = { width: rect.width, height: rect.height, gap: parseFloat(getComputedStyle(node).paddingInlineStart) };
		};
		const observer = new ResizeObserver(measure);
		observer.observe(node);
		measure();
		return () => observer.disconnect();
	});
</script>

{#if active}
	<aside class="chart-tooltip" role="tooltip" popover="manual" aria-hidden="true" bind:this={tooltip}
		data-chart-tooltip={active.name} style:left="{position.left}px" style:top="{position.top}px">
		<strong>{active.reading.heading}</strong>
		<dl>
			{#each active.reading.entries.filter((entry) => !entry.held) as entry, index (index)}
				<div>
					<dt>{#if entry.swatch}<span class="swatch" style:background={entry.swatch}></span>{/if}{entry.label}</dt>
					{#if entry.value !== ''}<dd>{entry.value}</dd>{/if}
				</div>
			{/each}
		</dl>
		{#if active.footnote !== false}<p>Also shown on the page</p>{/if}
	</aside>
{/if}

<style>
	.chart-tooltip {
		position: fixed;
		inset: auto;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: var(--console-control-gap);
		inline-size: max-content;
		max-inline-size: min(var(--zone-aside), calc(100dvw - 2 * var(--console-panel-gap)));
		max-block-size: calc(100dvh - 2 * var(--console-panel-gap));
		padding: var(--console-control-padding-inline);
		border: 1px solid var(--color-rule-strong);
		border-radius: var(--console-panel-radius);
		background: var(--color-surface-raised);
		box-shadow: var(--shadow-md);
		color: var(--color-text);
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
		pointer-events: none;
		overflow-wrap: anywhere;
	}
	strong { font-weight: var(--console-panel-title-weight); }
	dl { min-block-size: 0; overflow: hidden; margin: 0; display: grid; gap: var(--console-control-padding-block); }
	dl > div { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 0 var(--console-control-gap); }
	dt { color: var(--color-text-secondary); }
	dd { margin: 0; font-family: var(--font-data); font-variant-numeric: tabular-nums; }
	.swatch { display: inline-block; inline-size: var(--console-small-size); block-size: var(--console-small-size); margin-inline-end: var(--console-control-padding-block); vertical-align: middle; }
	p { margin: 0; color: var(--color-text-tertiary); }
</style>
