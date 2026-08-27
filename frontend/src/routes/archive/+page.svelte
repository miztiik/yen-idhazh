<script lang="ts">
	/** The archive: one list of stories, newest first, over a compact row of days.
	 *
	 * The stories are fetched a month at a time rather than inlined. Everything
	 * this page renders from its own data - the day row, the counts, the topic
	 * names - grows per day or per month; nothing grows per story. That is the
	 * point of the change: the page used to carry every committed day whole.
	 *
	 * The eager payloads below are still here for on-device search, which is
	 * unchanged. They leave in their own commit, so either half can be undone.
	 */
	import { base } from '$app/paths';
	import { longDate, plural, shortDate } from '$lib/format';
	import AssistSearch from '$lib/components/AssistSearch.svelte';
	import { loadMonth } from '$lib/assist/index';
	import type { SearchIndexEntry } from '$lib/payload/types';
	import { onMount } from 'svelte';

	let { data } = $props();

	let entries = $state<SearchIndexEntry[]>([]);
	let loadedMonths = $state<string[]>([]);
	let shown = $state(0);
	let status = $state<'idle' | 'loading' | 'ready' | 'unavailable'>('idle');

	const page = $derived(data.ui.archive_page_size);
	const listed = $derived(entries.slice(0, shown));
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

		<h2 class="mt-8 text-[1.0625rem] font-semibold text-text">Stories</h2>

		<noscript>
			<p class="mt-1 text-[0.9375rem] text-text-secondary">
				The story list needs JavaScript. The days above work without it.
			</p>
		</noscript>

		{#if status === 'unavailable'}
			<p class="mt-1 text-[0.9375rem] text-text-secondary" data-story-list="unavailable">
				The story list could not be loaded. Open a day above to read it.
			</p>
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

	<AssistSearch days={data.payloads} assist={data.assist} />
</section>
