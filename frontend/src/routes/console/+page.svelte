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
	import TimeHistogram from '$lib/components/TimeHistogram.svelte';
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
		publishingHorizon,
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
	/** What one item cost the model, for the window in force. Reduced once per
	 * preset at build time, the same way the source table above it is.
	 *
	 * It cannot be recomputed here: the seeded rows carry the model's clocks and
	 * token counts as nulls, because seeding their real values cost this page
	 * 176,753 gzipped bytes and put it 98,182 over its ceiling. So the section
	 * follows the window's length and not a pan, and says so.
	 */
	const cost = $derived(
		data.itemCostByWindow.find((entry) => entry.days === windowDays) ?? data.itemCostByWindow[0]
	);

	/** Whole seconds, and `<1` where a real measurement rounds away. The console
	 * prints no decimal, and a `0` there would say the work was free. */
	function asSeconds(ms: number): string {
		const value = Math.round(ms / 1000);
		return value === 0 && ms > 0 ? '<1 s' : `${grouped(value)} s`;
	}

	/** A count, or a dash where the ledger holds no answer. Null and zero are
	 * different facts, and a zero that was really an absence is the one number
	 * nobody checks. */
	function count(value: number | null): string {
		return value === null ? '-' : grouped(value);
	}

	/** The same rule for a share, which the console prints as whole percent. */
	function pct(value: number | null): string {
		return value === null ? '-' : `${value}%`;
	}
	/** The chart arm's own rule, read from config rather than written into a
	 * component. An operator moves a threshold in `config/appearance.json`. */
	const thresholds = $derived({
		ruleDays: data.console.chart_arm_rule_days,
		minutesTarget: data.console.chart_arm_minutes_target,
		coveragePct: data.console.chart_arm_coverage_pct
	});
	/** The chart-arm days inside the open window. The rule reads them and so do
	 * the rows behind the disclosure: a table under a control that ignored it
	 * would answer a question the reader did not ask, at a span nothing on the
	 * page states. */
	const chartsInWindow = $derived(data.charts.filter((day) => inWindow(day.date)));
	const arm = $derived(chartArm(chartsInWindow, thresholds, windowDays));
	/** Articles per published day, as a map, so the cost arithmetic reads it the
	 * same way the server did. */
	const articles = $derived(new Map(Object.entries(data.publishedItems)));
	const perArticle = $derived(siteCost(data.manifests, articles, viewport));
	/** How long the cap lasts at this window's two measured rates.
	 *
	 * The panel exists to answer this and had never said so. Both rates come off
	 * the same published days the chart above is drawn from, so the sentence and
	 * the picture cannot be read off two different windows.
	 */
	const horizon = $derived(
		publishingHorizon(data.band.size.bytes, perArticle, articles)
	);
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

	/** Three significant figures, the rule the band's own headroom prints by.
	 *
	 * The rate under this is a median whose spread is near a fifth of itself, so
	 * the trailing digits of a six-figure answer are noise and printing them
	 * claims an accuracy nothing measured (Rule #10). */
	function roughly(value: number): string {
		if (value <= 0) return '0';
		const scale = 10 ** Math.max(0, Math.floor(Math.log10(value)) - 2);
		return (Math.round(value / scale) * scale).toLocaleString('en-GB');
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
	 * visual planner was free, and printing a per-visual cost of infinity on a day
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

	<!-- Strip, band, control, in that order. Chrome above content is the one
	     ordering a reader never has to learn, and the band's worst fact links
	     into the strip. The control is last of the three because a control read
	     before any fact asks the operator to configure a page he has been told
	     nothing about - and it governs everything below it and nothing above. -->
	<ConsoleNav routes={data.routes} active="pipelines" />
	<ConsoleBand band={data.band} />
	<WindowControl days={windowDays} {presets} {monthsFor} busy={fetching} {ready} onChange={show} />

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
	     marker above it read one declaration: fewer minutes spent is better and
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
				<figcaption class="text-[0.75rem] text-text-tertiary">Runs that finished</figcaption>
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
			note="How long we can keep publishing. The 1 GB Pages cap is fixed, so what one more article costs is what sets the date we reach it. Bytes the committed payload tree gained on each published day, over the articles that day published. Over {windowDays} days. {sizeDelta}"
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
				{#if horizon}
					<!-- The horizon, and the one thing it cannot say about itself. The
					     cap is measured on the built site and this rate is measured on
					     the payload tree behind it, so the room is the most we have and
					     never the least. Both rates come off the same published days the
					     chart below is drawn from. -->
					<p class="mt-1 text-[0.8125rem] text-text-secondary" data-cost-horizon>
						At {bytes(perArticle.median ?? 0)} an article, the 1 GB cap has room for about {roughly(
							horizon.articles
						)} more. At a median of {grouped(Math.round(horizon.articlesPerDay))} articles a published
						day, that is about {horizon.years.toFixed(1)} years. The cap is measured on the built site,
						which is larger than the payload tree this rate came from, so that is the most room we have
						and not the least.
					</p>
				{/if}
				{#if data.glance.perArticleSvg}
					{#key windowDays}
						<Chart
							svg={data.glance.perArticleSvg}
							option={perArticle.option}
							width={data.console.chart_width}
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
							     upward, while the DOM keeps reading run 1 first.

							     Stretched to the row rather than sized by its squares. A day with
							     no run has no squares, so a column sized by its content is a
							     zero-height box: nothing to point at, and no room for the tint
							     that says which day the readout is on - which is the column a
							     reader most needs to see selected. -->
							<div
								class="flex flex-col-reverse justify-start self-stretch"
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

	<h2 class="console-h2">Sources we may ask, and what they yield</h2>

	{#if data.sourceHealth === null}
		<p class="mt-2 text-[0.9375rem] text-text-secondary" data-source-health="absent">
			No run has published a source census yet, so there is nothing to draw here. It fills on the
			next run that publishes a day.
		</p>
	{:else}
		<p
			class="mt-2 text-[0.9375rem] text-text"
			data-source-health-lead
			data-source-health-sources={data.sourceHealth.sources}
			data-source-health-withheld={data.sourceHealth.withheld}
		>
			{data.sourceHealth.sources} sources sit on the desks that publish, and {data.sourceHealth
				.withheld}
			{data.sourceHealth.withheld === 1 ? 'of them is' : 'of them are'} held back right now.
		</p>

		<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-window-exempt="source-health">
			Four separate facts, and none of them is averaged into the others: whether the site's own
			rules let us ask, whether the address is answering, whether a run has stopped asking it for
			good, and what it has published. A single score across the four would tell you something is
			wrong and nothing about what to do. The run decides all four from the private record and
			publishes them here, so this section renders a decision rather than making a second one.
			None of it follows the window control above - permission, answering and retirement are read
			over the whole record, and the publishing record has a fixed span of its own. This counts
			only the addresses a curator has left active, so it is a smaller list than the feeds below,
			which read every feed the ledger has ever carried.
		</p>

		<div class="console-table mt-3" data-source-health="states">
			<table class="w-full text-[0.8125rem]">
				<thead class="text-text-tertiary">
					<tr class="border-b border-rule">
						<th class="py-2 text-start font-normal">Fact</th>
						<th class="py-2 text-start font-normal">State</th>
						<th class="py-2 text-end font-normal">Sources</th>
						<th class="py-2 text-start font-normal">What it withholds</th>
					</tr>
				</thead>
				<tbody>
					{#each data.sourceHealth.permission as fact (fact.id)}
						<tr class="border-b border-rule" data-source-state="permission-{fact.id}">
							<td class="py-2">Permission</td>
							<td class="py-2">{fact.label}</td>
							<td class="py-2 text-end tabular-nums" data-source-state-count>{fact.count}</td>
							<td class="py-2 text-text-secondary">{fact.withheld ?? 'nothing'}</td>
						</tr>
					{/each}
					{#each data.sourceHealth.availability as fact (fact.id)}
						<tr class="border-b border-rule" data-source-state="availability-{fact.id}">
							<td class="py-2">Reading</td>
							<td class="py-2">{fact.label}</td>
							<td class="py-2 text-end tabular-nums" data-source-state-count>{fact.count}</td>
							<td class="py-2 text-text-secondary">{fact.withheld ?? 'nothing'}</td>
						</tr>
					{/each}
					<tr class="border-b border-rule" data-source-state="retirement-retired">
						<td class="py-2">Retirement</td>
						<td class="py-2">the server said the address is gone</td>
						<td class="py-2 text-end tabular-nums" data-source-state-count
							>{data.sourceHealth.retired}</td
						>
						<td class="py-2 text-text-secondary"
							>no run asks this address again until its configured address changes</td
						>
					</tr>
				</tbody>
			</table>
		</div>

		{#if data.sourceHealth.notes.length === 0}
			<p class="mt-3 text-[0.9375rem] text-text-secondary" data-source-health="clear">
				Every source is allowed to be asked and answering, so there is nothing to name.
			</p>
		{:else}
			<div
				class="console-table mt-3"
				data-source-health="notes"
				data-source-health-drawn={data.sourceHealth.notes.length}
			>
				<p class="feeds-note">
					The sources held back, loudest state first. Retirement and a refusal come before a rest,
					because a rest lifts itself and neither of those does. The two counts span the same
					complete days as the record below, and a dash means the source was offered nothing in
					that span.
				</p>
				<table class="w-full text-[0.8125rem]">
					<thead class="text-text-tertiary">
						<tr class="border-b border-rule">
							<th class="py-2 text-start font-normal">Source</th>
							<th class="py-2 text-start font-normal">Desk</th>
							<th class="py-2 text-start font-normal">What is holding it back</th>
							<th class="py-2 text-end font-normal">Offered</th>
							<th class="py-2 text-end font-normal">Published</th>
						</tr>
					</thead>
					<tbody>
						{#each data.sourceHealth.notes as note (note.sourceId)}
							<tr class="border-b border-rule" data-source-note={note.sourceId}>
								<td class="py-2"
									>{note.title}<span class="source-note-id" data-source-note-id>{note.sourceId}</span
									></td
								>
								<td class="py-2 text-text-secondary">{note.vertical}</td>
								<td class="py-2 text-text-secondary" data-source-note-withheld>{note.withheld}</td>
								<td class="py-2 text-end tabular-nums"
									>{note.opportunities === 0 ? '-' : grouped(note.opportunities)}</td
								>
								<td class="py-2 text-end tabular-nums"
									>{note.opportunities === 0 ? '-' : grouped(note.publications)}</td
								>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			{#if data.sourceHealth.hidden > 0}
				<p class="mt-3 text-[0.8125rem] text-text-tertiary" data-source-health-more>
					{data.sourceHealth.hidden} more {data.sourceHealth.hidden === 1 ? 'source is' : 'sources are'}
					held back, none by a louder state than the last row here.
				</p>
			{/if}
		{/if}

		<p
			class="mt-3 text-[0.9375rem] text-text"
			data-source-health-record={data.sourceHealth.record.readable ? 'measured' : 'short'}
			data-source-health-days={data.sourceHealth.record.completeDates}
		>
			{#if data.sourceHealth.record.completeDates === 0}
				No day has finished with a planned article on it, so there is no publishing record yet.
			{:else}
				Over {data.sourceHealth.record.completeDates}
				complete {data.sourceHealth.record.completeDates === 1 ? 'day' : 'days'}, {data
					.sourceHealth.record.firstDate} to {data.sourceHealth.record.lastDate}, these sources
				were offered {grouped(data.sourceHealth.record.opportunities)} addresses and published {grouped(
					data.sourceHealth.record.publications
				)}. {grouped(data.sourceHealth.record.sourceFailures)}
				of those addresses were lost to a failure the source itself owns.
				{#if !data.sourceHealth.record.readable}
					The record is under the {data.sourceHealth.record.minCompleteDays} complete days a yield
					judgement needs, so these are counts and not a rate.
				{/if}
			{/if}
		</p>

		<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-source-health-basis>
			An offer is one address planned on a day that has finished, counted once however many runs of
			that day tried it. Today is never counted: the run is still working, so its addresses have
			not all been attempted. A lost address is reported beside the two counts and never subtracted
			from either, so one lost article is counted once.
		</p>
	{/if}

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
			data-feed-ineligible={data.feedRecord.ineligible.length}
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
			{#if data.feedRecord.ineligible.length > 0}
				{data.feedRecord.ineligible.length} more {data.feedRecord.ineligible.length === 1
					? 'feed has'
					: 'feeds have'} never been read at all - a rest or the site's own rules held
				{data.feedRecord.ineligible.length === 1 ? 'it' : 'them'} back on every run - so
				{data.feedRecord.ineligible.length === 1 ? 'it is' : 'they are'} in neither count.
			{/if}
		</p>

		{#if data.feedRecord.ineligible.length > 0}
			<details class="console-disclosure mt-2" data-feed-ineligible-list>
				<summary class="console-summary" data-feed-ineligible-toggle>
					Name the {data.feedRecord.ineligible.length} the pipeline has never read
				</summary>
				<p class="mt-2 text-[0.8125rem] text-text-tertiary" data-feed-ineligible-note>
					A source honouring its own <code>robots.txt</code> has not failed, and neither has one the
					pipeline was resting. Neither has delivered anything either, so counting them among the
					feeds that never failed reported a source we have never read as a reliable one.
				</p>
				<ul class="feed-clean-names" data-feed-ineligible-names>
					{#each data.feedRecord.ineligible as feedId (feedId)}
						<li data-feed-ineligible-name={feedId}>{feedId}</li>
					{/each}
				</ul>
			</details>
		{/if}

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

	<!-- Reading and writing are drawn apart and never pooled. Measured over the
	     committed projection they cost different amounts per token, and an
	     operator acts on them differently: the article's length moves the first
	     and the summary's length moves the second. One "model seconds" chart
	     would hide which of the two moved. -->
	<div data-windowed="item-cost" data-window-days={cost.days}>
		<h2 class="console-h2">What one item cost the model</h2>

		<p class="mt-2 text-[0.9375rem] text-text-secondary" data-item-cost-lead data-item-cost-rows={cost.rows}>
			{#if cost.rows === 0}
				No item is on the published record for these {cost.days} days, so there is nothing here to
				measure yet. It fills as runs publish.
			{:else}
				{grouped(cost.timed)} of the {grouped(cost.rows)} items in these {cost.days} days were
				timed by the model itself. The rest failed before it saw them, or were kept without ever
				being sent to it.
			{/if}
			Panning does not move these days: they always end on the newest day the ledger holds.
		</p>

		{#if cost.reading === null && cost.writing === null}
			{#if cost.rows > 0}
				<p class="mt-4 text-[0.9375rem] text-text-secondary" data-item-cost="unmeasured">
					Nothing recorded a model clock in these {cost.days} days. This fills as runs publish.
				</p>
			{/if}
		{:else}
			{#if cost.reading === null}
				<p class="mt-4 text-[0.9375rem] text-text-secondary" data-item-cost-reading="empty">
					Nothing timed the reading of a prompt in these {cost.days} days.
				</p>
			{:else if cost.reading.n < data.console.min_attempts_for_rate}
				<p class="mt-4 text-[0.9375rem] text-text-secondary" data-item-cost-reading="thin">
					{grouped(cost.reading.n)}
					{cost.reading.n === 1 ? 'prompt was' : 'prompts were'} timed in these {cost.days} days. Too
					few to give a middle or a slowest one in twenty - {data.console.min_attempts_for_rate}
					needed. The fastest took {asSeconds(cost.reading.fastest)} and the slowest {asSeconds(
						cost.reading.slowest
					)}.
				</p>
			{:else}
				<Panel
					title="Reading the prompt"
					note="How long the model spent taking in one article and its instructions, before it wrote a word. This is what the article's length costs."
					wide
				>
					<TimeHistogram
						times={cost.reading}
						name="reading-the-prompt"
						subject="Time to read one prompt"
						verb="read"
						noun="prompt"
						nouns="prompts"
						noRuleReason="one distribution over the window, with no day axis to place a boundary on"
						width={data.console.chart_width}
						height={data.console.chart_height}
						readoutMaxShare={data.chart.readout_max_share}
					/>
					<p class="mt-2 text-[0.8125rem] text-text-tertiary" data-item-cost-reading="readout">
						Half of the {grouped(cost.reading.n)} prompts were read inside
						<span data-item-cost-reading="median">{asSeconds(cost.reading.median)}</span>, and one
						in twenty took longer than
						<span data-item-cost-reading="p95">{asSeconds(cost.reading.p95)}</span>. Over
						{cost.timedDays} of these {cost.days} days.
					</p>
				</Panel>
			{/if}

			{#if cost.writing === null}
				<p class="mt-4 text-[0.9375rem] text-text-secondary" data-item-cost-writing="empty">
					Nothing timed the writing of a summary in these {cost.days} days.
				</p>
			{:else if cost.writing.n < data.console.min_attempts_for_rate}
				<p class="mt-4 text-[0.9375rem] text-text-secondary" data-item-cost-writing="thin">
					{grouped(cost.writing.n)}
					{cost.writing.n === 1 ? 'summary was' : 'summaries were'} timed in these {cost.days} days.
					Too few to give a middle or a slowest one in twenty - {data.console.min_attempts_for_rate}
					needed. The fastest took {asSeconds(cost.writing.fastest)} and the slowest {asSeconds(
						cost.writing.slowest
					)}.
				</p>
			{:else}
				<Panel
					title="Writing the summary"
					note="How long it spent writing the summary itself, after it had read the whole prompt. This is what the summary's length costs."
					wide
				>
					<TimeHistogram
						times={cost.writing}
						name="writing-the-summary"
						subject="Time to write one summary"
						verb="written"
						noRuleReason="one distribution over the window, with no day axis to place a boundary on"
						width={data.console.chart_width}
						height={data.console.chart_height}
						readoutMaxShare={data.chart.readout_max_share}
					/>
					<p class="mt-2 text-[0.8125rem] text-text-tertiary" data-item-cost-writing="readout">
						Half of the {grouped(cost.writing.n)} summaries were written inside
						<span data-item-cost-writing="median">{asSeconds(cost.writing.median)}</span>, and one
						in twenty took longer than
						<span data-item-cost-writing="p95">{asSeconds(cost.writing.p95)}</span>. Over
						{cost.timedDays} of these {cost.days} days.
					</p>
				</Panel>
			{/if}

			{#if cost.msPerReadToken !== null && cost.msPerWrittenToken !== null}
				<p class="mt-3 text-[0.9375rem] text-text-secondary" data-item-cost-rates>
					A prompt token costs
					<span
						class="tabular-nums"
						data-item-cost-ms-per-read-token={Math.round(cost.msPerReadToken)}
						>{grouped(Math.round(cost.msPerReadToken))} ms</span
					>
					to read and a written one costs
					<span
						class="tabular-nums"
						data-item-cost-ms-per-written-token={Math.round(cost.msPerWrittenToken)}
						>{grouped(Math.round(cost.msPerWrittenToken))} ms</span
					>
					to write, so a written token costs
					<strong data-item-cost-write-ratio={(cost.writeCostRatio ?? 0).toFixed(1)}
						>{(cost.writeCostRatio ?? 0).toFixed(1)}x</strong
					>
					a read one.
					{#if (cost.writeCostRatio ?? 0) >= 1}
						Cutting a hundred tokens from the summary saves more time than cutting a hundred from
						the article.
					{:else}
						Cutting a hundred tokens from the article saves more time than cutting a hundred from
						the summary.
					{/if}
				</p>
			{/if}

			{#if cost.counted === 0}
				<p class="mt-4 text-[0.9375rem] text-text-secondary" data-item-cost-cache="unmeasured">
					No item in these {cost.days} days recorded a token count, so nothing here can say what
					the prompt cost or what was already in memory.
				</p>
			{:else}
				<Panel
					title="How much of each prompt was already in memory"
					note="Prompt tokens the model had to read, against the ones it did not - the instructions in front of every article stay in memory between items."
				>
					<div
						class="cost-track"
						role="img"
						data-item-cost-read-tokens={cost.readTokens}
						data-item-cost-reused-tokens={cost.reusedTokens}
						data-item-cost-reused-pct={cost.reusedPct}
						aria-label="{grouped(cost.readTokens)} prompt tokens were read and {grouped(
							cost.reusedTokens
						)} were already in memory, which is {cost.reusedPct} percent of the {grouped(
							cost.readTokens + cost.reusedTokens
						)} the window needed."
					>
						<span
							class="cost-seg read"
							style="inline-size: {100 - (cost.reusedPct ?? 0)}%"
						></span>
						<span class="cost-seg held" style="inline-size: {cost.reusedPct ?? 0}%"></span>
					</div>
					<p class="cost-key" data-item-cost-key>
						<span class="cost-swatch read"></span>read {grouped(cost.readTokens)} tokens
						<span class="cost-swatch held"></span>already in memory {grouped(cost.reusedTokens)} tokens
						({pct(cost.reusedPct)})
					</p>

					<div class="cost-figures">
						<p class="cost-figure">
							<span class="cost-figure-value tabular-nums" data-item-cost-prompt-tokens={cost.promptTokens}
								>{count(cost.promptTokens)}</span
							>
							<span class="cost-figure-label"
								>tokens in the middle prompt, over {grouped(cost.counted)} items</span
							>
						</p>
						<p class="cost-figure">
							<span
								class="cost-figure-value tabular-nums"
								data-item-cost-written-tokens={cost.writtenTokens}>{count(cost.writtenTokens)}</span
							>
							<span class="cost-figure-label"
								>tokens in the middle summary, over {grouped(cost.counted)} items</span
							>
						</p>
						<p class="cost-figure">
							<span
								class="cost-figure-value tabular-nums"
								data-item-cost-item-reused-pct={cost.itemReusedPct}>{pct(cost.itemReusedPct)}</span
							>
							<span class="cost-figure-label"
								>of the middle item's prompt was already in memory</span
							>
						</p>
						<p class="cost-figure">
							<span class="cost-figure-value tabular-nums" data-item-cost-read-whole={cost.readWhole}
								>{grouped(cost.readWhole)}</span
							>
							<span class="cost-figure-label"
								>items of {grouped(cost.counted)} were read whole, with nothing held over</span
							>
						</p>
					</div>

					<!-- The share is printed and never plotted as a trend, and this is why.
					     The held part barely moves; the prompt does. A falling line here
					     would read as the cache getting worse when it means the articles
					     got longer, and that is the one wrong conclusion this panel could
					     cause somebody to act on. -->
					<p class="mt-3 text-[0.8125rem] text-text-tertiary" data-item-cost-share-note>
						The share follows the article, not the memory. The held part hardly changes - the
						middle item kept {count(cost.reusedMedian)} tokens and the largest kept {count(
							cost.reusedWidest
						)} - so a longer article reads as a smaller share while exactly as much is held. Read
						the token counts above, not the direction of the percentage.
					</p>
				</Panel>
			{/if}
		{/if}
	</div>

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
			{#if data.flowSvg}
				{@const flow = chartFlow(data.charts)}
				<!-- Two shapes, one flow. The diagram needs 700px of viewport before its
				     labels stop overlapping (measured 2026-09-01), and a phone column
				     cannot give it that at any font size - so below the page's own
				     stacking breakpoint the same numbers are a stepped list, which is a
				     shape a 360px column can hold. Both are built from one `chartFlow`
				     call, so they cannot report two different flows. -->
				<div class="panel mt-4" data-flow="chart">
					<Chart
						svg={data.flowSvg}
						option={flow.option}
						width={data.console.chart_width}
						height={FLOW_HEIGHT}
						label="Where items go between the visual planner reaching one and a visual being published, across the window. Every drop leaves the flow as its own branch, and a branch is as wide as the number of items in it."
						noReadout="a flow between stages, so there is no column two branches share"
					/>
				</div>
				<ol class="panel flow-steps mt-4" data-flow-steps={flow.steps.length}>
					{#each flow.steps as step (step.label)}
						<li class="flow-step" data-flow-step={step.label}>
							<p class="flow-step-head">
								<span class="flow-step-swatch" style="background: var({step.token})"></span>
								<span class="grow">{step.label}</span>
								<span class="tabular-nums" data-flow-step-value={step.value}
									>{grouped(step.value)} ({step.share}%)</span
								>
							</p>
							{#if step.lost}
								<p class="flow-step-lost" data-flow-lost={step.lost.label}>
									<span class="grow">{step.lost.label}</span>
									<span class="tabular-nums" data-flow-lost-value={step.lost.value}
										>{grouped(step.lost.value)} ({step.lost.share}%)</span
									>
								</p>
							{/if}
						</li>
					{/each}
				</ol>
			{:else if data.flowNote}
				<p class="panel mt-4 text-[0.8125rem] text-text-tertiary" data-flow="none">{data.flowNote}</p>
			{/if}
			<!-- A native disclosure, not a button and a block: the console is complete
			     before any script runs, and a button would leave the rows unreachable
			     with JavaScript off. It ends the section it answers rather than hanging
			     below it, and it follows the control above it like everything else in
			     here. -->
			<details
				class="console-disclosure mt-4"
				data-charts="daily"
				data-daily-figures="pipelines"
				data-daily-rows={chartsInWindow.length}
			>
				<summary class="console-summary" data-charts-toggle
					>Show these figures day by day, over these {windowDays} days</summary
				>
				<p class="mt-3 text-[0.8125rem] text-text-tertiary">
					One row per day in the open window, newest first. Reached is every item the visual planner
					looked at, asked the model is the part it sent a request for, visuals drafted is what the
					model returned, and visuals published is what survived the checks after it. A dash means no
					minutes are on record, so there is no rate to divide. Zero reached means nothing committed
					says what the visual planner did: it never ran, or its manifest is older than these counts.
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
							{#each chartsInWindow as day (day.date)}
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
										>{minutes(day.plannerMinutes)}</td
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
		</div>
	{/if}
</section>

<style>
/* Route-specific only. The shapes every console route shares - the h2, the
   framed table, the disclosure, the carry sentence - are in app.css, so three
   routes cannot drift into three identities that merely agree today. */

/* One track, two segments, the same shape the Hardware route splits reading
   against writing with. Absolute tokens set the geometry and the share is
   printed beside it: a share over a prompt that keeps changing length is not
   the question this panel answers. */
.cost-track {
display: flex;
block-size: 0.75rem;
overflow: hidden;
border-radius: var(--radius-sm);
background: var(--color-surface-sunken);
}

.cost-seg {
display: block;
block-size: 100%;
}

.cost-seg.read {
background: var(--chart-1);
}

.cost-seg.held {
background: var(--chart-3);
}

.cost-key {
display: flex;
flex-wrap: wrap;
align-items: center;
gap: var(--space-2);
margin: var(--space-2) 0 0;
font-size: var(--text-xs);
line-height: var(--leading-xs);
color: var(--color-text-tertiary);
}

.cost-swatch {
display: inline-block;
inline-size: 0.625rem;
block-size: 0.625rem;
border-radius: var(--radius-sm);
}

.cost-swatch.read {
background: var(--chart-1);
}

.cost-swatch.held {
background: var(--chart-3);
}

/* Four figures on one auto-fit grid, the same shape the measure cards take.
   Each carries its own denominator, because the two clocks and the token
   counts answer for different numbers of items. */
.cost-figures {
display: grid;
grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
gap: var(--space-4);
margin-block-start: var(--space-4);
}

.cost-figure {
display: flex;
flex-direction: column;
gap: var(--space-1);
margin: 0;
min-inline-size: 0;
}

.cost-figure-value {
font-size: var(--text-xl);
font-weight: 600;
line-height: var(--leading-sm);
color: var(--color-text);
}

.cost-figure-label {
font-size: var(--text-xs);
line-height: var(--leading-xs);
color: var(--color-text-tertiary);
}

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

/* The movement pair, never the confidence ramp: a window in which the planner
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

/* Two feeds in this repository are both titled "Anthropic", and the thing an
   operator edits is one configured address. Without the id the table drew two
   identical rows and neither said which one to go and fix. */
.source-note-id {
display: block;
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

/* The chart-arm flow, as a stepped list. It replaces the diagram below the
   page's own stacking breakpoint and never sits beside it: two shapes of one
   flow on one screen is two answers to one question. */
.flow-steps {
display: none;
margin-block-start: var(--space-4);
padding: var(--space-4);
list-style: none;
}

.flow-step + .flow-step {
margin-block-start: var(--space-3);
padding-block-start: var(--space-3);
border-block-start: 1px solid var(--color-rule);
}

.flow-step-head,
.flow-step-lost {
display: flex;
align-items: baseline;
gap: var(--space-2);
margin: 0;
}

.flow-step-head {
font-size: var(--text-sm);
color: var(--color-text);
}

/* Indented under the stage it left, so a branch reads as leaving that stage
   rather than as a fifth one. */
.flow-step-lost {
margin-block-start: var(--space-1);
padding-inline-start: calc(10px + var(--space-2));
font-size: var(--text-xs);
color: var(--color-text-tertiary);
}

.flow-step-swatch {
inline-size: 10px;
block-size: 10px;
flex-shrink: 0;
border-radius: 2px;
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

/* Measured 2026-09-01 in Chromium on the built console: the flow's labels stop
   colliding at 700px of viewport and collide at every width below it - three
   pairs at 390, worst 56.2px. The list carries the same numbers in a shape a
   360px column can hold. 48rem is the breakpoint the rest of this page already
   stacks at, and it clears the measurement by 68px. */
[data-flow='chart'] {
display: none;
}

.flow-steps {
display: block;
}
}
</style>
