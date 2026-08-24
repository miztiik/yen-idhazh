<script lang="ts">
	/** One topic on the all-topics page: its name, its best few, and a way in.
	 *
	 * The day page used to be one queue. At 586 items its first screen was
	 * whichever topic id sorted first, which is an accident rather than an
	 * edit. Sections give the day a shape without removing, hiding or
	 * re-ranking anything - every item is still one click away, in the order
	 * the pipeline published it.
	 *
	 * The heading carries no count. The link already states it, and printing a
	 * number twice is the defect the day notice just lost.
	 */
	import { base } from '$app/paths';
	import type { DigestItem, DigestVerticalRef } from '$lib/payload/types';
	import { verticalHref } from '$lib/links';
	import DigestItemView from './DigestItem.svelte';

	let {
		vertical,
		items,
		more,
		datePrefix = '',
		showMark = true,
		read,
		onRead
	}: {
		vertical: DigestVerticalRef;
		items: DigestItem[];
		/** The day published more of this topic than this section shows. */
		more: boolean;
		datePrefix?: string;
		showMark?: boolean;
		read: Set<string>;
		onRead: (itemId: string) => void;
	} = $props();

	const href = $derived(verticalHref(base, datePrefix, vertical.id));
</script>

<section class="pt-8" data-topic={vertical.id}>
	<h2
		class="border-b border-rule pb-2 text-[0.8125rem] font-semibold tracking-wide text-text-tertiary uppercase"
	>
		{vertical.display_name}
	</h2>

	{#each items as item (item.item_id)}
		<DigestItemView
			{item}
			level={3}
			verticalName={vertical.display_name}
			showVertical={false}
			{showMark}
			read={read.has(item.item_id)}
			onRead={() => onRead(item.item_id)}
		/>
	{/each}

	{#if more}
		<p class="pt-4">
			<a href={href} class="text-[0.9375rem] text-accent hover:underline" data-topic-link>
				All {vertical.count}
				{vertical.display_name} stories
			</a>
		</p>
	{/if}
</section>
