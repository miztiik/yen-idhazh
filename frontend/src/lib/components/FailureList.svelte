<script lang="ts">
	/** The rows behind the shape, on demand.
	 *
	 * Every failed row in the window measured 7824px and pushed the compression
	 * chart 9000px down the page. The list keeps its job - after a spike the
	 * operator needs rows - and gives up its claim on the scroll bar.
	 */
	import { failedRows, type TelemetryRow } from '$lib/charts/series';
	import type { TimeWindow } from '$lib/charts/viewport';

	let {
		rows,
		window,
		selectedCode,
		max
	}: {
		rows: TelemetryRow[];
		window: TimeWindow;
		selectedCode: string | null;
		max: number;
	} = $props();

	const failures = $derived(failedRows(rows, window, selectedCode));
	// svelte-ignore state_referenced_locally
	let shown = $state(max);

	// A new window or a new chip is a new question. Opening it at 200 rows
	// because the last question needed them is answering the wrong one.
	$effect(() => {
		void window.start;
		void window.end;
		void selectedCode;
		shown = max;
	});

	const page = $derived(failures.slice(0, shown));
	const remaining = $derived(Math.max(failures.length - page.length, 0));
	const scope = $derived(
		selectedCode ? `${selectedCode} failures` : `failed ${failures.length === 1 ? 'item' : 'items'}`
	);
</script>

<section class="mt-8">
	<h2 class="text-[1.0625rem] font-semibold text-text">Failed items</h2>
	{#if failures.length === 0}
		<p class="mt-1 text-[0.8125rem] text-text-tertiary">
			Panel chips filter this list. It names items, not article text.
		</p>
		<p class="mt-3 text-[0.9375rem] text-text-secondary" data-failure-list="empty">
			No failed item is in this window.
		</p>
	{:else}
		<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-failure-scope>
			{#if remaining > 0}
				Showing {page.length} of {failures.length}
				{scope} in this window.
			{:else}
				{failures.length}
				{scope} in this window.
			{/if}
			Panel chips filter this list. It names items, not article text.
		</p>
		<div class="mt-3 overflow-x-auto" data-failure-list="rows">
			<table class="w-full text-[0.8125rem]">
				<thead class="text-text-tertiary">
					<tr class="border-b border-rule">
						<th class="py-2 text-start font-normal">Day</th>
						<th class="py-2 text-start font-normal">Item</th>
						<th class="py-2 text-start font-normal">Source</th>
						<th class="py-2 text-start font-normal">Stage</th>
						<th class="py-2 text-start font-normal">Code</th>
					</tr>
				</thead>
				<tbody>
					{#each page as row (`${row.run_id}-${row.item_id}`)}
						<tr class="border-b border-rule" data-failure-code={row.code}>
							<td class="py-2 tabular-nums">{row.date}</td>
							<td class="py-2">{row.item_id}</td>
							<td class="py-2">{row.source_id}</td>
							<td class="py-2">{row.stage}</td>
							<td class="py-2">{row.code || 'unknown'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		{#if remaining > 0}
			<button
				type="button"
				class="mt-3 min-h-11 w-full text-[0.8125rem] text-accent hover:underline"
				onclick={() => (shown = page.length + max)}
				data-failure-more
			>
				Show {Math.min(remaining, max)} more
			</button>
		{/if}
	{/if}
</section>

