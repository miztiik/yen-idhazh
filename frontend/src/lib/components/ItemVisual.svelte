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
	 * apiece would make the stream something a keyboard cannot get past. The ring
	 * is the scale's own step rather than a rule in the block below, because a px
	 * size in an authored style block ignores a reader who set their browser text
	 * larger and `frontend/tests/tokens.spec.ts` refuses one.
	 *
	 * **The drawing is written by Svelte from geometry `$lib/visual/bar`
	 * computed**, so the marks are ordinary elements in this component's own
	 * subtree. They take the page's tokens through plain scoped CSS rather than
	 * through `:global` overrides of a renderer's class vocabulary, and every
	 * string a model cut out of a stranger's page lands as a text node rather
	 * than as markup (Guardrail #11).
	 *
	 * **The drawing takes the width the card gives it** (plan 12 row #2). The
	 * figure's content box is measured first and every mark is placed in it, so
	 * one drawn unit is one CSS pixel and there is no scale factor between what a
	 * token says and what a reader sees. Before this the drawing was laid out at
	 * a fixed 720 units and stretched to fit, so a `--text-xs` string resolved at
	 * 4.8 CSS px on a 390 px phone - the right size in a coordinate space nobody
	 * reads. The height is a count of bars and does not depend on the width, so
	 * the figure is its final height from the frame the marks land in and the
	 * story cannot shift as it is read; that is the promise the `viewBox` used to
	 * keep by holding an aspect ratio.
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
	import { whenWide } from '$lib/visual/width';

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
	/** How much room the card gives the drawing, or 0 before it has been measured. */
	let room = $state(0);
	const drawing = $derived<Drawing | null>(
		arrived && room > 0 ? drawBars(arrived, room) : null
	);
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
	/** Follow the card's own content box, and redraw whenever it moves.
	 *
	 * The figure is measured rather than the svg inside it, because the figure's
	 * width does not depend on what it holds - so the reading is stable on the
	 * frame the marks land in, before a mark is placed. Every chart on the page
	 * shares one watcher, which lives in `$lib/visual/width`.
	 */
	function measured(node: Element): { destroy: () => void } {
		const forget = whenWide(node, (wide) => {
			room = wide;
		});
		return { destroy: forget };
	}
</script>

{#if arrived}
	<!-- The figure takes the focus, not the marks inside it: `role="img"` replaces
	     its whole subtree with one name, so a bar given its own tab stop would be
	     a stop announcing nothing. It is not a control and it is still focusable,
	     because the alternative is a chart a keyboard cannot reach at all. -->
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<figure
		class="visual my-4 overflow-hidden rounded-md border border-rule bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
		tabindex="0"
		role="img"
		aria-label={stated}
		use:measured
	>
		{#if drawing}
			<svg
				viewBox="0 0 {drawing.width} {drawing.height}"
				width={drawing.width}
				height={drawing.height}
				role="presentation"
			>
				{#each drawing.bars as bar (bar.y)}
					<text class="name" x="0" y={bar.label}>{bar.name}</text>
					<rect class="bar" x="0" y={bar.y} width={bar.width} height={bar.height} rx="3" />
					<text class="figure" x={bar.figure} y={bar.y + bar.height / 2}>{bar.stated}</text>
				{/each}
				<line class="axis" x1="0" y1={drawing.baseline} x2={drawing.width} y2={drawing.baseline} />
				{#if drawing.unit}
					<text class="unit" x="0" y={drawing.baseline + 16}>{drawing.unit}</text>
				{/if}
			</svg>
		{/if}
	</figure>
{:else if wanted}
	<!-- Where the drawing will go, and nothing a reader can see: no box, no
	     border, no height. It exists so the fetch can wait until the story is
	     nearly on screen, and a story whose marks never arrive keeps exactly the
	     height it has now. -->
	<div class="slot" use:askWhenNear={wanted}></div>
{/if}

<style>
	/* The svg draws at the width it was measured in, so one drawn unit is one CSS
	   pixel and the `viewBox` scales nothing. `max-width` rather than `width` is
	   the guard: the measured room is floored to whole pixels so the drawing
	   already fits, and this only catches the frame between a card moving and the
	   watcher reporting it. A `width: 100%` here would stretch the coordinate
	   space again and undo the whole row. */
	.visual svg {
		display: block;
		height: auto;
		max-width: 100%;
	}

	/* Type on the card, read the way the reader note above it is read. The chart
	   ramp is for marks that carry no word, and a name and a figure both do.

	   `--text-xs` rather than a px size, for the reason every other type on the
	   site takes a token: a px size ignores a reader who set their browser text
	   larger. **And it is now the size a reader gets**, because the drawing is
	   placed at the card's own width: a 12 px token resolves at 12 CSS px rather
	   than at the 4.8 the old 720-unit box scaled it to. Row #4 is the row that
	   holds that to a floor; this row is what makes the token mean what it says. */
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

