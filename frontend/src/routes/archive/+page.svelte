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
	 */
	import { base } from '$app/paths';
	import { longDate, plural, shortDate } from '$lib/format';
	import ArchiveSearch from '$lib/components/ArchiveSearch.svelte';
	import DigestItem from '$lib/components/DigestItem.svelte';
	import { itemOf, loadDay } from '$lib/assist/day';
	import { loadMonth } from '$lib/assist/index';
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

	const page = $derived(data.ui.archive_page_size);
	const listed = $derived(entries.slice(0, shown));
	// A search with no answer leaves the browse list showing. That is the whole
	// empty state, and it is why there is only one list here.
	const showingResults = $derived(results !== null && results.hits.length > 0);
	// While months are still unread, the day list is the honest count - it counts
	// the same stories the months hold. Once every month is in hand, say what
	// actually arrived.
	const reachable = $derived(
		loadedMonths.length >= data.months.length ? entries.length : data.stories
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
		while (entries.length < wanted && loadedMonths.length < data.months.length) {
			const month = data.months[loadedMonths.length]!;
			loadedMonths = [...loadedMonths, month];
			const more = await loadMonth(month);
			if (more !== null) entries = [...entries, ...more];
		}
		shown = Math.min(wanted, entries.length);
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

	onMount(() => {
		if (data.days.length > 0) void showMore();
	});
</script>

<svelte:head>
	<title>Archive &mdash; {data.ui.site_title}</title>
</svelte:head>

<section class="py-6">
	<h1 class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text">Archive</h1>
	<p class="mt-1 text-[0.9375rem] text-text-secondary" data-archive-scope>
		{plural(data.days.length, 'day', 'days')}, {plural(data.stories, 'story', 'stories')}.
		{retention}
	</p>

	{#if data.days.length === 0}
		<p class="mt-8 text-[0.9375rem] text-text-secondary">Nothing has been published yet.</p>
	{:else}
		<nav class="mt-4 flex flex-wrap gap-x-4 gap-y-2" aria-label="Published days" data-day-row>
			{#each data.days as entry (entry.date)}
				<a
					href="{base}/{entry.date}/"
					class="text-[0.8125rem] text-accent hover:underline"
					title={longDate(entry.date)}
				>
					{shortDate(entry.date)}
				</a>
			{/each}
		</nav>

		<div class="mt-8 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
			<h2 class="text-[1.0625rem] font-semibold text-text">
				{showingResults ? 'Search results' : 'Stories'}
			</h2>
			{#if showingResults}
				<button
					type="button"
					onclick={() => onResults(null)}
					class="text-[0.8125rem] text-accent hover:underline"
					data-search-clear
				>
					Show all stories
				</button>
			{/if}
		</div>

		<noscript>
			<p class="mt-1 text-[0.9375rem] text-text-secondary">
				The story list needs JavaScript. The days above work without it.
			</p>
		</noscript>

		{#if results !== null && results.hits.length === 0}
			<p
				class="mt-1 text-[0.9375rem] text-text-secondary"
				data-search-empty
			>{`Nothing in ${results.scope} is close to that.`}</p>
		{/if}

		{#if status === 'unavailable' && !showingResults}
			<p class="mt-1 text-[0.9375rem] text-text-secondary" data-story-list="unavailable">
				The story list could not be loaded. Open a day above to read it.
			</p>
		{:else if showingResults && results !== null}
			<p
				class="mt-1 text-[0.8125rem] text-text-tertiary"
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
								<a {href} class="text-[1.0625rem] text-accent hover:underline">{hit.entry.title}</a>
								<span class="mt-1 block text-[0.8125rem] text-text-tertiary">
									{shortDate(hit.entry.date)} &mdash; {data.verticalNames[hit.entry.vertical] ??
										hit.entry.vertical}
								</span>
							</p>
						{/if}
					</li>
				{/each}
			</ul>
		{:else if listed.length > 0}
			<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-story-scope>
				Showing {listed.length} of {reachable}, newest first.
			</p>
			<ul class="mt-3" data-story-list="rows">
				{#each listed as entry (`${entry.date}-${entry.item_id}`)}
					<li class="border-b border-rule py-3" data-story-date={entry.date}>
						<a
							href="{base}/{entry.date}/#{entry.item_id}"
							class="text-[1.0625rem] text-accent hover:underline"
						>
							{entry.title}
						</a>
						<p class="mt-1 text-[0.8125rem] text-text-tertiary">
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
					class="min-h-11 w-full py-6 text-[0.9375rem] text-accent hover:underline"
					data-story-more
				>
					Show {Math.min(page, remaining)} more
				</button>
			{/if}
		{:else if status === 'loading'}
			<p class="mt-1 text-[0.9375rem] text-text-secondary">Loading the stories.</p>
		{/if}
	{/if}

	<ArchiveSearch months={data.months} assist={data.assist} {onResults} />
</section>
