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
	 * from the markup and the image still cannot shift the page as it loads.
	 */
	import { base } from '$app/paths';
	import type { DigestVisual } from '$lib/payload/types';

	let { visual }: { visual: DigestVisual | null } = $props();
	const rendered = $derived(visual?.state === 'rendered' && visual.path);
</script>

{#if rendered && visual}
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
