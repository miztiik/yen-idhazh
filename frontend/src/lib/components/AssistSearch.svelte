<script lang="ts">
	/** One tertiary line, not a search field.
	 *
	 * A search field promises instant results. This one promises a download, so
	 * it says so in the same breath as the offer - before anything is fetched,
	 * with the real number rather than a rounded guess.
	 *
	 * Everything here is secondary by construction. Delete the model directory
	 * and this control reports itself unavailable; the archive above it is
	 * unchanged, and so is every digest assertion on the page.
	 *
	 * **It reads the month index, and it says which months it read.** The page
	 * used to carry every committed day so this component could reach the
	 * vectors inside them. It now fetches `assist.search_months` shards and
	 * prints the months it searched next to the box - a reader who gets nothing
	 * back has to be able to tell "never published" from "not in this month".
	 *
	 * **A result is rendered from the day it names**, through the same component
	 * the digest itself uses, so the result list is not a second place where
	 * fetched web text reaches a page. Until that day arrives, and if it never
	 * does, the result is the title, the date and the topic the index carried.
	 */
	import { DOWNLOAD_MB, embedQuery, supported, type AssistState } from '$lib/assist/loader';
	import { ENCODER_DIMENSIONS } from '$lib/assist/encoder';
	import { loadIndex, loadVectors } from '$lib/assist/index';
	import { itemOf, loadDay } from '$lib/assist/day';
	import {
		rank,
		searchable,
		type RankOptions,
		type SearchableMonth,
		type SearchHit
	} from '$lib/assist/search';
	import type { DigestDay } from '$lib/payload/types';
	import DigestItem from './DigestItem.svelte';
	import { monthName, plural, shortDate } from '$lib/format';
	import { base } from '$app/paths';

	// Every knob comes from `config/idhazh.json` through the route's load, so
	// nothing here decides how many months to read, how many results to show, or
	// how close is close enough.
	let {
		months,
		verticalNames = {},
		assist: settings
	}: {
		months: string[];
		verticalNames?: Record<string, string>;
		assist: { similarity_floor: number; result_limit: number; search_months: number };
	} = $props();

	const ranking: RankOptions = $derived({
		limit: settings.result_limit,
		minScore: settings.similarity_floor
	});

	let assist = $state<AssistState>({ status: 'idle' });
	let query = $state('');
	let hits = $state<SearchHit[]>([]);
	let searched = $state(false);
	let scope = $state<SearchableMonth[]>([]);
	// One entry per result day, so a re-render sees a day the moment it lands.
	let dayPayloads = $state<Record<string, DigestDay | null>>({});

	const available = $derived(months.length > 0);
	const searchedCount = $derived(
		scope.reduce(
			(count, month) => count + month.index.entries.filter((entry) => entry.vector !== null).length,
			0
		)
	);
	// Oldest to newest, because that is the way a range reads out loud.
	const scopeNames = $derived(scope.map((month) => monthName(month.index.month)).reverse());
	const scopeSentence = $derived(
		scopeNames.length === 0
			? ''
			: `Searching ${
					scopeNames.length === 1
						? scopeNames[0]
						: `${scopeNames[0]} to ${scopeNames[scopeNames.length - 1]}`
				} - ${plural(searchedCount, 'story', 'stories')}.` +
				(scope.length < months.length ? ' Older months are not searched.' : '')
	);

	/** Read the newest `search_months` shards, and keep the ones that can be searched. */
	async function readScope(): Promise<SearchableMonth[]> {
		const wanted = months.slice(0, Math.max(settings.search_months, 1));
		const ready: SearchableMonth[] = [];
		for (const month of wanted) {
			const index = await loadIndex(month);
			if (!index || !searchable(index, ENCODER_DIMENSIONS)) continue;
			const vectors = await loadVectors(month);
			if (!vectors) continue;
			ready.push({ index, vectors });
		}
		return ready;
	}

	async function enable() {
		if (!supported()) {
			assist = { status: 'unavailable', reason: 'this browser cannot run the encoder' };
			return;
		}
		// Before the download rather than after it. A reader whose stories were
		// written by a different encoder cannot be helped by fetching this one, and
		// neither can a reader whose vectors never arrived - so both get the
		// sentence instead of the 43 MB. One line, in place of the offer.
		scope = await readScope();
		if (scope.length === 0) {
			assist = {
				status: 'unavailable',
				reason: 'these stories cannot be searched on this device'
			};
			return;
		}
		assist = { status: 'loading' };
		try {
			await embedQuery('warm');
			assist = { status: 'ready' };
		} catch (error) {
			console.error('[assist] the encoder did not load', error);
			assist = { status: 'unavailable', reason: 'the encoder did not load' };
		}
	}

	/** Fetch the day behind every result on screen. Once each, never twice. */
	async function fetchDays(shown: SearchHit[]) {
		const dates = [...new Set(shown.map((hit) => hit.entry.date))];
		await Promise.all(
			dates.map(async (date) => {
				const day = await loadDay(date);
				dayPayloads = { ...dayPayloads, [date]: day };
			})
		);
	}

	async function run(event: SubmitEvent) {
		event.preventDefault();
		const text = query.trim();
		if (!text || assist.status !== 'ready') return;
		try {
			hits = rank(scope, await embedQuery(text), ranking);
			searched = true;
			void fetchDays(hits);
		} catch (error) {
			console.error('[assist] the search did not run', error);
			assist = { status: 'unavailable', reason: 'the search did not run' };
		}
	}
</script>

{#if available}
	<section class="mt-10 border-t border-rule pt-4 text-sm" data-assist>
		{#if assist.status === 'idle'}
			<p class="text-muted">
				<button
					type="button"
					onclick={enable}
					class="underline underline-offset-4 hover:text-ink focus-visible:outline-2"
				>
					Search this archive on your device
				</button>
				<span class="ms-1">
					- a {DOWNLOAD_MB} MB one-time download. Nothing you type leaves your browser.
				</span>
			</p>
		{:else if assist.status === 'loading'}
			<p class="text-muted">Loading the encoder, once. This is the {DOWNLOAD_MB} MB.</p>
		{:else if assist.status === 'unavailable'}
			<p class="text-muted" data-assist-unavailable>
				Search is unavailable here - {assist.reason}.
			</p>
		{:else}
			<form onsubmit={run} class="flex gap-2">
				<label class="sr-only" for="assist-query">Search this archive</label>
				<input
					id="assist-query"
					bind:value={query}
					type="search"
					placeholder="What are you looking for?"
					class="flex-1 rounded-[--radius-md] border border-rule bg-surface px-3 py-2"
				/>
				<button
					type="submit"
					class="rounded-[--radius-md] border border-rule px-3 py-2 hover:text-ink"
				>
					Search
				</button>
			</form>

			<p class="mt-2 text-[0.8125rem] text-text-tertiary" data-assist-scope>{scopeSentence}</p>

			{#if searched && hits.length === 0}
				<p class="mt-3 text-muted">Nothing in the archive is close to that.</p>
			{:else if hits.length > 0}
				<h2 class="sr-only">Search results</h2>
				<ul class="mt-3" data-assist-results>
					{#each hits as hit (hit.entry.date + hit.entry.item_id)}
						{@const item = itemOf(dayPayloads[hit.entry.date] ?? null, hit.entry.item_id)}
						<li data-assist-date={hit.entry.date}>
							{#if item}
								<p class="pt-3 text-[0.8125rem] text-text-tertiary">
									<a href="{base}/{hit.entry.date}/#{hit.entry.item_id}" class="hover:underline">
										{shortDate(hit.entry.date)}
									</a>
								</p>
								<DigestItem
									{item}
									verticalName={verticalNames[item.vertical] ?? item.vertical}
									level={3}
									showVertical={false}
									showMark={false}
								/>
							{:else}
								<p class="border-b border-rule py-3">
									<a
										href="{base}/{hit.entry.date}/#{hit.entry.item_id}"
										class="text-[1.0625rem] text-accent hover:underline"
									>
										{hit.entry.title}
									</a>
									<span class="mt-1 block text-[0.8125rem] text-text-tertiary">
										{shortDate(hit.entry.date)} - {verticalNames[hit.entry.vertical] ??
											hit.entry.vertical}
									</span>
								</p>
							{/if}
						</li>
					{/each}
				</ul>
			{/if}
		{/if}
	</section>
{/if}
