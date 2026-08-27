<script lang="ts">
	/** The archive's search control: one field, one gesture, one sentence.
	 *
	 * **The field is always there and always typeable.** It used to be a link
	 * that enabled a search box. Nobody wants to enable anything; they want an
	 * answer. So a reader types the question first and clicks Search once, and
	 * that one click fetches the vectors, downloads the encoder and runs the
	 * query that was already in the box.
	 *
	 * **The model's state is a sentence, never a dot.** Five of them: not
	 * downloaded, downloading, ready, the encoder changed since last time, and
	 * this browser cannot run it. A dot is colour on its own unless it carries a
	 * word, and once it carries a word it is a sentence.
	 *
	 * **Progress is bytes, and it stops when the measurement stops.** The count
	 * is the library's own, so it covers the encoder's files and not the ONNX
	 * runtime behind them. When the weights land the counter can no longer see
	 * anything, so it gives up and prints a word rather than animating over a
	 * number it does not have.
	 *
	 * **A stop is offered throughout, and it leaves the page exactly as it was.**
	 * Nothing greys out while the download runs, the story list above stays
	 * live, and a failed download offers a retry rather than turning the feature
	 * off for the rest of the page's life.
	 *
	 * **The results are not rendered here.** They replace the contents of the
	 * one story list this page already has, which is what makes that list the
	 * search's empty state as well. Two lists would leave a reader working out
	 * which one answered them.
	 *
	 * Everything here is secondary by construction. Delete the model directory
	 * and this control reports itself unavailable; the archive above it is
	 * unchanged, and so is every digest assertion on the page.
	 */
	import { onMount } from 'svelte';
	import {
		cachedEncoder,
		DOWNLOAD_MB,
		embedQuery,
		supported,
		type CachedEncoder,
		type EncoderProgress
	} from '$lib/assist/loader';
	import { loadIndex, loadVectors } from '$lib/assist/index';
	import type { MonthIndex } from '$lib/assist/month';
	import {
		dayRange,
		rank,
		readScope,
		searchedDays,
		type RankOptions,
		type SearchableMonth,
		type SearchOutcome
	} from '$lib/assist/search';
	import { plural } from '$lib/format';

	// Every knob comes from `config/idhazh.json` through the route's load, so
	// nothing here decides how many months to read, how many results to show, or
	// how close is close enough.
	let {
		months,
		assist: settings,
		onResults
	}: {
		months: string[];
		assist: {
			similarity_floor: number;
			result_limit: number;
			search_months: number;
			search_min_days: number;
		};
		/** Hand the page one search, or null to give it its story list back. */
		onResults: (outcome: SearchOutcome | null) => void;
	} = $props();

	const ranking: RankOptions = $derived({
		limit: settings.result_limit,
		minScore: settings.similarity_floor
	});

	/** What the block is doing right now. Each one is a sentence a reader reads. */
	type Phase =
		| { name: 'offer' }
		| { name: 'working'; progress: EncoderProgress }
		/** The download did not finish. One flaky connection, and a way back. */
		| { name: 'failed' }
		/** Nothing to retry: this browser, or these stories, cannot do it. */
		| { name: 'blocked'; reason: string };

	let phase = $state<Phase>({ name: 'offer' });
	let cached = $state<CachedEncoder>('unknown');
	let held = $state(false);
	let query = $state('');
	let indexes = $state<MonthIndex[]>([]);
	// Not reactive: nothing on screen is a function of the raw vectors.
	let scope: SearchableMonth[] = [];
	// Which download the sentence is allowed to describe. Bumped by a stop, by
	// every new search, and by a failure, so a file that lands after any of those
	// is dropped rather than reviving a state the reader was taken out of.
	let attempt = 0;

	const searchedCount = $derived(
		indexes.reduce(
			(count, index) => count + index.entries.filter((entry) => entry.vector !== null).length,
			0
		)
	);
	// Days, not month names. The scope is a floor of days filled by whole shards,
	// so a month name over a partial month would name thirty days and hold one.
	const days = $derived(searchedDays(indexes));
	const scopeLabel = $derived(
		days.length === 0 ? '' : dayRange(days[0]!, days[days.length - 1]!)
	);
	const scopeSentence = $derived(
		scopeLabel === ''
			? ''
			: `Searching ${scopeLabel} - ${plural(searchedCount, 'story', 'stories')}.` +
				(indexes.length < months.length ? ' Older stories are not searched.' : '')
	);

	/** Mebibytes to one place, which is the precision a reader can use. */
	function megabytes(bytes: number): string {
		return (bytes / 1024 / 1024).toFixed(1);
	}

	const stateSentence = $derived.by(() => {
		if (phase.name === 'blocked') {
			return `Search is unavailable here - ${phase.reason}. Everything above still works.`;
		}
		if (phase.name === 'failed') {
			return 'Search is unavailable right now - the download did not finish.';
		}
		if (phase.name === 'working') {
			return phase.progress.loaded > 0 && !phase.progress.landed
				? `Downloading - ${megabytes(phase.progress.loaded)} MB of ${DOWNLOAD_MB} MB.`
				: 'Getting ready to search.';
		}
		if (held || cached === 'present') {
			return 'Search runs on your device. Nothing you type leaves your browser. The download is done.';
		}
		if (cached === 'stale') {
			return `The search files changed since your last visit. The next search downloads ${DOWNLOAD_MB} MB again, once. Nothing you type leaves your browser.`;
		}
		return `Search runs on your device. The first search downloads ${DOWNLOAD_MB} MB, once. Nothing you type leaves your browser.`;
	});

	onMount(async () => {
		if (!supported()) {
			phase = { name: 'blocked', reason: 'this browser cannot run it' };
			return;
		}
		// The newest month is the one the story list above has already asked for,
		// from the same cache. A second shard is read only when that one is thin,
		// which is when it is small, and the sentence under the box can then say how
		// far back a search would reach before a reader spends anything on it.
		const ready = await readScope(
			months,
			{ months: settings.search_months, minDays: settings.search_min_days },
			loadIndex
		);
		if (ready.length === 0) {
			phase = { name: 'blocked', reason: 'these stories cannot be searched on this device' };
			return;
		}
		indexes = ready;
		cached = await cachedEncoder();
	});

	/** Fetch the vectors of every month in scope, before the encoder and not after.
	 *
	 * 2.53 MB a month against 43 MB, measured 2026-08-26 at the rate the committed
	 * days ran. A reader the big download cannot help is not asked to spend it,
	 * which is the same rule the encoder-identity check follows.
	 */
	async function readVectors(): Promise<boolean> {
		if (scope.length > 0) return true;
		const ready: SearchableMonth[] = [];
		for (const index of indexes) {
			const vectors = await loadVectors(index.month);
			if (vectors) ready.push({ index, vectors });
		}
		scope = ready;
		return ready.length > 0;
	}

	async function run() {
		const text = query.trim();
		if (!text || phase.name === 'working' || phase.name === 'blocked') return;

		const mine = ++attempt;
		phase = { name: 'working', progress: { loaded: 0, landed: false } };
		try {
			if (!(await readVectors())) {
				if (mine !== attempt) return;
				phase = { name: 'blocked', reason: 'these stories cannot be searched on this device' };
				return;
			}
			const vector = await embedQuery(text, (progress) => {
				if (mine === attempt) phase = { name: 'working', progress };
			});
			if (mine !== attempt) return;
			held = true;
			phase = { name: 'offer' };
			const hits = rank(scope, vector, ranking);
			onResults({
				query: text,
				hits,
				searched: searchedCount,
				scope: scopeLabel,
				capped: hits.length >= settings.result_limit
			});
		} catch (error) {
			console.error('[archive] the search did not run', error);
			if (mine !== attempt) return;
			// This attempt is over. Its other files are still arriving - the library
			// loads the tokenizer and the weights at the same time, and only one of
			// them failed - and each one still reports its progress. Ending the
			// attempt here is what stops the next report reviving a download the
			// reader has already been told did not finish, and taking the retry with
			// it for the rest of the page's life.
			attempt += 1;
			phase = { name: 'failed' };
		}
	}

	/** Leave the page exactly as it was.
	 *
	 * The bytes already asked for keep arriving - a browser fetch cannot be
	 * called back - and the loader holds that one request, so a second search
	 * joins it rather than starting another. What stops is the waiting.
	 */
	function stop() {
		attempt += 1;
		phase = { name: 'offer' };
	}

	function submit(event: SubmitEvent) {
		event.preventDefault();
		void run();
	}
</script>

{#if months.length > 0}
	<section class="mt-10 border-t border-rule pt-4 text-sm" data-archive-search>
		{#if phase.name !== 'blocked'}
			<form onsubmit={submit} class="flex gap-2">
				<label class="sr-only" for="archive-query">Search this archive</label>
				<input
					id="archive-query"
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
		{/if}

		<p class="mt-2 text-[0.8125rem] text-text-tertiary" data-search-state>
			{stateSentence}
			{#if phase.name === 'working'}
				<button
					type="button"
					onclick={stop}
					class="ms-1 underline underline-offset-4 hover:text-ink"
					data-search-stop
				>
					Stop
				</button>
			{:else if phase.name === 'failed'}
				<button
					type="button"
					onclick={() => void run()}
					class="ms-1 underline underline-offset-4 hover:text-ink"
					data-search-retry
				>
					Try again
				</button>
			{/if}
		</p>

		{#if phase.name !== 'blocked'}
			<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-search-scope>{scopeSentence}</p>
		{/if}
	</section>
{/if}
