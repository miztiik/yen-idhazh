<script lang="ts">
	/** A chart that is finished before any script runs, and interactive after.
	 *
	 * The server hands `svg` - real marks, real geometry, colours already
	 * named as custom properties so both themes work with no JavaScript at
	 * all. That is what a reader with a blocked script, a slow network or an
	 * old browser keeps.
	 *
	 * On mount the engine replaces it with a live chart so a pointer, a tap or
	 * an arrow key names the value. If that never happens, nothing is lost that
	 * the axis did not already say - which is the whole reason the readout is
	 * allowed to exist (design-system.md).
	 */
	import type { EChartsOption } from 'echarts';
	import { onMount } from 'svelte';
	import type { LiveChart } from './engine';

	let {
		svg,
		option,
		width,
		height,
		label
	}: {
		/** Prerendered by `$lib/server/chart-render`. */
		svg: string;
		option: EChartsOption;
		width: number;
		height: number;
		/** What the chart is, for anyone who cannot see it. */
		label: string;
	} = $props();

	let host: HTMLDivElement;
	let live: LiveChart | null = null;
	// The prerendered width is only a starting point; the observer owns it from
	// mount onward. Not reactive - nothing in the markup reads it.
	// svelte-ignore state_referenced_locally
	let measured = width;

	onMount(() => {
		let cancelled = false;
		let observer: ResizeObserver | null = null;

		// Deferred so the engine is never on the critical path: the page is
		// already complete and this only adds the readout.
		void (async () => {
			const { hydrate } = await import('./engine');
			if (cancelled) return;
			live = await hydrate(host, option, { width: measured, height });
			observer = new ResizeObserver((entries) => {
				const next = Math.round(entries[0].contentRect.width);
				if (next > 0 && next !== measured) {
					measured = next;
					live?.resize({ width: next, height });
				}
			});
			observer.observe(host);
		})();

		return () => {
			cancelled = true;
			observer?.disconnect();
			live?.destroy();
		};
	});
</script>

<figure class="chart" aria-label={label}>
	<div bind:this={host} class="chart-host" style="height: {height}px">
		<!-- eslint-disable-next-line svelte/no-at-html-tags -->
		{@html svg}
	</div>
</figure>

<style>
	.chart {
		margin: 0;
	}

	.chart-host {
		width: 100%;
	}

	/* The prerendered SVG is authored at a fixed width and then asked to fill
	   the panel it is in. Without this it would keep its authored width and sit
	   in a corner - which is how the surface ended up with charts drawn at
	   164px inside a 624px column. */
	.chart-host :global(svg) {
		width: 100%;
		height: auto;
		display: block;
	}
</style>
