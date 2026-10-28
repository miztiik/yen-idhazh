<script lang="ts">
	/** Fetch and render one source-backed actor/claim grid. */
	import { base } from '$app/paths';
	import { navigating } from '$app/state';
	import { whenNear } from '$lib/reveal';
	import {
		isWhowhatGridData,
		publishedWhowhatGrid,
		refusedWhowhatGridData
	} from '$lib/payload/whowhat-grid';
	import { whowhatVisualState } from '$lib/visual/whowhat-state';
	import type { DigestVisual, WhowhatGridData } from '$lib/payload/types';

	let { visual, itemId }: { visual: DigestVisual; itemId: string } = $props();
	const wanted = $derived(
		visual.kind === 'whowhat' && visual.state === 'rendered' && visual.data_path
			? visual.data_path
			: null
	);
	let loaded = $state<{ file: string; data: WhowhatGridData | null } | null>(null);
	let near = $state(false);
	let settled = $state<string | null>(null);
	const gridState = $derived(whowhatVisualState(wanted, settled, loaded));
	const current = $derived(gridState === 'ready' ? loaded?.data ?? null : null);

	async function read(file: string, signal: AbortSignal): Promise<WhowhatGridData | null> {
		if (!publishedWhowhatGrid(file, itemId)) {
			console.warn('[digest] whowhat grid path is not a published item asset');
			return null;
		}
		try {
			const response = await fetch(`${__ASSET_BASE_URL__ || base}/${file}`, { signal });
			if (!response.ok) {
				console.warn(`[digest] ${file}: not available (${response.status}), so it is not drawn`);
				return null;
			}
			const data: unknown = await response.json();
			if (!isWhowhatGridData(data, itemId)) {
				console.warn(`[digest] ${file}: ${refusedWhowhatGridData(data, itemId)}, so it is not drawn`);
				return null;
			}
			return data;
		} catch (error) {
			if (signal.aborted) return null;
			console.warn(`[digest] ${file} could not be read, so it is not drawn`, error);
			return null;
		}
	}

	$effect(() => {
		const file = wanted;
		if (!near || !file || navigating.to !== null || settled === file) return;
		const request = new AbortController();
		void read(file, request.signal).then((data) => {
			if (!request.signal.aborted) {
				settled = file;
				loaded = { file, data };
			}
		});
		return () => request.abort();
	});

	function askWhenNear(node: Element): { destroy: () => void } {
		return { destroy: whenNear(node, () => { near = true; }) };
	}

	function retry(): void {
		settled = null;
		loaded = null;
	}
</script>

<div data-whowhat-state={gridState}>
	{#if current}
		<section class="my-4 overflow-hidden rounded-md border border-rule bg-surface">
			<div class="border-b border-rule px-3 py-2 text-sm font-semibold leading-snug text-text">
				Who did what
			</div>
			<div class="w-full">
				<table class="w-full table-fixed border-collapse text-left text-xs leading-normal">
					<caption class="sr-only">Who did what</caption>
					<thead>
						<tr class="text-text-secondary">
							<th scope="col" class="w-2/5 px-3 py-2 font-semibold">Who</th>
							<th scope="col" class="px-3 py-2 font-semibold">What</th>
						</tr>
					</thead>
					<tbody>
						{#each current.rows as row, index (`${index}-${row.actor?.element_id ?? 'empty'}`)}
							<tr class="border-t border-rule">
								<td class="break-words px-3 py-2 align-top text-text">
									{row.actor?.display_text ?? ''}
								</td>
								<td class="break-words px-3 py-2 align-top text-text-secondary">
									{row.claim?.display_text ?? ''}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>
	{:else if gridState === 'loading'}
		<div class="whowhat-slot" use:askWhenNear></div>
	{/if}
	<div aria-live="polite">
		{#if gridState === 'failed'}
			<section class="grid-failure" role="status">
				<p class="grid-failure-copy">This actor and claim grid could not be loaded.</p>
				<button
					type="button"
					class="grid-retry focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
					onclick={retry}
				>
					Try again
				</button>
			</section>
		{/if}
	</div>
</div>

<style>
	.whowhat-slot {
		height: 0;
	}

	.grid-failure {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--space-2);
		margin-block: var(--space-4);
		padding: var(--space-4);
		border: 1px solid var(--item-edge);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
	}

	.grid-failure-copy {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.grid-retry {
		display: inline-flex;
		align-items: center;
		min-height: var(--space-6);
		margin-block-start: var(--space-2);
		padding-inline: var(--space-4);
		border: 1px solid var(--color-accent);
		border-radius: var(--radius-md);
		background: transparent;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-accent);
		cursor: pointer;
	}

	.grid-retry:hover {
		background: var(--tint-accent);
	}
</style>
