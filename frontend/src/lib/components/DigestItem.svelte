<script lang="ts">
	/** One item. Three levels of hierarchy and no fourth.
	 *
	 * A card on the page ground, carrying a hairline and no shadow at rest. The
	 * surface and the edge do the separating; one step of elevation and a
	 * warmer edge arrive on hover and on focus to say that these lines belong
	 * together. Nothing moves - the title is a heading rather than a link, so a
	 * rise would promise a click the card does not answer.
	 *
	 * Read is marked on the title link only - one step down the ramp, accent
	 * removed, a weight lighter. Never dimmed: a dimmed item reads as "you cannot
	 * have this" rather than "you already had this".
	 */
	import type { DigestItem } from '$lib/payload/types';
	import { shownLenses } from '$lib/payload/lenses';
	import ItemMeta from './ItemMeta.svelte';
	import ItemVisual from './ItemVisual.svelte';
	import LensChips from './LensChips.svelte';

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

	const lenses = $derived(shownLenses(item.lenses));
</script>

<article
	id={item.item_id}
	class="item"
	data-band={item.band}
	data-vertical={item.vertical}
	data-truncated={item.truncated}
	data-read={read}
	data-visual={item.visual?.state ?? 'absent'}
	data-lenses={lenses.length ? lenses.join(' ') : undefined}
>
	<div class="item-body">
		<!-- Under a topic heading the name would repeat the heading, and a bullet on
		     its own is decoration. The line then earns its place only when it has
		     the one thing left to say. A topic is one of those things. -->
		{#if showVertical || read || lenses.length}
			<p class="mb-1 flex items-center gap-2 text-xs tracking-wide text-text-tertiary uppercase">
				{#if showVertical || read}
					<span
						class="inline-block h-1.5 w-1.5 rounded-full border border-current"
						class:bg-current={!read}
						aria-hidden="true"
					></span>
				{/if}
				{#if showVertical}{verticalName}{/if}
				{#if read}<span class="normal-case">Read</span>{/if}
				<LensChips {lenses} />
			</p>
		{/if}

		<svelte:element
			this={`h${level}`}
			class="measure mb-2 text-2xl"
			class:font-semibold={!read}
			class:font-normal={read}
			class:text-text={!read}
			class:text-text-secondary={read}
		>
			{item.title}
		</svelte:element>

		<p class="measure text-lg text-text">{item.summary}</p>
		{#if item.reader_note}
			<p class="measure mt-2 text-base text-text-secondary">
				{item.reader_note}
			</p>
		{/if}

		<ItemVisual visual={item.visual} />
	</div>

	<div class="item-rail">
		<ItemMeta {item} {showMark} {day} {onRead} />
	</div>
</article>

<style>
	/* The measure is on the TEXT, never on the shell. Below the side-rail
	   breakpoint the item is one column and the rail simply follows the body,
	   which is what a phone should do. */
	.item {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: var(--space-2);
		margin-block-start: var(--space-4);
		padding: var(--space-4);
		border: 1px solid var(--item-edge);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
		transition:
			border-color var(--dur-fast) var(--ease-standard),
			box-shadow var(--dur-fast) var(--ease-standard);
	}

	/* No shadow at rest: a page of items that all float is a page where nothing
	   is in front of anything either. The elevation is what the pointer and the
	   keyboard buy, and :focus-within earns it for a reader who never uses a
	   pointer at all. */
	.item:hover,
	.item:focus-within {
		border-color: var(--color-accent);
		box-shadow: var(--shadow-md);
	}

	/* At this width the meta line - source, date, confidence, read mark - stops
	   interrupting the read and moves beside it. The value matches
	   frame.breakpoints_px[1] in config/appearance.json; a media query cannot
	   read a custom property, which is the one place this duplication is
	   unavoidable. */
	@media (min-width: 1024px) {
		.item {
			grid-template-columns: minmax(0, 1fr) 14rem;
			gap: var(--space-6);
			align-items: start;
			padding: var(--space-5);
		}

		.item-rail {
			position: sticky;
			top: var(--space-4);
		}
	}
</style>

