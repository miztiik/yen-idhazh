<script lang="ts">
	/** A dated day page.
	 *
	 * The document carries the head of the day plus every story its leading
	 * block points at, and the rest arrive from
	 * `<base>/digest/<Y>/<M>/<D>/digest.json` - the same served day a search
	 * result and every topic page already read.
	 *
	 * **`prerender` and `entries()` are untouched.** What moved is the item list,
	 * not the document. The page keeps its own address, its own title, and a
	 * first screen that is complete with script off: the leading block, the
	 * topic row and the head of the stream all render before a request is made,
	 * and the stream pages at twelve, so nothing left the first screen.
	 *
	 * **`/` is deliberately not this.** It is one document per build rather than
	 * one per published day, so it costs the site nothing that grows, and it is
	 * the address a stranger meets first - it keeps the whole day inline and
	 * stays readable with no script at all.
	 */
	import { restoreAnchor, watchDay, type DayStatus } from '$lib/assist/day';
	import { base } from '$app/paths';
	import { keepDrawings } from '$lib/day-shape';
	import DigestList from '$lib/components/DigestList.svelte';
	import PayloadState from '$lib/components/PayloadState.svelte';
	import { longDate } from '$lib/format';
	import { daysHeldOffline } from '$lib/offline';
	import type { DigestItem } from '$lib/payload/types';
	import { tick } from 'svelte';

	let { data } = $props();

	/** The day's whole list, once it is in hand. Null until then, and the
	 * document's own seed is what the page shows in the meantime. */
	let arrived = $state<DigestItem[] | null>(null);
	/** What the loader last reported, or null before it has said anything. Null
	 * rather than an initial guess, so the prerendered document states the truth
	 * about itself: a document short of its day is waiting, and a complete one is
	 * not. */
	let reported = $state<DayStatus | null>(null);
	/** The other days this device still holds. Asked for only when this one
	 * failed, because it is the only state that has anything to do with it. */
	let held = $state<{ label: string; href: string }[]>([]);

	const status = $derived(reported ?? (data.awaiting > 0 ? 'loading' : 'ready'));
	const day = $derived(arrived === null ? data.day : { ...data.day, items: arrived });

	async function offerHeldDays(current: string) {
		const dates = (await daysHeldOffline()).filter((date) => date !== current);
		held = dates.map((date) => ({ label: longDate(date), href: `${base}/${date}/` }));
	}

	function fetchRest(date: string, again: boolean) {
		watchDay(date, {
			slowMs: data.ui.payload_slow_ms,
			again,
			onStatus: (next, whole) => {
				reported = next;
				if (next === 'unreachable') void offerHeldDays(date);
				if (whole === null) return;
				// The served day is this day, whole and unfiltered, so there is no
				// rule to re-apply here - the topic pages are the ones that filter.
				// What the served day does not carry is the seed's drawings, which
				// the document read off disk so they could take the page's colours.
				arrived = keepDrawings(data.day?.items ?? [], whole.items);
				// A browser honours a fragment once, at load. The story a deep link
				// names may only have arrived just now.
				void tick().then(() => restoreAnchor());
			}
		});
	}

	// Keyed on the date rather than on mount: SvelteKit reuses this component
	// when only the date moves, and a fetch that ran once would leave yesterday's
	// stories on today's page.
	$effect(() => {
		const { date, awaiting } = data;
		arrived = null;
		reported = null;
		held = [];
		if (awaiting > 0) fetchRest(date, false);
	});
</script>

<svelte:head>
	<title>{longDate(data.date)} &mdash; {data.ui.site_title}</title>
</svelte:head>

<DigestList
	{day}
	datePrefix="{data.date}/"
	latest={data.latest}
	settled={status === 'ready'}
	ui={data.ui}
/>

<PayloadState
	{status}
	{held}
	day={longDate(data.date)}
	onRetry={() => fetchRest(data.date, true)}
/>
