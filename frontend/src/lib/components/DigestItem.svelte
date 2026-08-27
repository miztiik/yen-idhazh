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
		level = 2,
		showVertical = true,
		showMark = true,
		read = false,
		day,
		onRead
	}: {
		item: DigestItem;
		verticalName: string;
		/** 2 on a flat list, 3 under a topic heading. A skipped level breaks
		 * heading-to-heading navigation. */
		level?: 2 | 3;
		/** False under a topic heading, which already says the topic. */
		showVertical?: boolean;
		showMark?: boolean;
		read?: boolean;
		/** Set on a search result: the day it was found on, and the link back. */
		day?: { date: string; href: string };
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
	<!-- Under a topic heading the name would repeat the heading, and a bullet on
	     its own is decoration. The line then earns its place only when it has
	     the one thing left to say. -->
	{#if showVertical || read}
		<p
			class="mb-1 flex items-center gap-2 text-[0.75rem] tracking-wide text-text-tertiary uppercase"
		>
			<span
				class="inline-block h-1.5 w-1.5 rounded-full border border-current"
				class:bg-current={!read}
				aria-hidden="true"
			></span>
			{#if showVertical}{verticalName}{/if}
			{#if read}<span class="normal-case">Read</span>{/if}
		</p>
	{/if}

	<svelte:element
		this={`h${level}`}
		class="mb-2 text-[1.375rem] leading-[1.25] tracking-[-0.011em]"
		class:font-semibold={!read}
		class:font-normal={read}
		class:text-text={!read}
		class:text-text-secondary={read}
	>
		{item.title}
	</svelte:element>

	<p class="text-[1.0625rem] leading-[1.6] text-text">{item.summary}</p>
	{#if item.reader_note}
		<p class="mt-2 text-[0.9375rem] leading-[1.55] text-text-secondary">{item.reader_note}</p>
	{/if}

	<ItemVisual visual={item.visual} />

	<ItemMeta {item} {showMark} {day} {onRead} />
</article>
