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
	 *
	 * Where the chart draws more than one series, `columns` turns on the same
	 * fixed strip a hand-written chart prints: every series at one column, below
	 * the plot, capped at a share of it, with a guide line down the column and
	 * the arrow keys stepping through them. The engine's own tooltip still fires,
	 * but it is never the only place a value appears - a tooltip needs a hover,
	 * and a hover is not a thing a thumb can do.
	 *
	 * The strip is also the key, so no chart that carries one draws a legend as
	 * well. A chart with no shared column says why in `noReadout` instead: the
	 * wrapper declares one of the two, and `console-readout.spec.ts` fails on a
	 * chart that declares neither.
	 */
	import type { EChartsOption } from 'echarts';
	import { onMount } from 'svelte';
	import {
		bandShares,
		pointerReadout,
		readoutMarks,
		type DayReadout,
		type PlotGrid
	} from './frame';
	import ChartReadout from '../components/ChartReadout.svelte';
	import type { LiveChart } from './engine';

	let {
		svg,
		option,
		width,
		height,
		label,
		columns = [],
		readoutName = '',
		noReadout = '',
		readoutMaxShare = 0.33,
		restingNote = ', the newest column',
		hint = 'Point at a column to read it. Left and Right step through them, Escape returns to the newest.',
		grid = { left: 48, right: 12 }
	}: {
		/** Prerendered by `$lib/server/chart-render`. */
		svg: string;
		option: EChartsOption;
		width: number;
		height: number;
		/** What the chart is, for anyone who cannot see it. */
		label: string;
		/** One entry per category column, in drawing order. Empty turns the strip
		 * off, which is right for a chart with one series or with no columns. */
		columns?: DayReadout[];
		readoutName?: string;
		/** Why this chart has no strip, in words, where `columns` is empty.
		 * Left blank only where an enclosing element already says it - a card's
		 * trend line is declared once by the card, not once per card. */
		noReadout?: string;
		/** `chart.readout_max_share`. */
		readoutMaxShare?: number;
		restingNote?: string;
		hint?: string;
		/** The engine's own plot insets, in pixels. They decide where a column
		 * centre falls, and they are not the same for every option this wraps. */
		grid?: PlotGrid;
	} = $props();

	// Bound in one of two branches, so it is state rather than a plain binding.
	let host = $state<HTMLDivElement | null>(null);
	let live: LiveChart | null = null;
	/** The option the live chart is holding, so an unchanged one is not handed
	 * over again the first time the effect runs. */
	let handed: EChartsOption | null = null;
	// The prerendered width is only a starting point; the observer owns it from
	// mount onward. Reactive because the strip's column centres come off it: the
	// engine keeps its grid insets in pixels, so the share of the element a
	// column sits at moves with every resize.
	// svelte-ignore state_referenced_locally
	let measured = $state(width);

	/** The column a pointer or an arrow key has picked, or null for none. */
	let selected = $state<number | null>(null);

	const shares = $derived(bandShares(columns.length, measured, grid));
	const marks = $derived(
		readoutMarks(columns.map((column, index) => ({ ...column, x: shares[index] ?? 0 })))
	);
	/** The newest column, which is the one a reader came for. It is what the strip
	 * prints before anything is pointed at, so the strip is never blank and never
	 * changes the room the panel takes as it fills. */
	const at = $derived(selected ?? (columns.length === 0 ? null : columns.length - 1));
	const readout = $derived(at === null ? null : (columns[at] ?? null));
	const guide = $derived(selected === null ? null : (shares[selected] ?? null));

	onMount(() => {
		let cancelled = false;
		const node = host;
		if (node === null) return;

		// The element's own width, from mount onward and whether or not the engine
		// ever runs. The strip's column centres come off it, so it cannot wait for
		// a chart that may be nine screens down.
		const observer = new ResizeObserver((entries) => {
			const next = Math.round(entries[0].contentRect.width);
			if (next > 0 && next !== measured) {
				measured = next;
				live?.resize({ width: next, height });
			}
		});
		observer.observe(node);

		// Deferred so the engine is never on the critical path: the page is
		// already complete and this only adds the readout.
		void (async () => {
			// The engine is a network fetch and it can fail - an offline reader, a
			// dropped connection. The server already drew this chart, so a failure
			// costs the tooltip and nothing else. It is said once, in the console,
			// rather than thrown: an unhandled rejection per chart is noise a
			// reader cannot act on and a real fault cannot be seen through.
			const engine = await import('./engine').catch((reason: unknown) => {
				console.warn(`chart "${label}": the engine did not load, so it stays as drawn`, reason);
				return null;
			});
			// The import is a network fetch, so the component can be gone by now.
			// `hydrate` hands back a handle in the same turn, so past this check
			// there is no window where an instance exists and nothing holds it.
			if (engine === null || cancelled) return;
			handed = option;
			live = engine.hydrate(node, option, { width: measured, height });
		})();

		return () => {
			cancelled = true;
			observer.disconnect();
			live?.destroy();
			live = null;
		};
	});

	// A live chart keeps the option it was given until it is told otherwise. A
	// control that redraws a chart - the failure mix's shape switch is one -
	// changes this prop and nothing else, so without this the page and the chart
	// disagree and the chart is the one that is wrong.
	$effect(() => {
		const next = option;
		if (live === null || next === handed) return;
		handed = next;
		live.update(next);
	});
</script>

<figure
	class="chart"
	aria-label={label}
	data-readout-columns={columns.length > 0 ? columns.length : undefined}
	data-readout-none={columns.length > 0 || noReadout === '' ? undefined : noReadout}
>
	{#if columns.length > 0}
		<!-- The action goes on the wrapper, never on the SVG: the engine swaps that
		     SVG out on hydration, so an action bound to it would come away holding
		     the markup it was attached to. The wrapper takes the focus for the same
		     reason - and one tab stop for a chart, never one per column. -->
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<div
			class="chart-frame"
			tabindex="0"
			role="img"
			aria-label={label}
			data-chart-readout={readoutName}
			use:pointerReadout={{ marks, width: 1, onSelect: (index) => (selected = index) }}
		>
			<div bind:this={host} class="chart-host" style="height: {height}px">
				<!-- eslint-disable-next-line svelte/no-at-html-tags -->
				{@html svg}
			</div>
			{#if guide !== null}
				<span
					class="chart-guide"
					style="left: {(guide * 100).toFixed(3)}%"
					data-chart-guide={readoutName}
					aria-hidden="true"
				></span>
			{/if}
		</div>
		<ChartReadout
			{readout}
			name={readoutName}
			maxShare={readoutMaxShare}
			resting={selected === null}
			{restingNote}
			{hint}
		/>
	{:else}
		<div bind:this={host} class="chart-host" style="height: {height}px">
			<!-- eslint-disable-next-line svelte/no-at-html-tags -->
			{@html svg}
		</div>
	{/if}
</figure>

<style>
	.chart {
		margin: 0;
	}

	.chart-frame {
		position: relative;
	}

	.chart-frame:focus-visible {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}

	/* Down the whole plot, so several series are read at one column rather than
	   one at a time. Drawn over the chart because it marks a position rather
	   than carrying a value - the values are in the strip below, where they
	   cover nothing. */
	.chart-guide {
		position: absolute;
		inset-block: 0;
		inline-size: 1px;
		background: var(--color-text-tertiary);
		opacity: 0.5;
		pointer-events: none;
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
