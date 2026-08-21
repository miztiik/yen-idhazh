<script lang="ts">
	/** How sure we are about this summary, in words and one dot.
	 *
	 * Not a stripe, not a tint, not a card border. If most items land medium or
	 * low then a large treatment paints most of the page as broken, and the
	 * reader concludes the whole digest is - rather than that two items need
	 * care. One dot and a short sentence stays proportionate at any distribution.
	 */
	import { BANDS } from '$lib/bands';
	import type { ConfidenceBand } from '$lib/payload/types';

	let { band }: { band: ConfidenceBand } = $props();
	const copy = $derived(BANDS[band]);
</script>

{#if copy.showOnItem}
	<span class="inline-flex items-center gap-1.5" data-band={band}>
		<span
			class="h-1.5 w-1.5 shrink-0 rounded-full"
			style="background-color: {copy.token}"
			aria-hidden="true"
		></span>
		<span style={band === 'low' ? `color: ${copy.token}` : undefined}>{copy.label}</span>
	</span>
{/if}
