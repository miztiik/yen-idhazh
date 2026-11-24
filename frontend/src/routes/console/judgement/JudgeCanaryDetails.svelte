<script lang="ts">
	/** Show both recorded orders and the saved answer for each selected canary pair. */
	import type { CanaryReading } from '$lib/console/judge-canaries';
	import { longDate } from '$lib/format';
	import { numberFormatter, type NumberFormatConfig } from '$lib/number-format';

	let { reading, note = 'Not recorded.', selected = null, format }: {
		reading: CanaryReading | null; note?: string; selected?: string | null; format: NumberFormatConfig;
	} = $props();

	const number = $derived(numberFormatter(format));
	const exact = (n: number) => number(n, { exact: true });
	const matches = $derived(reading?.items.filter(({ outcome }) => outcome === 'Matched').length ?? 0);
</script>

<section class="pair-answers" aria-labelledby="judge-known-answers">
	<h4 id="judge-known-answers">
		{#if selected !== null}Pair answers for <time datetime={selected}>{longDate(selected)}</time> UTC
		{:else}Known-answer pairs{/if}
	</h4>
	{#if reading === null}
		<p>{note}</p>
	{:else}
		{#if reading.keyState === 'saved'}
			<p><strong>{exact(matches)}/{exact(reading.items.length)} pairs matched</strong> the saved agent-labelled key.
				{#if reading.kappa !== null && reading.eligible !== null}
					Cohen's kappa: {number(reading.kappa, { si: false })} across {exact(reading.eligible)} {reading.eligible === 1 ? 'pair' : 'pairs'}.
				{:else if reading.eligible !== null && reading.eligible < reading.items.length}
					Cohen's kappa not measured: only {exact(reading.eligible)} of {exact(reading.items.length)} pairs agreed in both orders.
				{:else if reading.eligible === reading.items.length}
					Cohen's kappa not measured: the chance-adjusted denominator was zero.
				{:else}
					Cohen's kappa not recorded.
				{/if}
			</p>
		{:else if reading.keyState === 'invalid'}
			<p>Saved key could not be read. The observed answers are not graded.</p>
		{:else if reading.items.length}
			<p>No saved key. The observed answers are not graded.</p>
		{:else}
			<p>No canary evidence recorded for this attempt.</p>
		{/if}
		{#if reading.items.length}
			<ul>
				{#each reading.items as item (item.id)}
					{@const absent = item.band === 'missing' ? 'No reply' : 'No valid answer'}
					<li>
						<strong>{item.id}</strong>
						<span>Expected: {item.expected ?? 'No usable key'} &middot;
							Original: {item.original ?? absent} &middot; Reversed: {item.reversed ?? absent}</span>
						<span class="outcome">{item.outcome}</span>
					</li>
				{/each}
			</ul>
		{/if}
	{/if}
</section>

<style>
	.pair-answers { display: grid; gap: var(--space-2); }
	h4, p { margin: 0; overflow-wrap: anywhere; }
	ul { list-style: none; margin: 0; padding: 0; }
	li {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-1) var(--space-3);
		padding-block: var(--space-2);
		border-block-start: 1px solid var(--color-rule);
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
		overflow-wrap: anywhere;
	}
	.outcome { margin-inline-start: auto; color: var(--color-text-secondary); }
</style>
