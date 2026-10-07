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
	 * Where the server hands no picture - `svg` is empty - the box holds one
	 * sentence until the first mark lands: the chart is loading, it did not load,
	 * or, with no script, it needs JavaScript. Then it says where the chart's
	 * numbers are in words. The engine says which of the first two it is, through
	 * `hydrate`, at the moment it writes the same word on the host, so the
	 * component keeps no guess of its own about whether anything has drawn.
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
	import { openWithSpan } from '$lib/console/span-words';
	import { bandShares, type PlotGrid } from './frame';
	import { pointerReadout, readoutMarks, type Readout } from './readout';
	import ChartReadout from '../components/ChartReadout.svelte';
	import type { ChartState, LiveChart } from './engine';

	/** What an empty box says. Each is one fact about one download, true of
	 * every chart at once, so every chart says it the same way. */
	const LOADING_WORDS = 'This chart is loading.';
	const FAILED_WORDS = 'This chart did not load. Check your connection, then reload the page.';
	const NO_SCRIPT_WORDS = 'This chart needs JavaScript.';
	/** Where a chart with a readout strip keeps its numbers while its box is
	 * empty. Every such chart that only a browser draws has a column per day, and
	 * the strip rests on the newest one. A window of one day has no newest, so
	 * there the line names the window, as Reader chose on 2026-10-07. */
	const STRIP_NUMBERS = "The newest day's numbers are below.";

	let {
		svg,
		option,
		width,
		height,
		label,
		readout = null,
		readoutName = '',
		noReadout = '',
		readoutMaxShare = 1,
		restingNote = ', the newest column',
		hint = 'Point at a column to read it. Left and Right step through them, Escape returns to the newest.',
		grid = { left: 48, right: 12 },
		numbersNote,
		windowDays = null,
		fetched = false
	}: {
		/** Prerendered by `$lib/server/chart-render`, or empty where the chart is
		 * drawn from rows only a browser has. An empty one holds a sentence until
		 * the engine's first mark lands. */
		svg: string;
		option: EChartsOption;
		width: number;
		height: number;
		/** What the chart is, for anyone who cannot see it. */
		label: string;
		/** The strip `readoutOf` built, one column per category in drawing order.
		 * Null turns the strip off, which is right for a chart with one series or
		 * with no columns. */
		readout?: Readout | null;
		readoutName?: string;
		/** Why this chart has no strip, in words, where `readout` has no column.
		 * Left blank only where an enclosing element already says it. */
		noReadout?: string;
		/** `chart.readout_max_share`. */
		readoutMaxShare?: number;
		restingNote?: string;
		hint?: string;
		/** The engine's own plot insets, in pixels. They decide where a column
		 * centre falls, and they are not the same for every option this wraps. */
		grid?: PlotGrid;
		/** Where this chart's numbers can be read while its box is empty, said
		 * after the box's own sentence. A chart with a readout strip leaves it
		 * out: the strip is the answer, and the component says so itself. A chart
		 * with no strip names the text that carries its numbers, so a reader
		 * facing an empty box still has somewhere to go. */
		numbersNote?: string;
		/** The days of the window a windowed chart follows, so the empty box can
		 * name a window of one day. Null for a chart that follows none. */
		windowDays?: number | null;
		/** True where the rows behind this chart arrive by fetch rather than in
		 * the document. It changes what the chart owes a reader with no script:
		 * a chart over inlined data owes its resting column in the prerendered
		 * markup, and one over fetched rows cannot have it there and says so. */
		fetched?: boolean;
	} = $props();

	// Bound in one of two branches, so it is state rather than a plain binding.
	let host = $state<HTMLDivElement | null>(null);
	let live: LiveChart | null = null;
	/** What the engine has said about this chart, in the word it writes on the
	 * host as `data-chart`. It is `failed` here as well when the engine module
	 * itself never downloads, which is a failure no host hears about. */
	let chartState = $state<ChartState>('waiting');
	/** True once a mark is on screen - the server's SVG, or the engine's first
	 * draw. Until then the box holds a sentence saying which nothing it is. */
	const drawn = $derived(svg !== '' || chartState === 'live');
	/** How many columns the strip reads, and zero where the chart has none. */
	const count = $derived(readout?.columns.length ?? 0);
	const note = $derived(
		numbersNote ??
			(count === 0
				? ''
				: windowDays === 1
					? `${openWithSpan(windowDays)}'s numbers are below.`
					: STRIP_NUMBERS)
	);
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

	const shares = $derived(bandShares(count, measured, grid));
	const marks = $derived(readoutMarks(Array.from({ length: count }, (_, index) => shares[index] ?? 0)));
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
			// dropped connection. Where the server drew this chart, a failure costs
			// the tooltip and nothing else; where it did not, the box says the chart
			// did not load. It is said once, in the console, rather than thrown: an
			// unhandled rejection per chart is noise a reader cannot act on and a
			// real fault cannot be seen through.
			const engine = await import('./engine').catch((reason: unknown) => {
				console.warn(`chart "${label}": the engine did not load, so it stays as drawn`, reason);
				return null;
			});
			// The import is a network fetch, so the component can be gone by now.
			// `hydrate` hands back a handle in the same turn, so past this check
			// there is no window where an instance exists and nothing holds it.
			if (cancelled) return;
			if (engine === null) {
				chartState = 'failed';
				return;
			}
			handed = option;
			live = engine.hydrate(node, option, { width: measured, height }, (state) => {
				chartState = state;
			});
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

<!-- What stands where the plot will be until a mark lands. With no script the
     promise that the chart is coming is false for the whole visit, so the
     `<noscript>` rule hides it and says what is true instead. It reaches the
     promise by attribute, for the reason `FilterBar` records: a `<noscript>`
     rule cannot outrank a scoped class, so that element carries no class and
     no display of its own. -->
{#snippet emptyBox()}
	<p
		class="chart-pending text-[0.8125rem] text-text-tertiary"
		data-chart-pending={chartState === 'failed' ? 'failed' : 'waiting'}
	>
		<span>
			{#if chartState === 'failed'}
				{FAILED_WORDS}
			{:else}
				<span data-chart-scripted>{LOADING_WORDS}</span>
				<noscript>
					<style>
						[data-chart-scripted] {
							display: none;
						}
					</style>
					{NO_SCRIPT_WORDS}
				</noscript>
			{/if}
			{note}
		</span>
	</p>
{/snippet}

<figure
	class="chart"
	aria-label={label}
	data-readout-columns={count > 0 ? count : undefined}
	data-readout-none={count > 0 || noReadout === '' ? undefined : noReadout}
	data-readout-fetched={fetched ? 'yes' : undefined}
	data-chart-drawn={drawn ? 'yes' : 'no'}
>
	{#if count > 0}
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
				{#if !drawn}
					{@render emptyBox()}
				{/if}
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
			at={selected}
			name={readoutName}
			maxShare={readoutMaxShare}
			{restingNote}
			{hint}
		/>
	{:else}
		<div bind:this={host} class="chart-host" style="height: {height}px">
			<!-- eslint-disable-next-line svelte/no-at-html-tags -->
			{@html svg}
			{#if !drawn}
				{@render emptyBox()}
			{/if}
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

	/* What stands where the plot will be until something draws there. Centred in
	   the reserved height so the panel does not change size when the engine
	   arrives, and quiet enough that a chart which draws immediately never reads
	   as having flashed a warning. Its colour and size are classes rather than
	   custom properties, so it takes the same two the readout strip takes. Its
	   words sit in one span: centred as flex items, each sentence would be laid
	   out as a column of its own. */
	.chart-pending {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
		margin: 0;
		padding: 0 1rem;
		text-align: center;
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
