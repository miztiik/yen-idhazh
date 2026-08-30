<script lang="ts">
	/** A deterministic mark for a publication: no fetch, no asset, no trademark.
	 *
	 * A favicon would be a runtime third-party request that announces every
	 * reader to every publisher, and its failure mode is a broken-image glyph in
	 * the middle of a reading page. The name in type is the identifier; this is
	 * a scanning aid.
	 */
	import { monogram, swatchIndex } from '$lib/format';

	let { name, sourceId }: { name: string; sourceId: string } = $props();
	const swatch = $derived(`var(--source-swatch-${swatchIndex(sourceId)})`);
</script>

<span
	class="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-[0.3rem] text-[0.625rem] font-semibold tracking-tight text-text-secondary"
	style="background-color: {swatch}"
	aria-hidden="true"
>
	{monogram(name)}
</span>
