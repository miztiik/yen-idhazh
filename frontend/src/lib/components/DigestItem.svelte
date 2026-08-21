<script lang="ts">
	/** One item. Three levels of hierarchy and no fourth.
	 *
	 * Hairline rules rather than cards: seventeen boxes of chrome on a page whose
	 * product is prose is chrome winning.
	 */
	import type { DigestItem } from '$lib/payload/types';
	import ItemMeta from './ItemMeta.svelte';
	import ItemVisual from './ItemVisual.svelte';

	let {
		item,
		verticalName,
		showMark = true
	}: { item: DigestItem; verticalName: string; showMark?: boolean } = $props();
</script>

<article
	id={item.item_id}
	class="border-b border-rule py-7"
	data-band={item.band}
	data-vertical={item.vertical}
	data-truncated={item.truncated}
	data-visual={item.visual?.state ?? 'absent'}
>
	<p class="mb-1 text-[0.75rem] tracking-wide text-text-tertiary uppercase">{verticalName}</p>

	<h2 class="mb-2 text-[1.375rem] leading-[1.25] font-semibold tracking-[-0.011em] text-text">
		{item.title}
	</h2>

	<p class="text-[1.0625rem] leading-[1.6] text-text">{item.summary}</p>

	<ItemVisual visual={item.visual} />

	<ItemMeta {item} {showMark} />
</article>
