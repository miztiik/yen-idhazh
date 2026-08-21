<script lang="ts">
	/** The aggregate, where the colour is honest.
	 *
	 * "How much of today can you trust" is a day-level question. Colour plus
	 * number plus position, spent once, instead of seventeen small warnings.
	 */
	import { BAND_ORDER, BANDS } from '$lib/bands';
	import type { ConfidenceBand } from '$lib/payload/types';

	let { counts }: { counts: Record<ConfidenceBand, number> } = $props();
	const total = $derived(BAND_ORDER.reduce((sum, band) => sum + counts[band], 0));
	const present = $derived(BAND_ORDER.filter((band) => counts[band] > 0));
</script>

{#if total > 0}
	<div class="flex flex-col gap-2">
		<div
			class="flex h-1.5 w-full overflow-hidden rounded-full bg-rule"
			role="img"
			aria-label={present
				.map((band) => `${counts[band]} ${BANDS[band].label.toLowerCase()}`)
				.join(', ')}
		>
			{#each present as band (band)}
				<span
					style="width: {(counts[band] / total) * 100}%; background-color: {BANDS[band].token}"
				></span>
			{/each}
		</div>
		<p class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.8125rem] text-text-secondary">
			{#each present as band (band)}
				<span class="inline-flex items-center gap-1.5">
					<span
						class="h-1.5 w-1.5 rounded-full"
						style="background-color: {BANDS[band].token}"
						aria-hidden="true"
					></span>
					{counts[band]}
					{BANDS[band].label.toLowerCase()}
				</span>
			{/each}
		</p>
	</div>
{/if}
