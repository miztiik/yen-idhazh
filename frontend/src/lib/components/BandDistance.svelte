<script lang="ts">
	/** How far each day's summaries landed from the length we asked for.
	 *
	 * This was a scatter of article length against summary length: 2,740 marks in
	 * one colour on a 1026px plot, measured 2026-08-30. The dense middle rendered
	 * as a solid block, which hid the outliers - the only marks on it anybody can
	 * act on. It also asked the operator to read two axes per mark to answer one
	 * question, and that question is "how far from the target band".
	 *
	 * So the distance is what it draws. A column is a day, split three ways, and
	 * the worst misses are listed underneath by name. Hand-written SVG at one CSS
	 * pixel per unit, like every other chart on this page: 90 columns replace
	 * 2,740 marks, and the page is complete before any script runs.
	 */
	import {
		chartWidth,
		dayColumnX,
		dayColumns,
		dayTicks,
		frame,
		linearAxis,
		MARGIN,
		observeWidth,
		pointerReadout,
		readoutMarks,
		type DayReadout
	} from '$lib/charts/frame';
	import ChartReadout from './ChartReadout.svelte';
	import { rank, tailSentence, type Rankable, type RankedDisplay } from '$lib/charts/rank';
	import {
		bandOutliers,
		bandPlacements,
		bandSpan,
		bandSplit,
		grouped,
		rowsInWindow,
		type BandDay,
		type BandPlace,
		type CompressionPoint,
		type SummaryBand,
		type UnplottedDay
	} from '$lib/charts/series';
	import { daysBetween, type TimeWindow } from '$lib/charts/viewport';
	import { dayMonth } from '$lib/format';
	import RankedList from './RankedList.svelte';

	let {
		points,
		viewport,
		bands,
		unplotted,
		height,
		width,
		tickDensity,
		outlierRows,
		readoutMaxShare = 0.33
	}: {
		points: CompressionPoint[];
		viewport: TimeWindow;
		bands: SummaryBand[];
		unplotted: UnplottedDay[];
		height: number;
		width: number;
		/** The most date labels the day axis may carry - `chart.tick_density`. */
		tickDensity: number;
		/** How many outliers the list prints before the tail sentence takes over. */
		outlierRows: number;
		/** `chart.readout_max_share`. */
		readoutMaxShare?: number;
	} = $props();

	/** One row of dates under the plot, and room for a descender. */
	const AXIS_ROOM = 30;
	/** The rotated axis title gets a column of its own. `MARGIN.left` is the tick
	 * numbers' room, and two labels sharing one margin overlap. */
	const Y_TITLE_ROOM = 14;
	const PLOT_MARGIN = {
		...MARGIN,
		top: 8,
		bottom: AXIS_ROOM,
		left: MARGIN.left + Y_TITLE_ROOM
	};
	const Y_TITLE_X = 8;
	/** Wide enough to read a colour off, narrow enough that 90 columns fit. */
	const MAX_BAR = 18;
	const MIN_BAR = 2;

	/** The three parts of a column, bottom first, each with the word it carries.
	 *
	 * Inside is the mass, so it sits on the axis and the two misses ride on top
	 * where they can be compared across days. Colour comes from the categorical
	 * chart ramp and never the confidence ramp: a summary outside its band missed
	 * a length somebody chose in `config/`, and a policy limit is not a verdict.
	 */
	const PARTS: { place: BandPlace; text: string; colour: string }[] = [
		{ place: 'inside', text: 'Inside the band', colour: 'var(--chart-1)' },
		{ place: 'short', text: 'Shorter than the band', colour: 'var(--chart-2)' },
		{ place: 'long', text: 'Longer than the band', colour: 'var(--chart-3)' }
	];

	let measured = $state<number | null>(null);

	const windowDays = $derived(daysBetween(viewport.start, viewport.end));
	const box = $derived(frame(chartWidth(measured, width), height + AXIS_ROOM, PLOT_MARGIN));

	const placed = $derived(bandPlacements(points, bands, viewport));
	const split = $derived(bandSplit(placed, viewport));
	const outliers = $derived(bandOutliers(placed));

	/** How many rows in this window carry no article length, so no band can be
	 * read for them. Counted from the rows the server dropped, so the sentence
	 * and the columns answer out of one decision. */
	const notPlaced = $derived(
		rowsInWindow(unplotted, viewport).reduce((total, day) => total + day.n, 0)
	);

	const tallest = $derived(split.reduce((high, day) => Math.max(high, day.items), 0));
	const yAxis = $derived(linearAxis([0, tallest], [box.bottom, box.top], { tickCount: 4 }));
	/** A count has no halves. d3 offers them on a short domain, so they are
	 * dropped rather than rounded - a repeated `1` reads as a broken axis. */
	const yTicks = $derived(yAxis.ticks.filter((tick) => Number.isInteger(tick)));
	const bar = $derived(
		Math.max(MIN_BAR, Math.min(MAX_BAR, (box.innerWidth / Math.max(1, split.length)) * 0.7))
	);
	const ticks = $derived(
		dayTicks(
			split.map((day) => day.date),
			{ density: tickDensity, columns: dayColumns(split.length, box, bar / 2) }
		)
	);

	const ranked = $derived(
		rank<RankedDisplay>(
			outliers.map(
				(one): Rankable<RankedDisplay> => ({
					key: `${one.date}-${one.item_id}`,
					value: one.distance,
					tiebreak: one.source_words,
					row: {
						label: one.item_id,
						value: `${grouped(one.distance)} words`,
						status: one.place === 'long' ? 'too long' : 'too short',
						context: `${dayMonth(one.date)} - article ${grouped(
							one.source_words
						)} words, summary ${grouped(one.summary_words)} words, asked for ${
							one.band.target_words_min
						} to ${one.band.target_words_max}`
					}
				})
			),
			outlierRows
		)
	);

	/** Rows, and no sum. Counts add and distances do not: two summaries 40 words
	 * out are not one summary 80 words out. */
	const tail = $derived(tailSentence(ranked, { one: 'article', many: 'articles' }));

	function px(value: number): number {
		return Math.round(value * 10) / 10;
	}

	function centre(index: number): number {
		return px(dayColumnX(index, split.length, box, bar / 2));
	}

	/** Where one part of a column starts and how tall it is, in plot pixels. */
	function segment(day: BandDay, index: number): { y: number; height: number } {
		let below = 0;
		for (let n = 0; n < index; n += 1) below += day[PARTS[n].place];
		const value = day[PARTS[index].place];
		return {
			y: px(yAxis.scale(below + value)),
			height: px(yAxis.scale(below) - yAxis.scale(below + value))
		};
	}

	function columnTitle(day: BandDay): string {
		const noun = day.items === 1 ? 'summary' : 'summaries';
		return `${dayMonth(day.date)} - ${day.items} ${noun}: ${day.inside} inside the band, ${day.short} shorter, ${day.long} longer.`;
	}

	/** The column a pointer or an arrow key has picked. */
	let selected = $state<number | null>(null);

	/** All three parts of a day, printed together. A stack is the shape where
	 * reading one band off the middle is hardest, and the two bands that ride on
	 * top are the ones anybody acts on. */
	const columns = $derived<DayReadout[]>(
		split.map((day, index) => ({
			x: centre(index),
			date: dayMonth(day.date),
			rows: [
				...PARTS.map((part) => ({
					label: part.text,
					value: String(day[part.place]),
					colour: part.colour
				})),
				{ label: 'Summaries that day', value: String(day.items), colour: '' }
			]
		}))
	);
	const marks = $derived(readoutMarks(columns));
	const at = $derived(selected ?? (columns.length === 0 ? null : columns.length - 1));
	const readout = $derived(at === null ? null : (columns[at] ?? null));
	const guide = $derived(selected === null ? null : (columns[selected]?.x ?? null));
</script>

<section
	class="mt-8"
	data-windowed="band-distance"
	data-window-days={windowDays}
	aria-label="Summary length against the length asked for, {windowDays} days"
>
	<h2 class="text-[1.0625rem] font-semibold text-text">
		Summary length against the length asked for
	</h2>
	<p class="mt-1 text-[0.8125rem] text-text-tertiary">
		One column is one day. An article's own length decides the band we ask the machine to write to,
		so every summary is inside that band, short of it, or past it.
		{#if notPlaced > 0}
			<span data-band-note="not-plotted"
				>{notPlaced} articles in this window recorded no length, so no band can be read for them and
				they are not counted here.</span
			>
		{/if}
	</p>

	<div
		class="mt-4 rounded-md border border-rule bg-surface p-3"
		data-band-distance
		data-readout-columns={columns.length}
	>
		<div use:observeWidth={(next) => (measured = next)}>
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<svg
				class="block max-w-full overflow-visible focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
				width={box.width}
				height={box.height}
				viewBox={`0 0 ${box.width} ${box.height}`}
				role="img"
				tabindex="0"
				aria-label="Summaries a day, split by whether each landed inside its target band"
				use:pointerReadout={{
					marks,
					width: box.width,
					onSelect: (index) => (selected = index)
				}}
			>
				{#if guide !== null}
					<line
						x1={guide}
						x2={guide}
						y1={box.top}
						y2={box.bottom}
						stroke="var(--color-text-tertiary)"
						stroke-opacity="0.5"
						data-band-distance="guide"
					/>
				{/if}
				<line
					x1={box.left}
					x2={box.right}
					y1={box.bottom}
					y2={box.bottom}
					stroke="var(--color-rule)"
				/>
				<line x1={box.left} x2={box.left} y1={box.top} y2={box.bottom} stroke="var(--color-rule)" />

				{#each yTicks as tick (tick)}
					<line
						x1={box.left - 4}
						x2={box.left}
						y1={yAxis.scale(tick)}
						y2={yAxis.scale(tick)}
						stroke="var(--color-text-tertiary)"
					/>
					<text
						x={box.left - 6}
						y={yAxis.scale(tick)}
						dy="0.32em"
						text-anchor="end"
						fill="var(--color-text-tertiary)"
						font-size="10"
						data-tick="y"
					>
						{tick}
					</text>
				{/each}

				{#if placed.length === 0}
					<line
						x1={box.left}
						x2={box.right}
						y1={(box.top + box.bottom) / 2}
						y2={(box.top + box.bottom) / 2}
						stroke="var(--color-text-tertiary)"
						stroke-dasharray="4 4"
					/>
					<text
						x={box.left + 8}
						y={(box.top + box.bottom) / 2 - 8}
						fill="var(--color-text-tertiary)"
						font-size="12"
					>
						No summaries in this window
					</text>
				{:else}
					{#each split as day, index (day.date)}
						{#if day.items > 0}
							<g
								data-band-day={day.date}
								data-band-inside={day.inside}
								data-band-short={day.short}
								data-band-long={day.long}
								data-band-items={day.items}
							>
								<title>{columnTitle(day)}</title>
								{#each PARTS as part, position (part.place)}
									{#if day[part.place] > 0}
										<rect
											x={px(centre(index) - bar / 2)}
											y={segment(day, position).y}
											width={px(bar)}
											height={segment(day, position).height}
											fill={part.colour}
											data-band-part={part.place}
										/>
									{/if}
								{/each}
							</g>
						{/if}
					{/each}
				{/if}

				<!-- The mark stays where the date was dropped, so a reader counting
				     columns keeps the grid. -->
				{#each ticks as tick (tick.index)}
					<line
						x1={centre(tick.index)}
						x2={centre(tick.index)}
						y1={box.bottom}
						y2={box.bottom + 4}
						stroke="var(--color-text-tertiary)"
						data-day-tick={tick.date}
					/>
					{#if tick.text}
						<text
							x={centre(tick.index)}
							y={box.bottom + 16}
							text-anchor={tick.anchor}
							fill="var(--color-text-tertiary)"
							font-size="10"
							data-day-axis
							data-day-label={tick.date}
						>
							{tick.text}
						</text>
					{/if}
				{/each}

				<text
					x={Y_TITLE_X}
					y={(box.top + box.bottom) / 2}
					transform={`rotate(-90 ${Y_TITLE_X} ${(box.top + box.bottom) / 2})`}
					text-anchor="middle"
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-axis="y"
				>
					Summaries
				</text>
			</svg>
		</div>

		<!-- Below the plot, never over it, and the same strip every chart on this
		     console prints - see `ChartReadout.svelte` for the rules it holds. -->
		<ChartReadout
			{readout}
			name="band-distance"
			maxShare={readoutMaxShare}
			resting={selected === null}
			restingNote=", the newest day"
			hint="Point at a day to read all three parts. Left and Right step through the days, Escape returns to the newest."
		/>

		<!-- The bounds as numbers, beside the chart drawn from them. A band
		     nobody can read is a band nobody can check a column against. No key
		     beside it any more: the strip above names all three parts in their own
		     colours at the day the reader is on, and one fact drawn twice is how
		     two of them drift. -->
		<table class="mt-4 text-[0.75rem] tabular-nums text-text-tertiary" data-band-bounds>
			<caption class="text-left text-[0.75rem] text-text-secondary">What we ask for</caption>
			<thead>
				<tr>
					<th scope="col" class="pe-4 text-left font-normal">Article length, words</th>
					<th scope="col" class="text-left font-normal">Target summary length, words</th>
				</tr>
			</thead>
			<tbody>
				{#each bands as band, index (band.min_source_words)}
					<tr data-band-row={band.min_source_words}>
						<td class="pe-4">{bandSpan(bands, index)}</td>
						<td data-band-target={band.min_source_words}>
							{band.target_words_min} to {band.target_words_max}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	<div class="mt-6" data-band-outliers>
		<h3 class="text-[0.9375rem] font-semibold text-text">Furthest from the band</h3>
		<p class="mt-1 text-[0.8125rem] text-text-tertiary">
			The summaries that missed by the most words, worst first. Nothing here failed - the band is
			the length we ask for, not the length we accept.
		</p>
		<div class="mt-3">
			<RankedList
				caption="Summaries furthest from their target band"
				{ranked}
				maxText="{grouped(ranked.max)} words outside the band"
				measured={placed.length > 0}
				unmeasuredNote="Nothing in this window recorded both an article length and a summary length."
				emptyNote="Every summary in these {windowDays} days landed inside its band."
				{tail}
			/>
		</div>
	</div>
</section>
