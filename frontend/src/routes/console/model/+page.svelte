<script lang="ts">
	/** What the model did, and nothing else.
	 *
	 * It is one of the console's three routes. The band and the strip above are
	 * identical to the other two; below them this page answers one question and
	 * refuses the rest: what the model wrote for the day's own articles, how
	 * long it took, and what it got wrong.
	 *
	 * Everything here reads the committed ledger. The only arithmetic is one
	 * committed count divided by another, which is deliberate: a stored rate can
	 * disagree with the counts printed beside it.
	 */
	import { onMount } from 'svelte';
	import { windowOfDays } from '$lib/charts/viewport';
	import { grouped } from '$lib/charts/series';
	import { sparklineMarks, type SparklineMarks } from '$lib/charts/sparkline';
	import type { MovementPolarity } from '$lib/charts/theme';
	import ConsoleBand from '$lib/components/ConsoleBand.svelte';
	import ConsoleNav from '$lib/components/ConsoleNav.svelte';
	import KpiCard from '$lib/components/KpiCard.svelte';
	import RunLengths from '$lib/components/RunLengths.svelte';
	import Sparkline from '$lib/components/Sparkline.svelte';
	import SwapDots from '$lib/components/SwapDots.svelte';
	import ThroughputTrend from '$lib/components/ThroughputTrend.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import WriteTimeHistogram from '$lib/components/WriteTimeHistogram.svelte';
	import { base } from '$app/paths';
	import type { ModelDay } from './+page.server';

	let { data } = $props();

	/** The same key the other two routes read, so the operator's choice of span
	 * follows him between them rather than resetting on every click. */
	const WINDOW_KEY = 'idhazh:console-window';

	const presets = $derived(data.console.window_presets);

	// svelte-ignore state_referenced_locally
	let windowDays = $state(data.console.default_window_days);
	/** False until a browser has run this page. */
	let ready = $state(false);

	onMount(() => {
		ready = true;
		if (typeof localStorage === 'undefined') return;
		const stored = Number(localStorage.getItem(WINDOW_KEY));
		if (presets.includes(stored) && stored !== windowDays) show(stored);
	});

	function show(days: number, remember = true) {
		windowDays = days;
		if (remember && typeof localStorage !== 'undefined') {
			localStorage.setItem(WINDOW_KEY, String(days));
		}
	}

	/** Nothing on this route is fetched. Every day it draws is already inlined,
	 * so no preset costs a month file and none of them is priced. */
	function monthsFor(): number {
		return 0;
	}

	/** Whole units, never a decimal, and never a zero that was really work. */
	function whole(ms: number | null, per: number): string {
		if (ms === null) return '-';
		const value = Math.round(ms / per);
		return value === 0 && ms > 0 ? '<1' : String(value);
	}

	/** A count of today's items, or a dash where the ledger holds no answer.
	 *
	 * Null is not zero. A day the scorer never ran on has summaries nobody
	 * counted, and a zero there would say the model wrote nothing.
	 */
	function count(value: number | null): string {
		return value === null ? '-' : String(value);
	}

	function percent(value: number | null): string {
		return value === null ? '-' : `${value}%`;
	}

	/** Every column of the model table, in the order it is printed.
	 *
	 * The label and the sentence under it live together, so a column cannot be
	 * added without saying in plain words what it counts - and now without
	 * saying which way is the good way. `polarity` is declared here because
	 * this is where the measure is defined; a card that decided its own is how
	 * two cards come to disagree about whether down is good.
	 *
	 * Three of the eleven have no agreed direction and say so on the card.
	 * `Summaries today` and `Model minutes` both rise on a busy news day, so a
	 * rule that called one good would have to call the other bad for the same
	 * cause. `Copied, not rewritten` has no agreed threshold - this page already
	 * refused to tint it for that reason - and more copying is not obviously
	 * worse than more invention.
	 */
	const COLUMNS: { key: string; label: string; line: string; polarity: MovementPolarity }[] = [
		{ key: 'summaries', label: 'Summaries today', line: '', polarity: 'no-agreed-direction' },
		{
			key: 'not-sure',
			label: 'Marked "not sure"',
			line: "How many of today's summaries we told you not to trust.",
			polarity: 'lower-is-better'
		},
		{
			key: 'unsupported',
			label: 'Numbers not in the article',
			line: 'The summary had a figure. The article did not.',
			polarity: 'lower-is-better'
		},
		{
			key: 'hedge',
			label: '"Maybe" told as fact',
			line: 'The article said it might have happened. The summary said it did.',
			polarity: 'lower-is-better'
		},
		{
			key: 'part',
			label: 'Article read only in part',
			line: 'The article was too long, so the machine read the start and stopped.',
			polarity: 'lower-is-better'
		},
		{
			key: 'part-pct',
			label: 'Read only in part, as a percent',
			line: "The same articles, against the day's own count, so a busy day and a quiet one compare.",
			polarity: 'lower-is-better'
		},
		{
			key: 'copied',
			label: 'Copied, not rewritten',
			line: 'How much of a normal summary is lifted word for word.',
			polarity: 'no-agreed-direction'
		},
		{
			key: 'per-item',
			label: 'Time to write one',
			line: 'How long the machine takes on one article. The second figure is the articles it read only the start of.',
			polarity: 'lower-is-better'
		},
		{ key: 'minutes', label: 'Model minutes', line: '', polarity: 'no-agreed-direction' },
		{
			key: 'too-long',
			label: 'Too long to send',
			line: 'The article and the instructions together did not fit, so the machine was never asked.',
			polarity: 'lower-is-better'
		},
		{ key: 'failed', label: 'Failed', line: '', polarity: 'lower-is-better' }
	];

	/** One day's printed cells, in the order `COLUMNS` names them.
	 *
	 * Built here rather than spelled out in the markup so a header and its column
	 * cannot drift apart, which is the way a table starts lying.
	 */
	function cells(day: ModelDay): { key: string; text: string; aside?: string }[] {
		return [
			{ key: 'summaries', text: count(day.summaries) },
			{ key: 'not-sure', text: count(day.notSure) },
			{ key: 'unsupported', text: count(day.unsupportedNumbers) },
			{ key: 'hedge', text: count(day.hedgeDropped) },
			{ key: 'part', text: count(day.readInPart) },
			{ key: 'part-pct', text: percent(day.readInPartPct) },
			{ key: 'copied', text: percent(day.copiedPct) },
			// The second figure is only carried where the day cut something, because
			// a dash under every other day would be a column of absences pretending
			// to be a split.
			{
				key: 'per-item',
				text: whole(day.perItemMs, 1000),
				...(day.perItemCutMs === null
					? {}
					: { aside: `${whole(day.perItemCutMs, 1000)} when cut short` })
			},
			{ key: 'minutes', text: whole(day.totalMs, 60_000) },
			{ key: 'too-long', text: count(day.refusedForLength) },
			{ key: 'failed', text: count(day.failed) }
		];
	}

	/** What each column counts, day by day.
	 *
	 * Keyed the same way `cells` is, so a card's line and the figure above it
	 * cannot come from two different columns. A day the ledger has no answer for
	 * arrives as null and is left out of the line rather than drawn as a zero,
	 * which is the same rule the cells follow.
	 */
	const SERIES: Record<string, (day: ModelDay) => number | null> = {
		summaries: (day) => day.summaries,
		'not-sure': (day) => day.notSure,
		unsupported: (day) => day.unsupportedNumbers,
		hedge: (day) => day.hedgeDropped,
		part: (day) => day.readInPart,
		'part-pct': (day) => day.readInPartPct,
		copied: (day) => day.copiedPct,
		'per-item': (day) => day.perItemMs,
		minutes: (day) => day.totalMs,
		'too-long': (day) => day.refusedForLength,
		failed: (day) => day.failed
	};

	/** The card grid's minimum column, and the room a card leaves inside it. */
	const CARD_MIN_PX = 220;
	const CARD_PAD_PX = 16;
	const SPARK_WIDTH_PX = CARD_MIN_PX - CARD_PAD_PX * 2;

	/** Every day the model worked, newest first, with the dividers taken out. */
	const modelDays = $derived(data.modelWork.flatMap((row) => (row.kind === 'day' ? [row.day] : [])));
	/** The newest day either ledger holds. Every card's figure is this day. */
	const newestModelDay = $derived(modelDays[0] ?? null);
	/** Every day the model changed, read from the rows the table draws its
	 * dividers from. One source, so a rule on a card and a divider in the table
	 * cannot disagree about when the ground moved. */
	const modelSwaps = $derived(data.modelWork.flatMap((row) => (row.kind === 'swap' ? [row] : [])));

	/** The days the cards' lines cover, oldest first. */
	const modelSpan = $derived(
		windowOfDays(
			modelDays.map((day) => day.date),
			data.today,
			windowDays,
			data.console.today_anchor
		)
	);
	const modelWindow = $derived(
		[...modelDays.filter((day) => day.date >= modelSpan.start && day.date <= modelSpan.end)].reverse()
	);

	/** One card's drawn points, and the swap rules that land on them. */
	function trendFor(key: string): {
		marks: SparklineMarks;
		rules: { at: number; label: string }[];
	} {
		const read = SERIES[key];
		const values: number[] = [];
		const dates: string[] = [];
		for (const day of modelWindow) {
			const value = read(day);
			if (value === null) continue;
			values.push(value);
			dates.push(day.date);
		}
		const marks = sparklineMarks(values);
		if (marks.empty) return { marks, rules: [] };
		const rules = modelSwaps.flatMap((swap) => {
			const at = dates.findIndex((date) => date >= swap.date);
			if (at < 1) return [];
			return [
				{
					at: at / (dates.length - 1),
					label: `The model changed to ${swap.model} on ${swap.date}.`
				}
			];
		});
		return { marks, rules };
	}

	/** What a quality figure is out of, printed beside it. */
	function outOf(key: string, day: ModelDay): string | null {
		const summaries = (of: number) => `of ${of} ${of === 1 ? 'summary' : 'summaries'}`;
		if (['not-sure', 'unsupported', 'hedge', 'copied'].includes(key)) {
			return day.summaries === null ? null : summaries(day.summaries);
		}
		if (['part', 'part-pct'].includes(key)) {
			return day.readInPartOf === null ? null : summaries(day.readInPartOf);
		}
		return null;
	}

	/** The eleven cards, in the order `COLUMNS` names them. */
	const cards = $derived.by(() => {
		const day = newestModelDay;
		if (day === null) return [];
		return cells(day).map((cell, index) => ({
			key: cell.key,
			label: COLUMNS[index].label,
			line: COLUMNS[index].line,
			polarity: COLUMNS[index].polarity,
			value: cell.text,
			note: cell.aside ?? outOf(cell.key, day),
			trend: trendFor(cell.key)
		}));
	});

	/** The span every panel below the cards draws, decided once on the server for
	 * each span the control offers. A percentile has to be taken over the values
	 * themselves, so the browser picks the answer for the open window rather than
	 * recomputing one off the bars. */
	const span = $derived(data.windows[String(windowDays)] ?? null);
	const writeTimes = $derived(data.writeTimes[String(windowDays)] ?? null);
	const scoreCost = $derived(data.scoreCost[String(windowDays)] ?? null);

	/** The runs inside the open window, oldest first. Each is already three
	 * numbers, so the window is a filter and never a re-aggregation. */
	const runsInWindow = $derived(
		span === null
			? []
			: data.runLengths.filter((run) => run.date >= span.start && run.date <= span.end)
	);

	/** Whole seconds off a millisecond clock, and `<1 s` where a real
	 * measurement rounds away. */
	function asSeconds(ms: number): string {
		const value = Math.round(ms / 1000);
		return value === 0 && ms > 0 ? '<1 s' : `${value} s`;
	}
</script>

<svelte:head>
	<title>Console: Model &mdash; {data.ui.site_title}</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<section class="py-6" data-surface="operator" data-console-route="model">
	<h1 class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text">Console</h1>
	<p class="mt-1 text-[0.9375rem] text-text-secondary">
		What the model wrote, how long it took, and what it got wrong, per day, from the committed
		ledger.
	</p>

	<ConsoleBand band={data.band}>
		{#snippet window()}
			<WindowControl days={windowDays} {presets} {monthsFor} {ready} onChange={show} />
		{/snippet}
	</ConsoleBand>
	<ConsoleNav routes={data.routes} active="model" />

	<!-- One sentence, no chart. A route that never points at another is a route
	     that hides the panel explaining its own numbers. -->
	<p class="console-carry" data-console-carry="machine">
		{data.carries.model}
		<a class="carry-link" href="{base}/console/machine/">Machine &rarr;</a>
	</p>

	{#if data.modelWork.length === 0 && data.throughputDays.length === 0}
		<h2 class="console-h2">What the model did</h2>
		<p class="mt-2 text-[0.9375rem] text-text-secondary" data-model="empty">
			The model has not summarised anything yet. This fills as days publish.
		</p>
	{:else}
		<div data-model-section>
			<h2 class="console-h2">What the model did</h2>
			<p class="mt-1 text-[0.8125rem] text-text-tertiary">
				Every figure is that day's own articles, measured the day it ran. The articles change
				every day, so a dip can be the news rather than the model. Fixed benchmark figures are
				not here - they are in the
				<a href={data.measurementsReference} class="text-accent hover:underline" rel="noreferrer"
					>measurements write-up</a
				>.
			</p>

			<!-- What the recording was doing, in the panel it governs rather than as
			     a banner: three panels can be in three different states on one day.
			     None of these is an error and none is styled as one. -->
			{#if data.recording.off}
				<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="off">
					{data.recording.off}
				</p>
			{/if}
			{#if data.recording.sampled}
				<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="sampled">
					{data.recording.sampled}
				</p>
			{/if}
			{#if data.recording.countersOnly}
				<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="counters-only">
					{data.recording.countersOnly}
				</p>
			{/if}
			{#if data.recording.startedMidWindow}
				<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="started">
					{data.recording.startedMidWindow}
				</p>
			{/if}

			<!-- Always rendered, empty window included. The chart owns its own empty
			     state, so a window with nothing in it says so instead of taking the
			     heading away with it. -->
			<ThroughputTrend
				days={data.throughputDays}
				height={data.console.chart_height}
				width={data.console.chart_width}
				reference={data.throughputReference}
				tickDensity={data.chart.tick_density}
				readoutMaxShare={data.chart.readout_max_share}
			/>

			{#if newestModelDay !== null}
				<!-- Eleven measures, eleven cards. A wide table is the one shape that
				     cannot answer "did it get worse": a trend is a vertical scan, and
				     every column beside the one being scanned is a different quantity.
				     No card is tinted - `Copied, not rewritten` at 12 percent has no
				     agreed threshold, and a tint would invent one and publish it. -->
				<p
					class="mt-4 text-[0.8125rem] text-text-tertiary"
					data-model-cards-note
					data-model-newest={newestModelDay.date}
					data-windowed="model-cards"
					data-window-days={windowDays}
				>
					Every figure is {newestModelDay.date}, the newest day either ledger holds. Each line is
					the {windowDays} days ending there, and a dashed rule across one is a day the model
					changed. The percentage beside it is the change from the start of that line to its
					end, coloured green where the measure went the way we want and red where it did not;
					a measure nobody has agreed a direction for says "no target" instead.
				</p>

				<div class="auto-grid mt-4" style="--auto-grid-min: {CARD_MIN_PX}px" data-model-cards>
					{#each cards as card (card.key)}
						<KpiCard
							label={card.label}
							value={card.value}
							note={card.note}
							line={card.line}
							movement={card.trend.marks.movement}
							polarity={card.polarity}
						>
							{#snippet trend()}
								<Sparkline
									marks={card.trend.marks}
									rules={card.trend.rules}
									width={SPARK_WIDTH_PX}
									height={data.chart.sparkline_height_px}
									label="{card.label}, over the {windowDays} days ending {newestModelDay?.date}"
								/>
							{/snippet}
						</KpiCard>
					{/each}
				</div>
			{/if}

			{#if data.modelWork.length > 0}
				<!-- The rows behind the shape, on demand. Nothing is deleted and nothing
				     needs a script: a closed disclosure is complete in the prerendered
				     document, and opening it costs no fetch. -->
				<details class="console-disclosure mt-4" data-model-table-control>
					<summary class="console-summary">Show the daily figures</summary>
					<div class="console-table mt-3" data-model="table">
						<table class="w-full text-[0.8125rem]">
							<thead class="text-text-tertiary">
								<tr class="border-b border-rule">
									<th class="py-2 pe-4 text-start align-bottom font-normal">Day</th>
									{#each COLUMNS as column (column.key)}
										<th class="py-2 ps-4 text-end align-bottom font-normal">
											<!-- The label alone. The sentence that used to hang under it is on
											     the card now, where there is room for it. -->
											<span class="ms-auto block max-w-[10rem]">{column.label}</span>
										</th>
									{/each}
								</tr>
							</thead>
							<tbody>
								{#each data.modelWork as row (row.kind === 'swap' ? `swap ${row.date}` : row.day.date)}
									{#if row.kind === 'swap'}
										<!-- A date and an id. An arrow or a delta here would claim the swap
										     caused whatever moved, and no committed figure says that. -->
										<tr class="border-b border-rule" data-model-swap={row.date}>
											<td colspan={COLUMNS.length + 1} class="py-2 text-[0.75rem] text-text-tertiary">
												{row.date} - {row.model}
											</td>
										</tr>
									{:else}
										<tr class="border-b border-rule" data-model-day={row.day.date}>
											<td class="py-2 pe-4">{row.day.date}</td>
											{#each cells(row.day) as cell (cell.key)}
												<td class="py-2 ps-4 text-end tabular-nums" data-model-cell={cell.key}>
													{cell.text}
													{#if cell.aside}
														<span
															class="mt-0.5 block text-[0.6875rem] text-text-tertiary"
															data-model-aside={cell.key}>{cell.aside}</span
														>
													{/if}
												</td>
											{/each}
										</tr>
									{/if}
								{/each}
							</tbody>
						</table>
					</div>
				</details>
			{/if}
		</div>

		<!-- What one item cost, as a distribution. A median answers "how long does
		     one take" and refuses "how bad does it get", and the second decides
		     whether a shard fits its timeout. -->
		<div data-model-cost>
			<h2 class="console-h2">What one summary cost</h2>
			<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-model-cost-intro>
				Each bar is a doubling of the clock. Read the tall bars for where the work sits, and the
				curve for how much of the day is finished by a given time.
			</p>

			{#if writeTimes === null}
				<p class="mt-2 text-[0.9375rem] text-text-secondary" data-write-times="empty">
					Nothing was timed in these {windowDays} days.
				</p>
			{:else if writeTimes.n < data.console.min_attempts_for_rate}
				<!-- A median over three summaries is the second summary, and a one in
				     twenty over three is the slowest of them. The counts are the whole
				     answer until there are enough of them to divide. -->
				<p class="mt-2 text-[0.9375rem] text-text-secondary" data-write-times="thin">
					{grouped(writeTimes.n)}
					{writeTimes.n === 1 ? 'summary was' : 'summaries were'} timed in these {windowDays} days.
					Too few to give a middle or a slowest one in twenty - {data.console
						.min_attempts_for_rate} needed. The fastest took {asSeconds(writeTimes.fastest)} and the
					slowest {asSeconds(writeTimes.slowest)}.
				</p>
			{:else}
				<WriteTimeHistogram
					times={writeTimes}
					width={data.console.chart_width}
					height={data.console.chart_height}
					readoutMaxShare={data.chart.readout_max_share}
				/>
				<p class="mt-2 text-[0.8125rem] text-text-tertiary" data-write-times="readout">
					Over {grouped(writeTimes.n)} summaries on {writeTimes.timedDays} of these {windowDays} days.
					The fastest took {asSeconds(writeTimes.fastest)} and the slowest {asSeconds(
						writeTimes.slowest
					)}.
				</p>
			{/if}

			<!-- Scoring runs after the summary is written, so nothing waits on it.
			     It sat beside fetch, extract and summarize until 2026-08-31, where a
			     fourth bar on a critical-path chart read as a fourth constraint. -->
			{#if scoreCost === null}
				<p class="mt-2 text-[0.8125rem] text-text-tertiary" data-score-cost="empty">
					Nothing scored a summary in these {windowDays} days.
				</p>
			{:else if scoreCost.n < data.console.min_attempts_for_rate}
				<p class="mt-2 text-[0.8125rem] text-text-tertiary" data-score-cost="thin">
					{grouped(scoreCost.n)}
					{scoreCost.n === 1 ? 'summary was' : 'summaries were'} checked in these {windowDays} days.
					Too few to give a middle or a slowest one in twenty - {data.console
						.min_attempts_for_rate} needed. It runs after the model has finished, so the run never
					waits on it.
				</p>
			{:else}
				<p class="mt-2 text-[0.8125rem] text-text-tertiary" data-score-cost="readout">
					Checking a summary afterwards took a middle of
					<span data-score-cost="median">{asSeconds(scoreCost.median)}</span>, and
					<span data-score-cost="p95">{asSeconds(scoreCost.p95)}</span> at the slowest one in
					twenty, over {grouped(scoreCost.n)} summaries in these {windowDays} days. It runs after
					the model has finished, so the run never waits on it.
				</p>
			{/if}
		</div>

		<!-- Three marks a run, never one a summary. -->
		<div data-model-lengths>
			<h2 class="console-h2">How long the summaries came out</h2>
			<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-model-lengths-intro>
				One column is one run: its shortest summary, its middle one and its longest. Read the
				ends against the shaded band - the middle of a run is rarely the problem.
			</p>

			{#if runsInWindow.length === 0}
				<p class="mt-2 text-[0.9375rem] text-text-secondary" data-run-lengths="empty">
					No run wrote a summary in these {windowDays} days.
				</p>
			{:else}
				<RunLengths
					runs={runsInWindow}
					width={data.console.chart_width}
					height={data.console.chart_height}
					tickDensity={data.chart.tick_density}
					readoutMaxShare={data.chart.readout_max_share}
				/>
			{/if}
		</div>

		<!-- Two models over two article sets is two measurements, not a trend. Both
		     counts print and the panel refuses to draw where either side is thin. -->
		{#if data.modelSwap !== null}
			<div data-model-swap-section>
				<h2 class="console-h2">Did the model change move anything</h2>
				<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-model-swap-intro>
					Every measure is drawn against its own value on the old model, so the dot on the rule
					is the old model and the arrow points to where the new one landed. Different articles
					ran on each, so a move is a difference and not yet a cause.
				</p>
				<p class="mt-2 text-[0.8125rem] text-text-secondary" data-model-swap-counts>
					{data.modelSwap.before.model} wrote {grouped(data.modelSwap.before.articles)} summaries to
					{data.modelSwap.before.to}. {data.modelSwap.after.model} has written {grouped(
						data.modelSwap.after.articles
					)} since {data.modelSwap.at}.
				</p>

				{#if data.modelSwap.enough}
					<SwapDots swap={data.modelSwap} width={data.console.chart_width} />
				{:else}
					<p class="mt-2 text-[0.9375rem] text-text-secondary" data-model-swap="thin">
						One side of the change holds fewer than {data.console.min_attempts_for_rate}
						summaries, so nothing is drawn. The two counts above are the whole answer.
					</p>
				{/if}
			</div>
		{/if}
	{/if}
</section>
