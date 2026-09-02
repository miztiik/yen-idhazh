<script lang="ts">
	/** The day page. Section order is config, which is the modularity story:
	 * reordering the page is a config edit, not a code change.
	 *
	 * Read-state lives here and touches nothing but appearance. The item set and
	 * its order are computed before any of it is consulted, which is what makes
	 * two readers at the same URL see the same page.
	 */
	import DayNotice from '$lib/components/DayNotice.svelte';
	import DigestItemView from '$lib/components/DigestItem.svelte';
	import EmptyDay from '$lib/components/EmptyDay.svelte';
	import FilterBar from '$lib/components/FilterBar.svelte';
	import LeadingStories from '$lib/components/LeadingStories.svelte';
	import TimeRail from '$lib/components/TimeRail.svelte';
	import { filterNeedle, leadingStories, matchItems, orderByTime, railRows } from '$lib/day-shape';
	import type { UiConfig } from '$lib/server/config';
	import type { DigestDay, DigestItem } from '$lib/payload/types';
	import { forgetAll, loadHideRead, loadRead, markRead, setHideRead } from '$lib/readstate';
	import { onMount } from 'svelte';

	let {
		day,
		vertical = null,
		datePrefix = '',
		latest = null,
		ui
	}: {
		day: DigestDay;
		vertical?: string | null;
		datePrefix?: string;
		latest?: string | null;
		ui: UiConfig;
	} = $props();

	let query = $state('');
	let read = $state(new Set<string>());
	let hideRead = $state(false);
	let shownCount = $state(0);

	const PAGE = 12;

	onMount(() => {
		hideRead = loadHideRead();
	});

	// Marks are per digest date, and this component is reused when a reader moves
	// from one date to another on the same route. An effect re-reads on the way
	// in; `onMount` would leave the previous day's marks on the new day's page.
	$effect(() => {
		read = loadRead(day.date, ui.read_mark_days);
	});

	// The order the reader gets, decided before read-state is consulted. Newest
	// first by the time on the item, which is a re-order and never a filter: the
	// set here is the set the payload published, and the day's own view of what
	// matters is in the leading block rather than in this order. `orderByTime` is
	// idempotent, so a document whose seed the build already ordered pays for it
	// once and a fetched day is ordered the same way when it lands.
	const scoped = $derived(
		orderByTime(vertical ? day.items.filter((item) => item.vertical === vertical) : day.items)
	);
	// What the day published, not what is in hand. A reading route's document
	// carries a seed and fetches the rest, so counting the list here would print
	// a number that ticks up while the reader watches - and the topic pill beside
	// it already shows the day's own count for its own desk. Both halves read a
	// bounded fact off the payload instead: one desk's count, or every desk's.
	const total = $derived(
		vertical
			? (day.verticals.find((ref) => ref.id === vertical)?.count ?? scoped.length)
			: day.verticals.length > 0
				? day.verticals.reduce((sum, ref) => sum + ref.count, 0)
				: scoped.length
	);
	const needle = $derived(filterNeedle(query, ui.filter_min_chars));
	// Over `scoped`, which is derived from the `day` prop - so when a reading
	// route's fetch lands, the filter re-runs over the whole day. A list captured
	// once would narrow the document's seed for ever.
	const matched = $derived(matchItems(scoped, needle));
	const filtering = $derived(needle !== null);
	const visible = $derived(hideRead ? matched.filter((item) => !read.has(item.item_id)) : matched);

	// Chosen by the pipeline over the whole day and published on the payload.
	// The block only draws on the all-topics view: a topic route and a filter
	// both already have a subject, and a block whose leads sit outside what the
	// page is showing is a set of links that scroll to nothing. Resolved against
	// `visible` for the same reason - a lead a reader has hidden drops out of the
	// block rather than leaving a dead anchor behind.
	const leads = $derived(
		vertical === null && !filtering ? leadingStories(day.leads ?? [], visible) : []
	);
	const leading = $derived(new Set(leads.map((story) => story.item_id)));

	// The head of the published order, plus every lead. A lead is chosen across
	// the WHOLE day - measured 2026-09-01 on the 601-story day of 2026-08-31,
	// the five sat at positions 249, 285, 337, 344 and 493 - so a page holding
	// only the head is a block whose links land on nothing. They keep their own
	// published positions and the set never holds one twice: past the last lead
	// this is exactly the prefix it always was.
	const paged = $derived(
		visible.filter((item, index) => index < (shownCount || PAGE) || leading.has(item.item_id))
	);
	const remaining = $derived(Math.max(visible.length - paged.length, 0));
	const verticalNames = $derived(
		Object.fromEntries(day.verticals.map((ref) => [ref.id, ref.display_name]))
	);

	function toggleHide() {
		hideRead = !hideRead;
		setHideRead(hideRead);
	}

	// The day is drawn in parts so the leads can be painted beside the stream at
	// the wide breakpoint without leaving their place in the document. Every
	// part renders its own sections in `digest.sections` order and the parts
	// themselves are in that order too, so reordering the page is still a config
	// edit and a narrow screen sees exactly what config asked for.
	//
	// The aside stands beside the STREAM, never beside the day's controls: the
	// filter panel sticks only where it is one band, and one band needs the
	// whole content box. So it needs the leads to come before the items; any
	// other order and the day stays one column at every width.
	const leadsAt = $derived(ui.sections.indexOf('leads'));
	const streamAt = $derived(ui.sections.indexOf('items'));
	const split = $derived(leads.length > 0 && leadsAt >= 0 && streamAt > leadsAt);
	const headBefore = $derived(split ? ui.sections.slice(0, leadsAt) : ui.sections);
	const headAfter = $derived(split ? ui.sections.slice(leadsAt + 1, streamAt) : []);
	const stream = $derived(split ? ui.sections.slice(streamAt) : []);
</script>

{#snippet part(section: string)}
	{#if section === 'notice'}
		<DayNotice {day} />
	{:else if section === 'leads'}
		<LeadingStories stories={leads} />
	{:else if section === 'topics' && day.verticals.length > 0}
		<FilterBar
			label="Topics and filter"
			verticals={day.verticals}
			active={vertical}
			{total}
			pillsMax={ui.topic_pills_max}
			{datePrefix}
			bind:query
			fieldId="page-filter"
			fieldLabel="Filter today's stories"
			placeholder="Filter today's stories"
			showField={ui.show_filter}
			deskThinMax={ui.desk_thin_max}
			matchNote={filtering ? `${visible.length} of ${total}` : ''}
			noscriptNote="Filtering needs JavaScript. Every topic above is a link and still works."
		/>
	{:else if section === 'items'}
		{#if day.items.length === 0}
			<EmptyDay date={day.date} {latest} />
		{:else if matched.length === 0}
			<p class="py-12 text-base text-text-secondary">
				Nothing on today's page matches &ldquo;{query}&rdquo;.
			</p>
		{:else}
			{#if read.size > 0}
				<div class="flex justify-end pt-3">
					<button
						type="button"
						onclick={toggleHide}
						aria-pressed={hideRead}
						class="min-h-11 text-sm text-text-tertiary hover:text-accent"
					>
						{hideRead ? 'Show everything' : 'Hide what I have read'}
					</button>
				</div>
			{/if}

			{#if visible.length === 0}
				<p class="py-12 text-base text-text-secondary">
					You have read everything here today.
				</p>
			{:else}
				<TimeRail rows={railRows(paged, day.date, ui.rail_group_minutes)}>
					{#snippet story(item: DigestItem)}
						<DigestItemView
							{item}
							verticalName={verticalNames[item.vertical] ?? item.vertical}
							showMark={ui.source_mark}
							read={read.has(item.item_id)}
							onRead={() => (read = markRead(item.item_id, read, day.date))}
						/>
					{/snippet}
				</TimeRail>

				{#if remaining > 0}
					<button
						type="button"
						onclick={() => (shownCount = (shownCount || PAGE) + PAGE)}
						class="min-h-11 w-full py-6 text-base text-accent hover:underline"
					>
						Show {remaining} more
					</button>
				{/if}
			{/if}

			{#if read.size > 0}
				<p class="pt-6 text-sm text-text-tertiary">
					<button
						type="button"
						onclick={() => (read = forgetAll(day.date))}
						class="hover:text-accent"
					>
						Forget what I have read
					</button>
				</p>
			{/if}
		{/if}
	{/if}
{/snippet}

<div class="day">
	<div class="day-head">
		{#each headBefore as section (section)}
			{@render part(section)}
		{/each}
	</div>

	{#if split}
		<div class="day-aside">
			<LeadingStories stories={leads} />
		</div>
		<div class="day-head">
			{#each headAfter as section (section)}
				{@render part(section)}
			{/each}
		</div>
		<div class="day-stream">
			{#each stream as section (section)}
				{@render part(section)}
			{/each}
		</div>
	{/if}
</div>
