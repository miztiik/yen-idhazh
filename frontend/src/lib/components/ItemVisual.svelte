<script lang="ts">
	/** An item with no visual is simply shorter.
	 *
	 * No placeholder and no reserved slot: a grey rectangle makes "we correctly
	 * decided this needed no picture" look identical to "the image failed", which
	 * is the wrong signal on a page whose product is trust. Two items in three
	 * carry no visual, so this is the default shape, not a fallback.
	 */
	import { base } from '$app/paths';
	import type { DigestVisual } from '$lib/payload/types';

	let { visual }: { visual: DigestVisual | null } = $props();
	const rendered = $derived(visual?.state === 'rendered' && visual.path);
</script>

{#if rendered && visual}
	<figure
		class="my-4 aspect-[16/10] overflow-hidden rounded-[--radius-md] border border-rule bg-surface"
	>
		<img
			src="{base}/{visual.path}"
			alt={visual.alt ?? ''}
			loading="lazy"
			decoding="async"
			class="h-full w-full object-contain"
		/>
	</figure>
{/if}
