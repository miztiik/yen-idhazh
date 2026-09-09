<script lang="ts">
	/** A topic page: the day, filtered to one desk.
	 *
	 * The same shell the dated day route is served from, and the larger half of
	 * what this row deletes - 96 of the 116 documents a build used to write were
	 * this route. A topic is one desk of one day, so it was always a filter over
	 * a file the browser can fetch for itself, and the build was writing five
	 * documents a day to run that filter early.
	 *
	 * **A topic this day did not publish is not here, and it says so.** The
	 * payload names every desk the day had, so the page can tell a topic that ran
	 * nothing from a day that was never published - and both get the screen a
	 * wrong address gets rather than an empty room.
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
	let reported = $state<DayStatus>('loading');
	let held = $state<{ label: string; href: string }[]>([]);

	const day = $derived(arrived === null ? null : { ...arrived, date: data.date });
	const desks = $derived(arrived?.verticals ?? null);
	/** Whether the day says it published this desk. Null until the day is in
	 * hand, and null again for a payload that names no desk at all - absent is
	 * unknown, and refusing a topic on a payload that did not say is a screen
	 * that hides stories the reader can see the pills for. */
	const ran = $derived(desks === null ? null : desks.some((ref) => ref.id === data.vertical));
	const name = $derived(
		desks?.find((ref) => ref.id === data.vertical)?.display_name ?? data.vertical
	);

	async function offerHeldDays(current: string) {
		const dates = (await daysHeldOffline()).filter((date) => date !== current);
		held = dates.map((date) => ({ label: longDate(date), href: `${base}/${date}/` }));
	}

	/** The watch in flight, so a change of date or topic, or a retry, can abort
	 * it. A stale callback would otherwise deliver the previous desk's stories
	 * onto this page, because the served day arrives after the parameters moved. */
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
				void tick().then(() => restoreAnchor());
			}
		});
	}

	// Keyed on the parameters rather than on mount: SvelteKit reuses this
	// component when only the date or the topic moves, and a fetch that ran once
	// would leave the previous desk's stories on the new desk's page.
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
	<title>{name} &mdash; {longDate(data.date)} &mdash; {data.ui.site_title}</title>
</svelte:head>

{#if reported === 'missing'}
	<NotHere
		status={404}
		headline="Not here"
		detail="No digest was published for {longDate(data.date)}."
		next="The address may be wrong, or the day it names was never published."
	/>
{:else if ran === false}
	<NotHere
		status={404}
		headline="Not here"
		detail="Nothing was published under {data.vertical} on {longDate(data.date)}."
		next="The day itself is here, and every topic it did publish is on it."
	/>
{:else}
	{#if day}
		<DigestList
			{day}
			vertical={data.vertical}
			datePrefix="{data.date}/"
			settled={reported === 'ready'}
			ui={data.ui}
		/>
	{/if}
	<!-- Named for the desk rather than for the date. The reader came for one topic,
	     and "30 August" on a page of AI stories asks them to know that a topic page
	     fetches a whole day. -->
	<PayloadState
		status={reported}
		{held}
		holding={day !== null}
		day="{name} on {longDate(data.date)}"
		onRetry={() => fetchDay(data.date, true)}
	/>
{/if}
