<script lang="ts">
	/** Which cause is worst, and then the rows behind it.
	 *
	 * The rows sort newest-first, which is the right shape for a detail and the
	 * wrong one for a decision: 25 rows of a 214-row spike were 25 rows of one
	 * code, and nothing on the page said so. A cause - a stage and a code - is
	 * the unit an operator acts on, so it is ranked above, and the rows stay as
	 * the detail behind a selected one.
	 *
	 * Breadth is the column that earns its width. One source changing its markup
	 * and the extractor being broken produce the same count. They do not produce
	 * the same number of sources.
	 *
	 * There is no cause text here and none is invented. The published projection
	 * withholds `detail`, which can carry fetched article text, so the code is
	 * everything the browser is given.
	 */
	import { rank, tailSentence, type Rankable, type RankedDisplay } from '$lib/charts/rank';
	import {
		failedRows,
		failureLedger,
		failureRowKey,
		type TelemetryRow
	} from '$lib/charts/series';
	import { sparklineMarks } from '$lib/charts/sparkline';
	import type { TimeWindow } from '$lib/charts/viewport';
	import RankedList from './RankedList.svelte';
	import Sparkline from './Sparkline.svelte';

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

	let selectedCause = $state<string | null>(null);

	const ledger = $derived(failureLedger(rows, window));
	const failures = $derived(failedRows(rows, window, selectedCode, selectedCause));
	// svelte-ignore state_referenced_locally
	let shown = $state(max);

	// A new window or a new chip is a new question. Opening it at 200 rows
	// because the last question needed them is answering the wrong one, and a
	// cause picked out of the previous window is not in this one.
	$effect(() => {
		void window.start;
		void window.end;
		void selectedCode;
		selectedCause = null;
	});

	// Kept apart from the reset above, which writes `selectedCause` and so
	// cannot read it without looping.
	$effect(() => {
		void selectedCause;
		shown = max;
	});

	function occurrence(ago: number): string {
		if (ago <= 0) return 'last on the newest day in view';
		return `last ${ago} ${ago === 1 ? 'day' : 'days'} earlier`;
	}

	function failureWord(count: number): string {
		return count === 1 ? 'failure' : 'failures';
	}

	const entries = $derived<Rankable<RankedDisplay>[]>(
		ledger.causes.map((cause) => ({
			key: cause.key,
			value: cause.count,
			// A tie goes to the more recent cause, so two equal counts hold the
			// same order on every build and the prerendered page does not move.
			tiebreak: -cause.lastAgo,
			row: {
				label: cause.code,
				status: cause.stage,
				value: `${cause.count} ${failureWord(cause.count)}`,
				context:
					`sources hit: ${cause.sources} of ${ledger.sourcesSeen}` +
					` - ${occurrence(cause.lastAgo)}`
			}
		}))
	);
	const ranked = $derived(rank(entries, max));
	const tail = $derived(
		tailSentence(ranked, {
			one: 'cause',
			many: 'causes',
			unitOne: 'failure',
			unitMany: 'failures'
		})
	);
	// Keyed by cause, because the snippet is handed a ranked row and the ranking
	// caps and reorders what it was built from.
	const trends = $derived(
		new Map(ledger.causes.map((cause) => [cause.key, sparklineMarks(cause.daily)]))
	);

	const page = $derived(failures.slice(0, shown));
	const remaining = $derived(Math.max(failures.length - page.length, 0));
	const scope = $derived(
		selectedCause
			? `${selectedCause} failures`
			: selectedCode
				? `${selectedCode} failures`
				: `failed ${failures.length === 1 ? 'item' : 'items'}`
	);
</script>

<section class="mt-8">
	<h2 class="text-[1.0625rem] font-semibold text-text">Why items failed</h2>
	<p class="mt-1 text-[0.8125rem] text-text-tertiary">
		One row per cause, worst first. A cause is a stage and the code it stopped on. Pick one to see
		the items behind it.
	</p>

	<div class="mt-3" data-failure-ledger>
		<RankedList
			caption="Failure causes in this window, most failures first"
			{ranked}
			maxText="{ranked.max} {failureWord(ranked.max)}"
			measured={ledger.rows > 0}
			unmeasuredNote="Nothing was recorded in this window."
			emptyNote="No item failed in this window."
			{tail}
			selectedKey={selectedCause}
			onSelect={(key) => (selectedCause = selectedCause === key ? null : key)}
		>
			{#snippet trend(row)}
				<Sparkline
					marks={trends.get(row.key) ?? sparklineMarks([])}
					label="Failures a day for {row.key} across this window"
				/>
			{/snippet}
		</RankedList>
	</div>

	<div class="mt-6 flex flex-wrap items-baseline justify-between gap-3">
		<h3 class="text-[0.9375rem] font-semibold text-text">Failed items</h3>
		{#if selectedCause}
			<button
				type="button"
				class="min-h-11 rounded-full border border-rule px-3 text-[0.75rem] text-text-secondary"
				onclick={() => (selectedCause = null)}
				data-failure-clear
			>
				Show every cause
			</button>
		{/if}
	</div>

	{#if failures.length === 0}
		<p class="mt-1 text-[0.8125rem] text-text-tertiary">
			Panel chips and the ledger above filter this list. It names items, not article text.
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
			Panel chips and the ledger above filter this list. It names items, not article text.
		</p>
		<div class="mt-3 overflow-x-auto" data-failure-list="rows">
			<table class="w-full text-[0.8125rem]">
				<thead class="text-text-tertiary">
					<tr class="border-b border-rule">
						<th class="py-2 text-start font-normal">Day</th>
						<th class="py-2 text-start font-normal">Source</th>
						<th class="py-2 text-start font-normal">Stage</th>
						<th class="py-2 text-start font-normal">Code</th>
					</tr>
				</thead>
				<tbody>
					<!-- The item id rides on the row rather than in a column. It is a
					     content address, it was the widest cell on the page, and nothing an
					     operator does starts from one. -->
					{#each page as row, index (failureRowKey(row, index))}
						<tr
							class="border-b border-rule"
							title={row.item_id}
							data-failure-item={row.item_id}
							data-failure-stage={row.stage}
							data-failure-code={row.code}
						>
							<td class="py-2 tabular-nums">{row.date}</td>
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

