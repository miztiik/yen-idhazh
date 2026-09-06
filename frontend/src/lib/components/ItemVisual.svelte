<script lang="ts">
	/** An item with no visual is simply shorter.
	 *
	 * No placeholder and no reserved slot: a grey rectangle makes "we correctly
	 * decided this needed no picture" look identical to "the image failed", which
	 * is the wrong signal on a page whose product is trust. Two items in three
	 * carry no visual, so this is the default shape, not a fallback.
	 *
	 * The figure takes the chart's own shape rather than a ratio chosen here. A
	 * fixed 16:10 box reserved space the chart never used: measured 2026-09-02,
	 * the committed charts are 825 x 437 and the box beside a 890px card body was
	 * 890 x 556, so 85 px of empty band sat above and below every one of them.
	 * An SVG carries its width and height, so the browser reserves the right box
	 * from the markup and the image still cannot shift the page as it loads. That
	 * survives inlining: a `viewBox` is an aspect ratio, so `height: auto`
	 * resolves before a byte of the drawing has been read.
	 *
	 * **The drawing is always in the document, never in an `img`.** An SVG inside
	 * an `img` is a separate document. It reads none of the page's custom
	 * properties, so the chart kept the colours the renderer baked in - black
	 * axis type and grey rules, which on the dark theme is black type on a
	 * near-black card. Inlined, the same markup loses to any stylesheet rule,
	 * because a presentation attribute has the lowest priority there is. So the
	 * page repaints it from its own tokens and the backend writes the same bytes
	 * it always wrote.
	 *
	 * A story the prerendered document carries arrives with its drawing already in
	 * hand. A story past that seed arrives with a path, and this component fetches
	 * the file and puts the same markup in the same place - so one scroll shows
	 * one treatment rather than two.
	 *
	 * **A drawing that does not arrive costs the story its picture and nothing
	 * else.** No broken-image glyph, no grey box, no skeleton: the story is
	 * shorter, which is the shape two stories in three already have.
	 */
	import { base } from '$app/paths';
	import { publishedVisual, refusedDrawing } from '$lib/payload/drawing';
	import type { SeededVisual } from '$lib/payload/types';
	import { whenNear } from '$lib/reveal';

	let { visual }: { visual: SeededVisual | null } = $props();

	/** The drawing this story arrived with, for a story the document seeded. */
	const seeded = $derived(visual?.markup ?? null);
	/** The file this story's drawing is in, for a story that arrived without one.
	 *
	 * Null once the markup is in hand, so a seeded story never asks for a file it
	 * is already holding.
	 */
	const wanted = $derived(
		!visual?.markup && visual?.state === 'rendered' && visual.path ? visual.path : null
	);
	const alt = $derived(visual?.alt ?? '');

	/** What the fetch brought back, or null while it has not run or did not work. */
	let arrived = $state<string | null>(null);
	const drawing = $derived(seeded ?? arrived);

	/** The drawing that file holds, or null when there is nothing safe to draw.
	 *
	 * The refusal is the same one the build runs, out of the same module. Inlined
	 * markup is markup in our own origin whichever side put it there, and the
	 * labels inside it were written by a model that read a stranger's page
	 * (Rule #11). The path is matched before it is joined onto `base`, for the
	 * same reason `dayUrl` matches a date: it is about to become an address.
	 *
	 * **`__ASSET_BASE_URL__` moves where the drawing is asked for and nothing
	 * else.** It is `visuals.asset_base_url`, injected at build time, and it
	 * ships empty - so the join is `base`, this site, exactly as it was. Naming a
	 * host there takes the drawings a reader scrolls to off the 1 GB published
	 * ceiling without touching the carrier: the bytes still arrive as text and
	 * are still inlined, so the page still repaints them from its own tokens, and
	 * an `img` - which cannot be repainted, see above - is still not an option.
	 * The origin comes from our config and can never come from a payload, and the
	 * path is still matched by `publishedVisual` before either half is joined.
	 */
	async function read(file: string, signal: AbortSignal): Promise<string | null> {
		if (!publishedVisual(file)) {
			console.warn(`[digest] ${file}: not a published visual path, so it is not drawn`);
			return null;
		}
		try {
			const response = await fetch(`${__ASSET_BASE_URL__ || base}/${file}`, { signal });
			if (!response.ok) {
				console.warn(`[digest] ${file}: not available (${response.status}), so it is not drawn`);
				return null;
			}
			const markup = await response.text();
			const refused = refusedDrawing(markup);
			if (refused !== null) {
				console.warn(`[digest] ${file}: ${refused}, so it is not drawn`);
				return null;
			}
			return markup;
		} catch (error) {
			// A story the reader scrolled away from cancelled its own request. That
			// is the page working, so it says nothing.
			if (signal.aborted) return null;
			console.warn(`[digest] ${file} could not be read, so it is not drawn`, error);
			return null;
		}
	}

	/** Ask for the drawing once the story is nearly on screen.
	 *
	 * The `img` this replaced carried `loading="lazy"`, so a browser asked for a
	 * drawing only when the reader was near it. A plain fetch on mount throws that
	 * away, and the case where it hurts is not the ordinary one: a reader
	 * following `/<date>/#<story>` pages the stream down to that story, so the
	 * whole prefix mounts at once. Measured 2026-09-05, the day carrying the most
	 * drawings is 2026-08-31 with 43 across 601 stories - so a deep link into the
	 * tail of that day would open 43 requests at once, 534 KB, against the day
	 * payload the same page is still waiting on.
	 *
	 * **Every waiting story shares one watcher**, which lives in `$lib/reveal`
	 * and holds the margin. A story built its own until 2026-09-06, so a day that
	 * published more drawings held more watchers - a cost that rose because a run
	 * published more, which is what Rule #12 refuses.
	 *
	 * **A story that leaves the page takes its request with it.** Unmount stops
	 * the watch and aborts the fetch, so a reader scrolling fast is not still
	 * downloading drawings for stories that are gone, and an answer that was
	 * already on its way is not written into a component nobody is reading.
	 */
	function askWhenNear(node: Element, file: string): { destroy: () => void } {
		const request = new AbortController();
		const forget = whenNear(node, () => {
			void read(file, request.signal).then((markup) => {
				if (!request.signal.aborted) arrived = markup;
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
	<figure
		class="visual my-4 overflow-hidden rounded-md border border-rule bg-surface"
		role="img"
		aria-label={alt}
		aria-hidden={alt ? undefined : true}
	>
		<!-- eslint-disable-next-line svelte/no-at-html-tags -->
		{@html drawing}
	</figure>
{:else if wanted}
	<!-- Where the drawing will go, and nothing a reader can see: no box, no
	     border, no height. It exists so the fetch can wait until the story is
	     nearly on screen, and a story whose drawing never arrives keeps exactly
	     the height it has now. -->
	<div class="slot" use:askWhenNear={wanted}></div>
{/if}

<style>
	/* Every rule here paints markup this component did not write, so every
	   selector is `:global`. What they name is the renderer's own vocabulary -
	   a mark group, an axis part - and never a colour, so the drawing keeps
	   saying what it said and only the paint comes from the page.

	   The root svg takes the width because the markup carries the renderer's
	   own pixel size, 721 wide, and a card body is narrower than that at every
	   width the site has. */
	.visual :global(svg) {
		display: block;
		width: 100%;
		height: auto;
		/* The one drawing that is not a chart paints itself in `currentColor`,
		   which inside an `img` could only ever resolve to black. Here it is the
		   page's ink. */
		color: var(--color-text);
	}

	/* Axis labels and the axis title. A text token rather than a chart one:
	   this is type on the card, read the way the reader note above it is read,
	   and the chart ramp is for marks that carry no word. */
	.visual :global(.mark-text text) {
		fill: var(--color-text-secondary);
	}

	/* Ticks and the axis line. `--chart-axis` is the token every console chart
	   already draws an axis with, so there is one answer to "what colour is an
	   axis here" rather than two. */
	.visual :global(.mark-rule line) {
		stroke: var(--chart-axis);
	}

	/* After the rule above, and quieter than it: a grid line sits behind the
	   data where an axis line bounds it. It repaints nothing any published
	   drawing has ever carried - counted 2026-09-05 over all 351 drawings the 15
	   committed days hold, every one carries a bar, an axis label and an axis
	   line, and none carries a grid line, because `chart_spec()` writes
	   `"axis": {"grid": false}` on every spec. The only drawing that exercises
	   this rule is the canary fixture, whose spec is hand-written and leaves the
	   grid at the renderer's default. Kept as insurance: baked at #ddd, a grid
	   would draw near-white across the bars on the dark theme the day the
	   renderer starts emitting one. */
	.visual :global(.role-axis-grid line) {
		stroke: var(--chart-grid);
	}

	/* The bars. Named by mark type rather than by `.role-mark`, which also
	   covers marks drawn as an outline - filling one of those turns a line into
	   a blob. Every chart the pipeline emits today is bars. */
	.visual :global(.mark-rect > path) {
		fill: var(--chart-1);
	}

	/* Stated rather than left to an empty box, so nothing a later rule does to a
	   bare div can give this one a height a reader would see. */
	.slot {
		height: 0;
	}
</style>

