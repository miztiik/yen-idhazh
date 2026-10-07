<script lang="ts">
	/** Which cause is worst, then which source it cost the most, then the rows.
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
	 * Which source is the second ranking, and it is the one column of the item
	 * table nothing above it answered. A cause says what broke; a source says
	 * where, and the two answer different questions about the same failures.
	 *
	 * The rows themselves sit behind a disclosure. They are the evidence and the
	 * address in them is where troubleshooting one URL starts, so they survive
	 * verbatim - but they are also the only child of this page that can outgrow
	 * the screen, and a shut disclosure is what keeps the two rankings readable.
	 *
	 * There is no cause text here and none is invented. The published projection
	 * withholds `detail`, which can carry fetched article text, so the code is
	 * everything the browser is given.
	 */
	import { rank, tailSentence, type Rankable, type RankedDisplay } from '$lib/charts/rank';
	import { gridStep, type GridPick } from '$lib/charts/readout';
	import {
		failedRows,
		failureLedger,
		failureRowKey,
		grouped,
		sourceLosses,
		type TelemetryRow
	} from '$lib/charts/series';
	import { sparklineMarks, sparklineReadout } from '$lib/charts/sparkline';
	import { daysInWindow, type TimeWindow } from '$lib/charts/viewport';
	import { countDays } from '$lib/console/span-words';
	import ChartReadout from './ChartReadout.svelte';
	import RankedList from './RankedList.svelte';
	import Sparkline from './Sparkline.svelte';

	let {
		rows,
		window,
		selectedCode,
		max,
		sourceMax,
		readoutMaxShare
	}: {
		rows: TelemetryRow[];
		window: TimeWindow;
		selectedCode: string | null;
		max: number;
		/** How many sources the ranking draws before its tail sentence -
		 * `console.source_rows`. */
		sourceMax: number;
		/** `chart.readout_max_share`. */
		readoutMaxShare: number;
	} = $props();

	let selectedCause = $state<string | null>(null);
	let selectedSource = $state<string | null>(null);
	let rowsOpen = $state(false);

	const ledger = $derived(failureLedger(rows, window));
	const losses = $derived(sourceLosses(rows, window));
	const failures = $derived(
		failedRows(rows, window, selectedCode, selectedCause, selectedSource)
	);
	// svelte-ignore state_referenced_locally
	let shown = $state(max);

	// A new window or a new chip is a new question. Opening it at 200 rows
	// because the last question needed them is answering the wrong one, and a
	// cause or a source picked out of the previous window is not in this one.
	$effect(() => {
		void window.start;
		void window.end;
		void selectedCode;
		selectedCause = null;
		selectedSource = null;
	});

	// Kept apart from the reset above, which writes both selections and so
	// cannot read them without looping.
	$effect(() => {
		void selectedCause;
		void selectedSource;
		shown = max;
	});

	/** A window of one day, where every row was last seen on that day, so a row
	 * says nothing about when. */
	const oneDay = $derived(window.start === window.end);

	/** When a row's failures were last seen, joined to the row by a dash, or
	 * nothing at one day. */
	function lastSeen(ago: number): string {
		if (oneDay) return '';
		return ` - ${ago <= 0 ? 'last on the newest day in view' : `last ${countDays(ago)} earlier`}`;
	}

	function failureWord(count: number): string {
		return count === 1 ? 'failure' : 'failures';
	}

	function articleWord(count: number): string {
		return count === 1 ? 'article' : 'articles';
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
				value: `${grouped(cause.count)} ${failureWord(cause.count)}`,
				context: `sources hit: ${cause.sources} of ${ledger.sourcesSeen}${lastSeen(cause.lastAgo)}`
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
	// A trend is built only where the ranking drew its cause. `ranked` caps and
	// reorders `ledger.causes`, and the snippet is handed a drawn row, so a
	// sparkline for a capped-off cause is a line nothing renders. Keyed by cause,
	// which is what the snippet looks a row up by. `daily` holds one count for
	// each day of the window, so each count takes that day's date.
	const days = $derived(daysInWindow(window));
	const dailyByCause = $derived(new Map(ledger.causes.map((cause) => [cause.key, cause.daily])));
	const trends = $derived(
		new Map(
			ranked.rows.map((row) => [
				row.key,
				sparklineMarks(
					(dailyByCause.get(row.key) ?? []).map((value, index) => ({ date: days[index], value }))
				)
			])
		)
	);
	/** Which drawn row each cause is, so a line knows the row it reports for. */
	const rowOf = $derived(new Map(ranked.rows.map((row, index) => [row.key, index])));

	/** The row and the day the ledger's lines have picked, or null for rest: the
	 * worst cause on the newest day, which is the one reading most worth seeing
	 * without a tap. One pick for every line, so only one row reads at a time. */
	let trendPick = $state<GridPick | null>(null);
	const trendColumns = $derived(trends.get(ranked.rows[0]?.key ?? '')?.dates.length ?? 0);
	const trendDrawn = $derived(
		ranked.rows.length > 0 && [...trends.values()].some((marks) => !marks.empty)
	);
	/** The one strip under the ledger: the picked row's line, built by the same
	 * function a line on its own prints its strip with. */
	const trendReadout = $derived.by(() => {
		const row = ranked.rows[trendPick?.row ?? 0];
		const marks = row === undefined ? undefined : trends.get(row.key);
		if (row === undefined || marks === undefined || marks.empty) return null;
		return sparklineReadout(
			marks,
			{ label: row.key, format: (value) => `${grouped(value)} ${failureWord(value)}` },
			[]
		);
	});

	// A new window is a new set of days, so a pick into the old one is dropped.
	$effect(() => {
		void window.start;
		void window.end;
		trendPick = null;
	});

	/** A row's line reports every change: a day, or null when the pointer left. */
	function pointAt(key: string, column: number | null): void {
		const row = rowOf.get(key);
		trendPick = row === undefined || column === null ? null : { row, column };
	}

	/** The ledger's one tab stop for all of its lines. Keys that land on a row's
	 * own button belong to that button, so only the stop itself answers them. */
	function stepTrend(event: KeyboardEvent): void {
		if (event.target !== event.currentTarget) return;
		const next = gridStep(
			event.key,
			trendPick ?? { row: 0, column: 0 },
			ranked.rows.length,
			trendColumns
		);
		if (next === undefined) return;
		event.preventDefault();
		// The ledger sits inside the viewport control, which pans on the same two
		// arrows; one step through the days must not also move the window.
		event.stopPropagation();
		trendPick = next;
	}

	function enterTrend(event: FocusEvent): void {
		if (event.target === event.currentTarget && trendPick === null && trendColumns > 0) {
			trendPick = { row: 0, column: 0 };
		}
	}

	function leaveTrend(event: FocusEvent): void {
		if (event.target === event.currentTarget) trendPick = null;
	}

	const sourceEntries = $derived<Rankable<RankedDisplay>[]>(
		losses.sources.map((source) => ({
			key: source.key,
			value: source.lost,
			tiebreak: -source.lastAgo,
			row: {
				label: source.key,
				// The denominator rides in the value rather than under it: a source
				// that lost 42 of 42 articles has stopped working, and one that lost
				// 42 of 500 had a bad afternoon, and the count alone cannot tell them
				// apart. No tint and no verdict - per-source yield is not measurable
				// until the ledger is thirty days deep.
				value: `${grouped(source.lost)} of ${grouped(source.articles)} ${articleWord(source.articles)}`,
				context: `${source.cause ?? `${source.causes} causes`}${lastSeen(source.lastAgo)}`
			}
		}))
	);
	const sourceRanked = $derived(rank(sourceEntries, sourceMax));
	const sourceTail = $derived(
		tailSentence(sourceRanked, {
			one: 'source',
			many: 'sources',
			unitOne: 'lost article',
			unitMany: 'lost articles'
		})
	);

	// A picked row opens the rows it filters. A filter whose result is behind a
	// shut disclosure is a control with no visible effect.
	function pickCause(key: string) {
		selectedCause = selectedCause === key ? null : key;
		if (selectedCause) rowsOpen = true;
	}

	function pickSource(key: string) {
		selectedSource = selectedSource === key ? null : key;
		if (selectedSource) rowsOpen = true;
	}

	const page = $derived(failures.slice(0, shown));
	const remaining = $derived(Math.max(failures.length - page.length, 0));
	const picked = $derived(selectedCause ?? selectedCode);
	const scope = $derived(
		picked && selectedSource
			? `${picked} ${failureWord(failures.length)} from ${selectedSource}`
			: picked
				? `${picked} ${failureWord(failures.length)}`
				: selectedSource
					? `${failureWord(failures.length)} from ${selectedSource}`
					: `failed ${failures.length === 1 ? 'item' : 'items'}`
	);
</script>

<section class="mt-8">
	<h2 class="text-[1.0625rem] font-semibold text-text">Why items failed</h2>
	<p class="mt-1 text-[0.8125rem] text-text-tertiary">
		One row per cause, worst first. A cause is a stage and the code it stopped on. Pick one to see
		the items behind it.
	</p>

	<!-- Every row's line reads into the one strip under the ledger, which prints
	     the row the reader pointed at: ten strips under ten rows would print one
	     date ten times and break the one-line rows that make this a ranking. The
	     rows are drawn from the month the page fetches, so the strip arrives with
	     them and is never in the prerendered document. -->
	<div
		class="mt-3"
		data-failure-ledger
		data-readout-columns={trendDrawn && trendReadout !== null ? trendColumns : undefined}
		data-readout-fetched="yes"
	>
		<!-- One tab stop for every row's line. Up and Down step causes and Left and
		     Right step days; each row's own button is a stop of its own. -->
		<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
		<div
			class="failure-trends"
			role="group"
			aria-label="Failures a day for each cause across this window"
			tabindex={trendDrawn ? 0 : undefined}
			onkeydown={trendDrawn ? stepTrend : undefined}
			onfocusin={trendDrawn ? enterTrend : undefined}
			onfocusout={trendDrawn ? leaveTrend : undefined}
		>
			<RankedList
				caption="Failure causes in this window, most failures first"
				{ranked}
				maxText="{grouped(ranked.max)} {failureWord(ranked.max)}"
				measured={ledger.rows > 0}
				unmeasuredNote="Nothing was recorded in this window."
				emptyNote="No item failed in this window."
				{tail}
				selectedKey={selectedCause}
				onSelect={pickCause}
			>
				{#snippet trend(row)}
					<Sparkline
						marks={trends.get(row.key) ?? sparklineMarks([])}
						label="Failures a day for {row.key} across this window"
						series={{
							label: row.key,
							format: (value) => `${grouped(value)} ${failureWord(value)}`
						}}
						strip={{
							onSelect: (column) => pointAt(row.key, column),
							selected: trendPick !== null && trendPick.row === rowOf.get(row.key)
								? trendPick.column
								: null
						}}
					/>
				{/snippet}
			</RankedList>
		</div>
		{#if trendDrawn && trendReadout !== null}
			<ChartReadout
				readout={trendReadout}
				at={trendPick?.column ?? null}
				name="failure-trends"
				maxShare={readoutMaxShare}
				hint="Point at a cause's line to read a day. Up and Down step causes, Left and Right step days, Escape returns to the worst cause on the newest day."
			/>
		{/if}
	</div>

	<h3 class="mt-8 text-[0.9375rem] font-semibold text-text">Which sources lost the most</h3>
	<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-source-losses-intro>
		One row per source, most articles lost first. The second number is every article the window saw
		from that source, so a source that lost all of them reads differently from one that lost a few.
		Pick one to see the items behind it.
	</p>

	<div class="mt-3" data-source-losses>
		<RankedList
			caption="Sources in this window, most articles lost first"
			ranked={sourceRanked}
			maxText="{grouped(sourceRanked.max)} {articleWord(sourceRanked.max)}"
			measured={losses.rows > 0}
			unmeasuredNote="Nothing was recorded in this window."
			emptyNote="No source lost an article in this window."
			tail={sourceTail}
			selectedKey={selectedSource}
			onSelect={pickSource}
		/>
	</div>

	<details class="console-disclosure mt-6" bind:open={rowsOpen} data-failure-rows>
		<summary class="console-summary" data-failure-toggle>
			{#if failures.length === 0}
				No failed item to list
			{:else}
				Show the {grouped(failures.length)}
				{scope}
			{/if}
		</summary>

		{#if selectedCause || selectedSource}
			<button
				type="button"
				class="mt-3 min-h-11 rounded-full border border-rule px-3 text-[0.75rem] text-text-secondary"
				onclick={() => {
					selectedCause = null;
					selectedSource = null;
				}}
				data-failure-clear
			>
				Show every failure
			</button>
		{/if}

		{#if failures.length === 0}
			<p class="mt-3 text-[0.9375rem] text-text-secondary" data-failure-list="empty">
				No failed item is in this window.
			</p>
			<p class="mt-1 text-[0.8125rem] text-text-tertiary">
				The code chips and the two rankings above filter this list. It names items, not article
				text.
			</p>
		{:else}
			<p class="mt-3 text-[0.8125rem] text-text-tertiary" data-failure-scope>
				{#if remaining > 0}
					Showing {grouped(page.length)} of {grouped(failures.length)}
					{scope} in this window.
				{:else}
					{grouped(failures.length)}
					{scope} in this window.
				{/if}
				The code chips and the two rankings above filter this list. It names items, not article
				text.
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
								data-failure-source={row.source_id}
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
	</details>
</section>

<style>
	.failure-trends {
		border-radius: var(--radius-md);
	}

	.failure-trends:focus-visible {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}
</style>

