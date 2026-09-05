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
	 * **The drawing is in the document when the build could put it there.** An
	 * SVG inside an `img` is a separate document. It reads none of the page's
	 * custom properties, so the chart kept the colours the renderer baked in -
	 * black axis type and grey rules, which on the dark theme is black type on a
	 * near-black card. Inlined, the same markup loses to any stylesheet rule,
	 * because a presentation attribute has the lowest priority there is. So the
	 * page repaints it from its own tokens and the backend writes the same bytes
	 * it always wrote.
	 *
	 * The `img` below is what a story past the seed still gets. It is the
	 * unreadable carrier and it is on its way out; until the fetch that replaces
	 * it lands, deleting it here would take the drawing away from those stories
	 * rather than fix it, and a fact a reader can half-see beats a fact that is
	 * gone.
	 */
	import { base } from '$app/paths';
	import type { SeededVisual } from '$lib/payload/types';

	let { visual }: { visual: SeededVisual | null } = $props();
	const rendered = $derived(visual?.state === 'rendered' && visual.path);
	const drawing = $derived(visual?.markup ?? null);
	const alt = $derived(visual?.alt ?? '');
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
{:else if rendered && visual}
	<figure class="my-4 overflow-hidden rounded-md border border-rule bg-surface">
		<img
			src="{base}/{visual.path}"
			alt={visual.alt ?? ''}
			loading="lazy"
			decoding="async"
			class="block h-auto w-full"
		/>
	</figure>
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
	   data where an axis line bounds it. Baked at #ddd, which on the dark theme
	   drew eighteen near-white lines across the bars. */
	.visual :global(.role-axis-grid line) {
		stroke: var(--chart-grid);
	}

	/* The bars. Named by mark type rather than by `.role-mark`, which also
	   covers marks drawn as an outline - filling one of those turns a line into
	   a blob. Every chart the pipeline emits today is bars. */
	.visual :global(.mark-rect > path) {
		fill: var(--chart-1);
	}
</style>

