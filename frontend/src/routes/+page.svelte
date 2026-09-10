<script lang="ts">
	/** The front page: the newest day, seeded into the document and then filled in.
	 *
	 * **It carried the whole day inline until 2026-09-10.** The reason given was
	 * that `/` stayed readable with no script, and it did not - see the
	 * measurement in [+page.server.ts](+page.server.ts). What it actually shipped
	 * a script-free reader was most of a day they could not reach and a pager
	 * that did nothing.
	 *
	 * **Three things make this different from a dated URL, and all three are why
	 * `/` is still prerendered.** It is one document per build rather than one per
	 * published day, so it costs the site nothing that grows. It is the address a
	 * stranger meets first, so its seed and its leading block are in the first
	 * bytes rather than a request away. And when the fetch fails the reader is not
	 * left with a headline and a button: the seed is on screen, `MoreDays` is
	 * under it, and every one of those days opens.
	 *
	 * **The seed holds the day's leads**, so the two-column layout is decided in
	 * the prerendered document. Without that the aside arrives with the fetch, the
	 * grid changes mode under the reader, and every card on screen re-wraps.
	 */
	import { restoreAnchor, watchDay, type DayStatus } from '$lib/assist/day';
	import DigestList from '$lib/components/DigestList.svelte';
	import EmptyDay from '$lib/components/EmptyDay.svelte';
	import MoreDays from '$lib/components/MoreDays.svelte';
	import PayloadState from '$lib/components/PayloadState.svelte';
	import { longDate } from '$lib/format';
	import type { DayForPage } from '$lib/payload/types';
	import { tick } from 'svelte';

	let { data } = $props();

	/** The whole day, once it is in hand. Null until then, and after a failure. */
	let arrived = $state<DayForPage | null>(null);
	let reported = $state<DayStatus>('loading');

	/** The seed until the fetch lands, the whole day after it. The seed's own
	 * facts are the day's facts either way, so nothing the header says moves. */
	const day = $derived(arrived ?? data.day);

	/** How much of the day is on screen against how much it published, in the
	 * day's own units. `PayloadState` formats nothing, so the sentence is built
	 * here - and it is only true to say when both numbers are known. */
	const published = $derived(
		(data.day?.verticals ?? []).reduce((sum, desk) => sum + desk.count, 0)
	);
	const shortfall = $derived(
		published > 0 && (day?.items.length ?? 0) < published
			? `${day?.items.length ?? 0} of ${published} stories arrived. The days below are all here.`
			: undefined
	);

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
				if (whole === null) return;
				arrived = whole;
				// A browser honours a fragment once, at load. A story the reader's
				// address named may only have arrived now.
				void tick().then(() => restoreAnchor());
			}
		});
	}

	// Keyed on the date the document was built with. `/` is one document, so this
	// runs once - the cleanup is here because a reader who navigates away mid
	// flight should not have the day delivered onto a page they left.
	$effect(() => {
		const date = data.day?.date;
		if (!date) return;
		fetchDay(date, false);
		return () => {
			watcher?.abort();
			watcher = null;
		};
	});
</script>

<svelte:head>
	<title>{data.ui.site_title}</title>
	<meta name="description" content={data.ui.tagline} />
</svelte:head>

{#if day}
	<DigestList {day} datePrefix="{day.date}/" settled={reported === 'ready'} ui={data.ui} />
	<PayloadState
		status={reported}
		holding={true}
		{shortfall}
		day={longDate(day.date)}
		onRetry={() => fetchDay(day.date, true)}
	/>
	<MoreDays days={data.recent} current={day.date} />
{:else}
	<EmptyDay date={data.today} />
	<MoreDays days={data.recent} current={data.today} />
{/if}
