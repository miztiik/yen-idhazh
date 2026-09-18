<script lang="ts">
	/** What the judge said about the line, split at the line itself.
	 *
	 * Four counts, one line over time, two population strips and a shut table.
	 *
	 * **The cells say ELIGIBLE and never MERGED.** The record holds counts in
	 * slots rather than pairs, so splitting it says which side of the line a
	 * verdict fell on and nothing more. Whether the day merged a pair depends on
	 * two things the record never saw - a group is refused unless every pair in it
	 * clears the line, and two items on different published days never fold at
	 * all. A cell labelled MERGED would overstate what happened, which is the
	 * exact class of defect this page exists to catch.
	 *
	 * **One line over time, and only one.** The other three cells only ever rise,
	 * because the record only accumulates; four rising lines would say the record
	 * got bigger, which is what the date axis already says.
	 *
	 * **The two strips replaced a 120-slot chart.** 120 slots and two series in a
	 * 190 px plot is 240 marks changing by single counts a day - a grey wall. Two
	 * ranges on one score axis answer the question a reader actually brings: do
	 * the two populations still separate?
	 */
	import { chartWidth, frame, linearAxis, observeWidth } from '$lib/charts/frame';
	import Panel from '$lib/components/Panel.svelte';
	import { grouped } from '$lib/charts/series';
	import {
		populationRange,
		precisionCorridor,
		precisionMiss,
		rebin,
		splitAtLine,
		type ScoreRecord
	} from '$lib/console/verdict-split';

	let {
		record,
		applied,
		discardShare,
		axisMultiple,
		width,
		figures
	}: {
		/** Null where no day has folded a record yet. */
		record: ScoreRecord | null;
		/** The line the newest day was built with. */
		applied: number;
		discardShare: number;
		axisMultiple: number;
		width: number;
		/** The day's three counts. Null where the ledger holds no answer. */
		figures: { inBand: number | null; judged: number | null; usable: number | null };
	} = $props();

	/** The width the table rebins to. One row a fifth of the numbers, at the
	 * resolution a reader can compare off a page. */
	const TABLE_WIDTH = 0.005;
	const STRIP_HEIGHT = 96;

	let measured = $state<number | null>(null);

	const split = $derived(
		record === null
			? { eligibleAgreed: 0, eligibleDisagreed: 0, refusedAgreed: 0, refusedDisagreed: 0 }
			: splitAtLine(record, applied)
	);
	const miss = $derived(precisionMiss(split));
	const corridor = $derived(precisionCorridor(discardShare, axisMultiple));
	const rows = $derived(record === null ? [] : rebin(record, TABLE_WIDTH));
	const agreed = $derived(record === null ? null : populationRange(record, 'same'));
	const disagreed = $derived(record === null ? null : populationRange(record, 'different'));

	const box = $derived(frame(chartWidth(measured, width), STRIP_HEIGHT));
	const xAxis = $derived(
		linearAxis(record === null ? [0.88, 1] : [record.bandLow, record.bandHigh], [
			box.left,
			box.right
		], { tickCount: 4, zero: false, nice: false })
	);

	function reads(value: number): string {
		return value.toFixed(3);
	}

	function percent(share: number | null): string {
		return share === null ? '-' : `${(share * 100).toFixed(1)}%`;
	}

	function figure(value: number | null): string {
		// A dash where the ledger holds no answer, never a zero. Null and zero are
		// different facts and a zero here would say the day drew nothing.
		return value === null ? '-' : grouped(value);
	}

	const cells = $derived([
		{
			key: 'eligible-agreed',
			words: 'Eligible to merge, and the judge agrees',
			count: split.eligibleAgreed
		},
		{
			key: 'eligible-disagreed',
			words: 'Eligible to merge, and the judge disagrees',
			count: split.eligibleDisagreed
		},
		{
			key: 'refused-disagreed',
			words: 'Not eligible, and the judge disagrees',
			count: split.refusedDisagreed
		},
		{
			key: 'refused-agreed',
			words: 'Not eligible, and the judge agrees',
			count: split.refusedAgreed
		}
	]);
</script>

<Panel
	title="What the judge said about the line"
	note="Every judged pair, split by whether its score cleared the line the day was built with and by what the judge said about it."
>
	<div data-verdict-split data-verdict-line={reads(applied)} data-verdict-days={record?.daysFolded ?? 0}>
		<div class="grid">
			{#each cells as cell (cell.key)}
				<div class="cell" data-verdict-cell={cell.key}>
					<span class="count">{grouped(cell.count)}</span>
					<span class="words">{cell.words}</span>
				</div>
			{/each}
		</div>

		<!-- The one sentence on this route that is not derived from a number. -->
		<p class="cost" data-verdict-cost>
			The line would let a pair in the second cell through, and where the group forms it
			is a story the reader never sees. A pair in the cell below it is one the reader
			sees twice.
		</p>

		<p class="reading" data-verdict-precision={miss === null ? '' : miss.toFixed(4)}>
			{#if miss === null}
				<span data-verdict-state="empty"
					>No pair has been judged above the line yet, so there is nothing to report
					about it.</span
				>
			{:else}
				<span data-verdict-state="reading"
					>{percent(miss)} of the pairs above the line were called two stories. The fit
					aims for {percent(discardShare)}.</span
				>
			{/if}
		</p>

		<div use:observeWidth={(next) => (measured = next)}>
			<svg
				class="block max-w-full overflow-visible"
				width={box.width}
				height={box.height}
				viewBox={`0 0 ${box.width} ${box.height}`}
				role="img"
				aria-label="Where each verdict's pairs sit on the score, and where the line is"
			>
				{#each [{ at: agreed, y: box.top + 18, name: 'same', words: 'called one story' }, { at: disagreed, y: box.top + 52, name: 'different', words: 'called two stories' }] as strip (strip.name)}
					<text
						x={box.left}
						y={strip.y - 10}
						fill="var(--color-text-tertiary)"
						font-size="10"
						data-verdict-strip-label={strip.name}
					>
						{strip.at === null
							? `Nothing was ${strip.words} yet`
							: `${strip.words}: ${reads(strip.at.min)} to ${reads(strip.at.max)}`}
					</text>
					{#if strip.at !== null}
						<line
							x1={xAxis.scale(strip.at.min)}
							x2={xAxis.scale(strip.at.max)}
							y1={strip.y}
							y2={strip.y}
							stroke={strip.name === 'same' ? 'var(--chart-1)' : 'var(--chart-3)'}
							stroke-width="6"
							stroke-linecap="round"
							data-verdict-strip={strip.name}
						/>
						<circle
							cx={xAxis.scale(strip.at.median)}
							cy={strip.y}
							r="3"
							fill="var(--color-surface)"
							data-verdict-median={strip.name}
						/>
					{/if}
				{/each}

				<!-- The line across both strips. Overlap either side of it is where the
				     line is being asked to do something the evidence cannot support. -->
				<line
					x1={xAxis.scale(applied)}
					x2={xAxis.scale(applied)}
					y1={box.top}
					y2={box.bottom}
					stroke="var(--color-text-tertiary)"
					stroke-dasharray="3 3"
					data-verdict-rule={reads(applied)}
				/>

				{#each xAxis.ticks as tick (tick)}
					<text
						x={xAxis.scale(tick)}
						y={box.bottom + 12}
						text-anchor="middle"
						fill="var(--color-text-tertiary)"
						font-size="10"
						data-tick="x"
					>
						{reads(tick)}
					</text>
				{/each}
			</svg>
		</div>

		<dl class="figures" data-verdict-figures>
			<div>
				<dt>In the band</dt>
				<dd data-verdict-figure="in-band">{figure(figures.inBand)}</dd>
				<p>How many pairs were close enough to be worth judging.</p>
			</div>
			<div>
				<dt>Judged</dt>
				<dd data-verdict-figure="judged">{figure(figures.judged)}</dd>
				<p>How many the day's budget actually read. A smaller number means the cap cut the draw.</p>
			</div>
			<div>
				<dt>Usable</dt>
				<dd data-verdict-figure="usable">{figure(figures.usable)}</dd>
				<p>How many got two readings that agreed. Only these went into the record.</p>
			</div>
		</dl>

		<details class="detail" data-verdict-table>
			<summary>The record, slice by slice</summary>
			{#if rows.length === 0}
				<p class="reading">The record holds nothing yet.</p>
			{:else}
				<table>
					<thead>
						<tr>
							<th scope="col">Score</th>
							<th scope="col">One story</th>
							<th scope="col">Two stories</th>
							<th scope="col">Could not tell</th>
						</tr>
					</thead>
					<tbody>
						{#each rows as row (row.from)}
							<tr data-verdict-row={reads(row.from)}>
								<th scope="row">{reads(row.from)} to {reads(row.to)}</th>
								<td>{grouped(row.same)}</td>
								<td>{grouped(row.different)}</td>
								<td>{grouped(row.unclear)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		</details>
	</div>
</Panel>

<style>
	.grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--space-2);
	}

	.cell {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		padding: var(--space-3);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-sm);
		background: var(--color-surface-sunken);
	}

	.count {
		font-size: var(--text-lg);
		font-variant-numeric: tabular-nums;
		color: var(--color-text);
	}

	.words {
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.cost,
	.reading {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.figures {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
		gap: var(--space-3);
		margin: var(--space-4) 0 0;
	}

	.figures dt {
		font-size: var(--text-sm);
		color: var(--color-text-secondary);
	}

	.figures dd {
		margin: 0;
		font-size: var(--text-lg);
		font-variant-numeric: tabular-nums;
		color: var(--color-text);
	}

	.figures p {
		margin: var(--space-1) 0 0;
		font-size: var(--text-xs);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}

	/* Shut it drops its border and background, the way the Summaries route's
	   day-by-day disclosure does, so the attention cost of a closed detail is
	   zero. */
	.detail {
		margin: var(--space-4) 0 0;
		font-size: var(--text-sm);
	}

	.detail[open] {
		padding: var(--space-3);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-sm);
	}

	.detail summary {
		cursor: pointer;
		color: var(--color-text-secondary);
	}

	.detail table {
		width: 100%;
		margin-top: var(--space-3);
		border-collapse: collapse;
		font-variant-numeric: tabular-nums;
	}

	.detail th,
	.detail td {
		padding: var(--space-1) var(--space-2);
		text-align: right;
		border-bottom: 1px solid var(--color-rule);
	}

	.detail th[scope='row'],
	.detail thead th:first-child {
		text-align: left;
		font-weight: 400;
		color: var(--color-text-secondary);
	}
</style>
