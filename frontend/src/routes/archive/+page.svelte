<script lang="ts">
	/** The archive: one list of stories, newest first, over a compact row of days.
	 *
	 * The stories are fetched a month at a time rather than inlined. Everything
	 * this page renders from its own data - the day row, the counts, the topic
	 * names - grows per day or per month; nothing grows per story.
	 *
	 * **There is one list, and a search replaces what is in it.** The heading
	 * changes, the count changes, and a link gives the browse list back. Two
	 * lists side by side would leave a reader working out which one answered
	 * them, and it would leave the search with no empty state - which this list
	 * already is, because a search that matches nothing leaves it exactly where
	 * it was.
	 *
	 * Search reads the same months. The page used to carry every committed day
	 * whole so search could reach the vectors inside them; it now reads the
	 * sibling vector file and fetches a day only when a result from it is shown.
	 *
	 * **The panel sits above the answer.** Until 2026-09-01 the search box was
	 * the last thing on the page, under every story it might have replaced, and
	 * the topic names were nowhere. One panel now carries the topics and the
	 * field, and the two sentences about the on-device model follow it.
	 */
	import { base } from '$app/paths';
	import { longDate, plural, shortDate } from '$lib/format';
	import ArchiveSearch from '$lib/components/ArchiveSearch.svelte';
	import DigestItem from '$lib/components/DigestItem.svelte';
	import { itemOf, loadDay } from '$lib/assist/day';
	import { loadMonth } from '$lib/assist/index';
	import { filterNeedle } from '$lib/day-shape';
	import type { SearchHit, SearchOutcome } from '$lib/assist/search';
	import type { DigestDay, SearchIndexEntry } from '$lib/payload/types';
	import { onMount } from 'svelte';

	let { data } = $props();

	let entries = $state<SearchIndexEntry[]>([]);
	let loadedMonths = $state<string[]>([]);
	let shown = $state(0);
	let status = $state<'idle' | 'loading' | 'ready' | 'unavailable'>('idle');
	let results = $state<SearchOutcome | null>(null);
	// One entry per result day, so a re-render sees a day the moment it lands.
	let dayPayloads = $state<Record<string, DigestDay | null>>({});
	/** What the panel's field holds. Typing narrows the stories already fetched
	 * and fetches nothing; only the Search button spends the encoder download. */
	let query = $state('');
	let topic = $state<string | null>(null);
	/** True from the moment the reader presses Search until they type again. A
	 * question is not a substring, so the words in the box stop narrowing the
	 * list under it - otherwise a search that found nothing would leave an empty
	 * page instead of the browse list it is supposed to fall back to. */
	let asked = $state(false);

	const page = $derived(data.ui.archive_page_size);
	const needle = $derived(asked ? null : filterNeedle(query, data.ui.filter_min_chars));
	const filtering = $derived(needle !== null);
	const topicTotals = $derived(
		Object.fromEntries(data.verticals.map((ref) => [ref.id, ref.count]))
	);
	// The browse list, narrowed by whichever of the two controls a reader used.
	// Both read the months already in hand and neither asks for a byte. Title
	// only: the index carries no summary, so there is nothing else here to match.
	const browsable = $derived(
		entries.filter(
			(entry) =>
				(topic === null || entry.vertical === topic) &&
				(needle === null || entry.title.toLowerCase().includes(needle))
		)
	);
	const listed = $derived(browsable.slice(0, shown));
	const allLoaded = $derived(loadedMonths.length >= data.months.length);
	// A search with no answer leaves the browse list showing. That is the whole
	// empty state, and it is why there is only one list here.
	const showingResults = $derived(results !== null && results.hits.length > 0);
	// While months are still unread, a count off the payload is the honest one -
	// the whole archive, or one topic's share of it, both decided at build time. A
	// title filter has no such number, so there it can only be what was read.
	const reachable = $derived(
		allLoaded || filtering
			? browsable.length
			: topic === null
				? data.stories
				: (topicTotals[topic] ?? browsable.length)
	);
	const remaining = $derived(Math.max(reachable - listed.length, 0));

	const retention = $derived(
		data.retentionMonths > 0
			? `Charts older than ${plural(data.retentionMonths, 'month', 'months')} are deleted. ` +
					'Every story and every link stays.'
			: 'Nothing here is deleted.'
	);

	// The count is over the stories that were searched, never over the archive -
	// a total taken across months this did not read would be the page claiming an
	// answer it does not hold. The cap is stated when it bites, for the same
	// reason: ten of ten is a ceiling, and printing it as a total is a lie.
	const countSentence = $derived(
		results === null
			? ''
			: `${plural(results.hits.length, 'result', 'results')} from the ` +
				`${plural(results.searched, 'story', 'stories')} searched.` +
				(results.capped ? ` Only the closest ${results.hits.length} are shown.` : '')
	);

	async function showMore() {
		if (status === 'loading') return;
		status = 'loading';
		const wanted = shown + page;
		// Counted over what the reader would actually see: with a topic pill on, a
		// month that holds none of it buys no rows, so the loop reads the next one.
		while (browsable.length < wanted && loadedMonths.length < data.months.length) {
			const month = data.months[loadedMonths.length]!;
			loadedMonths = [...loadedMonths, month];
			const more = await loadMonth(month);
			if (more !== null) entries = [...entries, ...more];
		}
		shown = Math.min(wanted, browsable.length);
		status = entries.length > 0 ? 'ready' : 'unavailable';
	}

	/** Fetch the day behind every result on screen. Once each, never twice. */
	async function fetchDays(hits: SearchHit[]) {
		const dates = [...new Set(hits.map((hit) => hit.entry.date))];
		await Promise.all(
			dates.map(async (date) => {
				const day = await loadDay(date);
				dayPayloads = { ...dayPayloads, [date]: day };
			})
		);
	}

	function onResults(outcome: SearchOutcome | null) {
		results = outcome;
		if (outcome) void fetchDays(outcome.hits);
	}

	/** `Show all stories` means all of them, so it empties the box as well as
	 * dropping the answer. Leaving the question in there would put the reader one
	 * keystroke away from a list narrowed by a sentence no title contains. */
	function showAll() {
		query = '';
		topic = null;
		asked = false;
		results = null;
	}

	/** A topic pill. It narrows the list already fetched and asks for nothing;
	 * a search answer was about every topic, so it stops describing the page. */
	function onTopic(id: string | null) {
		topic = id;
		results = null;
		if (shown === 0) void showMore();
	}

	onMount(() => {
		if (data.days.length > 0) void showMore();
	});
</script>

<svelte:head>
	<title>Archive &mdash; {data.ui.site_title}</title>
</svelte:head>

<section class="py-6">
	<h1 class="text-xl font-semibold text-text">Archive</h1>
	<p class="mt-1 text-base text-text-secondary" data-archive-scope>
		{plural(data.days.length, 'day', 'days')}, {plural(data.stories, 'story', 'stories')}.
		{retention}
	</p>

	{#if data.days.length === 0}
		<p class="mt-8 text-base text-text-secondary">Nothing has been published yet.</p>
	{:else}
		<ArchiveSearch
			months={data.months}
			assist={data.assist}
			verticals={data.verticals}
			activeTopic={topic}
			total={data.stories}
			pillsMax={data.ui.topic_pills_max}
			bind:query
			{onResults}
			{onTopic}
			onAsk={() => (asked = true)}
			onType={() => {
				asked = false;
				results = null;
			}}
		/>

		<nav class="mt-6 flex flex-wrap gap-x-4 gap-y-2" aria-label="Published days" data-day-row>
			{#each data.days as entry (entry.date)}
				<a
					href="{base}/{entry.date}/"
					class="text-sm text-accent hover:underline"
					title={longDate(entry.date)}
				>
					{shortDate(entry.date)}
				</a>
			{/each}
		</nav>

		<div class="mt-8 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
			<h2 class="text-lg font-semibold text-text">
				{showingResults ? 'Search results' : 'Stories'}
			</h2>
			{#if showingResults}
				<button
					type="button"
					onclick={showAll}
					class="text-sm text-accent hover:underline"
					data-search-clear
				>
					Show all stories
				</button>
			{/if}
		</div>

		<noscript>
			<p class="mt-1 text-base text-text-secondary">
				The story list needs JavaScript. The days above work without it.
			</p>
		</noscript>

		{#if results !== null && results.hits.length === 0}
			<p
				class="mt-1 text-base text-text-secondary"
				data-search-empty
			>{`No story from ${results.scope} is close to that.`}</p>
		{/if}

		{#if status === 'unavailable' && !showingResults}
			<p class="mt-1 text-base text-text-secondary" data-story-list="unavailable">
				The story list could not be loaded. Open a day above to read it.
			</p>
		{:else if showingResults && results !== null}
			<p
				class="mt-1 text-sm text-text-tertiary"
				data-story-scope
			>{countSentence}</p>
			<ul class="mt-3" data-story-list="rows">
				{#each results.hits as hit (`${hit.entry.date}-${hit.entry.item_id}`)}
					{@const item = itemOf(dayPayloads[hit.entry.date] ?? null, hit.entry.item_id)}
					{@const href = `${base}/${hit.entry.date}/#${hit.entry.item_id}`}
					<li data-story-date={hit.entry.date}>
						{#if item}
							<DigestItem
								{item}
								verticalName={data.verticalNames[item.vertical] ?? item.vertical}
								level={3}
								showVertical={false}
								showMark={false}
								day={{ date: hit.entry.date, href }}
							/>
						{:else}
							<p class="border-b border-rule py-3">
								<a {href} class="text-lg text-accent hover:underline">{hit.entry.title}</a>
								<span class="mt-1 block text-sm text-text-tertiary">
									{shortDate(hit.entry.date)} &mdash; {data.verticalNames[hit.entry.vertical] ??
										hit.entry.vertical}
								</span>
							</p>
						{/if}
					</li>
				{/each}
			</ul>
		{:else if listed.length > 0}
			<p class="mt-1 text-sm text-text-tertiary" data-story-scope>
				Showing {listed.length} of {reachable}, newest first.
			</p>
			<!-- The one list on the site that goes multi-column. It is a scan
			     surface - a reader here is finding the one they remember, not
			     reading the day in order - so "find it fast" outranks the ranked
			     order the digest has to protect. It splits on the width it HAS,
			     never on the viewport's. -->
			<ul class="auto-grid mt-3" style="--auto-grid-min: 22rem" data-story-list="rows">
				{#each listed as entry (`${entry.date}-${entry.item_id}`)}
					<li class="border-b border-rule py-3" data-story-date={entry.date}>
						<a
							href="{base}/{entry.date}/#{entry.item_id}"
							class="text-lg text-accent hover:underline"
						>
							{entry.title}
						</a>
						<p class="mt-1 text-sm text-text-tertiary">
							{shortDate(entry.date)} &mdash; {data.verticalNames[entry.vertical] ?? entry.vertical}
						</p>
					</li>
				{/each}
			</ul>

			{#if remaining > 0}
				<button
					type="button"
					onclick={showMore}
					disabled={status === 'loading'}
					class="min-h-11 w-full py-6 text-base text-accent hover:underline"
					data-story-more
				>
					Show {Math.min(page, remaining)} more
				</button>
			{/if}
		{:else if status === 'loading'}
			<p class="mt-1 text-base text-text-secondary">Loading the stories.</p>
		{:else if status === 'ready' && (filtering || topic !== null)}
			<p class="mt-1 text-base text-text-secondary" data-story-list="empty">
				No story on this page matches that. Press Search to look through the whole archive.
			</p>
		{/if}
	{/if}
</section>
