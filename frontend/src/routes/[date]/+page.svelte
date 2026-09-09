<script lang="ts">
	/** A dated day page.
	 *
	 * **The document is the one shell every dated URL is served from**, so this
	 * page starts with the date and nothing else and fetches the whole day from
	 * `<base>/digest/<Y>/<M>/<D>/digest.json` - the same served file a search
	 * result and a topic page already read. Until 2026-09-09 a build wrote one
	 * document per published day carrying the head of it; those 20 documents and
	 * 96 topic documents are what this row deletes.
	 *
	 * **Three answers, three screens, and they are not the same sentence.** The
	 * day arrives and the page draws it. Or the host answers that it holds no
	 * payload for that date, and the reader gets the screen a wrong address gets -
	 * named, with two ways on. Or the fetch failed, and the reader is told the
	 * connection did, with a retry. A reader whose train went into a tunnel is
	 * never told the day does not exist.
	 *
	 * **`/` is deliberately not this.** It is one document per build rather than
	 * one per published day, so it costs the site nothing that grows, and it is
	 * the address a stranger meets first - it keeps the whole day inline and
	 * stays readable with no script at all.
	 */
	import { restoreAnchor, watchDay, type DayStatus } from '$lib/assist/day';
	import { base } from '$app/paths';
	import DigestList from '$lib/components/DigestList.svelte';
	import NotHere from '$lib/components/NotHere.svelte';
	import PayloadState from '$lib/components/PayloadState.svelte';
	import { longDate } from '$lib/format';
	import { daysHeldOffline } from '$lib/offline';
	import type { DayForPage } from '$lib/payload/types';
	import { tick } from 'svelte';

	let { data } = $props();

	/** The day, once it is in hand. Null until then, and after a failure. */
	let arrived = $state<DayForPage | null>(null);
	/** What the loader last reported. `loading` until it has said anything, which
	 * is what it is: the request goes out on mount. */
	let reported = $state<DayStatus>('loading');
	/** The other days this device still holds. Asked for only when this one
	 * failed, because it is the only state that has anything to do with it. */
	let held = $state<{ label: string; href: string }[]>([]);

	/** The day's own date always wins over the payload's. It is in the address the
	 * reader typed, so it is known before any request - and a payload written
	 * before a served day carried a date has none to read. */
	const day = $derived(arrived === null ? null : { ...arrived, date: data.date });

	async function offerHeldDays(current: string) {
		const dates = (await daysHeldOffline()).filter((date) => date !== current);
		held = dates.map((date) => ({ label: longDate(date), href: `${base}/${date}/` }));
	}

	/** The watch in flight, so a date change or a retry can abort it. A stale
	 * callback would otherwise deliver the previous date's stories onto this
	 * page, because the served day arrives after the date has already moved. */
	let watcher: AbortController | null = null;

	function fetchDay(date: string, again: boolean) {
		watcher?.abort();
		const controller = new AbortController();
		watcher = controller;
		watchDay(date, {
			slowMs: data.ui.payload_slow_ms,
			again,
			signal: controller.signal,
			onStatus: (next, whole) => {
				reported = next;
				if (next === 'unreachable') void offerHeldDays(date);
				if (whole === null) return;
				arrived = whole;
				// A browser honours a fragment once, at load. The story a deep link
				// names has only arrived now.
				void tick().then(() => restoreAnchor());
			}
		});
	}

	// Keyed on the date rather than on mount: SvelteKit reuses this component
	// when only the date moves, and a fetch that ran once would leave yesterday's
	// stories on today's page. The cleanup aborts the in-flight watch, so a
	// change of date - or leaving the page - cannot deliver the old day.
	$effect(() => {
		const { date } = data;
		arrived = null;
		reported = 'loading';
		held = [];
		fetchDay(date, false);
		return () => {
			watcher?.abort();
			watcher = null;
		};
	});
</script>

<svelte:head>
	<title>{longDate(data.date)} &mdash; {data.ui.site_title}</title>
</svelte:head>

{#if reported === 'missing'}
	<NotHere
		status={404}
		headline="Not here"
		detail="No digest was published for {longDate(data.date)}."
		next="The address may be wrong, or the day it names was never published."
	/>
{:else}
	{#if day}
		<DigestList {day} datePrefix="{data.date}/" settled={reported === 'ready'} ui={data.ui} />
	{/if}
	<PayloadState
		status={reported}
		{held}
		holding={day !== null}
		day={longDate(data.date)}
		onRetry={() => fetchDay(data.date, true)}
	/>
{/if}
