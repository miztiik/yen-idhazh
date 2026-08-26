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
	 */
	import { DOWNLOAD_MB, embedQuery, supported, type AssistState } from '$lib/assist/loader';
	import { rank, type SearchHit } from '$lib/assist/search';
	import type { DigestDay } from '$lib/payload/types';
	import { base } from '$app/paths';

	let { days }: { days: DigestDay[] } = $props();

	let assist = $state<AssistState>({ status: 'idle' });
	let query = $state('');
	let hits = $state<SearchHit[]>([]);
	let searched = $state(false);

	// Truthiness, not `!== null`. A payload written before the embeddings block
	// existed has no key at all, and `undefined !== null` would offer a reader the
	// whole download for an archive that could not be searched. No figure in this
	// sentence on purpose: it said 33 MB while the offer below said 43, and
	// `DOWNLOAD_MB` is the one that is measured against the committed files.
	const available = $derived(days.some((day) => Boolean(day.embeddings)));

	async function enable() {
		if (!supported()) {
			assist = { status: 'unavailable', reason: 'this browser cannot run the encoder' };
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

	async function run(event: SubmitEvent) {
		event.preventDefault();
		const text = query.trim();
		if (!text || assist.status !== 'ready') return;
		try {
			hits = rank(days, await embedQuery(text));
			searched = true;
		} catch (error) {
			console.error('[assist] the search did not run', error);
			assist = { status: 'unavailable', reason: 'the search did not run' };
		}
	}
</script>

{#if available}
	<section class="mt-10 border-t border-rule pt-4 text-sm">
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
			<p class="text-muted">Search is unavailable here - {assist.reason}.</p>
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

			{#if searched && hits.length === 0}
				<p class="mt-3 text-muted">Nothing in the archive is close to that.</p>
			{:else if hits.length > 0}
				<ol class="mt-3 space-y-2">
					{#each hits as hit (hit.item.item_id + hit.date)}
						<li>
							<a
								href="{base}/{hit.date}/"
								class="underline underline-offset-4 hover:text-ink"
							>
								{hit.item.title}
							</a>
							<span class="text-muted"> - {hit.date}</span>
						</li>
					{/each}
				</ol>
			{/if}
		{/if}
	</section>
{/if}
