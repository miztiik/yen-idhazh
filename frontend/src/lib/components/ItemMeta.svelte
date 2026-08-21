<script lang="ts">
	/** Where it came from, how sure we are, and the way out.
	 *
	 * Order is deliberate: what it is, then what it says, then where it came
	 * from and how sure we are. The confidence claim is about the summary, so it
	 * sits after it, next to the link that lets you check.
	 */
	import { KIND_WORTH_SAYING, SOURCE_KINDS } from '$lib/bands';
	import { shortDate } from '$lib/format';
	import type { DigestItem } from '$lib/payload/types';
	import ConfidenceChip from './ConfidenceChip.svelte';
	import ReadAloud from './ReadAloud.svelte';
	import SourceLink from './SourceLink.svelte';
	import SourceMark from './SourceMark.svelte';

	let {
		item,
		showMark = true,
		onRead
	}: { item: DigestItem; showMark?: boolean; onRead?: () => void } = $props();
	const kindWorthSaying = $derived(KIND_WORTH_SAYING.includes(item.source_kind));
</script>

<div
	class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.8125rem] leading-[1.4] text-text-secondary"
>
	<span class="inline-flex items-center gap-1.5">
		{#if showMark}
			<SourceMark name={item.source_name} sourceId={item.source_id} />
		{/if}
		{item.source_name}
	</span>

	{#if kindWorthSaying}
		<span class="text-text-tertiary">{SOURCE_KINDS[item.source_kind]}</span>
	{/if}

	{#if item.published_at}
		<span class="text-text-tertiary">{shortDate(item.published_at.slice(0, 10))}</span>
	{/if}

	<ConfidenceChip band={item.band} />

	{#if item.truncated}
		<span class="text-text-tertiary">Source was cut short</span>
	{/if}

	<ReadAloud title={item.title} summary={item.summary} />

	<SourceLink url={item.source_url} {onRead} />
</div>
