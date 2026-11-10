<script lang="ts">
	/** Keep archive browsing, date constraints and submitted answers in one list. */
	import { base } from '$app/paths';
	import { onMount } from 'svelte';
	import ArchiveSearch from '$lib/components/ArchiveSearch.svelte';
	import DigestItem from '$lib/components/DigestItem.svelte';
	import { itemOf, loadDay } from '$lib/assist/day';
	import { readIndex } from '$lib/assist/index';
	import { dateInRange, monthsInRange, windowStart, type ArchiveRange } from '$lib/assist/month';
	import { dayRange, type SearchOutcome } from '$lib/assist/search';
	import { longDate, plural, shortDate } from '$lib/format';
	import type { DayForPage, SearchIndexEntry } from '$lib/payload/types';

	let { data } = $props();
	let entries = $state<SearchIndexEntry[]>([]);
	let shown = $state(0);
	let nextMonth = $state(0);
	let status = $state<'idle' | 'loading' | 'ready' | 'unavailable'>('idle');
	let results = $state<SearchOutcome | null>(null);
	let dayPayloads = $state<Record<string, DayForPage | null>>({});
	let range = $state<ArchiveRange>({ from: '', to: '' });
	let initial = $state(true);
	let attempt = 0;
	let heading: HTMLHeadingElement;
	let scrollY = $state(0);
	let innerHeight = $state(0);
	const earliest = $derived(data.months.length ? `${data.months[data.months.length - 1]}-01` : '');
	const pageSize = $derived(data.ui.archive_page_size);
	const browseRange = $derived(initial && data.latest
		? { from: windowStart(data.latest, data.windowDays), to: data.latest }
		: range);
	const browseMonths = $derived(monthsInRange(data.months, browseRange));
	const rows = $derived(results === null ? entries.slice(0, shown) : results.hits.map((hit) => hit.entry));
	const more = $derived(results === null && (shown < entries.length || nextMonth < browseMonths.length));
	const showTop = $derived(innerHeight > 0 && scrollY > innerHeight * data.topViewports);
	const rangeLabel = $derived(
		range.from && range.to ? dayRange(range.from, range.to)
			: range.from ? `From ${longDate(range.from)}`
				: range.to ? `Through ${longDate(range.to)}` : 'All dates'
	);

	async function showMore() {
		if (status === 'loading') return;
		const mine = ++attempt;
		status = 'loading';
		const wanted = shown + pageSize;
		// Each action opens at most the configured month count, even for sparse dates.
		let remaining = data.assist.search_months;
		while (entries.length < wanted && nextMonth < browseMonths.length && remaining > 0) {
			const month = browseMonths[nextMonth]!;
			const index = await readIndex(month, fetch, 'no-cache');
			if (mine !== attempt) return;
			if (index === null) {
				status = 'unavailable';
				return;
			}
			nextMonth += 1;
			remaining -= 1;
			entries = [...entries, ...index.entries.filter((entry) => dateInRange(entry.date, browseRange))];
		}
		shown = Math.min(wanted, entries.length);
		status = 'ready';
	}

	function browse(selected: ArchiveRange) {
		attempt += 1;
		initial = false;
		range = selected;
		results = null;
		dayPayloads = {};
		entries = [];
		shown = 0;
		nextMonth = 0;
		status = 'idle';
		void showMore();
	}

	async function answer(outcome: SearchOutcome, selected: ArchiveRange) {
		const mine = ++attempt;
		results = outcome;
		range = selected;
		dayPayloads = {};
		status = 'ready';
		const dates = [...new Set(outcome.hits.map((hit) => hit.entry.date))];
		await Promise.all(dates.map(async (date) => {
			const day = await loadDay(date, (input, init) => fetch(input, { ...init, cache: 'no-cache' }), true);
			if (mine === attempt) dayPayloads = { ...dayPayloads, [date]: day };
		}));
	}

	function goTop() {
		heading.focus({ preventScroll: true });
		window.scrollTo({
			top: 0,
			behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'
		});
	}

	onMount(() => {
		if (data.months.length > 0) void showMore();
	});
</script>

<svelte:window bind:scrollY bind:innerHeight />
<svelte:head><title>Search our archives &mdash; {data.ui.site_title}</title></svelte:head>

<section class="archive">
	<h1 bind:this={heading} tabindex="-1" class="text-3xl font-semibold text-text">Search our archives</h1>
	<ArchiveSearch months={data.months} assist={data.assist} {earliest} latest={data.latest}
		onResults={(outcome, selected) => void answer(outcome, selected)} onBrowse={browse} />

	<section class="answers" aria-labelledby="archive-results">
		<h2 id="archive-results" class="text-lg font-semibold text-text">
			{results !== null ? 'Search results' : initial ? 'Latest stories' : 'Stories'}
		</h2>
		{#if results !== null}
			<p class="caption" data-story-scope>
				{plural(results.hits.length, 'result', 'results')} for "{results.query}" - {rangeLabel}.
				{results.capped ? 'Showing the closest matches.' : ''}
				{results.limited ? `Search coverage: ${results.scope}.` : ''}
			</p>
			{#if results.partial}
				<p class="caption" role="status" data-search-partial>
					Some requested dates could not be searched. Try Search again.
				</p>
			{/if}
		{:else if !initial}
			<p class="caption" data-story-scope>{rangeLabel} - newest first.</p>
		{/if}

		{#if rows.length > 0}
			<ul class="story-list" data-story-list="rows">
				{#each rows as entry (`${entry.date}-${entry.item_id}`)}
					{@const item = results === null ? null : itemOf(dayPayloads[entry.date] ?? null, entry.item_id)}
					{@const href = `${base}/${entry.date}/#${entry.item_id}`}
					<li data-story-date={entry.date}>
						{#if item}
							<DigestItem {item} numberFormat={data.ui.number_format}
								storyChartGeometry={data.ui.story_chart_geometry}
								chartTickDensity={data.ui.chart_tick_density}
								verticalName={item.vertical} level={3} showVertical={false} showMark={false}
								day={{ date: entry.date, href }} />
						{:else}
							<div class="story-row">
								<a {href} class="story-title">{entry.title}</a>
								<p class="caption">{shortDate(entry.date)}</p>
							</div>
						{/if}
					</li>
				{/each}
			</ul>
		{:else if results !== null}
			<p class="empty" data-search-empty>
				{results.partial
					? 'No matches in the dates that could be searched.'
					: results.searched === 0
						? 'No searchable stories in these dates.'
						: 'No matching stories. Try different words or dates.'}
			</p>
		{:else if data.months.length === 0}
			<p class="empty" data-story-list="empty">Nothing has been published yet.</p>
		{:else if status === 'loading'}
			<p class="empty" role="status">Loading stories.</p>
		{:else if status === 'ready'}
			<p class="empty" data-story-list="empty">No stories loaded for these dates.</p>
		{/if}

		{#if status === 'unavailable' && results === null}
			<p class="empty" role="status">The stories could not be loaded.</p>
			<button type="button" class="more" onclick={() => void showMore()}>Try again</button>
		{:else if more}
			<button type="button" class="more" onclick={() => void showMore()}
				disabled={status === 'loading'} data-story-more>
				{status === 'loading' ? 'Loading stories' : 'Show more stories'}
			</button>
		{/if}
	</section>
</section>

{#if showTop}
	<button class="back-to-top" type="button" aria-label="Back to top" onclick={goTop} data-archive-top>
		<span aria-hidden="true">^</span> Top
	</button>
{/if}

<style>
	.archive { padding-block: var(--space-6) var(--space-8); }
	h1 { text-wrap: balance; }
	.answers { margin-block-start: var(--space-6); }
	.caption {
		margin-block-start: var(--space-1);
		color: var(--color-text-secondary);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		overflow-wrap: anywhere;
	}
	.story-list { margin-block-start: var(--space-3); }
	.story-row {
		padding-block: var(--space-4);
		border-block-end: 1px solid var(--color-rule);
	}
	.story-title {
		color: var(--color-text);
		font-size: var(--text-lg);
		line-height: var(--leading-lg);
		overflow-wrap: anywhere;
	}
	.story-title:hover { color: var(--color-accent); text-decoration: underline; }
	.empty {
		margin-block-start: var(--space-4);
		color: var(--color-text-secondary);
		font-size: var(--text-base);
		line-height: var(--leading-base);
	}
	.more {
		min-block-size: var(--space-7);
		margin-block-start: var(--space-5);
		color: var(--color-accent);
		font-size: var(--text-base);
		line-height: var(--leading-base);
	}
	.more:hover:not(:disabled) { text-decoration: underline; }
	.more:disabled { color: var(--color-text-secondary); }
	.back-to-top {
		position: fixed;
		inset-block-end: calc(var(--space-4) + env(safe-area-inset-bottom));
		inset-inline-end: calc(var(--space-4) + env(safe-area-inset-right));
		display: flex;
		align-items: center;
		gap: var(--space-2);
		min-block-size: var(--space-7);
		padding-inline: var(--space-4);
		border: 1px solid var(--color-rule-strong);
		border-radius: var(--radius-full);
		background: var(--color-surface-raised);
		box-shadow: var(--shadow-md);
		color: var(--color-text-secondary);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
	}
	.back-to-top:hover { border-color: var(--color-accent); color: var(--color-accent); }
</style>
