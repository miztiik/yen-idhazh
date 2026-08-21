<script lang="ts">
	/** Operator instrumentation, off the reading path. No design budget, and one
	 * obligation: state its own denominator so a count is never mistaken for a
	 * census. Hand-written markup - a chart library would outweigh the data. */
	import { BAND_ORDER, BANDS } from '$lib/bands';
	import { longDate } from '$lib/format';
	import type { ConfidenceBand } from '$lib/payload/types';

	let { data } = $props();

	const byDate = $derived.by(() => {
		const days = new Map<string, Record<ConfidenceBand, number>>();
		for (const row of data.rows) {
			const date = String(row.date ?? '');
			const band = String(row.band ?? '') as ConfidenceBand;
			if (!date || !BAND_ORDER.includes(band)) continue;
			const bucket = days.get(date) ?? { high: 0, medium: 0, low: 0 };
			bucket[band] += 1;
			days.set(date, bucket);
		}
		return [...days.entries()].sort((a, b) => b[0].localeCompare(a[0]));
	});
	const widest = $derived(
		Math.max(1, ...byDate.map(([, counts]) => counts.high + counts.medium + counts.low))
	);
</script>

<svelte:head>
	<title>Scores &mdash; {data.ui.site_title}</title>
</svelte:head>

<section class="py-6">
	<h1 class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text">Scores</h1>
	<p class="mt-1 text-[0.9375rem] text-text-secondary">
		{data.rows.length} scored {data.rows.length === 1 ? 'item' : 'items'} across {byDate.length}
		{byDate.length === 1 ? 'day' : 'days'}. This page shows what was scored, not what was published.
	</p>

	{#if byDate.length === 0}
		<p class="mt-8 text-[0.9375rem] text-text-secondary">
			The ledger is empty. Nothing has been scored yet.
		</p>
	{:else}
		<ul class="mt-6">
			{#each byDate as [date, counts] (date)}
				{@const total = counts.high + counts.medium + counts.low}
				<li class="border-b border-rule py-3">
					<div class="flex items-baseline justify-between gap-3">
						<span class="text-[0.9375rem] text-text">{longDate(date)}</span>
						<span class="font-data text-[0.8125rem] tabular-nums text-text-tertiary">
							{total}
						</span>
					</div>
					<div
						class="mt-2 flex h-2 overflow-hidden rounded-full bg-rule"
						style="width: {(total / widest) * 100}%"
						role="img"
						aria-label={BAND_ORDER.map((b) => `${counts[b]} ${BANDS[b].label}`).join(', ')}
					>
						{#each BAND_ORDER as band (band)}
							{#if counts[band] > 0}
								<span
									style="width: {(counts[band] / total) * 100}%; background-color: {BANDS[band]
										.token}"
								></span>
							{/if}
						{/each}
					</div>
				</li>
			{/each}
		</ul>
	{/if}
</section>
