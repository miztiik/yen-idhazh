<script lang="ts">
	/** One item. Three levels of hierarchy and no fourth.
	 *
	 * A card on the page ground, carrying a hairline and no shadow at rest. The
	 * surface and the edge do the separating; one step of elevation and a
	 * warmer edge arrive on hover and on focus to say that these lines belong
	 * together. Nothing moves - the title is a heading rather than a link, so a
	 * rise would promise a click the card does not answer.
	 *
	 * Read is carried three ways and only one of them is brightness. The source
	 * mark on the leading edge is filled when unread and hollow when read, which
	 * is an area difference and survives a cheap panel and sunlight. The title
	 * steps one down the ramp and loses a weight - never further, because a
	 * dimmed item reads as "you cannot have this" rather than "you already had
	 * this". And a visually-hidden word opens the heading, because a fill and a
	 * font weight are announced to nobody.
	 *
	 * The item's facts sit in two places and the split is by what they are about.
	 * Above the title go the ones a reader uses to decide whether to read it at
	 * all - the mark, the desk, and who is speaking. Below the summary go the
	 * claims about the summary itself, and the two things you can do next. The
	 * fourth fact, when it happened, moved to the day's own time rail on
	 * 2026-09-02, because the stream now runs in that order and a time printed
	 * beside every story as well as down the rail is the same number twice.
	 */
	import { KIND_WORTH_SAYING, SOURCE_KINDS } from '$lib/bands';
	import { shortDate } from '$lib/format';
	import type { DigestItem } from '$lib/payload/types';
	import { shownLenses } from '$lib/payload/lenses';
	import ItemMeta from './ItemMeta.svelte';
	import ItemVisual from './ItemVisual.svelte';
	import LensChips from './LensChips.svelte';
	import SourceMark from './SourceMark.svelte';

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
		/** Set on a search result: the day it was found on, and the link back.
		 * It takes the time slot rather than adding to the line - the two dates
		 * are the same day or one apart, and printing both puts two dates on a
		 * line that already holds four facts. */
		day?: { date: string; href: string };
		onRead?: () => void;
	} = $props();

	const lenses = $derived(shownLenses(item.lenses));
	const kindWorthSaying = $derived(KIND_WORTH_SAYING.includes(item.source_kind));
</script>

<article
	id={item.item_id}
	class="item"
	class:has-mark={showMark}
	data-band={item.band}
	data-vertical={item.vertical}
	data-truncated={item.truncated}
	data-read={read}
	data-visual={item.visual?.state ?? 'absent'}
	data-lenses={lenses.length ? lenses.join(' ') : undefined}
>
	{#if showMark}
		<SourceMark name={item.source_name} sourceId={item.source_id} {read} />
	{/if}

	<div class="item-body">
		<!-- The eyebrow. Four facts, and the cap is four at every width: the desk,
		     the topics the item's own words earned, who is speaking, and when.
		     The lens chips arrive inside one wrapper however many an item earned,
		     because the cap is on this element's children and a third chip would
		     otherwise take a slot from the source name.

		     The monogram is the fourth thing above the title and it is not a child
		     here. It sits in the item's own leading column, level with this line,
		     because the read state it carries has to stay beside the title it
		     qualifies at every width. -->
		<p class="eyebrow" data-item-eyebrow>
			{#if showVertical}
				<span class="topic-chip">{verticalName}</span>
			{/if}

			{#if lenses.length}
				<span class="lens-group"><LensChips {lenses} /></span>
			{/if}

			<span class="source">
				{item.source_name}
				<!-- Only where the speaker has something to gain. A reporter who
				     checked and a ministry announcing its own policy were arriving
				     in the same typeface. -->
				{#if kindWorthSaying}<span class="kind">{SOURCE_KINDS[item.source_kind]}</span>{/if}
			</span>

			<!-- The time is on the day's rail, not here. It was in this line until
			     2026-09-02, and a time in both places is the duplicate the rail
			     exists to remove. What survives is the search result's day link:
			     that list has no rail, and the date is how a reader tells which
			     day a found story was published on. -->
			{#if day}
				<a href={day.href} class="when hover:underline" data-item-day={day.date}>
					{shortDate(day.date)}
				</a>
			{/if}
		</p>

		<svelte:element
			this={`h${level}`}
			class="measure mb-2 text-2xl"
			class:font-semibold={!read}
			class:font-normal={read}
			class:text-text={!read}
			class:text-text-secondary={read}
		>
			<!-- The ring and the weight say this to a reader looking at the page and
			     to nobody else. The word is what a screen reader gets. -->
			{#if read}<span class="sr-only">Read. </span>{/if}{item.title}
		</svelte:element>

		<p class="measure text-lg text-text" data-item-summary>{item.summary}</p>
		{#if item.reader_note}
			<p class="measure mt-2 text-base text-text-secondary">
				{item.reader_note}
			</p>
		{/if}

		<ItemVisual visual={item.visual} />
	</div>

	<div class="item-rail">
		<ItemMeta {item} {onRead} />
	</div>
</article>

<style>
	/* The measure is on the TEXT, never on the shell. Below the side-rail
	   breakpoint the item is one column and the rail simply follows the body,
	   which is what a phone should do.

	   Every column here is a `rem` token from config/appearance.json, so a
	   reader who set their browser text larger gets wider furniture with it -
	   measured 2026-09-02, a 22px root moved the mark column 28 -> 38.5px and
	   the rail 224 -> 308px, both 1.375x, which is what proves no zone is a
	   pixel count. */
	.item {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		align-items: start;
		column-gap: var(--space-3);
		row-gap: var(--space-2);
		margin-block-start: var(--space-4);
		padding: var(--space-4);
		border: 1px solid var(--item-edge);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
		transition:
			border-color var(--dur-fast) var(--ease-standard),
			box-shadow var(--dur-fast) var(--ease-standard);
	}

	/* Wraps rather than scrolls, like every other row of labels here. Four
	   children is the cap; what a narrow screen changes is how many lines they
	   take, never how many there are. */
	.eyebrow {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1) var(--space-2);
		margin-block-end: var(--space-1);
		color: var(--color-text-tertiary);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
	}

	/* A tinted fill and never an outline: an outline means you can tap it, and
	   the only thing a tap could do here is repeat the filter panel two inches
	   above. It takes the same tint as the lens chips beside it - one tint for
	   every member of a label family - and upper case is what separates the desk
	   we filed the story under from the words the story itself earned. */
	.topic-chip {
		padding: var(--space-1) var(--space-2);
		border-radius: var(--radius-full);
		background: var(--tint-accent);
		color: var(--color-text-secondary);
		font-weight: 500;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		white-space: nowrap;
	}

	/* One child of the eyebrow, whatever the item earned. */
	.lens-group {
		display: inline-flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1);
	}

	/* Who is speaking is the fact this line exists for, so it is the one thing
	   on it that is not tertiary. */
	.source {
		color: var(--color-text-secondary);
	}

	.kind,
	.when {
		color: var(--color-text-tertiary);
	}

	/* The mark leads the item at every width. It used to sit in the meta line,
	   which moves into the right rail on a wide screen - and a read indicator
	   14rem from the title it qualifies is paired with nothing. */
	.item.has-mark {
		grid-template-columns: var(--zone-mark) minmax(0, 1fr);
	}

	.item.has-mark > .item-body,
	.item.has-mark > .item-rail {
		grid-column: 2;
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

	/* At this width the footer - the two sentences about our summary, and the two
	   things you can do next - stops interrupting the read and moves beside it.
	   It is still after the summary in the document, which is what the split
	   promises; what moves is where it is painted. The value matches
	   frame.breakpoints_px[1] in config/appearance.json; a media query cannot
	   read a custom property, which is the one place this duplication is
	   unavoidable. */
	@media (min-width: 1024px) {
		.item {
			grid-template-columns: minmax(0, 1fr) var(--zone-rail);
			padding: var(--space-5);
		}

		.item.has-mark {
			grid-template-columns: var(--zone-mark) minmax(0, 1fr) var(--zone-rail);
		}

		.item.has-mark > .item-rail {
			grid-column: 3;
		}

		/* The rail sits further from the prose than the mark does, and one grid
		   gap cannot say both. */
		.item-rail {
			position: sticky;
			top: var(--space-4);
			margin-inline-start: var(--space-3);
		}
	}

	/* And at this width it gives the column back - but only to a day that grew an
	   aside (app.css). The frame's content box holds a 68-character measure plus
	   exactly ONE trailing column: measured 2026-09-02, keeping both leaves the
	   summary 570 CSS px against a measure of 659.81. So where the page has
	   claimed the column, the footer returns to where row 16 put it, under the
	   summary it is a claim about.

	   A day with no leading block has no aside - every committed day before
	   2026-09-01 is one, because the block did not exist yet - and there the
	   rail is the only thing standing beside the prose. Retiring it everywhere
	   would leave those days 466 px of empty card instead of 230. The value
	   matches frame.breakpoints_px[2]. */
	@media (min-width: 1400px) {
		:global(.day:has(> .day-aside)) .item {
			grid-template-columns: minmax(0, 1fr);
		}

		:global(.day:has(> .day-aside)) .item.has-mark {
			grid-template-columns: var(--zone-mark) minmax(0, 1fr);
		}

		:global(.day:has(> .day-aside)) .item.has-mark > .item-rail {
			grid-column: 2;
		}

		:global(.day:has(> .day-aside)) .item-rail {
			position: static;
			margin-inline-start: 0;
		}
	}
</style>

