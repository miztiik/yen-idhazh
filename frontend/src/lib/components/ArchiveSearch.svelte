<script lang="ts">
	/** Submit one archive question and its optional UTC dates without replacing the field. */
	import { onMount } from 'svelte';
	import SearchState from '$lib/components/SearchState.svelte';
	import {
		cachedEncoder, DOWNLOAD_MB, DOWNLOAD_MB_ELSEWHERE, embedQuery, supported,
		type CachedEncoder
	} from '$lib/assist/loader';
	import { readIndex, readVectors } from '$lib/assist/index';
	import type { ArchiveRange } from '$lib/assist/month';
	import {
		newSearch, privacyNote, stateSentence, type SearchPhase, type SearchSettings
	} from '$lib/assist/session';
	import type { SearchOutcome } from '$lib/assist/search';

	let { months, assist, earliest, latest, onResults, onBrowse }: {
		months: string[];
		assist: SearchSettings;
		earliest: string;
		latest: string;
		onResults: (outcome: SearchOutcome, range: ArchiveRange) => void;
		onBrowse: (range: ArchiveRange) => void;
	} = $props();

	let query = $state('');
	let from = $state('');
	let to = $state('');
	let ready = $state(false);
	let field: HTMLInputElement;
	let dates: HTMLDetailsElement;
	let phase = $state<SearchPhase>({ name: 'offer' });
	let cached = $state<CachedEncoder>('unknown');
	let held = $state(false);
	const cost = { here: DOWNLOAD_MB, elsewhere: DOWNLOAD_MB_ELSEWHERE };
	const search = $derived(newSearch({
		supported,
		loadIndex: (month) => readIndex(month, fetch, 'no-cache'),
		loadVectors: (month) => readVectors(month, fetch, 'no-cache'),
		embed: embedQuery
	}, assist));
	const report = { onPhase: (next: SearchPhase) => (phase = next) };
	const sentence = $derived(stateSentence({ phase, held, cached, cost }));

	onMount(async () => {
		ready = true;
		if (!supported()) phase = { name: 'blocked', reason: 'this browser cannot run it' };
		cached = await cachedEncoder();
	});

	async function run(event?: SubmitEvent) {
		event?.preventDefault();
		if (!ready || phase.name === 'working') return;
		dates.open = false;
		const range = { from, to };
		if (query.trim() === '') {
			search.stop(report);
			if (!supported()) phase = { name: 'blocked', reason: 'this browser cannot run it' };
			onBrowse(range);
			return;
		}
		const outcome = await search.ask(months, query, report, range);
		if (outcome === null) return;
		held = search.held();
		onResults(outcome, range);
	}

	function clearSearch() {
		search.stop(report);
		if (!supported()) phase = { name: 'blocked', reason: 'this browser cannot run it' };
		query = '';
		onBrowse({ from, to });
		field.focus();
	}
</script>

<form class="search-form" aria-label="Search archives" onsubmit={run} data-archive-form>
	<div class="field">
		<label class="sr-only" for="archive-query">Search our archives</label>
		<input
			bind:this={field}
			id="archive-query"
			type="search"
			bind:value={query}
			placeholder="What are you looking for?"
			autocomplete="off"
			disabled={!ready || months.length === 0}
		/>
		<button
			class="clear"
			type="button"
			aria-label="Clear search"
			onclick={clearSearch}
			disabled={!ready || query === ''}
			data-search-clear
		>Clear</button>
	</div>

	<details class="dates" bind:this={dates} data-selected={Boolean(from || to)}>
		<summary>Dates</summary>
		<div class="date-panel">
			<div class="date-fields">
				<label for="archive-from">From (UTC)
					<input id="archive-from" type="date" bind:value={from}
						min={earliest || undefined} max={to || latest || undefined} disabled={!ready} />
				</label>
				<label for="archive-to">To (UTC)
					<input id="archive-to" type="date" bind:value={to}
						min={from || earliest || undefined} max={latest || undefined} disabled={!ready} />
				</label>
			</div>
			{#if from || to}
				<button class="date-clear" type="button" disabled={!ready}
					onclick={() => { from = ''; to = ''; }}>Clear dates</button>
			{/if}
		</div>
	</details>

	<button class="submit font-semibold" type="submit"
		disabled={!ready || months.length === 0 || phase.name === 'working' ||
			(phase.name === 'blocked' && query.trim() !== '')}>Search</button>
</form>

{#if phase.name !== 'offer'}
	<SearchState {phase} {sentence} surface="archive"
		onStop={() => search.stop(report)} onRetry={() => void run()} />
{/if}

<details class="search-info">
	<summary>
		On-device search{!held && cached !== 'present' ? ` - ${DOWNLOAD_MB} MB first use` : ''}
	</summary>
	<p>{privacyNote(cost)}</p>
	<p>Date changes apply with Search.
		{assist.archive_search_months === -1
			? 'Leave both dates empty to search all indexed dates.'
			: `Search covers up to ${assist.archive_search_months ?? assist.search_months} eligible months.`}
	</p>
</details>
<noscript><p class="mt-3 text-base text-text-secondary">Archive search needs JavaScript.</p></noscript>

<style>
	.search-form {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto auto;
		align-items: start;
		gap: var(--space-3);
		margin-block-start: var(--space-5);
	}
	.field {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		min-inline-size: 0;
		min-block-size: var(--space-7);
		padding-inline: var(--space-4);
		border: 1px solid var(--color-rule-strong);
		border-radius: var(--radius-md);
		background: var(--color-surface);
		color: var(--color-text-secondary);
	}
	.field:focus-within { border-color: var(--color-accent); }
	.field input {
		min-inline-size: 0;
		inline-size: 100%;
		min-block-size: var(--space-7);
		background: transparent;
		color: var(--color-text);
		font-size: var(--text-base);
		line-height: var(--leading-base);
	}
	.field input::-webkit-search-cancel-button { display: none; }
	.field input::placeholder { color: var(--color-text-secondary); }
	.clear {
		min-block-size: var(--space-7);
		color: var(--color-accent);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
	}
	.clear:disabled { visibility: hidden; }
	.submit, .dates > summary {
		display: flex;
		align-items: center;
		justify-content: center;
		min-block-size: var(--space-7);
		padding-inline: var(--space-5);
		border: 1px solid var(--color-rule-strong);
		border-radius: var(--radius-md);
		font-size: var(--text-base);
		line-height: var(--leading-base);
		cursor: pointer;
	}
	.submit {
		border-color: var(--color-accent);
		background: var(--color-accent);
		color: var(--color-on-accent);
	}
	.submit:hover:not(:disabled) { background: var(--color-accent-strong); }
	.submit:disabled {
		cursor: default;
		background: var(--color-rule-strong);
		border-color: var(--color-rule-strong);
		color: var(--color-text-secondary);
	}
	.dates { position: relative; min-inline-size: 0; }
	.dates > summary { color: var(--color-text-secondary); }
	.dates[data-selected='true'] > summary { border-color: var(--color-accent); }
	.dates[open] > summary, .dates > summary:hover { color: var(--color-accent); }
	.date-panel {
		position: absolute;
		inset-inline-end: 0;
		inline-size: var(--zone-aside);
		margin-block-start: var(--space-2);
		padding: var(--space-4);
		border: 1px solid var(--color-rule-strong);
		border-radius: var(--radius-md);
		background: var(--color-surface-raised);
		box-shadow: var(--shadow-md);
	}
	.date-fields { display: grid; gap: var(--space-3); }
	.date-fields label {
		display: grid;
		gap: var(--space-1);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
	.date-fields input {
		color-scheme: light;
		min-inline-size: 0;
		inline-size: 100%;
		min-block-size: var(--space-7);
		padding-inline: var(--space-2);
		border: 1px solid var(--color-rule-strong);
		border-radius: var(--radius-md);
		background: var(--color-surface);
		color: var(--color-text);
	}
	:global([data-theme='dark']) .date-fields input { color-scheme: dark; }
	.date-clear {
		min-block-size: var(--space-7);
		color: var(--color-accent);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
	}
	.date-clear:disabled { color: var(--color-text-secondary); cursor: default; }
	.search-info {
		margin-block-start: var(--space-3);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
	.search-info summary { width: fit-content; cursor: pointer; }
	.search-info p { margin-block-start: var(--space-2); max-inline-size: var(--measure); }
	@media (width < 640px) {
		.search-form { grid-template-columns: minmax(0, 1fr) auto; }
		.submit { grid-column: 2; grid-row: 1; padding-inline: var(--space-4); }
		.dates { grid-column: 1 / -1; }
		.dates > summary { justify-content: start; width: fit-content; }
		.date-panel { position: static; inline-size: 100%; }
		.date-fields { grid-template-columns: repeat(2, minmax(0, 1fr)); }
	}
</style>
