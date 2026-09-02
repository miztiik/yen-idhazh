<script lang="ts">
	/** The day's stories down a time rail: newest first, with a marker where the
	 * time changes and nothing where it repeats.
	 *
	 * **One marker per group, never one per story.** A day of 359 stories over
	 * four groups is 355 duplicate labels, and a label repeated ninety times is
	 * texture rather than information. `railRows` decides where a group opens;
	 * this draws it.
	 *
	 * **No relative time, anywhere.** The page is prerendered once and read for
	 * the next 24 hours with script optionally off, so `3 hours ago` baked in at
	 * 06:20 is wrong by 18:20 and wrong for ever on an archived day. The zone is
	 * named once above the stream instead of suffixed onto every label.
	 *
	 * The mark beside `First seen` is the one glyph the rail draws, and it earns
	 * its place on that case alone: the printed clock there is ours rather than
	 * the publisher's, and a reader scanning a column of times would otherwise
	 * read it as a feed time. An old story gets no mark - the date says it.
	 */
	import type { RailRow } from '$lib/day-shape';
	import Icon from '$lib/icons/Icon.svelte';
	import type { DigestItem } from '$lib/payload/types';
	import type { Snippet } from 'svelte';

	let { rows, story }: { rows: RailRow[]; story: Snippet<[DigestItem]> } = $props();
</script>

<!-- The zone, once. Not a suffix on 359 labels and not a fifth band at the top
     of the page: it belongs to the column it explains, so it sits directly
     above it. -->
<p class="note" data-rail-note>Times shown in UTC.</p>

<div class="rail" data-time-rail>
	{#each rows as row (row.item.item_id)}
		<div class="cell">
			{#if row.mark}
				<span class="mark" data-rail-mark data-rail-form={row.mark.form}
					>{row.mark.label}{#if row.mark.form === 'first-seen'}&nbsp;<Icon
							id="clock-alert"
						/>{/if}</span
				>
			{/if}
		</div>
		<div class="story">{@render story(row.item)}</div>
	{/each}
</div>

<style>
	.note {
		margin-block-start: var(--space-5);
		color: var(--color-text-tertiary);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
	}

	/* Below the small breakpoint the rail is one column and the marker is a rule
	   with the time under it, at the head of its group.

	   That is not a smaller version of the wide layout, and the reason is
	   measured. A 360px screen leaves 328px of content box; the item already
	   spends 40 on the read mark and 32 on its own padding, and a 3.5rem column
	   plus its gap took 68 more - which left the summary 186px, about 25
	   characters, and broke `Interconnector` across two lines in the title.
	   Measured 2026-09-02 on the canary build. A column and a card cannot both
	   have the leading edge of a phone, so the label takes the width it needs
	   and gives the rest back. What the reader loses is the label sitting level
	   with the story it opens; what they get back is 70px of every line. */
	.mark {
		display: block;
		margin-block-start: var(--space-5);
		padding-block-start: var(--space-2);
		border-block-start: 1px solid var(--color-rule);
		color: var(--color-text-tertiary);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		font-variant-numeric: tabular-nums;
		overflow-wrap: break-word;
	}

	/* From the small breakpoint there is room for a column, and the rail becomes
	   the two-column grid it is on a desktop: a hairline the whole height of the
	   stream, with each marker knocking a hole in it by painting its own ground.
	   That is what makes a column of times read as one axis rather than as a
	   stack of separate numbers.

	   `--zone-time` is a `rem` knob in config/appearance.json, so a reader who
	   set their browser text larger gets a wider rail with it and the labels keep
	   the same number of lines. The breakpoint matches frame.breakpoints_px[0];
	   a media query cannot read a custom property, which is the one place this
	   duplication is unavoidable and is already true of the item's side rail. */
	@media (min-width: 640px) {
		.rail {
			position: relative;
			display: grid;
			grid-template-columns: var(--zone-time) minmax(0, 1fr);
			column-gap: var(--space-4);
			align-items: start;
		}

		.rail::before {
			content: '';
			position: absolute;
			/* Level with the first card's top edge - the item brings its own
			   `--space-4` of margin - and stopping at the last card's bottom. */
			inset-block: var(--space-4) 0;
			inset-inline-start: var(--zone-time);
			inline-size: 1px;
			background: var(--color-rule);
		}

		.cell {
			grid-column: 1;
			/* The same margin the card carries, so the marker sits level with the
			   top of the story it opens. */
			margin-block-start: var(--space-4);
			text-align: end;
		}

		.story {
			grid-column: 2;
			min-inline-size: 0;
		}

		/* A block rather than an inline run: its own ground has to cover the
		   hairline for the whole height of the label, and a label that wrapped to
		   two lines would otherwise leave the line showing between them. The
		   negative margin is what carries it the last pixel over. */
		.mark {
			margin-block-start: 0;
			padding-block-start: var(--space-1);
			padding-block-end: var(--space-1);
			padding-inline-end: var(--space-1);
			margin-inline-end: -1px;
			border-block-start: 0;
			background: var(--color-bg);
		}
	}
</style>
