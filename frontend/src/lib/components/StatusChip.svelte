<script lang="ts">
	/** A state, in a word and a hue.
	 *
	 * The console printed states as plain text inside table cells - "rested",
	 * "failed", "quarantined" - which reads at the same weight as the feed id
	 * beside it. A chip separates the state from its subject, and the hue means
	 * the same thing here as it does on a confidence mark: good, watch, broken.
	 *
	 * The word is never dropped in favour of the colour. A hue alone is a claim
	 * only a sighted reader who knows the convention can read.
	 */
	let {
		label,
		tone = 'neutral'
	}: {
		label: string;
		tone?: 'neutral' | 'good' | 'warn' | 'bad';
	} = $props();
</script>

<span class="chip" data-chip={label} data-tone={tone}>{label}</span>

<style>
	.chip {
		display: inline-flex;
		align-items: center;
		padding: 1px var(--space-2);
		border: 1px solid currentColor;
		border-radius: var(--radius-full);
		font-size: var(--text-xs);
		line-height: 1.6;
		white-space: nowrap;
		color: var(--color-text-tertiary);
	}

	.chip[data-tone='good'] {
		color: var(--band-high);
	}
	.chip[data-tone='warn'] {
		color: var(--band-medium);
	}
	.chip[data-tone='bad'] {
		color: var(--band-low);
	}
</style>
