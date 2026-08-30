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
	import { sparklineMarks, type SparklineMarks } from '$lib/charts/sparkline';
	import ConsoleBand from '$lib/components/ConsoleBand.svelte';
	import ConsoleNav from '$lib/components/ConsoleNav.svelte';
	import KpiCard from '$lib/components/KpiCard.svelte';
	import Sparkline from '$lib/components/Sparkline.svelte';
	import ThroughputTrend from '$lib/components/ThroughputTrend.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
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
	 * added without saying in plain words what it counts.
	 */
	const COLUMNS: { key: string; label: string; line: string }[] = [
		{ key: 'summaries', label: 'Summaries today', line: '' },
		{
			key: 'not-sure',
			label: 'Marked "not sure"',
			line: "How many of today's summaries we told you not to trust."
		},
		{
			key: 'unsupported',
			label: 'Numbers not in the article',
			line: 'The summary had a figure. The article did not.'
		},
		{
			key: 'hedge',
			label: '"Maybe" told as fact',
			line: 'The article said it might have happened. The summary said it did.'
		},
		{
			key: 'part',
			label: 'Article read only in part',
			line: 'The article was too long, so the machine read the start and stopped.'
		},
		{
			key: 'part-pct',
			label: 'Read only in part, as a percent',
			line: "The same articles, against the day's own count, so a busy day and a quiet one compare."
		},
		{
			key: 'copied',
			label: 'Copied, not rewritten',
			line: 'How much of a normal summary is lifted word for word.'
		},
		{
			key: 'per-item',
			label: 'Time to write one',
			line: 'How long the machine takes on one article. The second figure is the articles it read only the start of.'
		},
		{ key: 'minutes', label: 'Model minutes', line: '' },
		{
			key: 'too-long',
			label: 'Too long to send',
			line: 'The article and the instructions together did not fit, so the machine was never asked.'
		},
		{ key: 'failed', label: 'Failed', line: '' }
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
			value: cell.text,
			note: cell.aside ?? outOf(cell.key, day),
			trend: trendFor(cell.key)
		}));
	});
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
					changed.
				</p>

				<div class="auto-grid mt-4" style="--auto-grid-min: {CARD_MIN_PX}px" data-model-cards>
					{#each cards as card (card.key)}
						<KpiCard label={card.label} value={card.value} note={card.note} line={card.line}>
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
	{/if}
</section>
