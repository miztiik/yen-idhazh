<script lang="ts">
	/** Lists Data explorer runs kept by this browser and reopens one without running it. */
	import Icon from '$lib/icons/Icon.svelte';
	import { dayMonth } from '$lib/format';
	import type { RecentRun } from './keep';

	let { runs, onPick }: { runs: readonly RecentRun[]; onPick: (run: RecentRun) => void } = $props();

	function time(iso: string): string {
		const date = new Date(iso);
		return `${dayMonth(date.toISOString().slice(0, 10))} ${String(date.getUTCHours()).padStart(2, '0')}:${String(date.getUTCMinutes()).padStart(2, '0')} UTC`;
	}
</script>

<details class="history-list">
	<summary><Icon id="history" /> History</summary>
	<div class="history-menu">
		<p class="storage">Kept in this browser only.</p>
		{#if runs.length === 0}
			<p>Nothing asked in this browser yet.</p>
		{:else}
			<ul>
				{#each runs as run (run.id)}
					<li>
						<button type="button" onclick={() => onPick(run)}>
							<span>{time(run.askedAt)} - {run.rows} {run.rows === 1 ? 'row' : 'rows'} in {run.ms} ms - {run.ledgers.join(', ')}</span>
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</details>

<style>
	.history-list {
		position: relative;
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-surface);
		padding-inline: var(--space-3);
	}

	summary {
		min-block-size: 2.75rem;
		display: flex;
		align-items: center;
		gap: var(--space-2);
		cursor: pointer;
		font-weight: 600;
	}

	.history-list[open] .history-menu {
		position: absolute;
		z-index: 10;
		inset-block-start: calc(100% + var(--space-1));
		inset-inline-start: 0;
		inline-size: min(28rem, calc(100vw - 2 * var(--space-4)));
		padding: var(--space-3);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-surface-raised);
		box-shadow: var(--shadow-md);
	}

	.history-menu {
		display: none;
	}

	.storage {
		color: var(--color-text-secondary);
		font-size: var(--text-sm);
	}

	p,
	ul {
		margin: var(--space-2) 0 0;
	}

	ul {
		display: grid;
		gap: var(--space-1);
		padding: 0;
		list-style: none;
	}

	button {
		inline-size: 100%;
		border: 0;
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--color-text);
		padding: var(--space-2);
		text-align: start;
	}

	button:hover,
	button:focus-visible {
		background: var(--tint-neutral);
	}
</style>
