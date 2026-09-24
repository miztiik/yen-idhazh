<script lang="ts">
	/** The day page. Section order is config, which is the modularity story:
	 * reordering the page is a config edit, not a code change.
	 *
	 * Read-state lives here and touches nothing but appearance. The item set and
	 * its order are computed before any of it is consulted, which is what makes
	 * two readers at the same URL see the same page.
	 *
	 * **One field, two tiers.** A keystroke narrows this day by substring and
	 * fetches nothing at all - that is the common path and it stays instant and
	 * download-free. The Enter key asks a question instead, on the reader's own
	 * device, over the month shards the archive already publishes, and it can
	 * answer from days this page is not showing. The line under the panel says
	 * which of the two produced the list, and it names what the second one costs
	 * before a key can spend it (Susan, 2026-09-24). Nothing about the reading
	 * route waits on the model: a browser that cannot run it, weights that will not
	 * download and a month with no vectors all leave the day exactly as it was and
	 * say so in one sentence.
	 */
	import DayNotice from '$lib/components/DayNotice.svelte';
	import DigestItemView from '$lib/components/DigestItem.svelte';
	import EmptyDay from '$lib/components/EmptyDay.svelte';
	import FilterBar from '$lib/components/FilterBar.svelte';
	import FoundStories from '$lib/components/FoundStories.svelte';
	import LeadingStories from '$lib/components/LeadingStories.svelte';
	import SearchState from '$lib/components/SearchState.svelte';
	import { base } from '$app/paths';
	import { loadDay, restoreAnchor } from '$lib/assist/day';
	import { loadIndex, loadVectors } from '$lib/assist/index';
	import {
		cachedEncoder,
		DOWNLOAD_MB,
		DOWNLOAD_MB_ELSEWHERE,
		embedQuery,
		supported,
		type CachedEncoder
	} from '$lib/assist/loader';
	import { monthsBackFrom } from '$lib/assist/month';
	import {
		costNote,
		newSearch,
		NO_SCOPE,
		scopeSentence,
		stateSentence,
		type SearchPhase,
		type SearchScope
	} from '$lib/assist/session';
	import type { SearchHit, SearchOutcome } from '$lib/assist/search';
	import { plural } from '$lib/format';
	import {
		deskCount,
		deskOf,
		filterNeedle,
		foldedMembers,
		indexDay,
		leadingStories,
		orderByTime,
		revealed,
		shortlist
	} from '$lib/day-shape';
	import type { UiConfig } from '$lib/server/config';
	import type { DayForPage, DigestCoverage, DigestItem } from '$lib/payload/types';
	import { forgetAll, loadHideRead, loadRead, markRead, setHideRead } from '$lib/readstate';
	import { onMount, tick } from 'svelte';

	let {
		day,
		vertical = null,
		datePrefix = '',
		settled = true,
		ui
	}: {
		day: DayForPage;
		vertical?: string | null;
		datePrefix?: string;
		/** Whether the list in hand is everything this page will ever hold. False
		 * while a reading route is still fetching the stories past its seed, which
		 * is the one moment a story that is on its way looks like a story that was
		 * never here. */
		settled?: boolean;
		ui: UiConfig;
	} = $props();

	let query = $state('');
	let read = $state(new Set<string>());
	let hideRead = $state(false);
	let shownCount = $state(0);
	/** The story a reader's own address named, or the empty string.
	 *
	 * Read here rather than passed in, because the pager is the only thing that
	 * can reach it: a browser honours a fragment once and a story past the first
	 * page is not an element when it looks, so the reader lands at the top of the
	 * day with nothing focused. Empty on the server, so a prerendered document is
	 * exactly what it always was.
	 */
	let wanted = $state('');
	/** The last fragment already scrolled to. Deliberately not `$state`: it stops
	 * the page yanking itself back to the same story every time the list is
	 * re-derived, and nothing renders it. */
	let restored = '';

	const PAGE = 12;

	/** What the two origins cost. Both figures live in `assist/loader`, beside
	 * the code that fetches them; the words that print them are in `session`. */
	const COST = { here: DOWNLOAD_MB, elsewhere: DOWNLOAD_MB_ELSEWHERE };

	/** How wide and how close a question reaches, straight off `config/`.
	 *
	 * **A define, because this route has no server.** A dated URL is one shell
	 * with a universal load, so there is no `+page.server.ts` to read
	 * `assistConfig()` and hand it down - and the layout above every route may
	 * not carry it either, because whatever the layout returns is inlined into
	 * every prerendered document on the site including `/404`. `vite.config.ts`
	 * resolves it once per build out of the same reader the archive's load uses,
	 * so the four numbers ride only in the chunk that opens them
	 * (`docs/concepts/config.md`). No literal here (Guardrail #6). */
	const ASSIST = __ASSIST_CONFIG__;

	/** A question the reader asked, or null while the field is a filter. */
	let found = $state<SearchOutcome | null>(null);
	let phase = $state<SearchPhase>({ name: 'offer' });
	let cached = $state<CachedEncoder>('unknown');
	/** True once the encoder has answered in this tab, which is the difference
	 * between "the download is done" and a price still to pay. Held here rather
	 * than read off the session, because a session is rebuilt when the reader
	 * walks into another month and the encoder is not. */
	let held = $state(false);
	let scope = $state<SearchScope>(NO_SCOPE);
	/** One entry per result day, so a re-render draws a day the moment it lands. */
	let foundDays = $state<Record<string, DayForPage | null>>({});
	/** Whether this tab has asked its own disk about the encoder. Asked once, on
	 * the first keystroke, because it reads cache storage rather than the network
	 * and a reader who never types never pays for the question. */
	let askedDisk = false;
	/** The narrowed count, one settle behind the list. The list itself narrows on
	 * the keystroke; this is the number beside it, which would otherwise re-wrap
	 * the line under a reader's own hand on every letter (Susan, 2026-09-24).
	 * `ui.filter_settle_ms`, never a number written here (Guardrail #6). */
	let settledCount = $state(0);

	onMount(() => {
		hideRead = loadHideRead();
		const readHash = () => (wanted = window.location.hash.replace(/^#/, ''));
		readHash();
		window.addEventListener('hashchange', readHash);
		return () => window.removeEventListener('hashchange', readHash);
	});

	// Marks are per digest date, and this component is reused when a reader moves
	// from one date to another on the same route. An effect re-reads on the way
	// in; `onMount` would leave the previous day's marks on the new day's page.
	$effect(() => {
		read = loadRead(day.date, ui.read_mark_days);
	});

	// Every story this page is about, before anything is folded. It is what a
	// publisher name may link to: a folded story is still on this page's list, so
	// the anchor's card can reach it and the pager can walk to it.
	const inScope = $derived(
		vertical ? day.items.filter((item) => deskOf(item) === vertical) : day.items
	);
	// The stories drawn behind another story's card. `wanted` is never one of them,
	// which is the whole reachability answer: a reader who followed a publisher
	// name, or any deep link, gets the story they asked for drawn, paged to and
	// focused. See `foldedMembers`.
	const folded = $derived(foldedMembers(inScope, ui.draw_same_story, wanted));
	// The order the reader gets, decided before read-state is consulted. Newest
	// first by the time on the item, which is a re-order and never a filter: the
	// set here is the set the payload published, and the day's own view of what
	// matters is in the leading block rather than in this order. `orderByTime` is
	// idempotent, so a document whose seed the build already ordered pays for it
	// once and a fetched day is ordered the same way when it lands.
	const scoped = $derived(
		orderByTime(
			folded.size > 0 ? inScope.filter((item) => !folded.has(item.item_id)) : inScope
		)
	);
	// Every address a publisher name on this page may point at. A group can straddle
	// two desks, so on a topic route one half of it can be on another page - and a
	// name linking to a card this page does not hold is a link to nothing. It is not
	// lost either way: `also_covered_by` is the whole count, so a name dropped here
	// is still in the remainder the card prints.
	const onPage = $derived(new Set(inScope.map((item) => item.item_id)));
	function stackOf(item: DigestItem): DigestCoverage[] {
		if (!ui.draw_same_story) return [];
		return (item.covered_by ?? []).filter((one) => onPage.has(one.item_id));
	}
	// The topics the day published, or none when the payload does not say. A day
	// fetched by a shell older than the facts carries no topic list, and an empty
	// list is what draws no topic row - never an invented one.
	//
	// A topic the day drew nothing under is not one of them. It is listed on the
	// payload because its feeds carried a story the day then published elsewhere,
	// and `count` is owed that answer - but a pill is a way in, and one leading
	// to an empty room is a dead end.
	const desks = $derived((day.verticals ?? []).filter((ref) => deskCount(ref) > 0));
	// What the day published, not what is in hand. A reading route's document
	// carries a seed and fetches the rest, so counting the list here would print
	// a number that ticks up while the reader watches - and the topic pill beside
	// it already shows the day's own count for its own topic. Both halves read a
	// bounded fact off the payload instead: one topic's count, or every topic's.
	// `deskCount` and not `count`, because this is the number beside the stories
	// the page is actually drawing.
	const total = $derived.by(() => {
		if (vertical) {
			const ref = desks.find((entry) => entry.id === vertical);
			return ref ? deskCount(ref) : scoped.length;
		}
		return desks.length > 0 ? desks.reduce((sum, ref) => sum + deskCount(ref), 0) : scoped.length;
	});
	/** What the field holds, once it holds enough to narrow by. It is read even
	 * while a question is up, because it is what decides whether the line under
	 * the panel names the cost of the next key. */
	const typed = $derived(filterNeedle(query, ui.filter_min_chars));
	/** What the day is being narrowed by. Null once an answer is up, because a
	 * question is not a substring and the answer is drawn where the day was.
	 *
	 * **An answer, and not the press that asked for one.** Enter starts a 43 MB
	 * download and it can end in a refusal, so a needle dropped on the press
	 * would un-narrow the day the moment a reader asked a question of it - they
	 * would watch their twelve stories become the day's four hundred, and a
	 * search that then refused would leave them there with their own words still
	 * in the box. The day stays narrowed while the encoder warms and stays
	 * narrowed if the question never runs: the second tier is additive, and it
	 * never takes the first one away (`CLAUDE.md` section 1a). */
	const needle = $derived(found !== null ? null : typed);
	// The day's searchable text, lowercased, and every story's place in it.
	// Derived from `scoped` rather than captured, so when a reading route's fetch
	// lands the whole day is re-indexed and the filter runs over all of it - an
	// index taken once at mount would narrow the document's seed for ever. It is
	// NOT derived from the needle, which is the point: a reader types letters far
	// more often than the day changes.
	const index = $derived(indexDay(scoped));
	// Every lead the day published, not the block the page drew. `revealed` cuts
	// it back to what is on screen; this is only where they sit.
	const pinned = $derived(new Set((day.leads ?? []).map((lead) => lead.item_id)));
	// One walk down the day for the four answers below it. Read state is passed
	// as null rather than an empty set when the reader is not hiding anything, so
	// the ordinary case does no lookups.
	const list = $derived(shortlist(index, needle, hideRead ? read : null, pinned, wanted));
	const filtering = $derived(needle !== null);
	const visible = $derived(list.visible);

	// The months a question may reach, derived from the day in the address rather
	// than from a published list: a dated route is one shell with a universal
	// load, so it can read no server data, and baking the archive's month list
	// into the reading bundle would grow it as the archive grows (Guardrail #12).
	//
	// Exactly `search_months` of them, and never the speculative extra the
	// archive takes when its newest shard is thin. The archive holds the list of
	// months that exist, so its extra shard is a real one; here it would be a
	// guess, and a guess that misses is a refused request on every search a
	// reader runs from a day page. What that costs the reader is reach: a search
	// early in a month covers few days, and the empty state points at the
	// archive, which is the page whose job is the whole corpus (Susan's ruling 4).
	const months = $derived(monthsBackFrom(day.date, ASSIST.search_months - 1));
	// One session per scope. Rebuilt when the months move, because a session holds
	// the shards it opened and a reader who walks from one month into another must
	// not be answered out of the month they left.
	const search = $derived.by(() => {
		void months;
		return newSearch(
			{ supported, loadIndex, loadVectors, embed: embedQuery },
			ASSIST
		);
	});
	const report = {
		onPhase: (next: SearchPhase) => (phase = next),
		onScope: (next: SearchScope) => (scope = next)
	};
	// The line under the panel, and the two tiers are the two shapes it takes.
	// Nothing at rest: a reading page that opens with a 43 MB advert above the
	// stories is furniture a reader who never searches pays for every day.
	const searchSentence = $derived(
		phase.name === 'offer'
			? costNote(COST)
			: stateSentence({ phase, held, cached, cost: COST })
	);
	// Shown while there is something to say: a download in flight, a refusal, or a
	// price the reader has not paid and is one key away from spending. Never
	// without the field, because every sentence it prints is about a key there is
	// nowhere to press.
	const searchShown = $derived(
		ui.show_filter &&
			(phase.name !== 'offer' || (typed !== null && !held && cached !== 'present'))
	);
	const answered = $derived(found !== null);

	/** Which tier produced the list under the field, in the reader's words. */
	const caption = $derived.by(() => {
		if (found !== null) {
			const searched = `Searched ${found.scope} - ${plural(found.searched, 'story', 'stories')}.`;
			return found.hits.length === 0
				? `No stories match. ${searched}`
				: `${plural(found.hits.length, 'story', 'stories')} found. ${searched}`;
		}
		if (!filtering) return 'Typing filters this page. Press Enter to search other days.';
		return (
			`${settledCount} of ${plural(total, 'story', 'stories')} on this page. ` +
			'Press Enter to search other days.'
		);
	});

	// The count settles behind the list rather than with it. `visible.length` is
	// read here so the timer restarts on every keystroke and only the last one
	// lands, which is what stops the line re-wrapping letter by letter.
	$effect(() => {
		const next = visible.length;
		const wait = setTimeout(() => (settledCount = next), ui.filter_settle_ms);
		return () => clearTimeout(wait);
	});

	/** Fetch the day behind every result on screen. Once each, never twice. */
	async function fetchDays(hits: SearchHit[]) {
		const dates = [...new Set(hits.map((hit) => hit.entry.date))];
		await Promise.all(
			dates.map(async (date) => {
				const whole = await loadDay(date);
				foundDays = { ...foundDays, [date]: whole };
			})
		);
	}

	/** The Enter key, and the button behind it. */
	async function ask() {
		if (query.trim() === '') return;
		const outcome = await search.ask(months, query, report);
		// Null is a search that did not run, and the phase already says why. The day
		// under the field is untouched either way.
		if (outcome === null) return;
		held = true;
		found = outcome;
		void fetchDays(outcome.hits);
	}

	/** Put the day back. The field's next keystroke does this too, which is what
	 * makes an accidental Enter cost one key rather than a hunt for a control. */
	function clearSearch() {
		found = null;
	}

	// A topic pill moves the reader to another desk, and a cross-day answer drawn
	// over it would make that pill look like a control that does nothing. Only the
	// topic: a dated route nulls its day on a date change, so the whole component
	// is rebuilt there, and this is the one move that reuses it.
	$effect(() => {
		void vertical;
		clearSearch();
	});

	function onType() {
		clearSearch();
		// This device's own disk, never the network: the library caches every model
		// file it fetches under a same-origin key, so the answer is a lookup. Asked
		// on the first keystroke rather than on mount, so a reader who only reads
		// never asks it (`assist/loader.ts`).
		if (askedDisk) return;
		askedDisk = true;
		void cachedEncoder().then((state) => (cached = state));
	}

	// Chosen by the pipeline over the whole day and published on the payload.
	// The block only draws on the all-topics view: a topic route and a filter
	// both already have a subject, and a block whose leads sit outside what the
	// page is showing is a set of links that scroll to nothing. Resolved against
	// `visible` for the same reason - a lead a reader has hidden drops out of the
	// block rather than leaving a dead anchor behind.
	const leads = $derived(
		vertical === null && !filtering && !answered ? leadingStories(day.leads ?? [], visible) : []
	);
	const leading = $derived(new Set(leads.map((story) => story.item_id)));

	// The head of the published order, plus every lead. A lead is chosen across
	// the WHOLE day - measured 2026-09-01 on the 601-story day of 2026-08-31,
	// the five sat at positions 249, 285, 337, 344 and 493 - so a page holding
	// only the head is a block whose links land on nothing. They keep their own
	// published positions and the set never holds one twice: past the last lead
	// this is exactly the prefix it always was.
	//
	// And it reaches the story a reader's own address named. `/<date>/#<item id>`
	// is a published reader address, so a pager that stops at twelve makes every
	// story past the first page unaddressable - measured 2026-09-02 on the
	// 627-story day of 2026-09-01, 610 of 627 addresses landed the reader at the
	// top of the day with nothing focused. Nothing else sees this: `reach` is
	// zero with no fragment, so the server draws the same twelve it always drew
	// and so does every reader who followed an ordinary link. A lead is zero too,
	// because the line above already draws it - reaching for one would page the
	// whole stream down to its position for a click that never needed it. A
	// fragment naming a story this page is not showing is zero as well, which is
	// what `wantedRow` being -1 says.
	const reach = $derived(
		wanted === '' || leading.has(wanted) || list.wantedRow < 0 ? 0 : list.wantedRow + 1
	);
	const shown = $derived(Math.max(shownCount || PAGE, reach));
	const paged = $derived(revealed(visible, list.pinnedRows, leading, shown));
	// Counted against the day rather than the list in hand, because on a reading
	// route the list in hand is a seed. Counting the seed would offer "Show 2
	// more" and then "Show 55 more" the moment the fetch landed, which is a number
	// ticking under a reader who is looking at it - the same fault `DayNotice`
	// avoids by reading the desk counts. `total` is those counts, so it is already
	// the truth about the day and it does not move. A filter, a hide or a fold
	// narrows the list on purpose, and then the list IS the promise: a fold takes
	// cards off the page that `total` still counts, so leaving the day's own number
	// as the floor would offer a reader stories the pager can never draw.
	const reachable = $derived(
		filtering || hideRead || folded.size > 0 ? visible.length : Math.max(visible.length, total)
	);
	const remaining = $derived(Math.max(reachable - paged.length, 0));
	// A fragment naming a story this page never draws. The whole day rather than
	// what is visible, so a story the reader has hidden or filtered out is not
	// reported as absent - it is here, and the controls to bring it back are on
	// screen. A folded story is not absent either: it is excluded from the fold the
	// moment its own address names it, so by the time this is read its card is
	// drawn. Only once the list in hand is the whole list: a story still on its
	// way is not a story that was never here.
	const missing = $derived(settled && wanted !== '' && !index.at.has(wanted));
	const verticalNames = $derived(
		Object.fromEntries(desks.map((ref) => [ref.id, ref.display_name]))
	);

	// The pager has just drawn a story the browser already looked for and did not
	// find, so the fragment is honoured again now that the element exists. Once
	// per fragment: a reader who then hides what they have read must not be thrown
	// back up the page.
	$effect(() => {
		if (wanted === '' || list.wantedRow < 0 || restored === wanted) return;
		const target = wanted;
		void tick().then(() => {
			if (restoreAnchor(`#${target}`)) restored = target;
		});
	});

	function toggleHide() {
		hideRead = !hideRead;
		setHideRead(hideRead);
	}

	// The day is drawn in parts so the leads can be painted beside the stream at
	// the wide breakpoint without leaving their place in the document. Every
	// part renders its own sections in `digest.sections` order and the parts
	// themselves are in that order too, so reordering the page is still a config
	// edit and a narrow screen sees exactly what config asked for.
	//
	// The aside stands beside the STREAM, never beside the day's controls: the
	// filter panel sticks only where it is one band, and one band needs the
	// whole content box. So it needs the leads to come before the items; any
	// other order and the day stays one column at every width.
	const leadsAt = $derived(ui.sections.indexOf('leads'));
	const streamAt = $derived(ui.sections.indexOf('items'));
	const split = $derived(leads.length > 0 && leadsAt >= 0 && streamAt > leadsAt);
	const headBefore = $derived(split ? ui.sections.slice(0, leadsAt) : ui.sections);
	const headAfter = $derived(split ? ui.sections.slice(leadsAt + 1, streamAt) : []);
	const stream = $derived(split ? ui.sections.slice(streamAt) : []);
</script>

{#snippet part(section: string)}
	{#if section === 'notice'}
		<DayNotice {day} count={total} />
	{:else if section === 'leads'}
		<LeadingStories stories={leads} />
	{:else if section === 'topics' && desks.length > 0}
		<FilterBar
			label="Topics and search"
			verticals={desks}
			active={vertical}
			{total}
			pillsMax={ui.topic_pills_max}
			pillMoveMin={ui.pill_move_min}
			{datePrefix}
			bind:query
			fieldId="page-filter"
			fieldLabel="Filter this page, or press Enter to search other days"
			placeholder="Filter this page"
			showField={ui.show_filter}
			submitLabel="Search other days"
			submitVisible={false}
			onSubmit={() => void ask()}
			{onType}
			deskThinMax={ui.desk_thin_max}
			matchNote={ui.show_filter ? caption : ''}
			noscriptNote="Filtering and search need JavaScript. Every topic above is a link and still works."
		/>
		{#if searchShown}
			<SearchState
				{phase}
				sentence={searchSentence}
				scope={answered ? '' : scopeSentence(scope)}
				surface="day"
				onStop={() => search.stop(report)}
				onRetry={() => void ask()}
			/>
		{/if}
	{:else if section === 'items'}
		{#if found !== null && found.hits.length > 0}
			<FoundStories {found} days={foundDays} {verticalNames} onClear={clearSearch} />
		{:else if found !== null}
			<p class="py-12 text-base text-text-secondary" data-day-found="empty">
				Nothing matched &ldquo;{found.query}&rdquo; in the days we can search. The
				<a href="{base}/archive/" class="text-accent hover:underline">archive</a> lists every
				published day.
			</p>
		{:else if day.items.length === 0}
			<EmptyDay date={day.date} />
		{:else if list.matched === 0}
			<p class="py-12 text-base text-text-secondary">
				Nothing on this page matches &ldquo;{query}&rdquo;. Press Enter to search other days.
			</p>
		{:else}
			{#if read.size > 0}
				<div class="flex justify-end pt-3">
					<button
						type="button"
						onclick={toggleHide}
						aria-pressed={hideRead}
						class="min-h-11 text-sm text-text-tertiary hover:text-accent"
					>
						{hideRead ? 'Show everything' : 'Hide what I have read'}
					</button>
				</div>
			{/if}

			{#if visible.length === 0}
				<p class="py-12 text-base text-text-secondary">
					You have read everything here today.
				</p>
			{:else}
				<!-- The zone, once, above the stream it explains. Not a suffix on 627
				     stamps: every clock on this page is in the same zone, so it is a fact
				     about the page and it is drawn where the page's own facts are. It
				     hung above the time rail until 2026-09-12 and it outlived it - the
				     rail was the duplicate; this sentence is what makes a bare clock
				     readable. -->
				<p class="zone-note" data-time-note>Times shown in UTC.</p>

				{#each paged as item (item.item_id)}
					<DigestItemView
						{item}
						verticalName={verticalNames[deskOf(item)] ?? deskOf(item)}
						showMark={ui.source_mark}
						stack={stackOf(item)}
						onDate={day.date}
						{needle}
						read={read.has(item.item_id)}
						onRead={() => (read = markRead(item.item_id, read, day.date))}
					/>
				{/each}

				{#if remaining > 0}
					<!-- Hidden with no script, and replaced by a line that says so.
					     The control needs a click handler to do anything, so leaving it
					     drawn hands a script-free reader a button that promises 55
					     stories and does nothing when pressed - which is what `/` did
					     until 2026-09-10. The attribute is what the `<noscript>` rule
					     below hides, for the reason `FilterBar` records: a `<noscript>`
					     block cannot reach a scoped class, and it can reach an
					     attribute. -->
					<button
						type="button"
						data-pager-scripted
						onclick={() => (shownCount = shown + PAGE)}
						class="min-h-11 w-full py-6 text-base text-accent hover:underline"
					>
						Show {remaining} more
					</button>
					<noscript>
						<style>
							[data-pager-scripted][data-pager-scripted] {
								display: none;
							}
						</style>
						<p class="pager-noscript w-full py-6 text-sm text-text-tertiary">
							{remaining} more stories need JavaScript. Every topic above is a link and still
							works.
						</p>
					</noscript>
				{/if}
			{/if}

			{#if read.size > 0}
				<p class="pt-6 text-sm text-text-tertiary">
					<button
						type="button"
						onclick={() => (read = forgetAll(day.date))}
						class="hover:text-accent"
					>
						Forget what I have read
					</button>
				</p>
			{/if}
		{/if}
	{/if}
{/snippet}

<div class="day">
	<div class="day-head">
		<!-- A link that named a story this page does not have. The region is here on
		     every page, empty ones included: a live region has to be in the document
		     before its text changes or nothing announces it. Silence was the old
		     answer - the reader was dropped at the top of the day with no story
		     focused and nothing said. -->
		<div aria-live="polite" data-anchor-missing={missing ? 'yes' : 'no'}>
			{#if missing}
				<p class="pb-4 text-sm text-text-secondary">
					The story that link names is not on this page.
				</p>
			{/if}
		</div>
		{#each headBefore as section (section)}
			{@render part(section)}
		{/each}
	</div>

	{#if split}
		<div class="day-aside">
			<LeadingStories stories={leads} />
		</div>
		<div class="day-head">
			{#each headAfter as section (section)}
				{@render part(section)}
			{/each}
		</div>
		<div class="day-stream">
			{#each stream as section (section)}
				{@render part(section)}
			{/each}
		</div>
	{/if}
</div>

<style>
	/* The zone, once, in the day's own chrome type. The rail that used to carry
	   this sentence is gone; the sentence is not, because it is the fact that
	   makes every bare clock on the page readable. */
	.zone-note {
		margin-block-start: var(--space-5);
		color: var(--color-text-tertiary);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
	}
</style>
