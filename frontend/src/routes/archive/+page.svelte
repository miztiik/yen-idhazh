<script lang="ts">
	/** Find a story, with one answer list and optional date browsing.
	 *
	 * Typing filters loaded titles; submitted search ranks the indexed stories.
	 * Dates stay inside a native disclosure so they remain usable without
	 * JavaScript and never stand between a question and its answer.
	 */
	import { base } from '$app/paths';
	import { longDate, plural, shortDate } from '$lib/format';
	import ArchiveSearch from '$lib/components/ArchiveSearch.svelte';
	import DigestItem from '$lib/components/DigestItem.svelte';
	import { dayDate, type ArchiveMonth } from '$lib/archive-calendar';
	import { itemOf, loadDay } from '$lib/assist/day';
	import { loadMonth } from '$lib/assist/index';
	import { monthsInWindow, windowStart } from '$lib/assist/month';
	import { filterNeedle } from '$lib/day-shape';
	import type { SearchHit, SearchOutcome } from '$lib/assist/search';
	import type { DayForPage, SearchIndexEntry } from '$lib/payload/types';
	import { onMount } from 'svelte';

	let { data } = $props();

	let entries = $state<SearchIndexEntry[]>([]);
	let loadedMonths = $state<string[]>([]);
	let shown = $state(0);
	let status = $state<'idle' | 'loading' | 'ready' | 'unavailable'>('idle');
	let results = $state<SearchOutcome | null>(null);
	// One entry per result day, so a re-render sees a day the moment it lands.
	let dayPayloads = $state<Record<string, DayForPage | null>>({});
	/** What the panel's field holds. Typing narrows the stories already fetched
	 * and fetches nothing; only the Search button spends the encoder download. */
	let query = $state('');
	let topic = $state<string | null>(null);
	/** Submitted questions rank complete phrases rather than filter titles.
	 * Typing again restores loaded-title filtering. */
	let asked = $state(false);
	let searchAvailable = $state(true);
	/** How many days back the browse list reaches. The reader widens or narrows
	 * it over the presets; the loop then fetches only the months this window can
	 * hold a story from, and a story older than the window is out of the list
	 * until the window grows or a search reaches past it (Guardrail #12). */
	// svelte-ignore state_referenced_locally
	let windowDays = $state(data.window.default_days);
	// The day the window is measured back from - the newest published day, baked
	// at build time, so the window never drifts with the reader's own clock.
	// svelte-ignore state_referenced_locally
	const anchor = data.window.anchor;

	const page = $derived(data.ui.archive_page_size);
	const needle = $derived(asked ? null : filterNeedle(query, data.ui.filter_min_chars));
	const filtering = $derived(needle !== null);
	// The oldest day the window reaches, and the months it can hold a story from.
	// `windowMonths` is a newest-first prefix of `data.months`, which is what lets
	// the loop below fetch it one month at a time.
	const cutoff = $derived(windowStart(anchor, windowDays));
	const windowMonths = $derived(monthsInWindow(data.months, anchor, windowDays));
	// The browse list, narrowed by the window and by whichever of the two controls
	// a reader used. All three read the months already in hand and none asks for a
	// byte. The window is a date floor; the title filter has only the title to
	// match, because the index carries no summary.
	const browsable = $derived(
		entries.filter(
			(entry) =>
				entry.date >= cutoff &&
				(topic === null || entry.vertical === topic) &&
				(needle === null || entry.title.toLowerCase().includes(needle))
		)
	);
	const listed = $derived(browsable.slice(0, shown));
	// Every month the window reaches is in hand. It is `>=`, not `===`, because a
	// wider window loaded earlier leaves months a narrower one now filters out but
	// never unloads.
	const allWindowLoaded = $derived(loadedMonths.length >= windowMonths.length);
	const showingResults = $derived(results !== null);
	// Until every month is loaded, another page may require another shard.
	const reachable = $derived(allWindowLoaded || filtering ? browsable.length : null);
	const remaining = $derived(reachable !== null ? Math.max(reachable - listed.length, 0) : page);
	const widest = $derived(Math.max(...data.window.presets));
	// Named when the browse list is empty, so a reader can tell "nothing in this
	// window" from "nothing ever". A title filter has its own sentence below.
	const emptySentence = $derived(
		topic !== null
			? `No ${data.verticalNames[topic] ?? topic} story in the last ${plural(windowDays, 'day', 'days')}.`
			: `No story in the last ${plural(windowDays, 'day', 'days')}.`
	);

	// The rule, not a report. "Charts older than N months are deleted" reads as
	// an account of what has happened, so a reader who finds nothing missing is
	// left wondering what they cannot see - and the window is stated a year
	// before the first chart can age into it (Reader, 2026-09-13).
	const retention = $derived(
		data.retentionMonths > 0
			? `Charts are kept for ${plural(data.retentionMonths, 'month', 'months')}; ` +
					'stories and links remain.'
			: ''
	);

	const countSentence = $derived(
		results === null
			? ''
			: 'Closest matches.' +
				(results.capped ? ` Only the closest ${results.hits.length} are shown.` : '')
	);

	async function showMore() {
		if (status === 'loading') return;
		status = 'loading';
		const wanted = shown + page;
		// Bounded by the window, never by the archive: the loop reads the next month
		// the window reaches until the page is full or the window is spent. A month
		// that holds none of the current topic buys no rows, so it reads the one
		// after. `windowMonths[loadedMonths.length]` is always the next unread month,
		// because both lists are newest-first prefixes of `data.months` (Guardrail #12).
		while (browsable.length < wanted && loadedMonths.length < windowMonths.length) {
			const month = windowMonths[loadedMonths.length]!;
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

	function clearSearch() {
		query = '';
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

	/** Pick a window. It changes what the browse list holds, so it drops any
	 * search answer and starts the list at the top: a narrower window only hides
	 * months already in hand, a wider one fetches the months it now reaches, and
	 * nothing already fetched is fetched again. */
	function onWindow(days: number) {
		if (days === windowDays) return;
		windowDays = days;
		results = null;
		shown = 0;
		void showMore();
	}

	onMount(() => {
		if (data.dayCount > 0) void showMore();
	});
</script>

<svelte:head>
	<title>Archive &mdash; {data.ui.site_title}</title>
</svelte:head>

<!-- One month, as a disclosure. Rendered once here and used by the current
     year's rows and by the rows inside a prior year, so a month cannot end up
     reading two different ways depending on how old it is. -->
{#snippet monthFold(month: ArchiveMonth)}
	<details class="fold" data-archive-month={month.month}>
		<summary class="fold-summary">
			<span class="fold-name">{month.label}</span>
		</summary>
		<ul class="fold-body day-grid">
			{#each month.days as day (day)}
				{@const date = dayDate(month.month, day)}
				<li>
					<a href="{base}/{date}/" aria-label={longDate(date)}>{day}</a>
				</li>
			{/each}
		</ul>
	</details>
{/snippet}

<section class="py-6">
	<h1 class="text-xl font-semibold text-text">Archive</h1>
	{#if data.dayCount === 0}
		<p class="mt-8 text-base text-text-secondary">Nothing has been published yet.</p>
	{:else}
		<ArchiveSearch
			months={data.months}
			assist={data.assist}
			verticals={data.verticals}
			activeTopic={topic}
			total={data.stories}
			pillsMax={data.ui.topic_pills_max}
			pillMoveMin={data.ui.pill_move_min}
			bind:query
			{onResults}
			{onTopic}
			onAsk={() => (asked = true)}
			onSearchAvailability={(available) => (searchAvailable = available)}
			onType={() => {
				asked = false;
				results = null;
			}}
		/>

		<div class="answer-heading" data-archive-answer>
			<h2 class="text-lg font-semibold text-text">
				{showingResults ? 'Search results' : filtering ? 'Matching titles' : 'Recent stories'}
			</h2>
			{#if query.trim() !== '' || showingResults}
				<button
					type="button"
					onclick={clearSearch}
					class="text-sm text-accent hover:underline"
					data-search-clear
				>
					Clear search
				</button>
			{/if}
			<details class="date-browser" data-archive-dates>
				<summary class="fold-summary">Browse by date</summary>
				<nav class="days" aria-label="Published days" data-day-row>
			<ul class="recent" data-day-recent>
				{#each data.recent as entry (entry.date)}
					<li class="recent-row">
						<a href="{base}/{entry.date}/" class="recent-date">{longDate(entry.date)}</a>
						{#if entry.partial}
							<span class="recent-partial">Some stories did not finish</span>
						{/if}
					</li>
				{/each}
			</ul>

			{#each data.calendar.months as month (month.month)}
				{@render monthFold(month)}
			{/each}

			{#each data.calendar.years as year (year.year)}
				<details class="fold" data-archive-year={year.year}>
					<summary class="fold-summary">
						<span class="fold-name">{year.year}</span>
					</summary>
					<div class="fold-body">
						{#each year.months as month (month.month)}
							{@render monthFold(month)}
						{/each}
					</div>
				</details>
			{/each}
				</nav>
			</details>
		</div>

		{#if !showingResults}
			<!-- The window over the browse list. The same segmented control as the
			     operator console's, over the same preset list, so the two windowed
			     surfaces on the site read the same way. Hidden while a search answer is
			     up, because a search reads its own scope, not this window. -->
			<fieldset class="window" data-archive-window data-window-days={windowDays}>
				<legend class="window-legend">Look back</legend>
				<div class="segments">
					{#each data.window.presets as preset (preset)}
						<label
							class="segment"
							data-window-preset={preset}
							data-selected={preset === windowDays}
						>
							<input
								class="segment-input"
								type="radio"
								name="archive-window"
								value={preset}
								checked={preset === windowDays}
								onchange={() => onWindow(preset)}
							/>
							<span class="segment-days">{plural(preset, 'day', 'days')}</span>
						</label>
					{/each}
				</div>
			</fieldset>
		{/if}

		<noscript>
			<style>
				[data-archive-window] {
					display: none;
				}
			</style>
			<p class="mt-1 text-base text-text-secondary">
				Open Browse by date to read a published day. Search and the story list need JavaScript.
			</p>
		</noscript>

		{#if results !== null && results.hits.length === 0}
			<p
				class="mt-1 text-base text-text-secondary"
				data-search-empty
			>No matching stories in {results.scope}. Try different words or browse by date.</p>
		{/if}

		{#if status === 'unavailable' && !showingResults}
			<p class="mt-1 text-base text-text-secondary" data-story-list="unavailable">
				The story list could not be loaded. Browse by date to open a published day.
			</p>
		{:else if showingResults && results !== null}
			{#if results.hits.length > 0}
				<p class="mt-1 text-sm text-text-tertiary" data-story-scope>{countSentence}</p>
			{/if}
			<ul class="mt-3" data-story-list="rows">
				{#each results.hits as hit (`${hit.entry.date}-${hit.entry.item_id}`)}
					{@const item = itemOf(dayPayloads[hit.entry.date] ?? null, hit.entry.item_id)}
					{@const href = `${base}/${hit.entry.date}/#${hit.entry.item_id}`}
					<li data-story-date={hit.entry.date}>
						{#if item}
							<DigestItem
								{item}
								numberFormat={data.ui.number_format}
								storyChartGeometry={data.ui.story_chart_geometry}
								chartTickDensity={data.ui.chart_tick_density}
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
				Newest first.
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
					Show more stories
				</button>
			{/if}
		{:else if status === 'loading'}
			<p class="mt-1 text-base text-text-secondary">Loading the stories.</p>
		{:else if status === 'ready'}
			<p class="mt-1 text-base text-text-secondary" data-story-list="empty">
				{#if filtering}
					No loaded titles match "{query.trim()}".
					{#if searchAvailable}
						Press Search to find related stories.
					{:else}
						Change the filter or browse by date.
					{/if}
				{:else}
					{emptySentence}
					{#if windowDays < widest}
						<button
							type="button"
							onclick={() => onWindow(widest)}
							class="text-accent hover:underline"
							data-window-widen>Look back {plural(widest, 'day', 'days')}</button>.
					{/if}
					{#if searchAvailable}
						Press Search to find related stories.
					{:else}
						Browse by date to open a published day.
					{/if}
				{/if}
			</p>
		{/if}
		{#if retention}
			<p class="mt-8 text-sm text-text-tertiary" data-archive-retention>{retention}</p>
		{/if}
	{/if}
</section>

<style>
	.answer-heading {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-2) var(--space-4);
		margin-block-start: var(--space-5);
	}

	.answer-heading h2 {
		flex: 1 1 auto;
	}

	.date-browser[open] {
		flex-basis: 100%;
	}

	.days {
		margin-block: var(--space-5);
	}

	.recent-row {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-1) var(--space-3);
		padding-block: var(--space-2);
		border-block-end: 1px solid var(--color-rule);
	}

	.recent-date {
		flex: 1 1 auto;
		min-inline-size: 0;
		font-size: var(--text-base);
		color: var(--color-accent);
	}

	.recent-date:hover {
		text-decoration: underline;
	}

	/* A tinted fill, because it tells the reader something and cannot be tapped
	   (docs/concepts/design-system.md). The day link beside it is the outline. */
	.recent-partial {
		padding: var(--space-1) var(--space-2);
		border-radius: var(--radius-full);
		background: var(--tint-warn);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-secondary);
		white-space: nowrap;
	}

	/* A native disclosure, so a month opens with no script and is reachable from
	   the keyboard without a second label. */
	.fold {
		border-block-end: 1px solid var(--color-rule);
	}

	.fold-summary {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1) var(--space-3);
		min-block-size: 2.75rem;
		padding-block: var(--space-2);
		cursor: pointer;
		color: var(--color-text-secondary);
		list-style: none;
	}

	.fold-summary:hover {
		color: var(--color-text);
	}

	/* The native triangle is dropped by `display: flex` in Chrome and Safari and
	   kept in Firefox, so the mark is drawn here and the native one is turned off
	   in both. Without it a month is a line of text that gives no sign it opens. */
	.fold-summary::-webkit-details-marker {
		display: none;
	}

	.fold-summary::before {
		content: '';
		flex: none;
		inline-size: 0;
		block-size: 0;
		border-block: 0.3rem solid transparent;
		border-inline-start: 0.4rem solid currentColor;
		transition: transform var(--dur-fast) ease;
	}

	.fold[open] > .fold-summary::before,
	.date-browser[open] > .fold-summary::before {
		transform: rotate(90deg);
	}

	.fold-name {
		flex: 1 1 auto;
		min-inline-size: 0;
		font-size: var(--text-base);
	}

	.fold-body {
		padding-block-end: var(--space-3);
	}

	/* Wraps rather than scrolls: no reader-facing surface here scrolls sideways.
	   Every cell is a tap target, and the number is the whole label because the
	   summary above it already names the month - the link's accessible name
	   carries the full date for a reader who meets it out of that order. */
	.day-grid {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1);
	}

	.day-grid a {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-inline-size: 2.75rem;
		min-block-size: 2.75rem;
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-accent);
		transition: border-color var(--dur-fast) ease;
	}

	.day-grid a:hover {
		border-color: var(--color-accent);
	}

	/* A year holds months, and a month holds days. One step of indent says which
	   is inside which; the hairline says where each row ends. */
	.fold .fold {
		margin-inline-start: var(--space-3);
	}

	.fold .fold:last-child {
		border-block-end: none;
	}

	/* The window control. The same segmented pattern as the operator console's
	   `WindowControl`, so a reader who has seen one reads the other with no
	   relearning - the whole tile is the target, the tile carries the selected
	   state, and the ring is on the tile because the input is a 1px square. */
	.window {
		margin-top: var(--space-4);
		padding: var(--space-3) var(--space-4) var(--space-4);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
		box-shadow: var(--shadow-sm);
	}

	.window-legend {
		padding-inline: var(--space-2);
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}

	.segments {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
	}

	.segment {
		position: relative;
		display: flex;
		min-height: 2.75rem;
		align-items: center;
		padding: var(--space-2) var(--space-4);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-surface);
		cursor: pointer;
	}

	.segment[data-selected='true'] {
		border-color: var(--color-accent);
		background: var(--color-tint-accent);
	}

	.segment:has(.segment-input:focus-visible) {
		outline: 1px solid var(--color-focus);
		outline-offset: 1px;
	}

	.segment-input {
		position: absolute;
		width: 1px;
		height: 1px;
		margin: -1px;
		overflow: hidden;
		clip-path: inset(50%);
	}

	.segment-days {
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--color-text);
	}
</style>
