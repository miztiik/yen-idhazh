<script lang="ts">
	import { failedRows, type TelemetryRow } from '$lib/charts/series';
	import type { TimeWindow } from '$lib/charts/viewport';

	let {
		rows,
		window,
		selectedCode
	}: { rows: TelemetryRow[]; window: TimeWindow; selectedCode: string | null } = $props();

	const failures = $derived(failedRows(rows, window, selectedCode));
</script>

<section class="mt-8">
	<h2 class="text-[1.0625rem] font-semibold text-text">Failed items</h2>
	<p class="mt-1 text-[0.8125rem] text-text-tertiary">
		Panel chips filter this list. It names items, not article text.
	</p>
	{#if failures.length === 0}
		<p class="mt-3 text-[0.9375rem] text-text-secondary" data-failure-list="empty">
			No failed item is in this window.
		</p>
	{:else}
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
					{#each failures as row (`${row.run_id}-${row.item_id}`)}
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
	{/if}
</section>

