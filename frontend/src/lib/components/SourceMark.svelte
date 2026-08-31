<script lang="ts">
	/** A deterministic mark for a publication, and the item's read state.
	 *
	 * A favicon would be a runtime third-party request that announces every
	 * reader to every publisher, and its failure mode is a broken-image glyph in
	 * the middle of a reading page. The name in type is the identifier; this is
	 * a scanning aid.
	 *
	 * It carries one more thing now: a ring filled when the item is unread and
	 * hollow when it is read. Fill present or absent is an area difference, so
	 * it survives a cheap panel, sunlight and arm's length. Dimmer text and a
	 * lighter weight do not - both are less ink, so they are one signal twice
	 * and they fail together.
	 *
	 * The mark stays hidden from assistive technology. Its letters repeat the
	 * source name printed beside it, and the read state is a word in the
	 * heading rather than a colour.
	 */
	import { monogram, swatchIndex } from '$lib/format';

	let {
		name,
		sourceId,
		read = false
	}: { name: string; sourceId: string; read?: boolean } = $props();
	const swatch = $derived(`var(--source-swatch-${swatchIndex(sourceId)})`);
</script>

<span class="source-mark" data-read={read} style="--mark-fill: {swatch}" aria-hidden="true">
	{monogram(name)}
</span>

<style>
	/* Sized in rem, so the ring grows with a reader who set their browser text
	   larger. A pixel count would leave the mark behind the words beside it. */
	.source-mark {
		display: inline-flex;
		flex: none;
		align-items: center;
		justify-content: center;
		inline-size: 1.75rem;
		block-size: 1.75rem;
		border: 1px solid var(--color-rule-strong);
		border-radius: var(--radius-full);
		background: var(--mark-fill);
		color: var(--color-text-secondary);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		font-weight: 600;
		letter-spacing: -0.02em;
	}

	/* Read: the fill goes and the edge steps back one. The border is a hairline
	   in both states, so what changed is the area rather than the weight. */
	.source-mark[data-read='true'] {
		background: none;
		border-color: var(--color-rule);
	}
</style>
