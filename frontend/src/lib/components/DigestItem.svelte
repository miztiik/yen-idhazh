<script lang="ts">
	/** One item. Three levels of hierarchy and no fourth.
	 *
	 * Hairline rules rather than cards: seventeen boxes of chrome on a page whose
	 * product is prose is chrome winning.
	 *
	 * Read is marked on the title link only - one step down the ramp, accent
	 * removed, a weight lighter. Never dimmed: a dimmed item reads as "you cannot
	 * have this" rather than "you already had this".
	 */
	import type { DigestItem } from '$lib/payload/types';
	import ItemMeta from './ItemMeta.svelte';
	import ItemVisual from './ItemVisual.svelte';

	let {
		item,
		verticalName,
		showMark = true,
		read = false,
		onRead
	}: {
		item: DigestItem;
		verticalName: string;
		showMark?: boolean;
		read?: boolean;
		onRead?: () => void;
	} = $props();
</script>

<article
	id={item.item_id}
	class="border-b border-rule py-7"
	data-band={item.band}
	data-vertical={item.vertical}
	data-truncated={item.truncated}
	data-read={read}
	data-visual={item.visual?.state ?? 'absent'}
>
	<p class="mb-1 flex items-center gap-2 text-[0.75rem] tracking-wide text-text-tertiary uppercase">
		<span
			class="inline-block h-1.5 w-1.5 rounded-full border border-current"
			class:bg-current={!read}
			aria-hidden="true"
		></span>
		{verticalName}
		{#if read}<span class="normal-case">Read</span>{/if}
	</p>

	<h2
		class="mb-2 text-[1.375rem] leading-[1.25] tracking-[-0.011em]"
		class:font-semibold={!read}
		class:font-normal={read}
		class:text-text={!read}
		class:text-text-secondary={read}
	>
		{item.title}
	</h2>

	<p class="text-[1.0625rem] leading-[1.6] text-text">{item.summary}</p>

	<ItemVisual visual={item.visual} />

	<ItemMeta {item} {showMark} {onRead} />
</article>
