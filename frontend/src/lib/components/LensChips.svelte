<script lang="ts">
	/** The topics an item's own words earned, as inert tinted chips.
	 *
	 * Inert on purpose. On a page grouped by desk, "War" beside a World item and
	 * beside an Energy item tells the reader those two are the same story seen
	 * twice, which a desk heading cannot say. Filtering to it would leave two
	 * items on a seventeen-item day.
	 *
	 * Outline means you can tap it; a tinted fill means it is telling you
	 * something. That is what makes an inert chip honest beside the outlined
	 * topic pills above.
	 */
	import { LENS_NAMES, shownLenses } from '$lib/payload/lenses';

	let { lenses }: { lenses: readonly string[] | undefined } = $props();

	const shown = $derived(shownLenses(lenses));
</script>

{#if shown.length}
	<!-- Read aloud, the desk name and the topic run together into something we
	     did not say. The relation word is for that ear only. -->
	<span class="sr-only">Also about:</span>
	{#each shown as id (id)}
		<span class="lens-chip" data-lens={id}>{LENS_NAMES[id]}</span>
	{/each}
{/if}

<style>
	.lens-chip {
		display: inline-block;
		padding: var(--space-1) var(--space-2);
		border-radius: var(--radius-full);
		background: var(--tint-accent);
		color: var(--color-text-secondary);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		font-weight: 500;
		text-transform: none;
		letter-spacing: normal;
		white-space: nowrap;
	}
</style>
