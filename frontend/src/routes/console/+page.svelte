<script lang="ts">
	/** The operator's page, and the first of the console's three routes.
	 *
	 * It answers one question and refuses the others: did the pipeline work. Did
	 * the runs finish, which feeds are broken, how long each stage took, what the
	 * truncation cap is costing and to which sources, and whether the chart arm
	 * earns its minutes. What the model wrote is on `/console/model/` and
	 * the hardware under it is on `/console/machine/`.
	 *
	 * Every count is read from the committed ledger. The only arithmetic is one
	 * committed count divided by another, and that is deliberate: a stored rate
	 * can disagree with the counts printed beside it.
	 *
	 * The run grid stays static. The telemetry viewport and the timing trend are
	 * hand-written SVG, so the console still reads with JavaScript off.
	 */
	import { base } from '$app/paths';
	import { onMount } from 'svelte';
	import {
		axisLabels,
		cellFor,
		centreOffset,
		denseCellFor,
		ROW_STRIP_PX,
		type LabelAlign
	} from '$lib/charts/run-history';
	import {
		datesIn,
		failureSeries,
		grouped,
		parseTelemetryCsv,
		type TelemetryRow
	} from '$lib/charts/series';
	import {
		daysInWindow,
		defaultWindow,
		monthsToFetch,
		panWindow,
		stepPreset,
		windowOfDays,
		type TimeWindow
	} from '$lib/charts/viewport';
	import StageTimings from '$lib/components/StageTimings.svelte';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import ConsoleBand from '$lib/components/ConsoleBand.svelte';
	import ConsoleNav from '$lib/components/ConsoleNav.svelte';
	import KpiCard from '$lib/components/KpiCard.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import TargetBar from '$lib/components/TargetBar.svelte';
	import { shortDate } from '$lib/format';
	import { movementVerdict } from '$lib/charts/theme';
	import type { TargetSense } from '$lib/charts/targetbar';
	import Chart from '$lib/charts/Chart.svelte';
	import {
		columnStrip,
		notMeasuredRow,
		readoutMarks,
		pointerReadout,
		type DayReadout
	} from '$lib/charts/frame';
	import { chartFlow, FLOW_HEIGHT } from '$lib/charts/chart-flow';
	import {
		chartArm,
		failureMix,
		failureMixColumns,
		publishedSkyline,
		runHealth,
		siteCost,
		sizeGain,
		type Skyline,
		type SkylineBar
	} from '$lib/charts/glance';
	import type { StackShape } from '$lib/charts/stacked';
	import ShapeSwitch from '$lib/components/ShapeSwitch.svelte';
	import Sparkline from '$lib/components/Sparkline.svelte';
	import SourceCutRange from '$lib/components/SourceCutRange.svelte';
	import Viewport from '$lib/components/Viewport.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import type { FeedDayOutcome, Health } from './+page.server';

	let { data } = $props();

	/** Where the operator's choice of window is kept between visits. It is the
	 * same key all three console routes read, so the span follows him across the
	 * strip rather than resetting on every click. */
	const WINDOW_KEY = 'idhazh:console-window';

	const presets = $derived(data.console.window_presets);

	// svelte-ignore state_referenced_locally
	let windowDays = $state(data.console.default_window_days);
	// svelte-ignore state_referenced_locally
	let rows = $state<TelemetryRow[]>(data.telemetryRows);
	// svelte-ignore state_referenced_locally
	let loadedMonths = $state([...new Set(datesIn(data.telemetryRows).map((d) => d.slice(0, 7)))]);
	// svelte-ignore state_referenced_locally
	let viewport = $state<TimeWindow>(defaultWindow(datesIn(data.telemetryRows), data.today, data.console));
	/** How many month files are in the air. A count, not a flag: a pan can start
	 * a second fetch while the first is still running, and a flag would clear the
	 * busy state on the first one to finish. */
	let inFlight = $state(0);
	/** False until a browser has run this page. The control cannot do anything
	 * before that, so it says so rather than pretending. */
	let ready = $state(false);

	const fetching = $derived(inFlight > 0);

	/** The choice is read on mount and never during prerender, so first paint is
	 * always the window the server drew and the control always agrees with it. */
	onMount(() => {
		ready = true;
		if (typeof localStorage === 'undefined') return;
		const stored = Number(localStorage.getItem(WINDOW_KEY));
		if (presets.includes(stored) && stored !== windowDays) show(stored);
	});

	function merge(next: TelemetryRow[]) {
		const byKey = new Map(rows.map((row) => [`${row.run_id}-${row.item_id}`, row]));
		for (const row of next) byKey.set(`${row.run_id}-${row.item_id}`, row);
		rows = [...byKey.values()].sort((a, b) => a.date.localeCompare(b.date));
	}

	/** Fetch the month files the window reaches into and does not already hold.
	 *
	 * Widening re-uses this path rather than reloading the page: the rows already
	 * paid for stay in hand, and only the months past them cost anything.
	 */
	async function loadVisibleMonths() {
		const wanted = monthsToFetch(viewport, data.telemetryMonths, loadedMonths);
		if (wanted.length === 0) return;
		loadedMonths = [...loadedMonths, ...wanted];
		inFlight += wanted.length;
		for (const month of wanted) {
			try {
				const response = await fetch(`${base}/telemetry/${month}.csv`);
				if (response.ok) merge(parseTelemetryCsv(await response.text()));
				else console.warn(`telemetry ${month} unavailable; showing a gap`);
			} catch (error) {
				console.warn(`telemetry ${month} could not be read; showing a gap`, error);
			}
			inFlight -= 1;
		}
	}

	/** Set the span every windowed section reads.
	 *
	 * The window re-anchors on the newest day rather than keeping where a pan
	 * left it, because "the last 30 days" is the question the preset asks.
	 */
	function show(days: number, remember = true) {
		windowDays = days;
		viewport = windowOfDays(datesIn(rows), data.today, days, data.console.today_anchor);
		if (remember && typeof localStorage !== 'undefined') {
			localStorage.setItem(WINDOW_KEY, String(days));
		}
		void loadVisibleMonths();
	}

	function pan(days: number) {
		viewport = panWindow(viewport, days);
		void loadVisibleMonths();
	}

	/** The month files a preset would fetch, counted before it is picked. */
	function monthsFor(days: number): number {
		return monthsToFetch(
			windowOfDays(datesIn(rows), data.today, days, data.console.today_anchor),
			data.telemetryMonths,
			loadedMonths
		).length;
	}

	const inWindow = $derived(
		(date: string) => date >= viewport.start && date <= viewport.end
	);
	/** The source table for the window in force. One was built per preset at
	 * build time, so changing the window costs no fetch and no ledger read. */
	const cuts = $derived(
		data.sourceCutsByWindow.find((table) => table.days === windowDays) ??
			data.sourceCutsByWindow[0]
	);
	/** The chart arm's own rule, read from config rather than written into a
	 * component. An operator moves a threshold in `config/appearance.json`. */
	const thresholds = $derived({
		ruleDays: data.console.chart_arm_rule_days,
		minutesTarget: data.console.chart_arm_minutes_target,
		coveragePct: data.console.chart_arm_coverage_pct
	});
	const arm = $derived(
		chartArm(
			data.charts.filter((day) => inWindow(day.date)),
			thresholds,
			windowDays
		)
	);
	/** Articles per published day, as a map, so the cost arithmetic reads it the
	 * same way the server did. */
	const articles = $derived(new Map(Object.entries(data.publishedItems)));
	const perArticle = $derived(siteCost(data.manifests, articles, viewport));
	/** `siteCost`'s own plot insets, so a column the pointer lands on is the
	 * column the strip prints at every width. */
	const COST_GRID = { left: 56, right: 14 };
	/** The cost chart's strip. One series, and it still earns one: the axis
	 * carries a month and a day, the point carries a size, and nothing else on
	 * the chart says whether the day sat outside the band. */
	const costColumns = $derived(
		columnStrip(
			perArticle.days.map((day) => shortDate(day.date)),
			[
				{
					label: 'Payload bytes per article',
					colour: 'var(--chart-3)',
					value: (index) => bytes(Math.round(perArticle.days[index]?.bytesPerItem ?? 0))
				},
				{
					label: 'Against the window',
					colour: '',
					value: (index) =>
						perArticle.spread === null
							? 'one day, so no band'
							: perArticle.days[index]?.flagged
								? 'outside the band'
								: 'inside the band'
				}
			]
		)
	);
	/** What the tree gained over the window, in megabytes.
	 *
	 * It is here rather than in the band because it is a rate and the band is
	 * not windowed. A share is what this used to print, and from the 13,595 bytes
	 * of the oldest committed manifest it read +73,933 percent. */
	const windowedSize = $derived(sizeGain(data.manifests.filter((run) => inWindow(run.date))));
	const sizeDelta = $derived(
		windowedSize === null
			? `No second measurement in these ${windowDays} days.`
			: `${windowedSize >= 0 ? 'Up' : 'Down'} ${(Math.abs(windowedSize) / 1024 / 1024).toFixed(1)} MB over ${windowDays} days.`
	);
	/** One bar a day, over the window the control set. Each card's own count is
	 * the same window summed, so a reader can check the number against the
	 * picture - which an all-time total under a thirty-day strip could not do.
	 *
	 * Two measures, one geometry. Visuals published is a fraction of articles
	 * published, and the fraction only reads as one when the denominator is
	 * drawn beside it on the same window at the same pitch. */
	const articleSkyline = $derived(publishedSkyline(data.charts, viewport, 'items'));
	const visualSkyline = $derived(publishedSkyline(data.charts, viewport, 'published'));

	/** The card's trend slot, in CSS pixels. */
	const SKYLINE = { width: 220, height: 34 };

	/** A day that published one chart against a busiest of forty is a fortieth
	 * of the box, which draws as nothing at all. A hairline floor keeps a quiet
	 * day distinguishable from a day no run happened on. */
	function barHeight(bar: SkylineBar): number {
		return bar.published === 0 ? 0 : Math.max(1, bar.height * SKYLINE.height);
	}

	/** The days every feed strip is drawn over. One axis for the whole list, so
	 * two feeds can be read against each other: a feed broken since Tuesday and a
	 * feed flaky all month draw the same picture on two different axes. */
	const stripDates = $derived(data.feedDates.filter(inWindow));
	/** Fixed rather than measured. Twenty strips each watching their own width is
	 * twenty observers, and the room a list row has is a layout decision the
	 * server can make as well as the browser can. */
	const stripCell = $derived(denseCellFor(ROW_STRIP_PX, stripDates.length));
	const stripAxis = $derived(
		axisLabels(stripDates, {
			density: data.chart.tick_density,
			pitch: stripCell.cell + stripCell.gap
		})
	);
	const strips = $derived(
		new Map(
			data.feeds.map((feed) => [feed.feedId, new Map(feed.days.map((day) => [day.date, day]))])
		)
	);

	/** Is the record deep enough for "never failed" to mean anything?
	 *
	 * Two runs deep it means "did not fail twice". The bar is the same knob the
	 * failure chart above prints a stage rate on, because there is one question
	 * here - how thin is too thin a denominator - and a second number would be a
	 * second answer to it.
	 */
	const feedRecordReadable = $derived(
		data.feedRecord.runs >= data.console.min_attempts_for_rate
	);

	/** What a square means, in words. Colour is one signal and never the only
	 * one, and the two that are not a verdict take no band colour at all. */
	const FEED_KEY: { outcome: FeedDayOutcome; text: string }[] = [
		{ outcome: 'answered', text: 'answered' },
		{ outcome: 'failed', text: 'failed, or answered with nothing' },
		{ outcome: 'refused', text: 'politely refused' },
		{ outcome: 'resting', text: 'not asked - resting' }
	];

	let strip = $state<HTMLDivElement | null>(null);

	// The fill ramp, not the band ramp. The band tokens are text colours and a
	// 16px solid is not text: at text weight the light theme drew olive and
	// brick. tokens.css carries both ramps and design-system.md the band a fill
	// has to land in.
	const COLOUR: Record<Health, string> = {
		green: 'var(--fill-high)',
		amber: 'var(--fill-medium)',
		red: 'var(--fill-low)'
	};

	/** What a square means, in words. Colour is one signal and never the only
	 * one: the readout under the strip prints this word beside the swatch for
	 * the run the pointer is on, and the panel note states the rule once. A
	 * standing key would print the same pair a second time. */
	const VERDICT: Record<Health, string> = {
		green: 'ran clean',
		amber: 'worth a look',
		red: 'failed'
	};
	/** One column per day of the window, whether or not a run happened on it.
	 *
	 * The strip drew only the days a manifest exists for until 2026-09-01, so a
	 * thirty-day window drew eleven columns and a third of a page-wide frame.
	 * The other two thirds read as a chart that failed to load. An empty column
	 * is the fact this strip exists to show: nothing ran that day.
	 */
	const windowGrid = $derived.by(() => {
		const byDate = new Map(data.grid.map((day) => [day.date, day.squares]));
		return daysInWindow(viewport).map((date) => ({ date, squares: byDate.get(date) ?? [] }));
	});
	const windowRuns = $derived(windowGrid.reduce((count, day) => count + day.squares.length, 0));

	/** A label is placed inside its column, not laid out by it, so the widest
	 * date on the axis cannot push a single day track out of step. */
	const ANCHOR: Record<LabelAlign, string> = {
		start: 'left: 0',
		centre: 'left: 50%; transform: translateX(-50%)',
		end: 'right: 0'
	};

	// The newest run is the one an operator came to see, and it sits at the far
	// end. One frame, so the strip has been laid out before it is moved, and
	// never again - after this the scroll position belongs to the operator.
	$effect(() => {
		const node = strip;
		if (!node) return;
		const frame = requestAnimationFrame(() => {
			node.scrollLeft = node.scrollWidth - node.clientWidth;
		});
		return () => cancelAnimationFrame(frame);
	});

	/** The room the strip actually has. Null until a browser measures it, which
	 * is what keeps the prerendered strip drawing at the fixed pair rather than
	 * at zero. */
	let stripWidth = $state<number | null>(null);
	/** The strip grows into the room it has, and centres when it cannot fill it.
	 *
	 * Thirty columns fill a page-wide frame; seven cannot, whatever the cell
	 * size, and a seven-day strip drawn hard left leaves its spare room where a
	 * reader looks for the days that just happened.
	 */
	const strip_ = $derived(cellFor(stripWidth, windowGrid.length));
	const stripPad = $derived(centreOffset(stripWidth, strip_.width));

	/** Which columns of the run strip carry a date. The cell here grows from 16px
	 * to 34px with the room the strip has, so the number of labels that fit is a
	 * measurement and not a constant. */
	const axis = $derived(
		axisLabels(
			windowGrid.map((day) => day.date),
			{ density: data.chart.tick_density, pitch: strip_.cell + strip_.gap }
		)
	);

	/** One column of the run strip, as the readout under it prints it.
	 *
	 * A `title` attribute was the whole hover here until 2026-09-01, and a
	 * native tooltip is not keyboard-reachable, takes no styling and prints one
	 * square rather than the day's whole column. The strip prints every run of
	 * the day at once, each with the swatch it is drawn in - so the readout is
	 * the key as well, and no standing legend is drawn.
	 */
	const runColumns: DayReadout[] = $derived(
		windowGrid.map((day, index) => ({
			x: index * (strip_.cell + strip_.gap) + strip_.cell / 2,
			date: shortDate(day.date),
			rows:
				day.squares.length === 0
					? [notMeasuredRow('No run recorded a manifest')]
					: day.squares.map((square) => ({
							label: `Run ${square.n}`,
							value: VERDICT[square.health],
							colour: COLOUR[square.health]
						}))
		}))
	);
	/** The column a pointer or an arrow key has picked, or null for none. */
	let runAt = $state<number | null>(null);
	/** The newest day, which is the one an operator came for. It is what the
	 * strip prints before anything is pointed at, so it is never blank and the
	 * panel does not change height as it fills. */
	const runReadout = $derived(
		runAt === null ? (runColumns.at(-1) ?? null) : (runColumns[runAt] ?? null)
	);

	$effect(() => {
		const node = strip;
		if (!node || typeof ResizeObserver === 'undefined') return;
		const observer = new ResizeObserver(([entry]) => {
			stripWidth = Math.round(entry.contentRect.width);
		});
		observer.observe(node);
		return () => observer.disconnect();
	});

	/** Whole bytes with thousands separators. The per-article cost is a
	 * four-digit number, so a rounded kilobyte would hide the whole range the
	 * chart is drawn over. */
	function bytes(value: number): string {
		return `${Math.round(value).toLocaleString('en-GB')} B`;
	}

	/** The same window the server drew with. Both sides derive it from the rows
	 * rather than passing it, so the hydrated chart cannot disagree with the one
	 * already on the page. */
	function failureSeriesFor(rows: TelemetryRow[]) {
		const dates = datesIn(rows);
		if (dates.length === 0) return [];
		return failureSeries(rows, { start: dates[0], end: dates[dates.length - 1] });
	}

	/** The stage failure series the mix chart and its strip both read. One array,
	 * so the band a reader hovers and the number the strip prints are the same
	 * measurement rather than two that happen to agree today. */
	const mixSeries = $derived(failureSeriesFor(data.telemetryRows));
	/** The server drew stacked, so the first paint matches the prerendered
	 * document. Picking `Lines` redraws the identical values. */
	let mixShape = $state<StackShape>('bars');

	/** A minute count, or a dash where there is no number to print.
	 *
	 * Null means nothing was measured. Printing that as `0.0` would say the
	 * visuals planner was free, and printing a per-visual cost of infinity on a day
	 * with no visual would say it was ruinous. Both are answers to a question
	 * nobody asked.
	 */
	function minutes(value: number | null): string {
		return value === null ? '-' : value.toFixed(1);
	}
</script>

<svelte:head>
	<title>Console: Pipelines &mdash; {data.ui.site_title}</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<section class="py-6" data-surface="operator" data-console-route="pipelines">
	<h1 class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text">Console</h1>
	<p class="mt-1 text-[0.9375rem] text-text-secondary">
		What the pipeline cost and how well it did, per day, from the committed ledger.
	</p>

	<!-- The band stands on all three routes and carries the window control, so
	     the control is above everything it governs rather than under the first
	     chart that obeys it. -->
	<ConsoleBand band={data.band}>
		{#snippet window()}
			<WindowControl
				days={windowDays}
				{presets}
				{monthsFor}
				busy={fetching}
				{ready}
				onChange={show}
			/>
		{/snippet}
	</ConsoleBand>
	<ConsoleNav routes={data.routes} active="pipelines" />

	<!-- One sentence, no chart. It is what stops this route hiding the panel on
	     another route that explains its own numbers. -->
	<p class="console-carry" data-console-carry="model">
		{data.carries.pipelines}
		<a class="carry-link" href="{base}/console/model/">Model &rarr;</a>
	</p>

	<!-- Six questions, six shapes. A different chart per question is the point:
	     one shape repeated is what made this page read as a single instrument. -->
	<h2 class="console-h2">At a glance</h2>
	<!-- Bars, not a line: a count per day is a discrete quantity, and a line
	     between two days claims a value for the hours in between that nobody
	     counted. Drawn as markup rather than by the engine, so it is complete
	     before any script runs and follows the window with one drawing.

	     One snippet draws both strips. Two copies would agree on the day they
	     were written and drift on the first day either was tuned, and the pair
	     is only readable while both are one bar a day at the same pitch. -->
	{#snippet skylineBars(strip: Skyline, measure: string, noun: string)}
		<svg
			class="block"
			width={SKYLINE.width}
			height={SKYLINE.height}
			viewBox="0 0 {SKYLINE.width} {SKYLINE.height}"
			role="img"
			aria-label="{noun} each day over {windowDays} days, {grouped(strip.total)} in all, {grouped(
				strip.busiest
			)} on the busiest day"
			data-published-measure={measure}
			data-published-days={strip.bars.length}
			data-published-total={strip.total}
		>
			{#each strip.bars as bar (bar.date)}
				<rect
					x={(bar.x * SKYLINE.width).toFixed(2)}
					width={(bar.width * SKYLINE.width).toFixed(2)}
					y={(SKYLINE.height - barHeight(bar)).toFixed(2)}
					height={barHeight(bar).toFixed(2)}
					fill="var(--chart-3)"
					data-published-bar={bar.date}
					data-published={bar.published}
				/>
			{/each}
		</svg>
	{/snippet}
	{#snippet articleBars()}{@render skylineBars(articleSkyline, 'articles', 'Articles published')}{/snippet}
	{#snippet visualBars()}{@render skylineBars(visualSkyline, 'visuals', 'Visuals published')}{/snippet}

	<!-- Which way a chart-arm figure has moved across the window it draws.

	     The polarity comes off the bar's own marks, so the delta and the target
	     marker above it read one declaration: fewer router minutes is better and
	     a wider chart share is better, and neither is decided here. -->
	{#snippet armMove(change: number | null, sense: TargetSense, figure: string)}
		{#if change !== null}
			{@const verdict = movementVerdict(change, sense)}
			<p class="arm-move" data-arm-move={figure}>
				<span
					class="arm-move-value"
					data-movement={change.toFixed(4)}
					data-polarity={sense}
					data-movement-verdict={verdict}
					data-movement-paint="color"
					>{change >= 0 ? '+' : ''}{Math.round(change * 100)}%</span
				>
				across this window
			</p>
		{/if}
	{/snippet}
	<div class="auto-grid mt-4" style="--auto-grid-min: 17rem" data-glance>
		<!-- Articles first. Visuals published is a fraction of it, and a fraction
		     reads as one only when the denominator is beside it. -->
		<KpiCard
			label="Articles published"
			value={grouped(articleSkyline.total)}
			note="in these {windowDays} days"
			tone="info"
			trend={articleSkyline.empty ? null : articleBars}
		/>
		<KpiCard
			label="Visuals published"
			value={grouped(visualSkyline.total)}
			note="in these {windowDays} days"
			tone="info"
			trend={visualSkyline.empty ? null : visualBars}
		/>
		<!-- No site-size card here. The band above states the level, the share of
		     the 1 GB cap and the runway, and it states them on all three routes;
		     one page may not state one figure twice. What is left below is the
		     windowed per-article cost, which is the rate under that runway. -->
		{#if data.glance.healthSvg}
			<figure class="panel" data-glance-chart="runs">
				<figcaption class="text-[0.75rem] text-text-tertiary">Did the runs finish?</figcaption>
				<Chart
					svg={data.glance.healthSvg}
					option={runHealth(data.manifests).option}
					width={260}
					height={200}
					label="Share of planned items that finished, against those that failed"
					noReadout="two shares of one total, and each share carries its own label"
				/>
			</figure>
		{/if}
		<!-- No minutes card here. `Visuals drawn for articles` prints the
		     same window median against the same target, with the coverage half of
		     the rule beside it, and one page may not state one figure twice. -->
	</div>

	<div
		data-windowed="site-cost-per-item"
		data-window-days={windowDays}
		data-model-rule="no"
		data-model-rule-name="site-cost-per-item"
		data-model-rule-none="bytes an article are what got published, not how it was written"
	>
		<Panel
			title="What one more article costs"
			note="Bytes the committed payload tree gained on each published day, over the articles that day published. Over {windowDays} days. {sizeDelta}"
		>
			{#if perArticle.empty}
				<p class="mt-2 text-[0.8125rem] text-text-secondary" data-window-empty="site-cost-per-item">
					No day in these {windowDays} days both published an article and recorded a size, so there is
					no cost to divide.
				</p>
			{:else}
				<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-cost-summary>
					{#if perArticle.spread === null}
						One published day in these {windowDays} days, at {bytes(perArticle.median ?? 0)} an article.
						One day is not a spread, so no day is flagged.
					{:else}
						Median {bytes(perArticle.median ?? 0)} an article, give or take {bytes(
							perArticle.spread ?? 0
						)}.
						{perArticle.days.filter((day) => day.flagged).length} of {perArticle.days.length} days fall outside
						that.
					{/if}
				</p>
				{#if data.glance.perArticleSvg}
					{#key windowDays}
						<Chart
							svg={data.glance.perArticleSvg}
							option={perArticle.option}
							width={760}
							height={220}
							label="Payload bytes per article on each published day, over {windowDays} days, against the median and one standard deviation either side of it"
							columns={costColumns}
							readoutName="cost-per-article"
							readoutMaxShare={data.chart.readout_max_share}
							grid={COST_GRID}
							restingNote=", the newest published day"
							hint="Point at a day to read what its articles cost. Left and Right step through them, Escape returns to the newest."
						/>
					{/key}
				{/if}
				<!-- The values, as text. It is what a chart owes anybody who cannot
				     see it, and it is also the only honest way to check the flags:
				     a chart that flags by eye cannot be tested, and the browser suite
				     recomputes the band from exactly these numbers. -->
				<ul class="sr-only" data-cost-days>
					{#each perArticle.days as day (day.date)}
						<li
							data-cost-day={day.date}
							data-cost-bytes={Math.round(day.bytesPerItem)}
							data-cost-flagged={String(day.flagged)}
						>
							{day.date}: {bytes(day.bytesPerItem)} an article{day.flagged
								? ', outside the band'
								: ''}
						</li>
					{/each}
				</ul>
			{/if}
		</Panel>
	</div>

	{#if data.glance.mixSvg}
		<!-- No note. The heading names the subject and the strip under the chart
		     prints every stage at the hovered day, so a sentence restating the
		     encoding said what the shape already says - and said it wrongly the
		     moment the switch below drew lines. It survives verbatim in the chart's
		     accessible description, so nobody loses it. -->
		<Panel title="What is failing, by stage">
			<Chart
				svg={data.glance.mixSvg}
				option={failureMix(mixSeries, mixShape).option}
				width={760}
				height={220}
				label="Failures per day by stage. One column is one day, its height is that day's failures, and the bands are the stages they stopped at - so a quiet day and a clean day do not draw alike. Drawn as lines instead, each stage is its own count a day and the total is not shown."
				columns={failureMixColumns(mixSeries)}
				readoutName="failure-mix"
				readoutMaxShare={data.chart.readout_max_share}
				restingNote=", the newest day"
				hint="Point at a day to read every stage at once. Left and Right step through the days, Escape returns to the newest."
			/>
			<!-- Stacked answers what the mix is and how big the day got; lines answer
			     what one stage did on its own, which a stack hides when one band
			     halves while its neighbour doubles. Same array either way. -->
			<ShapeSwitch bind:shape={mixShape} name="failure-mix" label="How to draw the failure mix" />
		</Panel>
	{/if}

	<div data-windowed="run-health" data-window-days={windowDays}>
		<Panel
			title="Run health"
			note="The last {windowDays} days, one column per day, oldest on the left, one square per recorded run with run 1 at the bottom. A column with no square is a day nothing ran. A run is green when it published what it planned, amber when it found nothing new, and red when it failed or published under {data.floorPct}%. A skipped item does not count against a run - an article we already published is skipped by design."
		>
			{#if data.grid.length === 0}
				<p class="text-[0.9375rem] text-text-secondary" data-grid="empty">
					No run has recorded a manifest yet. The strip fills as runs publish.
				</p>
			{:else if windowRuns === 0}
				<!-- A different fact from the one above, so a different sentence: the
				     ledger answered, and the answer was nothing in this span. -->
				<p class="text-[0.9375rem] text-text-secondary" data-grid="outside-window">
					No run recorded a manifest in these {windowDays} days. Widen the window to look further
					back.
				</p>
			{:else}
				<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
				<div
					class="overflow-x-auto pb-1"
					role="region"
					tabindex="0"
					aria-label="Run health history for the last {windowDays} days, oldest to newest"
					bind:this={strip}
					data-run-history
				>
					<!-- Left-anchored while it overflows, centred while it does not, and
					     that is not the same question as where an overflowing strip
					     opens. `today_anchor` governs the scroll position; a strip with
					     room to spare puts its spare room on both sides, because the
					     right of a time axis ending today is where a reader looks for
					     the days that just happened. -->
					<div
						class="grid w-max items-end justify-start"
						style="grid-template-columns: repeat({windowGrid.length}, {strip_.cell}px); gap: {strip_.gap}px; margin-inline-start: {stripPad}px"
						data-grid="days"
						data-strip-pad={stripPad}
						tabindex="0"
						role="group"
						aria-label="Run health, one column a day. Left and Right read a day, Escape returns to the newest."
						use:pointerReadout={{
							marks: readoutMarks(runColumns),
							width: strip_.width,
							onSelect: (index) => (runAt = index)
						}}
					>
						{#each windowGrid as day, index (day.date)}
							<!-- Column-reverse, so run 1 sits on the baseline and later runs stack
							     upward, while the DOM keeps reading run 1 first. -->
							<div
								class="flex flex-col-reverse justify-start"
								style="grid-row: 1; grid-column: {index + 1}; gap: {strip_.gap}px"
								data-day={day.date}
								data-day-selected={runAt === index ? 'true' : null}
							>
								{#each day.squares as square (square.runId)}
									<span
										class="rounded-sm"
										style="width: {strip_.cell}px; height: {strip_.cell}px; background: {COLOUR[
											square.health
										]}"
										title={square.label}
										aria-label={square.label}
										data-health={square.health}
										role="img"
									></span>
								{/each}
							</div>
						{/each}

						{#each axis as label (label.column)}
							<div class="relative h-4" style="grid-row: 2; grid-column: {label.column}">
								<span
									class="absolute top-0 whitespace-nowrap text-[0.625rem] leading-4 tabular-nums text-text-tertiary"
									style={ANCHOR[label.align]}
									data-day-axis
									data-axis-label={label.column}
								>
									{label.text}
								</span>
							</div>
						{/each}
					</div>
				</div>

				<ChartReadout
					readout={runReadout}
					name="run-health"
					maxShare={data.chart.readout_max_share}
					resting={runAt === null}
					restingNote=", the newest day"
					hint="Point at a day to read every run on it. Left and Right step through the days, Escape returns to the newest."
				/>
			{/if}
		</Panel>
	</div>

	<Viewport
		{rows}
		window={viewport}
		config={data.console}
		bands={data.summarizeBands}
		tickDensity={data.chart.tick_density}
		readoutMaxShare={data.chart.readout_max_share}
		modelChanges={data.modelChanges}
		onPan={pan}
		onStep={(direction) => show(stepPreset(windowDays, presets, direction))}
	/>

	<div data-windowed="source-cuts" data-window-days={cuts.days}>
		<h2 class="console-h2">Sources cut short most often</h2>

		{#if cuts.cost}
			<!-- What the next move of the cap would buy, and the first line of the
			     section rather than the last. A count of cut articles says the cap
			     fired; how much it removed says whether raising it is worth
			     anything, and the n is what makes it a measurement. -->
			<p class="mt-2 text-[0.9375rem] text-text-secondary" data-source-cuts-cost>
				{cuts.cost.n} articles were cut short. Half of them lost more than {grouped(
					cuts.cost.median
				)} words each, and the longest lost {grouped(cuts.cost.max)}.
			</p>
		{/if}

		<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-source-cuts-intro>
			The last {cuts.days} days, {grouped(cuts.articles)}
			{cuts.articles === 1 ? 'article' : 'articles'} between them. An article longer than the cap
			is read from the start and stopped there, so the end never reaches the machine. Sorted by how
			many articles that cost each source. A source can carry several feeds, so this list and
			"Feeds that failed" below do not name the same things. Panning does not move these days:
			they always end on the newest day the ledger holds.
		</p>

		{#if !cuts.measured}
			<p class="mt-4 text-[0.9375rem] text-text-secondary" data-source-cuts="unmeasured">
				Nothing has recorded an article length yet. This fills as runs publish.
			</p>
		{:else if cuts.rows.length === 0}
			<p class="mt-4 text-[0.9375rem] text-text-secondary" data-source-cuts="none">
				No article was cut short in these {cuts.days} days.
			</p>
		{:else}
			<div class="mt-3">
				<SourceCutRange
					rows={cuts.rows}
					caps={cuts.caps}
					width={data.console.chart_width}
				/>
			</div>

			{#if cuts.moreSources > 0}
				<p class="mt-3 text-[0.8125rem] text-text-tertiary" data-source-cuts-more>
					{cuts.moreSources} more sources had {cuts.moreCuts} cuts between them.
				</p>
			{/if}
		{/if}
	</div>

	<h2 class="console-h2">Feeds that failed</h2>

	{#if data.feedRecord.runs === 0}
		<p class="mt-2 text-[0.9375rem] text-text-secondary" data-feeds="empty">
			No feed result has been recorded yet. The ledger fills as runs collect.
		</p>
	{:else}
		<p
			class="mt-2 text-[0.9375rem] text-text"
			data-feed-reliability={feedRecordReadable ? 'measured' : 'shallow'}
			data-feed-clean={data.feedRecord.clean.length}
			data-feed-checked={data.feedRecord.checked}
			data-feed-runs={data.feedRecord.runs}
		>
			{#if feedRecordReadable}
				{data.feedRecord.clean.length} of {data.feedRecord.checked} feeds have never failed a read,
				across {data.feedRecord.runs}
				{data.feedRecord.runs === 1 ? 'run' : 'runs'}.
			{:else}
				{data.feedRecord.clean.length} of {data.feedRecord.checked} feeds have not failed a read.
				The record is {data.feedRecord.runs}
				{data.feedRecord.runs === 1 ? 'run' : 'runs'} deep, under the {data.console
					.min_attempts_for_rate} this page prints a rate on, so it is too early to read that as reliability.
			{/if}
		</p>

		{#if data.feedRecord.clean.length > 0}
			<details class="console-disclosure mt-2" data-feed-clean-list>
				<summary class="console-summary" data-feed-clean-toggle>
					Name the {data.feedRecord.clean.length} that never failed
				</summary>
				<p class="mt-2 text-[0.8125rem] text-text-tertiary" data-feed-clean-note>
					Alphabetical, because there is no order here: a feed is read once a run, so every clean
					feed has the same record. A source whose <code>robots.txt</code> says no has not failed
					either.
				</p>
				<ul class="feed-clean-names" data-feed-clean-names>
					{#each data.feedRecord.clean as feedId (feedId)}
						<li data-feed-clean-name={feedId}>{feedId}</li>
					{/each}
				</ul>
			</details>
		{/if}
	{/if}

	<p class="mt-3 text-[0.8125rem] text-text-tertiary" data-window-exempt="feeds">
		The pipeline rests a feed after {data.quarantineAfter} failures in a row. The count beside
		each feed is that run of failures, read over every run on record - it does not follow the
		window above, because the pipeline rested on the whole count and not on a windowed one. The
		count above it is read over the same whole record, for the same reason. The strip of days
		beside each feed does follow the window. A feed that answered with nothing counts as a
		failure: an empty answer costs the digest the same articles a refusal does. A source whose
		<code>robots.txt</code> says no does not, and a feed nobody has asked is in neither count.
	</p>

	{#if data.feedRecord.runs > 0 && data.feeds.length === 0}
		<p class="mt-4 text-[0.9375rem] text-text-secondary" data-feeds="clean">
			No feed has failed in these {data.feedRecord.runs}
			{data.feedRecord.runs === 1 ? 'run' : 'runs'}, so there is nothing to list.
		</p>
	{:else if data.feeds.length > 0}
		<div
			class="console-table mt-3"
				data-windowed="feed-outcomes"
				data-window-days={windowDays}
				data-model-rule="no"
				data-model-rule-name="feed-outcomes"
				data-model-rule-none="a feed answered or it did not, before any summary was written"
			>
			<p class="feeds-note">
				Nearest to a rest first, then by how much has gone wrong in total. Each strip is one
				square a day, oldest to newest, over these {windowDays} days.
			</p>

			<ol class="feed-rows" data-feeds="table" data-feeds-drawn={data.feeds.length} data-feeds-hidden={data.feedsHidden}>
				{#each data.feeds as feed (feed.feedId)}
					<!-- The streak and the track length are published because they are what
					     the marker is drawn from. A check that re-reads the bar's own
					     numbers off the page cannot be fooled by a bar drawn to the wrong
					     scale, which is the failure worth catching here: nothing about it
					     looks broken. -->
					<li
						class="feed-row"
						data-feed={feed.feedId}
						data-feed-resting={feed.resting ? 'yes' : null}
						data-feed-streak={feed.streak}
						data-feed-failures={feed.failures}
						data-feed-track={feed.marks.track}
					>
						<p class="feed-name">
							<span>{feed.feedId}</span>
							{#if feed.resting}
								<span class="feed-rested" data-rested>rested</span>
							{/if}
						</p>

						<div class="feed-bar" data-feed-cell="bar">
							<TargetBar
								marks={feed.marks}
								label="Failures in a row"
								valueText={feed.streak === 1 ? '1 failure' : `${feed.streak} failures`}
								targetText="rested at {data.quarantineAfter} in a row"
								emptyNote="Nothing has asked this feed yet."
								tone="health"
							/>
						</div>

						{#if stripDates.length > 0}
							<div
								class="feed-strip"
								data-feed-strip={feed.feedId}
								style="grid-template-columns: repeat({stripDates.length}, {stripCell.cell}px); gap: {stripCell.gap}px"
							>
								{#each stripDates as date (date)}
									{@const day = strips.get(feed.feedId)?.get(date) ?? null}
									<span
										class="feed-square"
										style="block-size: {stripCell.cell}px"
										data-feed-day={date}
										data-feed-outcome={day ? day.outcome : 'none'}
										title={day ? day.label : `${shortDate(date)}: nothing on record.`}
										aria-label="{feed.feedId} on {day
											? day.label
											: `${shortDate(date)}: nothing on record.`}"
										role="img"
									></span>
								{/each}
							</div>
						{/if}

						<p class="feed-result" data-feed-result>
							{feed.lastResult}{feed.lastDetail ? ` - ${feed.lastDetail}` : ''}
						</p>
					</li>
				{/each}
			</ol>

			{#if data.feedsHidden > 0}
				<p class="feeds-note" data-feeds-more>
					{data.feedsHidden} more {data.feedsHidden === 1 ? 'feed' : 'feeds'} had {grouped(
						data.feedsHiddenFailures
					)}
					{data.feedsHiddenFailures === 1 ? 'failure' : 'failures'} between them, none closer to a
					rest than the last row here.
				</p>
			{/if}

			{#if stripDates.length > 0}
				<div
					class="feed-axis"
					style="inline-size: {stripCell.width}px; grid-template-columns: repeat({stripDates.length}, {stripCell.cell}px); gap: {stripCell.gap}px"
				>
					{#each stripAxis as label (label.column)}
						<div class="feed-axis-slot" style="grid-column: {label.column}">
							<span style={ANCHOR[label.align]} data-day-axis data-feed-axis={label.column}
								>{label.text}</span
							>
						</div>
					{/each}
				</div>
			{:else}
				<p class="feeds-note" data-feed-strip-empty>
					The pipeline read no feed in these {windowDays} days, so there is no strip to draw.
				</p>
			{/if}

			<ul class="feed-key">
				{#each FEED_KEY as entry (entry.outcome)}
					<li><span class="feed-square" data-feed-outcome={entry.outcome}></span>{entry.text}</li>
				{/each}
			</ul>
		</div>
	{/if}

	<StageTimings
		days={data.timingDays}
		span={viewport}
		height={data.console.chart_height}
		width={data.console.chart_width}
		tickDensity={data.chart.tick_density}
		readoutMaxShare={data.chart.readout_max_share}
		modelChanges={data.modelChanges}
	/>

	{#if data.charts.length > 0}
		<h2 class="console-h2">Visuals drawn for articles</h2>
		<div
			data-windowed="chart-arm"
			data-window-days={windowDays}
			data-model-rule="no"
			data-model-rule-name="chart-arm"
			data-model-rule-none="the chart arm is a different model call, judged on its own rule"
		>
			<p class="mt-1 text-[0.8125rem] text-text-tertiary">
				Over {thresholds.ruleDays} days with the chart-only gate on, the arm is retired if the
				median day spends more than {thresholds.minutesTarget} minutes per published visual, or
				puts a visual on fewer than {thresholds.coveragePct}% of the items it published. Over
				{windowDays} days.
			</p>
			<div class="console-panel mt-3" data-charts="arm">
				{#if arm.narrow}
					<!-- The rule is stated over its own span, and a median of any other
					     span is the same figure with a different meaning. -->
					<p class="text-[0.9375rem] text-text-secondary" data-window-too-narrow="chart-arm">
						The rule reads {thresholds.ruleDays} days. Widen the window to see it.
					</p>
				{:else}
					<p class="text-[0.9375rem] text-text" data-charts-verdict>{arm.verdict}</p>
					<div class="arm-figures">
						<div class="arm-figure" data-arm-figure="minutes">
							<TargetBar
								marks={arm.minutesMarks}
								label="Minutes per visual"
								valueText={arm.minutes === null ? '-' : arm.minutes.toFixed(1)}
								targetText="Retired above {thresholds.minutesTarget}, on the median day."
								emptyNote="No minutes are on record for these {windowDays} days."
							/>
							<Sparkline
								marks={arm.minutesTrend}
								width={220}
								height={30}
								label="Minutes per visual, day by day, over {arm.minutesDays} measured days"
							/>
							{@render armMove(arm.minutesTrend.movement, arm.minutesMarks.sense, 'minutes')}
						</div>
						<div class="arm-figure" data-arm-figure="coverage">
							<TargetBar
								marks={arm.coverageMarks}
								label="Published articles with a visual"
								valueText={arm.coverage === null ? '-' : `${Math.round(arm.coverage)}%`}
								targetText="Retired below {thresholds.coveragePct}%, on the median day."
								emptyNote="No day in these {windowDays} days published anything to put a visual on."
							/>
							<Sparkline
								marks={arm.coverageTrend}
								width={220}
								height={30}
								label="Share of published articles carrying a visual, day by day, over {arm.coverageDays} measured days"
							/>
							{@render armMove(arm.coverageTrend.movement, arm.coverageMarks.sense, 'coverage')}
						</div>
					</div>
				{/if}
			</div>
		</div>
		{#if data.flowSvg}
			<div class="panel mt-4" data-flow="chart">
				<Chart
					svg={data.flowSvg}
					option={chartFlow(data.charts).option}
					width={data.console.chart_width}
					height={FLOW_HEIGHT}
					label="Where items go between the visuals planner reaching one and a visual being published, across the window. Every drop leaves the flow as its own branch, and a branch is as wide as the number of items in it."
					noReadout="a flow between stages, so there is no column two branches share"
				/>
			</div>
		{:else if data.flowNote}
			<p class="panel mt-4 text-[0.8125rem] text-text-tertiary" data-flow="none">{data.flowNote}</p>
		{/if}
		<!-- A native disclosure, not a button and a block: the console is complete
		     before any script runs, and a button would leave the rows unreachable
		     with JavaScript off. -->
		<details class="console-disclosure mt-4" data-charts="daily">
			<summary class="console-summary" data-charts-toggle>Show the daily figures</summary>
			<p class="mt-3 text-[0.8125rem] text-text-tertiary">
				One row per day, newest first. Reached is every item the visuals planner looked at, asked
				the model is the part it sent a request for, visuals drafted is what the model returned,
				and visuals published is what survived the checks after it. A dash means no minutes are on
				record, so there is no rate to divide. Zero reached means nothing committed says what the
				visuals planner did: it never ran, or its manifest is older than these counts.
			</p>
			<div class="console-table mt-3" data-charts="table">
				<table class="w-full text-[0.8125rem]">
					<thead class="text-text-tertiary">
						<tr class="border-b border-rule">
							<th class="py-2 text-start font-normal">Day</th>
							<th class="py-2 text-end font-normal">Reached</th>
							<th class="py-2 text-end font-normal">Asked the model</th>
							<th class="py-2 text-end font-normal">Visuals drafted</th>
							<th class="py-2 text-end font-normal">Visuals published</th>
							<th class="py-2 text-end font-normal">Items published</th>
							<th class="py-2 text-end font-normal">Minutes spent</th>
							<th class="py-2 text-end font-normal">Minutes per visual</th>
						</tr>
					</thead>
					<tbody>
						{#each data.charts as day (day.date)}
							<tr class="border-b border-rule" data-chart-day={day.date}>
								<td class="py-2">{day.date}</td>
								<td class="py-2 text-end tabular-nums" data-charts-cell="reached">{day.reached}</td>
								<td class="py-2 text-end tabular-nums" data-charts-cell="asked">{day.asked}</td>
								<td class="py-2 text-end tabular-nums" data-charts-cell="drafted">{day.drafted}</td>
								<td class="py-2 text-end tabular-nums" data-charts-cell="published"
									>{day.published}</td
								>
								<td class="py-2 text-end tabular-nums" data-charts-cell="items">{day.items}</td>
								<td class="py-2 text-end tabular-nums" data-charts-cell="minutes"
									>{minutes(day.routerMinutes)}</td
								>
								<td class="py-2 text-end tabular-nums" data-charts-cell="per-chart"
									>{minutes(day.minutesPerChart)}</td
								>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</details>
	{/if}
</section>

<style>
/* Route-specific only. The shapes every console route shares - the h2, the
   framed table, the disclosure, the carry sentence - are in app.css, so three
   routes cannot drift into three identities that merely agree today. */

/* Two figures, side by side where there is room and stacked where there is
   not. The rule names both, so reading one without the other answers half a
   question. */
.arm-figures {
display: grid;
grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr));
gap: var(--space-6);
margin-block-start: var(--space-4);
}

.arm-figure {
display: flex;
flex-direction: column;
gap: var(--space-2);
min-inline-size: 0;
}

/* The movement pair, never the confidence ramp: a window in which the router
   got 3 percent slower is not a broken run, and painting it in --band-low is
   how an operator learns to ignore --band-low. The sign is printed beside the
   colour, so the hue is never the only signal. */
.arm-move {
margin: 0;
font-size: var(--text-xs);
line-height: var(--leading-xs);
color: var(--color-text-tertiary);
}

.arm-move-value[data-movement-verdict='good'] {
color: var(--movement-good);
}
.arm-move-value[data-movement-verdict='bad'] {
color: var(--movement-bad);
}
.arm-move-value[data-movement-verdict='neutral'] {
color: var(--color-text-secondary);
}

.feeds-note {
margin: 0 0 var(--space-3);
font-size: var(--text-xs);
line-height: var(--leading-xs);
color: var(--color-text-tertiary);
}

/* Names, not rows. There is nothing to rank and nothing to draw, so the list
   packs into as many columns as the room allows rather than running a hundred
   and fifty-six lines down the page. */
.feed-clean-names {
display: grid;
grid-template-columns: repeat(auto-fill, minmax(12rem, 1fr));
gap: var(--space-1) var(--space-4);
margin: var(--space-2) 0 0;
padding: 0;
list-style: none;
font-size: var(--text-sm);
line-height: var(--leading-sm);
color: var(--color-text-secondary);
}

/* One column set for the whole list, borrowed by every row, so a feed with a
   two-digit count does not get a shorter bar than a feed with a one-digit one.
   The same reason the ranked list does it. */
.feed-rows {
display: grid;
grid-template-columns: minmax(8rem, 1fr) minmax(11rem, 1.4fr) auto;
column-gap: var(--space-4);
margin: 0;
padding: 0;
list-style: none;
}

.feed-row {
grid-column: 1 / -1;
display: grid;
grid-template-columns: subgrid;
grid-template-areas: 'name bar strip' 'result bar strip';
align-items: center;
padding-block: var(--space-2);
border-block-end: 1px solid var(--color-rule);
}

.feed-row:last-child {
border-block-end: 0;
}

.feed-name {
grid-area: name;
display: flex;
align-items: center;
gap: var(--space-2);
margin: 0;
font-size: var(--text-sm);
line-height: var(--leading-sm);
color: var(--color-text);
overflow-wrap: anywhere;
}

/* The word, not the colour. A rested feed is the one thing on this list an
   operator has to act on, so it is written out. */
.feed-rested {
padding-inline: var(--space-2);
border-radius: var(--radius-full);
background: var(--tint-bad);
font-size: var(--text-xs);
line-height: var(--leading-xs);
color: var(--color-text-secondary);
white-space: nowrap;
}

/* The only human-readable cause on the page, and it is never traded for a
   glyph. It keeps its own line rather than becoming a caption on the bar. */
.feed-result {
grid-area: result;
margin: 0;
font-size: var(--text-xs);
line-height: var(--leading-xs);
color: var(--color-text-secondary);
}

.feed-bar {
grid-area: bar;
min-inline-size: 0;
}

.feed-strip,
.feed-axis {
display: grid;
}

/* The column the readout is printing. A tint behind the day rather than a rule
   through it: an empty column has no square for a rule to land on, and an empty
   column is exactly the one a reader most needs to see selected. */
[data-day-selected] {
background: var(--color-surface-sunken);
box-shadow: 0 0 0 2px var(--color-surface-sunken);
border-radius: 2px;
}

.feed-strip {
grid-area: strip;
}

.feed-square {
display: block;
border-radius: 2px;
background: transparent;
}

/* Quarantine is a health fact and every square carries its own sentence as
   well, so this is one of the two places a verdict ramp is the honest colour.
   The FILL ramp, the same one the run strip above uses: a square this small is
   a solid, not type, and the band tokens are weighted to be read as type. The
   two states that are not a verdict take no verdict colour at all. */
.feed-square[data-feed-outcome='answered'] {
background: var(--fill-high);
}

.feed-square[data-feed-outcome='failed'] {
background: var(--fill-low);
}

.feed-square[data-feed-outcome='refused'] {
background: var(--tint-neutral);
box-shadow: inset 0 0 0 1px var(--color-rule);
}

.feed-square[data-feed-outcome='resting'] {
box-shadow: inset 0 0 0 1px var(--color-rule);
}

/* Flush with the strips above it: the strip column is the last one, so it ends
   at the same edge the list does. */
.feed-axis {
margin-block-start: var(--space-2);
margin-inline-start: auto;
}

.feed-axis-slot {
position: relative;
block-size: 1rem;
}

.feed-axis-slot span {
position: absolute;
top: 0;
white-space: nowrap;
font-size: 0.625rem;
line-height: 1rem;
font-variant-numeric: tabular-nums;
color: var(--color-text-tertiary);
}

.feed-key {
display: flex;
flex-wrap: wrap;
gap: var(--space-2) var(--space-5);
margin: var(--space-4) 0 0;
padding: 0;
list-style: none;
font-size: var(--text-xs);
line-height: var(--leading-xs);
color: var(--color-text-tertiary);
}

.feed-key li {
display: flex;
align-items: center;
gap: var(--space-2);
}

.feed-key .feed-square {
inline-size: 12px;
block-size: 12px;
flex-shrink: 0;
}

/* The console frame is wide, and three columns on a laptop half-window crush
   the bar the row exists to show. Below that everything stacks. */
@media (max-width: 48rem) {
.feed-rows {
grid-template-columns: minmax(0, 1fr);
}

.feed-row {
grid-template-areas: 'name' 'bar' 'strip' 'result';
row-gap: var(--space-2);
}

.feed-axis {
margin-inline-start: 0;
}
}
</style>