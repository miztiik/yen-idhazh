<script lang="ts">
	/** An item with no visual is simply shorter.
	 *
	 * No placeholder and no reserved slot: a grey rectangle makes "we correctly
	 * decided this needed no picture" look identical to "the image failed", which
	 * is the wrong signal on a page whose product is trust. Two items in three
	 * carry no visual, so this is the default shape, not a fallback.
	 *
	 * **The reader's browser draws the chart and the pipeline never draws one**
	 * (owner ruling, 2026-09-13,
	 * `docs/architecture/publishing/visuals.md`). A story arrives carrying a
	 * pointer at its marks; this component asks for that file when the story
	 * comes near, checks the shape, and draws it. Nothing is rendered at build
	 * time and no drawing is committed.
	 *
	 * **What the reader gives up, stated where it lands.** A reader with
	 * JavaScript off gets no chart AND no sentence, where a committed SVG used to
	 * be markup inside the document itself. The figure below only exists once the
	 * marks have arrived, so there is no path on which a script-less page carries
	 * either one - which is a real loss and a different row's to answer. And every
	 * day published before 2026-09-13 loses its chart for every reader, because no
	 * marks file was ever written for one and back-filling would mean re-fetching
	 * source pages that have since moved.
	 *
	 * **No fact is left to a pointer.** The figure is one tab stop, and its
	 * accessible name is written from the same `Drawing` the marks are drawn from
	 * - so what a keyboard reaches and what an eye reaches are one set by
	 * construction rather than by two derivations agreeing. One tab stop for a
	 * chart and never one per bar: a day runs to hundreds of stories, and a bar
	 * apiece would make the stream something a keyboard cannot get past.
	 *
	 * **The drawing is written by Svelte from geometry `$lib/visual/bar`
	 * computed**, so the marks are ordinary elements in this component's own
	 * subtree. They take the page's tokens through plain scoped CSS rather than
	 * through `:global` overrides of a renderer's class vocabulary, and every
	 * string a model cut out of a stranger's page lands as a text node rather
	 * than as markup (Guardrail #11). The figure takes the chart's own shape: a
	 * `viewBox` is an aspect ratio, so the browser reserves the right box before
	 * a mark is placed and the story cannot shift as it is read.
	 *
	 * **Marks that do not arrive cost the story its picture and nothing else.**
	 * No broken-image glyph, no grey box, no skeleton: the story is shorter,
	 * which is the shape two stories in three already have.
	 */
	import { base } from '$app/paths';
	import { publishedVisualData, refusedVisualData } from '$lib/payload/drawing';
	import type { SeededVisual, VisualData } from '$lib/payload/types';
	import { whenNear } from '$lib/reveal';
	import { drawBars, statedBars, type Drawing } from '$lib/visual/bar';

	let { visual }: { visual: SeededVisual | null } = $props();

	/** The file this story's marks are in, or null when it has none to ask for.
	 *
	 * A day published before the marks existed carries no `data_path`, and so
	 * does a visual whose file did not land. Both read the same way and both are
	 * designed states: the story has no chart.
	 */
	const wanted = $derived(
		visual?.state === 'rendered' && visual.data_path ? visual.data_path : null
	);

	/** What the fetch brought back, or null while it has not run or did not work. */
	let arrived = $state<VisualData | null>(null);
	const drawing = $derived<Drawing | null>(arrived ? drawBars(arrived) : null);
	/** Every figure the bars are drawn at, in one sentence, for a reader who is
	 * not looking at them. It is the whole of what the tab stop below announces. */
	const stated = $derived(drawing ? statedBars(drawing) : '');

	/** The marks that file holds, or null when there is nothing safe to draw.
	 *
	 * **It refuses rather than guesses, and refusing is free.** A degrade path
	 * that draws something approximate is how a wrong chart reaches a reader, and
	 * the product is trust. The path is matched before it is joined onto `base`,
	 * for the same reason `dayUrl` matches a date: it is about to become an
	 * address.
	 *
	 * **`__ASSET_BASE_URL__` moves where the file is asked for and nothing
	 * else.** It is `visuals.asset_base_url`, injected at build time, and it
	 * ships empty - so the join is `base`, this site, exactly as it was. Naming a
	 * host there takes the marks a reader scrolls to off the 1 GB published
	 * ceiling without touching anything else: the bytes still arrive as data and
	 * are still checked here. The origin comes from our config and can never come
	 * from a payload.
	 */
	async function read(file: string, signal: AbortSignal): Promise<VisualData | null> {
		if (!publishedVisualData(file)) {
			console.warn(`[digest] ${file}: not a published visual path, so it is not drawn`);
			return null;
		}
		try {
			const response = await fetch(`${__ASSET_BASE_URL__ || base}/${file}`, { signal });
			if (!response.ok) {
				console.warn(`[digest] ${file}: not available (${response.status}), so it is not drawn`);
				return null;
			}
			const data: unknown = await response.json();
			const refused = refusedVisualData(data);
			if (refused !== null) {
				console.warn(`[digest] ${file}: ${refused}, so it is not drawn`);
				return null;
			}
			return data as VisualData;
		} catch (error) {
			// A story the reader scrolled away from cancelled its own request. That
			// is the page working, so it says nothing.
			if (signal.aborted) return null;
			console.warn(`[digest] ${file} could not be read, so it is not drawn`, error);
			return null;
		}
	}

	/** Ask for the marks once the story is nearly on screen.
	 *
	 * The `img` this path replaced carried `loading="lazy"`, so a browser asked
	 * for a drawing only when the reader was near it. A plain fetch on mount
	 * throws that away, and the case where it hurts is not the ordinary one: a
	 * reader following `/<date>/#<story>` pages the stream down to that story, so
	 * the whole prefix mounts at once.
	 *
	 * **Every waiting story shares one watcher**, which lives in `$lib/reveal`
	 * and holds the margin. A story built its own until 2026-09-06, so a day that
	 * published more visuals held more watchers - a cost that rose because a run
	 * published more, which is what Guardrail #12 refuses.
	 *
	 * **A story that leaves the page takes its request with it.** Unmount stops
	 * the watch and aborts the fetch, so a reader scrolling fast is not still
	 * downloading marks for stories that are gone, and an answer that was already
	 * on its way is not written into a component nobody is reading.
	 */
	function askWhenNear(node: Element, file: string): { destroy: () => void } {
		const request = new AbortController();
		const forget = whenNear(node, () => {
			void read(file, request.signal).then((data) => {
				if (!request.signal.aborted) arrived = data;
			});
		});
		return {
			destroy: () => {
				request.abort();
				forget();
			}
		};
	}
</script>

{#if drawing}
	<!-- The figure takes the focus, not the marks inside it: `role="img"` replaces
	     its whole subtree with one name, so a bar given its own tab stop would be
	     a stop announcing nothing. It is not a control and it is still focusable,
	     because the alternative is a chart a keyboard cannot reach at all. -->
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<figure
		class="visual my-4 overflow-hidden rounded-md border border-rule bg-surface"
		tabindex="0"
		role="img"
		aria-label={stated}
	>
		<svg
			viewBox="0 0 {drawing.width} {drawing.height}"
			width={drawing.width}
			height={drawing.height}
			role="presentation"
		>
			{#each drawing.bars as bar (bar.y)}
				<text class="name" x={drawing.left - 10} y={bar.y + bar.height / 2} text-anchor="end"
					>{bar.name}</text
				>
				<rect class="bar" x={drawing.left} y={bar.y} width={bar.width} height={bar.height} rx="3" />
				<text class="figure" x={drawing.left + bar.width + 8} y={bar.y + bar.height / 2}
					>{bar.stated}</text
				>
			{/each}
			<line
				class="axis"
				x1={drawing.left}
				y1={drawing.baseline}
				x2={drawing.width}
				y2={drawing.baseline}
			/>
			{#if drawing.unit}
				<text class="unit" x={drawing.left} y={drawing.baseline + 18}>{drawing.unit}</text>
			{/if}
		</svg>
	</figure>
{:else if wanted}
	<!-- Where the drawing will go, and nothing a reader can see: no box, no
	     border, no height. It exists so the fetch can wait until the story is
	     nearly on screen, and a story whose marks never arrive keeps exactly the
	     height it has now. -->
	<div class="slot" use:askWhenNear={wanted}></div>
{/if}

<style>
	/* The root svg takes the width the card gives it and the view box carries the
	   aspect ratio, so the browser reserves the right box before a mark is placed
	   and the story cannot shift as it is read. */
	.visual svg {
		display: block;
		height: auto;
		width: 100%;
	}

	/* The same ring every other focusable surface here draws, on the same token.
	   A tab stop nobody can see is the reason focus outlines get removed and then
	   missed. */
	.visual:focus-visible {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}

	/* Type on the card, read the way the reader note above it is read. The chart
	   ramp is for marks that carry no word, and a name and a figure both do.

	   `--text-xs` rather than a px size, for the reason every other type on the
	   site takes a token: a px size ignores a reader who set their browser text
	   larger.

	   **It is the token and not yet the floor, and that difference is real.**
	   The view box is a fixed 720 wide and the figure takes the card's width, so
	   the browser scales every user unit - and a 12-unit string on a 390 px
	   screen resolves near 6 CSS px, under the token it was set from. Plan 12
	   row #2 takes the width the screen actually has, which removes the scale,
	   and row #4 is the row that then holds the result to the floor. What this
	   row buys is that the size is a token a later row can move in one place,
	   and that the drawn strings can be measured at all. */
	.name,
	.figure,
	.unit {
		dominant-baseline: middle;
		fill: var(--color-text-secondary);
		font-family: inherit;
		font-size: var(--text-xs);
	}

	/* The figure a reader compares is the one thing on the drawing they read as a
	   number rather than as a label, so it takes the page's own ink. */
	.figure {
		fill: var(--color-text);
	}

	/* `--chart-axis` is the token every console chart already draws an axis with,
	   so there is one answer to "what colour is an axis here" rather than two. */
	.axis {
		stroke: var(--chart-axis);
		stroke-width: 1;
	}

	.bar {
		fill: var(--chart-1);
	}

	/* Stated rather than left to an empty box, so nothing a later rule does to a
	   bare div can give this one a height a reader would see. */
	.slot {
		height: 0;
	}
</style>

