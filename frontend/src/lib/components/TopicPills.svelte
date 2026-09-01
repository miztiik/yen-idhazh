<script lang="ts">
	/** Topic pills, plus an in-place filter.
	 *
	 * Pills rather than tabs: the vertical set is data-driven and varies per day,
	 * and pills read as filters over one list, which is what a topic is here.
	 * Only verticals actually present in the payload get a pill, so an empty one
	 * - which reads as broken software - cannot occur.
	 *
	 * The filter never navigates and never touches the URL. It searches only what
	 * is already on the page, and says how many it found, so it cannot imply an
	 * archive it has no way to reach.
	 *
	 * The row wraps. It was a horizontal scroll container until 2026-08-31, which
	 * is a control that hides its own contents and gives no hint of how much sits
	 * behind it. Topics past `topic_pills_max` fold into a native `<details>`
	 * instead, so the page still says how many there are and still works with no
	 * script (owner decision 3, 2026-08-31).
	 */
	import { base } from '$app/paths';
	import { dayRoot, verticalHref } from '$lib/links';
	import { splitPills } from '$lib/day-shape';
	import Icon from '$lib/icons/Icon.svelte';
	import { ICONS, type IconId } from '$lib/icons/generated';
	import type { DigestVerticalRef } from '$lib/payload/types';

	let {
		verticals,
		active,
		total,
		datePrefix = '',
		query = $bindable(''),
		shown,
		showFilter = true,
		pillsMax
	}: {
		verticals: DigestVerticalRef[];
		active: string | null;
		total: number;
		datePrefix?: string;
		query?: string;
		shown: number;
		showFilter?: boolean;
		pillsMax: number;
	} = $props();

	const root = $derived(dayRoot(base, datePrefix));
	const split = $derived(splitPills(verticals, active, pillsMax));

	// A vertical is declared in config and can be added without an icon. A pill
	// with no mark is fine; a pill that throws is not.
	function mark(id: string): IconId | null {
		const candidate = `topic-${id}`;
		return candidate in ICONS ? (candidate as IconId) : null;
	}
</script>

<nav
	class="sticky top-0 z-10 border-b border-rule bg-bg/85 py-3 backdrop-blur-sm"
	aria-label="Topics"
>
	<div class="flex flex-wrap items-center gap-2" data-topic-row>
		<a
			href={root}
			class="inline-flex min-h-11 items-center rounded-full border px-3.5 text-sm transition-colors"
			class:border-accent={active === null}
			class:text-accent={active === null}
			class:border-rule={active !== null}
			class:text-text-secondary={active !== null}
			aria-current={active === null ? 'page' : undefined}
		>
			All {total}
		</a>
		{#each split.shown as vertical (vertical.id)}
			<a
				href={verticalHref(base, datePrefix, vertical.id)}
				class="inline-flex min-h-11 items-center gap-1.5 rounded-full border px-3.5 text-sm whitespace-nowrap transition-colors"
				class:border-accent={active === vertical.id}
				class:text-accent={active === vertical.id}
				class:border-rule={active !== vertical.id}
				class:text-text-secondary={active !== vertical.id}
				aria-current={active === vertical.id ? 'page' : undefined}
			>
				{#if mark(vertical.id)}
					<Icon id={mark(vertical.id) as IconId} size={14} />
				{/if}
				{vertical.display_name}
				{vertical.count}
			</a>
		{/each}
		{#if split.folded.length > 0}
			<details class="max-w-full" data-topic-more={split.folded.length}>
				<summary
					class="inline-flex min-h-11 items-center rounded-full border border-rule px-3.5 text-sm text-text-secondary transition-colors"
				>
					+{split.folded.length} more
				</summary>
				<div class="mt-2 flex flex-wrap items-center gap-2">
					{#each split.folded as vertical (vertical.id)}
						<a
							href={verticalHref(base, datePrefix, vertical.id)}
							class="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-rule px-3.5 text-sm whitespace-nowrap text-text-secondary transition-colors"
						>
							{#if mark(vertical.id)}
								<Icon id={mark(vertical.id) as IconId} size={14} />
							{/if}
							{vertical.display_name}
							{vertical.count}
						</a>
					{/each}
				</div>
			</details>
		{/if}
	</div>

	{#if showFilter}
		<div class="mt-2 flex items-center gap-2">
			<label class="sr-only" for="page-filter">Filter today's stories</label>
			<input
				id="page-filter"
				type="search"
				bind:value={query}
				placeholder="Filter today's stories"
				autocomplete="off"
				class="min-h-11 w-full rounded-md border border-rule bg-surface px-3 text-base text-text placeholder:text-text-tertiary"
			/>
			{#if query}
				<span class="shrink-0 text-sm text-text-secondary">{shown} of {total}</span>
			{/if}
		</div>
	{/if}
</nav>

<style>
	/* The default disclosure triangle is dropped by `inline-flex` in Chrome and
	   Safari and kept in Firefox, where it would sit inside the pill's own
	   outline. The open row of topics below is the state indicator. */
	summary {
		cursor: pointer;
		list-style: none;
	}

	summary::-webkit-details-marker {
		display: none;
	}
</style>
