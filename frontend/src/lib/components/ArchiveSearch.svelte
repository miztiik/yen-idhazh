<script lang="ts">
	/** The archive's search control: one field, one gesture, one sentence.
	 *
	 * **The field is always there and always typeable.** It used to be a link
	 * that enabled a search box. Nobody wants to enable anything; they want an
	 * answer. So a reader types the question first and clicks Search once, and
	 * that one click fetches the vectors, downloads the encoder and runs the
	 * query that was already in the box.
	 *
	 * **The machine is not here any more.** The phases, the scope and the five
	 * state sentences moved to `$lib/assist/session` on 2026-09-24, when the day
	 * page gained a search of its own: two phase machines and two spellings of
	 * one privacy promise are how they drift apart (Guardrail #5, Guardrail #8).
	 * What is left is what belongs to this page - that the cost is spent by a
	 * named button rather than by a key, that the scope is read on arrival
	 * because this page has already fetched the same month for its list, and that
	 * the answer replaces the one story list below.
	 *
	 * **A stop is offered throughout, and it leaves the page exactly as it was.**
	 * Nothing greys out while the download runs, the story list above stays live,
	 * and a failed download offers a retry rather than turning the feature off
	 * for the rest of the page's life. `SearchState` draws both.
	 *
	 * **The results are not rendered here.** They replace the contents of the one
	 * story list this page already has, which is what makes that list the
	 * search's empty state as well. Two lists would leave a reader working out
	 * which one answered them.
	 *
	 * **The box and the list below always describe each other.** Typing narrows
	 * the stories already fetched, by title, and costs nothing. Pressing the
	 * button turns what is in the box into a question, and a question is not a
	 * substring - so the page is told, and it stops narrowing the list by the
	 * words in it until the next keystroke. Only the button spends the 43 MB, so
	 * the cost is named before it is paid.
	 *
	 * Everything here is secondary by construction. Delete the model directory
	 * and this control reports itself unavailable; the archive above it is
	 * unchanged, and so is every digest assertion on the page.
	 */
	import FilterBar from '$lib/components/FilterBar.svelte';
	import SearchState from '$lib/components/SearchState.svelte';
	import { onMount } from 'svelte';
	import {
		cachedEncoder,
		DOWNLOAD_MB,
		DOWNLOAD_MB_ELSEWHERE,
		embedQuery,
		supported,
		type CachedEncoder
	} from '$lib/assist/loader';
	import { loadIndex, loadVectors } from '$lib/assist/index';
	import {
		newSearch,
		NO_SCOPE,
		scopeSentence,
		stateSentence,
		type SearchPhase,
		type SearchScope
	} from '$lib/assist/session';
	import type { SearchOutcome } from '$lib/assist/search';
	import type { DigestVerticalRef } from '$lib/payload/types';

	// Every knob comes from `config/idhazh.json` through the route's load, so
	// nothing here decides how many months to read, how many results to show, or
	// how close is close enough.
	let {
		months,
		assist: settings,
		verticals,
		activeTopic,
		total,
		pillsMax,
		pillMoveMin,
		query = $bindable(''),
		onResults,
		onTopic,
		onAsk,
		onType
	}: {
		months: string[];
		assist: {
			similarity_floor: number;
			result_limit: number;
			search_months: number;
			search_min_days: number;
		};
		/** Every topic the archive holds, with its whole-archive count. */
		verticals: DigestVerticalRef[];
		activeTopic: string | null;
		/** Stories in the whole archive, for the `All` pill. */
		total: number;
		pillsMax: number;
		pillMoveMin: number;
		/** What the field holds. The page reads it to narrow its browse list. */
		query?: string;
		/** Hand the page one search, or null to give it its story list back. */
		onResults: (outcome: SearchOutcome | null) => void;
		onTopic: (id: string | null) => void;
		/** The reader pressed the button, so the box now holds a question. */
		onAsk: () => void;
		/** The reader typed, so it is a filter again. */
		onType: () => void;
	} = $props();

	/** What the two origins cost. Both figures live in `assist/loader`, beside
	 * the code that fetches them; the words that print them are in `session`. */
	const COST = { here: DOWNLOAD_MB, elsewhere: DOWNLOAD_MB_ELSEWHERE };

	let phase = $state<SearchPhase>({ name: 'offer' });
	let cached = $state<CachedEncoder>('unknown');
	/** True once the encoder has answered in this tab. Held on the component
	 * rather than read off the session, so the sentence above re-reads it. */
	let held = $state(false);
	let scope = $state<SearchScope>(NO_SCOPE);

	// One session per setting set. Derived rather than built once, so a knob that
	// moved would move the session with it rather than leaving a page running on
	// the numbers it was first handed.
	const search = $derived(
		newSearch({ supported, loadIndex, loadVectors, embed: embedQuery }, settings)
	);
	const report = {
		onPhase: (next: SearchPhase) => (phase = next),
		onScope: (next: SearchScope) => (scope = next)
	};
	const sentence = $derived(stateSentence({ phase, held, cached, cost: COST }));

	onMount(async () => {
		// The newest month is the one the story list above has already asked for,
		// from the same cache. A second shard is read only when that one is thin,
		// which is when it is small, and the sentence under the box can then say how
		// far back a search would reach before a reader spends anything on it.
		await search.open(months, report);
		cached = await cachedEncoder();
	});

	async function run() {
		if (query.trim() === '' || phase.name === 'working' || phase.name === 'blocked') return;
		onAsk();
		const outcome = await search.ask(months, query, report);
		// Null is a search that did not run, and the phase already says why.
		if (outcome === null) return;
		held = true;
		onResults(outcome);
	}
</script>

<FilterBar
	label="Topics and search"
	{verticals}
	active={activeTopic}
	{total}
	{pillsMax}
	{pillMoveMin}
	linked={false}
	{onTopic}
	bind:query
	fieldId="archive-query"
	fieldLabel="Search this archive"
	placeholder="What are you looking for?"
	showField={months.length > 0 && phase.name !== 'blocked'}
	submitLabel="Search"
	onSubmit={() => void run()}
	onType={() => onType()}
	noscriptNote="Search and the topic filters need JavaScript."
/>

{#if months.length > 0}
	<SearchState
		{phase}
		{sentence}
		scope={scopeSentence(scope)}
		surface="archive"
		onStop={() => search.stop(report)}
		onRetry={() => void run()}
	/>
{/if}
