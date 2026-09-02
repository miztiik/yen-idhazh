<script lang="ts">
	/** A topic page: the day, filtered to one desk.
	 *
	 * The document carries the head of that desk and the rest arrive from
	 * `<base>/digest/<Y>/<M>/<D>/digest.json` - the same served day the archive's
	 * search results already read, and one file for the whole day rather than one
	 * per topic. The filter that used to run at build time in six documents runs
	 * once here instead.
	 *
	 * **`prerender` and `entries()` are untouched.** What moved is the item list,
	 * not the document. The page keeps its own address, its own title, and a
	 * first screen that is complete with script off.
	 *
	 * **Nothing became unreachable.** The set this page holds after the fetch is
	 * the set the document used to inline, filtered the same way - and the page
	 * asks for the day only when its own document is short of the topic's
	 * stories, so a small desk still costs a reader no request at all.
	 */
	import { restoreAnchor, watchDay, type DayStatus } from '$lib/assist/day';
	import { base } from '$app/paths';
	import DigestList from '$lib/components/DigestList.svelte';
	import PayloadState from '$lib/components/PayloadState.svelte';
	import { longDate } from '$lib/format';
	import { daysHeldOffline } from '$lib/offline';
	import type { DigestItem } from '$lib/payload/types';
	import { tick } from 'svelte';

	let { data } = $props();
	const name = $derived(
		data.day.verticals.find((ref) => ref.id === data.vertical)?.display_name ?? data.vertical
	);

	/** The desk's whole list, once it is in hand. Null until then, and the
	 * document's own head is what the page shows in the meantime. */
	let arrived = $state<DigestItem[] | null>(null);
	/** What the loader last reported, or null before it has said anything. Null
	 * rather than an initial guess, so the prerendered document states the truth
	 * about itself: a document short of its desk is waiting, and a complete one
	 * is not. */
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

	function fetchRest(date: string, vertical: string, again: boolean) {
		watchDay(date, {
			slowMs: data.ui.payload_slow_ms,
			again,
			onStatus: (next, whole) => {
				reported = next;
				if (next === 'unreachable') void offerHeldDays(date);
				if (whole === null) return;
				// The served day is every desk, so this is the filter the prerendered
				// document used to apply at build time - same rule, same order, one
				// copy instead of five.
				arrived = whole.items.filter((item) => item.vertical === vertical);
				// A browser honours a fragment once, at load. The story a deep link
				// names may only have arrived just now.
				void tick().then(() => restoreAnchor());
			}
		});
	}

	// Keyed on the parameters rather than on mount: SvelteKit reuses this
	// component when only the date or the topic moves, and a fetch that ran once
	// would leave the previous desk's stories on the new desk's page.
	$effect(() => {
		const { date, vertical, awaiting } = data;
		arrived = null;
		reported = null;
		held = [];
		if (awaiting > 0) fetchRest(date, vertical, false);
	});
</script>

<svelte:head>
	<title>{name} &mdash; {longDate(data.date)} &mdash; {data.ui.site_title}</title>
</svelte:head>

<DigestList
	{day}
	vertical={data.vertical}
	datePrefix="{data.date}/"
	latest={data.latest}
	ui={data.ui}
/>

<!-- Named for the desk rather than for the date. The reader came for one topic,
     and "the rest of 30 August" on a page of AI stories asks them to know that
     a topic page fetches a whole day. -->
<PayloadState
	{status}
	{held}
	day="{name} on {longDate(data.date)}"
	onRetry={() => fetchRest(data.date, data.vertical, true)}
/>
