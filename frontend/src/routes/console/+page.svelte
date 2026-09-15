<script lang="ts">
	/** The operator's page, and the first of the console's five routes.
	 *
	 * It answers one question and refuses the others: did the pipeline work. Did
	 * the runs finish, how long each stage took, what the truncation cap is
	 * costing, and whether the chart drawing earns its minutes. Who supplied the day
	 * is on `/console/voices/` - every feed and source panel left this page on
	 * 2026-09-14 and none of them stayed behind. What the model wrote is on
	 * `/console/model/` and the hardware under it is on `/console/machine/`.
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
	import { axisLabels, cellFor, centreOffset, type LabelAlign } from '$lib/charts/run-history';
	import {
		datesIn,
		failureSeries,
		grouped,
		parseTelemetryCsv,
		rowsInWindow,
		timeSplit,
		type TelemetryRow
	} from '$lib/charts/series';
	import {
		daysInWindow,
		defaultWindow,
		panWindow,
		stepPreset,
		windowOfDays,
		type TimeWindow
	} from '$lib/charts/viewport';
	import {
		applyShard,
		heldMonths,
		holdRows,
		monthCeiling,
		monthsToLoad,
		seedHold,
		type TelemetryHold
	} from '$lib/charts/telemetry-hold';
	import {
		missingSentence,
		monthOutcomes,
		monthsIn,
		panelState,
		quietSentence,
		retryLabel,
		unreachableSentence,
		wideningPreset
	} from '$lib/console/waiting';
	import Reserved from '$lib/components/Reserved.svelte';
	import StageTimings from '$lib/components/StageTimings.svelte';
	import TimeHistogram from '$lib/components/TimeHistogram.svelte';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
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
		chartRule,
		failureMix,
		failureMixColumns,
		publishedSkyline,
		publishingHorizon,
		runHealth,
		siteCost,
		sizeGain,
		timeSplitChart,
		timeSplitColumns,
		type Skyline,
		type SkylineBar
	} from '$lib/charts/glance';
	import type { StackShape } from '$lib/charts/stacked';
	import ShapeSwitch from '$lib/components/ShapeSwitch.svelte';
	import Sparkline from '$lib/components/Sparkline.svelte';
	import Viewport from '$lib/components/Viewport.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import type { Health } from './+page.server';

	let { data } = $props();

	/** Where the operator's choice of window is kept between visits. It is the
	 * same key all three console routes read, so the span follows him across the
	 * strip rather than resetting on every click. */
	const WINDOW_KEY = 'idhazh:console-window';

	const presets = $derived(data.console.window_presets);

	// svelte-ignore state_referenced_locally
	let windowDays = $state(data.console.default_window_days);
	/** Every day the pipeline published, newest last.
	 *
	 * The window anchors on this rather than on the telemetry, which no longer
	 * crosses. It is the same set of days: `charts` holds one entry per published
	 * day and already costs the page 2.5 KB, where the rows it would have been
	 * taken from cost 3,334 KB (measured 2026-09-09, Intel Core i7-1265U).
	 */
	// svelte-ignore state_referenced_locally
	const publishedDates = data.charts.map((day) => day.date).sort();
	/** The window the page opens on, computed once so the first viewport and the
	 * first fetch agree on which months are wanted. */
	// svelte-ignore state_referenced_locally
	const opening = defaultWindow(publishedDates, data.today, data.console);
	/** The telemetry this session holds, as revision-owned month shards.
	 *
	 * **It starts empty and every row in it arrives by fetch.** The server used
	 * to inline one window of rows here, which was 3,334 KB of a 3,789 KB
	 * document - 88 percent of everything an operator downloaded to open the
	 * console, for a panel most visits never scroll to. The month fetch that
	 * already existed for widening the window now loads the page as well.
	 */
	let hold = $state<TelemetryHold>(seedHold([], null));
	/** Every held row, and the array every chart reads. Derived from the hold,
	 * so a shard that arrives - or a correction that retracts a row - redraws
	 * with none of the whole-cache rebuild the old merge did on every fetch. */
	const rows = $derived(holdRows(hold));
	/** How many fetched months to keep at most: the months the widest window can
	 * touch, so the open window is always in hand and memory does not climb with
	 * a long session's panning. */
	// svelte-ignore state_referenced_locally
	const monthCap = monthCeiling(data.console.max_window_days);
	/** Months a fetch is in flight for, so a second widen started before the
	 * first settles does not ask for the same file twice. Not reactive: nothing
	 * on the page reads it, and `flying` below is what drives the busy note. */
	const pending = new Set<string>();
	// svelte-ignore state_referenced_locally
	let viewport = $state<TimeWindow>(opening);
	/** The months whose files are in the air. A list rather than a flag: a pan
	 * can start a second fetch while the first is still running, and a flag would
	 * clear the busy state on the first one to finish. The names are here because
	 * a panel that reports a failed month has to know which month it was. */
	let flying = $state<string[]>([]);
	/** Months that were asked for and did not come back.
	 *
	 * **This list is the difference between a broken fetch and a quiet
	 * pipeline.** Without it both draw an unmarked gap, which is the one pair of
	 * facts this page exists to tell apart (Susan, plan row #12). */
	let refused = $state<string[]>([]);
	/** False until a browser has run this page. The control cannot do anything
	 * before that, so it says so rather than pretending. */
	let ready = $state(false);
	/** True once a wait has run past `console.shimmer_after_ms`.
	 *
	 * One flag for the whole surface, and that is what makes the sweep one
	 * timeline: every reserved block starts its animation in the frame this
	 * turns on, so twelve blocks read as one page waiting rather than as twelve
	 * broken things. A fetch that lands inside the delay never animates at all.
	 */
	let shimmer = $state(false);

	const fetching = $derived(flying.length > 0);

	/** The choice is read on mount and never during prerender, so first paint is
	 * always the window the server drew and the control always agrees with it.
	 *
	 * The first fetch starts here too. Nothing on this page holds a telemetry row
	 * before a browser runs it, so opening the page and widening the window are
	 * the same act now, and the panels that need rows say so until they land.
	 */
	onMount(() => {
		ready = true;
		if (typeof localStorage !== 'undefined') {
			const stored = Number(localStorage.getItem(WINDOW_KEY));
			if (presets.includes(stored) && stored !== windowDays) {
				show(stored);
				return;
			}
		}
		void loadVisibleMonths();
	});

	function merge(month: string, next: TelemetryRow[]) {
		hold = applyShard(hold, month, next, monthCap);
	}

	/** Fetch the month files the window reaches into and does not already hold.
	 *
	 * This is how the page loads and how it widens, in one path. Opening it holds
	 * nothing, so the first call asks for the months the default window touches -
	 * two of them and never more, whatever the archive has grown to. Widening
	 * re-uses the same path: the rows already paid for stay in hand and only the
	 * months past them cost anything. A month is marked in hand only when its
	 * shard arrives, so a fetch that fails leaves it unfetched for a later widen
	 * to fill rather than marking it done and hiding the gap for the rest of the
	 * session.
	 *
	 * The months come from the band, which the layout has already fetched. A page
	 * cannot ask for a month until it knows which months exist, so a list of its
	 * own would be one more wait before the first row (Carmack, 2026-09-08).
	 */
	async function loadVisibleMonths(only: readonly string[] | null = null) {
		const wanted = (only ?? monthsToLoad(hold, viewport, data.months)).filter(
			(month) => !pending.has(month)
		);
		if (wanted.length === 0) return;
		for (const month of wanted) pending.add(month);
		// A month being tried again is no longer refused. Clearing it here rather
		// than on the answer means the panel drops its warning the moment the
		// retry starts, which is what a pressed button owes the person who
		// pressed it.
		refused = refused.filter((month) => !wanted.includes(month));
		flying = [...flying, ...wanted];
		for (const month of wanted) {
			try {
				const response = await fetch(`${base}/telemetry/${month}.csv`);
				if (response.ok) merge(month, parseTelemetryCsv(await response.text()));
				else {
					refused = [...refused, month];
					console.warn(`telemetry ${month} unavailable; showing a gap`);
				}
			} catch (error) {
				refused = [...refused, month];
				console.warn(`telemetry ${month} could not be read; showing a gap`, error);
			} finally {
				pending.delete(month);
				flying = flying.filter((name) => name !== month);
			}
		}
	}

	/** What became of every month the open window reaches into.
	 *
	 * The band's `months` is the list of months a shard exists for, so a month
	 * absent from it was never written and is a real gap rather than a failure.
	 */
	const outcomes = $derived(
		monthOutcomes({
			window: viewport,
			published: data.months,
			held: heldMonths(hold),
			loading: flying,
			unreachable: refused
		})
	);
	const rowsInView = $derived(rowsInWindow(rows, viewport));
	/** Which of the five states the fetched panels are in.
	 *
	 * `ready` until a browser has run, and that is not a lie - it is what the
	 * document is. Nothing has been asked for yet, so nothing is late, and the
	 * panels show the empty states they have always shown. The `<noscript>` line
	 * in the console layout is what tells a reader with no script that those
	 * panels draw rows a browser fetches.
	 */
	const telemetryState = $derived(
		ready ? panelState(outcomes, rowsInView.length) : ('ready' as const)
	);
	const missingMonths = $derived(monthsIn(outcomes, 'missing'));
	const refusedMonths = $derived(monthsIn(outcomes, 'unreachable'));
	/** The narrowest preset that reaches a month with rows in it. Named in the
	 * quiet sentence, because widening is the only move an empty window offers. */
	const widen = $derived(
		wideningPreset(windowDays, presets, data.months, (days) =>
			windowOfDays(publishedDates, data.today, days, data.console.today_anchor)
		)
	);
	/** What every waiting panel says. One sentence per state, written once, so
	 * two panels in the same state cannot word it differently. */
	const stateSentence = $derived.by(() => {
		if (telemetryState === 'quiet') return quietSentence(windowDays, widen);
		if (telemetryState === 'missing') return missingSentence(missingMonths);
		if (telemetryState === 'unreachable') {
			return unreachableSentence(refusedMonths, datesIn(rowsInView).length);
		}
		return '';
	});
	const retryAction = $derived(
		telemetryState === 'unreachable' ? retryLabel(refusedMonths) : null
	);

	/** Ask again for the months that did not come back, and nothing else.
	 *
	 * Scoped to the failure rather than to the page: a retry that re-fetched the
	 * whole window would spend an operator's connection on months already in
	 * hand, and would blank panels that are answering correctly.
	 */
	function retry() {
		void loadVisibleMonths([...refusedMonths]);
	}

	/** The shimmer starts late and stops the moment the last file lands.
	 *
	 * `console.shimmer_after_ms` is what a wait has to outlast before it is worth
	 * drawing as one. Below it a reserved block is simply still, which is the
	 * right answer for a fetch that is over before the eye finds the box.
	 */
	$effect(() => {
		if (!fetching) {
			shimmer = false;
			return;
		}
		const timer = setTimeout(() => (shimmer = true), data.console.shimmer_after_ms);
		return () => clearTimeout(timer);
	});

	/** Set the span every windowed section reads.
	 *
	 * The window re-anchors on the newest day rather than keeping where a pan
	 * left it, because "the last 30 days" is the question the preset asks.
	 *
	 * It anchors on the published days and not on the rows in hand. Anchoring on
	 * the rows would put the window wherever the fetch had got to, so the first
	 * widen after opening the page would land on a different span from the same
	 * widen a second later.
	 */
	function show(days: number, remember = true) {
		windowDays = days;
		viewport = windowOfDays(publishedDates, data.today, days, data.console.today_anchor);
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
		return monthsToLoad(
			hold,
			windowOfDays(publishedDates, data.today, days, data.console.today_anchor),
			data.months
		).length;
	}

	const inWindow = $derived(
		(date: string) => date >= viewport.start && date <= viewport.end
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
	/** The chart drawing's own rule, read from config rather than written into a
	 * component. An operator moves a threshold in `config/appearance.json`. */
	const thresholds = $derived({
		ruleDays: data.console.chart_rule_days,
		minutesTarget: data.console.chart_minutes_target,
		coveragePct: data.console.chart_coverage_pct
	});
	/** The chart-drawing days inside the open window. The rule reads them and so do
	 * the rows behind the disclosure: a table under a control that ignored it
	 * would answer a question the reader did not ask, at a span nothing on the
	 * page states. */
	const chartsInWindow = $derived(data.charts.filter((day) => inWindow(day.date)));
	const rule = $derived(chartRule(chartsInWindow, thresholds, windowDays));
	/** What the extractor found over the open window, reduced once per span on the
	 * server. The browser picks the open one; nothing re-reads a record to change
	 * window. */
	const extraction = $derived(
		data.extractionByWindow.find((entry) => entry.days === windowDays) ??
			data.extractionByWindow[0]
	);
	/** The three classes, as rows. `Not yet classified` is named rather than
	 * folded into `narrative`: an article carrying two figures is not an article
	 * carrying none, and only one of those two is a gap in our own questions. */
	const extractionClasses = $derived(
		[
			{ id: 'chartable', label: 'Enough figures of one kind to draw', count: extraction.chartable },
			{
				id: 'unclassified',
				label: 'Figures, but not enough of one kind',
				count: extraction.unclassified
			},
			{ id: 'narrative', label: 'No figures at all', count: extraction.narrative }
		].map((row) => ({
			...row,
			share:
				extraction.spanIntegrityPass <= 0
					? null
					: Math.round((row.count / extraction.spanIntegrityPass) * 100)
		}))
	);
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
	// Built once from the committed grid, not per pan. `data.grid` holds every
	// recorded day and never changes in the browser, so rebuilding this index on
	// every window move re-read the whole history to answer a windowed question
	// (finding 109). The window walk below is output-sized: one lookup a day in
	// view.
	const gridByDate = $derived(new Map(data.grid.map((day) => [day.date, day.squares])));
	const windowGrid = $derived(
		daysInWindow(viewport).map((date) => ({ date, squares: gridByDate.get(date) ?? [] }))
	);
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
	 * claims an accuracy nothing measured (Guardrail #10). */
	function roughly(value: number): string {
		if (value <= 0) return '0';
		const scale = 10 ** Math.max(0, Math.floor(Math.log10(value)) - 2);
		return (Math.round(value / scale) * scale).toLocaleString('en-GB');
	}

	/** The window the rows in hand cover. Derived from the rows themselves rather
	 * than passed in, so the mix chart and the strip under it can never be drawn
	 * over two different spans. */
	function failureSeriesFor(rows: TelemetryRow[]) {
		const dates = datesIn(rows);
		if (dates.length === 0) return [];
		return failureSeries(rows, { start: dates[0], end: dates[dates.length - 1] });
	}

	/** The stage failure series the mix chart and its strip both read. One array,
	 * so the band a reader hovers and the number the strip prints are the same
	 * measurement rather than two that happen to agree today.
	 *
	 * It reads the hold, so it is empty until the first month shard lands and
	 * fills as each one does. The panel says which of those two it is in.
	 */
	const mixSeries = $derived(failureSeriesFor(rows));
	/** Where the time went, over the same span the mix chart reads and for the
	 * same reason: derived from the rows in hand, so the two panels can never be
	 * drawn over different days.
	 *
	 * Trimmed at both ENDS to the days that timed an item, and never in the
	 * middle. A run before the item clock was published carries no
	 * `item_total_ms` at all, so leading and trailing columns of eight zeroes
	 * would say the item took no time rather than that nothing timed it. A gap
	 * inside the span is kept: closing it up would slide every later day one
	 * column left and draw the hole as if it were the next day along.
	 */
	const timeDays = $derived.by(() => {
		const dates = datesIn(rows);
		if (dates.length === 0) return [];
		const days = timeSplit(rows, { start: dates[0], end: dates[dates.length - 1] });
		const first = days.findIndex((day) => day.items > 0);
		if (first === -1) return [];
		const last = days.findLastIndex((day) => day.items > 0);
		return days.slice(first, last + 1);
	});
	/** The server drew stacked, like the mix chart. Picking `Lines` redraws the
	 * identical values. */
	let timeShape = $state<StackShape>('bars');
	/** The share of planned items that finished, drawn from the manifests the
	 * page already carries. Built here rather than on the server: the shape is
	 * the engine's and the numbers are two, so drawing it at build time put a
	 * finished picture in the document to say what one sentence says. */
	const runsChart = $derived(runHealth(data.manifests));
	/** Where items go between the planner reaching one and a visual publishing.
	 * One call, so the diagram and the stepped list beside it cannot report two
	 * different flows. */
	const flow = $derived(chartFlow(data.charts));
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

<!-- The title, the strip and the band are the shell and live in `+layout.svelte`.
     What is left here is the route's own panels, and the control that governs
     them - it is last of the chrome because a control read before any fact asks
     the operator to configure a page he has been told nothing about.

     `data-telemetry-rows` is how anything outside this page knows whether the
     rows it draws from have landed. The page holds none at first paint and
     fills by fetch, so a check that read a panel the moment the document
     arrived would be reading the empty state and calling it the answer.

     `data-shimmer` is the one switch every reserved block on this page reads,
     and having exactly one is what puts them all on one timeline (app.css). -->
<div
	data-console-panels="pipelines"
	data-telemetry-rows={rows.length}
	data-telemetry-fetching={fetching ? 'yes' : 'no'}
	data-telemetry-state={telemetryState}
	data-shimmer={shimmer ? 'on' : 'off'}
>
	<WindowControl days={windowDays} {presets} {monthsFor} busy={fetching} {ready} onChange={show} />

	{#if stateSentence !== ''}
		<!-- Said once, above every panel, and beside the control that governs the
		     window. Every panel below is empty for the same reason, so a copy of
		     this in each of them would be one fact repeated a dozen times - and each
		     panel already has a better sentence about its OWN emptiness than this
		     one. What no panel can say for itself is which of the three nothings
		     this is, and that is the whole job of this line. -->
		<p
			class="console-standing"
			data-console-standing={telemetryState}
			data-tone={telemetryState === 'unreachable' ? 'warn' : 'neutral'}
		>
			{stateSentence}
			{#if retryAction !== null}
				<button type="button" class="standing-retry" data-console-retry onclick={retry}
					>{retryAction}</button
				>
			{/if}
		</p>
	{/if}

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
			aria-label="{noun} each day over {windowDays} days, {grouped(strip.total)} over the window, {grouped(
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

	<!-- Which way a chart-drawing figure has moved across the window it draws.

	     The polarity comes off the bar's own marks, so the delta and the target
	     marker above it read one declaration: fewer minutes spent is better and
	     a wider chart share is better, and neither is decided here. -->
	{#snippet ruleMove(change: number | null, sense: TargetSense, figure: string)}
		{#if change !== null}
			{@const verdict = movementVerdict(change, sense)}
			<p class="rule-move" data-rule-move={figure}>
				<span
					class="rule-move-value"
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
		{#if !runsChart.empty}
			<figure class="panel" data-glance-chart="runs">
				<figcaption class="text-[0.75rem] text-text-tertiary">Runs that finished</figcaption>
				<Chart
					svg=""
					option={runsChart.option}
					width={260}
					height={200}
					label="Share of planned items that finished, against those that failed"
					noReadout="two shares of one total, and each share carries its own label"
					pending="{runsChart.share === null
						? 'No run is on record.'
						: `${Math.round(runsChart.share * 100)}% of ${grouped(runsChart.total)} planned items finished.`} The shape is drawn once the engine loads."
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
				<Chart
					svg=""
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
					pending="The day-by-day shape is drawn once the engine loads. Every value is in the list below it."
				/>
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

	<!-- No note. The heading names the subject and the strip under the chart
	     prints every stage at the hovered day, so a sentence restating the
	     encoding said what the shape already says - and said it wrongly the
	     moment the switch below drew lines. It survives verbatim in the chart's
	     accessible description, so nobody loses it. -->
	<Panel title="What is failing, by stage">
		<!-- The box is the same height whether it is waiting, empty, gapped or
		     full, so this panel and everything under it stay where they were
		     drawn. Four different nothings, and the panel says which one it is:
		     before this row a broken fetch and a clean window drew the same
		     unmarked gap. -->
		<Reserved
			panelState={mixSeries.length === 0 ? telemetryState : 'ready'}
			height={data.console.chart_height}
			width={data.console.chart_width}
			name="failure-mix"
			label="Failures per day by stage"
		>
			{#if mixSeries.length === 0}
				<!-- The window was read and it holds no failure. That is an answer, and
				     it is a better one than the general "nothing was recorded" line
				     above the panels, because it names what was looked for. -->
				<p class="mt-2 text-[0.8125rem] text-text-secondary" data-mix-empty="none">
					No failure is on record in the months this session has read.
				</p>
			{:else}
				<Chart
					svg=""
					option={failureMix(mixSeries, mixShape).option}
					width={760}
					height={220}
					label="Failures per day by stage. One column is one day, its height is that day's failures, and the bands are the stages they stopped at - so a quiet day and a clean day do not draw alike. Drawn as lines instead, each stage is its own count a day and the total is not shown."
					columns={failureMixColumns(mixSeries)}
					readoutName="failure-mix"
					readoutMaxShare={data.chart.readout_max_share}
					restingNote=", the newest day"
					hint="Point at a day to read every stage at once. Left and Right step through the days, Escape returns to the newest."
					pending="The stage mix is drawn once the engine loads. Every count is in the strip below it."
					fetched
				/>
				<!-- Stacked answers what the mix is and how big the day got; lines answer
				     what one stage did on its own, which a stack hides when one band
				     halves while its neighbour doubles. Same array either way. -->
				<ShapeSwitch bind:shape={mixShape} name="failure-mix" label="How to draw the failure mix" />
			{/if}
		</Reserved>
	</Panel>

	<!-- The note is not a restatement of the encoding - the strip under the chart
	     already prints every band at the hovered day. It is there for the one
	     thing the shape cannot say: that the top band is time no step claimed,
	     and that it is the band to look at first. -->
	<Panel
		title="Where an item's time went"
		note="One column is one day and its height is the mean item's whole clock, split by what claimed it. The top band is time no named step claimed, so a step nobody thought to time shows up there rather than nowhere."
	>
		<!-- Same reserved box as the mix chart above, so this panel and everything
		     under it stay where they were drawn whether the months are still
		     arriving, absent, refused, or read and holding nothing. -->
		<Reserved
			panelState={timeDays.length === 0 ? telemetryState : 'ready'}
			height={data.console.chart_height}
			width={data.console.chart_width}
			name="time-split"
			label="Mean milliseconds an item spent in each step, per day"
		>
			{#if timeDays.length === 0}
				<!-- The months were read and no row carries an item clock. That is a
				     different answer from "no month arrived", and it is the one an
				     operator needs: the instrument has not reached this data yet. -->
				<p class="mt-2 text-[0.8125rem] text-text-secondary" data-time-split-empty="none">
					No item in the months this session has read carries an end-to-end clock, so
					there is no time to split.
				</p>
			{:else}
				<Chart
					svg=""
					option={timeSplitChart(timeDays, timeShape).option}
					width={760}
					height={220}
					label="Mean milliseconds an item spent in each step, per day. One column is one day and its height is the mean item's whole clock. The bands from the bottom are fetch, extract, the label call, the summary, the visual plan, the model time neither call claimed, the faithfulness scorers, and at the top the time no named step claimed. Drawn as lines instead, each step is its own milliseconds a day and the whole clock is not shown."
					columns={timeSplitColumns(timeDays)}
					readoutName="time-split"
					readoutMaxShare={data.chart.readout_max_share}
					restingNote=", the newest day"
					hint="Point at a day to read every step at once. Left and Right step through the days, Escape returns to the newest."
					pending="The split is drawn once the engine loads. Every step's milliseconds and share are in the strip below it."
					fetched
				/>
				<!-- Stacked answers what the split is and whether the item got slower;
				     lines answer what one step did on its own, which a stack hides when
				     one band halves while its neighbour doubles. Same array either way. -->
				<ShapeSwitch
					bind:shape={timeShape}
					name="time-split"
					label="How to draw the item time split"
				/>
			{/if}
		</Reserved>
	</Panel>

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
			data-windowed="chart-drawing"
			data-window-days={windowDays}
			data-model-rule="no"
			data-model-rule-name="chart-drawing"
			data-model-rule-none="the chart drawing is a different model call, judged on its own rule"
		>
			<p class="mt-1 text-[0.8125rem] text-text-tertiary">
				Over {thresholds.ruleDays} days with the chart-only gate on, chart drawing is retired if the
				median day spends more than {thresholds.minutesTarget} minutes per published visual, or
				puts a visual on fewer than {thresholds.coveragePct}% of the items it published. Over
				{windowDays} days.
			</p>
			<div class="console-panel mt-3" data-charts="rule">
				{#if rule.narrow}
					<!-- The rule is stated over its own span, and a median of any other
					     span is the same figure with a different meaning. -->
					<p class="text-[0.9375rem] text-text-secondary" data-window-too-narrow="chart-drawing">
						The rule reads {thresholds.ruleDays} days. Widen the window to see it.
					</p>
				{:else}
					<p class="text-[0.9375rem] text-text" data-charts-verdict>{rule.verdict}</p>
					<div class="rule-figures">
						<div class="rule-figure" data-rule-figure="minutes">
							<TargetBar
								marks={rule.minutesMarks}
								label="Minutes per visual"
								valueText={rule.minutes === null ? '-' : rule.minutes.toFixed(1)}
								targetText="Retired above {thresholds.minutesTarget}, on the median day."
								emptyNote="No minutes are on record for these {windowDays} days."
							/>
							<Sparkline
								marks={rule.minutesTrend}
								width={220}
								height={30}
								label="Minutes per visual, day by day, over {rule.minutesDays} measured days"
							/>
							{@render ruleMove(rule.minutesTrend.movement, rule.minutesMarks.sense, 'minutes')}
						</div>
						<div class="rule-figure" data-rule-figure="coverage">
							<TargetBar
								marks={rule.coverageMarks}
								label="Published articles with a visual"
								valueText={rule.coverage === null ? '-' : `${Math.round(rule.coverage)}%`}
								targetText="Retired below {thresholds.coveragePct}%, on the median day."
								emptyNote="No day in these {windowDays} days published anything to put a visual on."
							/>
							<Sparkline
								marks={rule.coverageTrend}
								width={220}
								height={30}
								label="Share of published articles carrying a visual, day by day, over {rule.coverageDays} measured days"
							/>
							{@render ruleMove(rule.coverageTrend.movement, rule.coverageMarks.sense, 'coverage')}
						</div>
					</div>
				{/if}
			</div>
			{#if !flow.empty}
				<!-- Two shapes, one flow. The diagram needs 700px of viewport before its
				     labels stop overlapping (measured 2026-09-01), and a phone column
				     cannot give it that at any font size - so below the page's own
				     stacking breakpoint the same numbers are a stepped list, which is a
				     shape a 360px column can hold. Both are built from one `chartFlow`
				     call, so they cannot report two different flows.
				     The list is the one that always draws: it is markup over the same
				     steps, so an operator with no engine still reads every stage and
				     every drop. -->
				<div class="panel mt-4" data-flow="chart">
					<Chart
						svg=""
						option={flow.option}
						width={data.console.chart_width}
						height={FLOW_HEIGHT}
						label="Where items go between the visual planner reaching one and a visual being published, across the window. Every drop leaves the flow as its own branch, and a branch is as wide as the number of items in it."
						noReadout="a flow between stages, so there is no column two branches share"
						pending="The diagram is drawn once the engine loads. Every stage and every drop is in the list below it."
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

	<h2 class="console-h2">What the extractor found, and what was drawn from it</h2>
	<div data-windowed="extraction" data-window-days={windowDays}>
		<p class="mt-1 text-[0.8125rem] text-text-tertiary">
			Every article is read for the quantities and dates it states, before the visual planner sees
			it. This is what that reading found over {windowDays} days, so a fall in published charts can
			name its own cause: if the planner stopped choosing charts this share climbs while the
			chartable count holds, and if the extractor stopped finding numbers the chartable count falls
			instead.
		</p>
		<Panel
			title="Extraction"
			tone="info"
			note="Three classes and not five. Comparative and processual are claims about how an article is written rather than about its numbers, so they have no test yet and arrive with the diagram work."
			wide
		>
			{#if extraction.measuredDays === 0}
				<!-- Named rather than absent, and it keeps the taxonomy sentence below it.
				     An operator who finds a heading and nothing under it cannot tell a
				     panel that measured nothing from one that is broken. -->
				<p class="text-[0.9375rem] text-text-secondary" data-extraction="none">
					No day in these {windowDays} days carries a record of what the extractor found. Every run
					before 2026-09-08 measured none of this, so a window reaching only those days is silent
					rather than empty. Widen the window, or wait for the next run.
				</p>
			{:else}
				<p class="text-[0.9375rem] text-text" data-extraction-verdict>{extraction.verdict}</p>
				<div class="extraction-figures mt-4">
					<KpiCard
						label="Articles that could carry a chart"
						value={grouped(extraction.chartable)}
						note="of {grouped(extraction.items)} read"
						line="The article states at least {data.visuals.min_chart_points} separate figures measured in the same unit. Watch this number, not the share beside it: when it falls, the reading did."
					/>
					<KpiCard
						label="Of those, published without one"
						value={extraction.unusedPct === null ? '-' : `${extraction.unusedPct}%`}
						note={extraction.unusedPct === null
							? 'nothing chartable published'
							: `${grouped(extraction.unused)} of ${grouped(extraction.chartablePublished)}`}
						line="Material the planner was handed and did not draw. It is never zero for long - the reading keeps figures the planner is right to drop - so read the direction, not the level."
						tone={extraction.unusedPct !== null && extraction.unusedPct >= 50 ? 'warn' : 'neutral'}
					/>
					<KpiCard
						label="Facts still where they were cut from"
						value={extraction.integrityPct === null ? '-' : `${extraction.integrityPct}%`}
						note="{grouped(extraction.spanIntegrityPass)} of {grouped(extraction.items)} articles"
						line="Every fact is kept with the characters it was cut from. Below 100 percent, an article's text moved underneath them: that article is degraded on its own and the rest of the day publishes."
						tone={extraction.integrityPct !== null && extraction.integrityPct < 100 ? 'bad' : 'good'}
					/>
					<KpiCard
						label="Facts found"
						value={grouped(extraction.elementsFound)}
						note="over {grouped(extraction.measuredDays)} measured {extraction.measuredDays === 1
							? 'day'
							: 'days'}"
						line="Quantities and dates the reading kept, added over the window. It answers to the patterns alone, so it moves when the reading changes and not when the planner does."
					/>
				</div>
				<div class="console-table mt-4" data-extraction="classes">
					<table class="w-full text-[0.8125rem]">
						<thead class="text-text-tertiary">
							<tr class="border-b border-rule">
								<th class="py-2 text-start font-normal">What the article states</th>
								<th class="py-2 text-end font-normal">Articles</th>
								<th class="py-2 text-end font-normal">Share</th>
							</tr>
						</thead>
						<tbody>
							{#each extractionClasses as row (row.id)}
								<tr class="border-b border-rule" data-extraction-class={row.id}>
									<td class="py-2">{row.label}</td>
									<td class="py-2 text-end tabular-nums" data-extraction-cell="count"
										>{grouped(row.count)}</td
									>
									<td class="py-2 text-end tabular-nums" data-extraction-cell="share"
										>{row.share === null ? '-' : `${row.share}%`}</td
									>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
			<p class="mt-3 text-[0.8125rem] text-text-tertiary" data-extraction="taxonomy">
				Two more classes are coming. Comparative and processual say how an article is written rather
				than what it counts, so nothing here can test for them and they arrive with the diagram
				work. Until then an article with figures but no comparison to draw is counted as not yet
				classified, which is a gap in our own questions and not a fault in the article.
			</p>
		</Panel>
	</div>
</div>

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
.rule-figures {
display: grid;
grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr));
gap: var(--space-6);
margin-block-start: var(--space-4);
}

/* Four cards, and they wrap rather than scroll. The narrowest is set to hold
   the longest label without breaking a word, so a 360px column gets one card a
   row and a wide console gets four - the same rule the chart-drawing figures above
   follow, at the width four cards need instead of two. */
.extraction-figures {
display: grid;
grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
gap: var(--space-4);
}

.rule-figure {
display: flex;
flex-direction: column;
gap: var(--space-2);
min-inline-size: 0;
}

/* The movement pair, never the confidence ramp: a window in which the planner
   got 3 percent slower is not a broken run, and painting it in --band-low is
   how an operator learns to ignore --band-low. The sign is printed beside the
   colour, so the hue is never the only signal. */
.rule-move {
margin: 0;
font-size: var(--text-xs);
line-height: var(--leading-xs);
color: var(--color-text-tertiary);
}

.rule-move-value[data-movement-verdict='good'] {
color: var(--movement-good);
}
.rule-move-value[data-movement-verdict='bad'] {
color: var(--movement-bad);
}
.rule-move-value[data-movement-verdict='neutral'] {
color: var(--color-text-secondary);
}

/* The chart-drawing flow, as a stepped list. It replaces the diagram below the
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

/* The column the readout is printing. A tint behind the day rather than a rule
   through it: an empty column has no square for a rule to land on, and an empty
   column is exactly the one a reader most needs to see selected. */
[data-day-selected] {
background: var(--color-surface-sunken);
box-shadow: 0 0 0 2px var(--color-surface-sunken);
border-radius: 2px;
}

@media (max-width: 48rem) {
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
