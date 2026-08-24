<script lang="ts">
	/** How sure we are about this summary, in words and one dot.
	 *
	 * Not a stripe, not a tint, not a card border. If most items land medium or
	 * low then a large treatment paints most of the page as broken, and the
	 * reader concludes the whole digest is - rather than that two items need
	 * care. One dot and a short sentence stays proportionate at any distribution.
	 *
	 * The sentence names what is missing rather than grading the item. A reader
	 * can act on "leaves out names or figures from the opening"; they cannot act
	 * on "mostly".
	 */
	import { BANDS, bandSentence } from '$lib/bands';
	import type { BandReason, ConfidenceBand } from '$lib/payload/types';

	let { band, reason = null }: { band: ConfidenceBand; reason?: BandReason | null } = $props();
	const copy = $derived(BANDS[band]);
	const sentence = $derived(bandSentence(band, reason));
</script>

{#if copy.showOnItem}
	<span class="inline-flex items-start gap-1.5" data-band={band} data-band-reason={reason}>
		<!-- Aligned to the first line, not to the block: a sentence wraps on a phone. -->
		<span
			class="mt-[0.45em] h-1.5 w-1.5 shrink-0 rounded-full"
			style="background-color: {copy.token}"
			aria-hidden="true"
		></span>
		<span style={band === 'low' ? `color: ${copy.token}` : undefined}>{sentence}</span>
	</span>
{/if}
