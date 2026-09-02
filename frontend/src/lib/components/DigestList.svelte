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
	import { restoreAnchor } from '$lib/assist/day';
	import { filterNeedle, leadingStories, matchItems, orderByTime, railRows } from '$lib/day-shape';
	import type { UiConfig } from '$lib/server/config';
	import type { DigestDay, DigestItem } from '$lib/payload/types';
	import { forgetAll, loadHideRead, loadRead, markRead, setHideRead } from '$lib/readstate';
	import { onMount, tick } from 'svelte';

	let {
		day,
		vertical = null,
		datePrefix = '',
		latest = null,
		settled = true,
		ui
	}: {
		day: DigestDay;
		vertical?: string | null;
		datePrefix?: string;
		latest?: string | null;
		/** Whether the list in hand is everything this page will ever hold. False
		 * while a reading route is still fetching the stories past its seed, which
		 * is the one moment a story that is on its way looks like a story that was
		 * never here. */
		settled?: boolean;
		ui: UiConfig;
	} = $props();

	let query = $state('');
	let read = $state(new Set<string>());
	let hideRead = $state(false);
	let shownCount = $state(0);
	/** The story a reader's own address named, or the empty string.
	 *
	 * Read here rather than passed in, because the pager is the only thing that
	 * can reach it: a browser honours a fragment once and a story past the first
	 * page is not an element when it looks, so the reader lands at the top of the
	 * day with nothing focused. Empty on the server, so a prerendered document is
	 * exactly what it always was.
	 */
	let wanted = $state('');
	/** The last fragment already scrolled to. Deliberately not `$state`: it stops
	 * the page yanking itself back to the same story every time the list is
	 * re-derived, and nothing renders it. */
	let restored = '';

	const PAGE = 12;

	onMount(() => {
		hideRead = loadHideRead();
		const readHash = () => (wanted = window.location.hash.replace(/^#/, ''));
		readHash();
		window.addEventListener('hashchange', readHash);
		return () => window.removeEventListener('hashchange', readHash);
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
	//
	// And it reaches the story a reader's own address named. `/<date>/#<item id>`
	// is a published reader address, so a pager that stops at twelve makes every
	// story past the first page unaddressable - measured 2026-09-02 on the
	// 627-story day of 2026-09-01, 610 of 627 addresses landed the reader at the
	// top of the day with nothing focused. Nothing else sees this: `reach` is
	// zero with no fragment, so the server draws the same twelve it always drew
	// and so does every reader who followed an ordinary link. A lead is zero too,
	// because the line above already draws it - reaching for one would page the
	// whole stream down to its position for a click that never needed it.
	const reach = $derived(
		wanted === '' || leading.has(wanted)
			? 0
			: visible.findIndex((item) => item.item_id === wanted) + 1
	);
	const shown = $derived(Math.max(shownCount || PAGE, reach));
	const paged = $derived(
		visible.filter((item, index) => index < shown || leading.has(item.item_id))
	);
	const remaining = $derived(Math.max(visible.length - paged.length, 0));
	// A fragment naming a story this page never draws. `scoped` rather than
	// `visible`, so a story the reader has hidden or filtered out is not reported
	// as absent - it is here, and the controls to bring it back are on screen.
	// Only once the list in hand is the whole list: a story still on its way is
	// not a story that was never here.
	const missing = $derived(
		settled && wanted !== '' && !scoped.some((item) => item.item_id === wanted)
	);
	const verticalNames = $derived(
		Object.fromEntries(day.verticals.map((ref) => [ref.id, ref.display_name]))
	);

	// The pager has just drawn a story the browser already looked for and did not
	// find, so the fragment is honoured again now that the element exists. Once
	// per fragment: a reader who then hides what they have read must not be thrown
	// back up the page.
	$effect(() => {
		if (reach === 0 || restored === wanted) return;
		const target = wanted;
		void tick().then(() => {
			if (restoreAnchor(`#${target}`)) restored = target;
		});
	});

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
		<DayNotice {day} count={total} />
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
						onclick={() => (shownCount = shown + PAGE)}
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
		<!-- A link that named a story this page does not have. The region is here on
		     every page, empty ones included: a live region has to be in the document
		     before its text changes or nothing announces it. Silence was the old
		     answer - the reader was dropped at the top of the day with no story
		     focused and nothing said. -->
		<div aria-live="polite" data-anchor-missing={missing ? 'yes' : 'no'}>
			{#if missing}
				<p class="pb-4 text-sm text-text-secondary">
					The story that link names is not on this page.
				</p>
			{/if}
		</div>
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
