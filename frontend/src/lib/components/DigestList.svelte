<script lang="ts">
	/** The day page. Section order is config, which is the modularity story:
	 * reordering the page is a config edit, not a code change. */
	import DayNotice from '$lib/components/DayNotice.svelte';
	import DigestItemView from '$lib/components/DigestItem.svelte';
	import EmptyDay from '$lib/components/EmptyDay.svelte';
	import TopicPills from '$lib/components/TopicPills.svelte';
	import type { UiConfig } from '$lib/config/ui';
	import type { DigestDay } from '$lib/payload/types';

	let {
		day,
		vertical = null,
		datePrefix = '',
		latest = null,
		ui
	}: {
		day: DigestDay;
		vertical?: string | null;
		datePrefix?: string;
		latest?: string | null;
		ui: UiConfig;
	} = $props();

	let query = $state('');

	const scoped = $derived(
		vertical ? day.items.filter((item) => item.vertical === vertical) : day.items
	);
	const needle = $derived(query.trim().toLowerCase());
	const visible = $derived(
		needle
			? scoped.filter(
					(item) =>
						item.title.toLowerCase().includes(needle) ||
						item.summary.toLowerCase().includes(needle) ||
						item.key_points.some((point) => point.toLowerCase().includes(needle))
				)
			: scoped
	);
	const verticalNames = $derived(
		Object.fromEntries(day.verticals.map((ref) => [ref.id, ref.display_name]))
	);
</script>

{#each ui.sections as section (section)}
	{#if section === 'notice'}
		<DayNotice {day} />
	{:else if section === 'topics' && day.verticals.length > 0}
		<TopicPills
			verticals={day.verticals}
			active={vertical}
			total={scoped.length}
			shown={visible.length}
			{datePrefix}
			bind:query
			showFilter={ui.show_filter}
		/>
	{:else if section === 'items'}
		{#if day.items.length === 0}
			<EmptyDay date={day.date} {latest} />
		{:else if visible.length === 0}
			<p class="py-12 text-[0.9375rem] text-text-secondary">
				Nothing on today's page matches &ldquo;{query}&rdquo;.
			</p>
		{:else}
			{#each visible as item (item.item_id)}
				<DigestItemView
					{item}
					verticalName={verticalNames[item.vertical] ?? item.vertical}
					showMark={ui.source_mark}
				/>
			{/each}
		{/if}
	{/if}
{/each}
