<script lang="ts">
	/** The operator's page. Not a reader's.
	 *
	 * It answers seven questions and refuses to answer any others: did the runs
	 * work, which feeds are broken, how long each stage took, what the model did
	 * to the day's own articles, what the truncation cap is costing and which
	 * sources it is costing it to, how big the site is getting, and whether the
	 * chart arm earns its router minutes. Every count is read from the committed
	 * ledger. The only arithmetic is one committed count divided by another, and
	 * that is deliberate: a stored rate can disagree with the counts printed
	 * beside it.
	 *
	 * The run grid stays static. The telemetry viewport and the timing trend are
	 * hand-written SVG, so the console still reads with JavaScript off.
	 */
	import { base } from '$app/paths';
	import { onMount } from 'svelte';
	import { axisLabels, cellFor, denseCellFor, ROW_STRIP_PX, type LabelAlign } from '$lib/charts/run-history';
	import {
		datesIn,
		failureSeries,
		grouped,
		parseTelemetryCsv,
		type TelemetryRow
	} from '$lib/charts/series';
	import {
		defaultWindow,
		monthsToFetch,
		panWindow,
		stepPreset,
		windowOfDays,
		type TimeWindow
	} from '$lib/charts/viewport';
	import StageTimings from '$lib/components/StageTimings.svelte';
	import KpiCard from '$lib/components/KpiCard.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import TargetBar from '$lib/components/TargetBar.svelte';
	import { sparklineMarks, type SparklineMarks } from '$lib/charts/sparkline';
	import { shortDate } from '$lib/format';
	import Chart from '$lib/charts/Chart.svelte';
	import { chartFlow, FLOW_HEIGHT } from '$lib/charts/chart-flow';
	import {
		chartArm,
		failureMix,
		publishedSkyline,
		routerCost,
		runHealth,
		PAGES_CAP_BYTES,
		siteCost,
		siteRunway,
		sizeGain,
		type SkylineBar
	} from '$lib/charts/glance';
	import Sparkline from '$lib/components/Sparkline.svelte';
	import ThroughputTrend from '$lib/components/ThroughputTrend.svelte';
	import SourceCutRange from '$lib/components/SourceCutRange.svelte';
	import Viewport from '$lib/components/Viewport.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import type { FeedDayOutcome, Health, ModelDay } from './+page.server';

	let { data } = $props();

	/** Where the operator's choice of window is kept between visits. */
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
	const windowedCost = $derived(
		routerCost(
			data.charts.filter((day) => inWindow(day.date)),
			data.console.chart_arm_minutes_target
		)
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
	const windowedSize = $derived(sizeGain(data.manifests.filter((run) => inWindow(run.date))));
	const perArticle = $derived(siteCost(data.manifests, articles, viewport));
	/** One bar a day, over the window the control set. The card's own count is
	 * the same window summed, so a reader can check the number against the
	 * picture - which an all-time total under a thirty-day strip could not do. */
	const skyline = $derived(publishedSkyline(data.charts, viewport));

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
	const stripAxis = $derived(axisLabels(stripDates));
	const strips = $derived(
		new Map(
			data.feeds.map((feed) => [feed.feedId, new Map(feed.days.map((day) => [day.date, day]))])
		)
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

	const KEY = $derived([
		{ health: 'green' as Health, text: 'ran clean' },
		{ health: 'amber' as Health, text: 'worth a look' },
		{ health: 'red' as Health, text: `failed, or under ${data.floorPct}% published` }
	]);

	/** The strip reads the page's window, like every other windowed section. */
	const windowGrid = $derived(data.grid.filter((day) => inWindow(day.date)));
	const windowRuns = $derived(windowGrid.reduce((count, day) => count + day.squares.length, 0));
	const axis = $derived(axisLabels(windowGrid.map((day) => day.date)));

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
	const strip_ = $derived(cellFor(stripWidth, windowGrid.length));

	$effect(() => {
		const node = strip;
		if (!node || typeof ResizeObserver === 'undefined') return;
		const observer = new ResizeObserver(([entry]) => {
			stripWidth = Math.round(entry.contentRect.width);
		});
		observer.observe(node);
		return () => observer.disconnect();
	});

	function mb(value: number): string {
		return `${(value / 1024 / 1024).toFixed(1)} MB`;
	}

	/** Whole bytes with thousands separators. The per-article cost is a
	 * four-digit number, so a rounded kilobyte would hide the whole range the
	 * chart is drawn over. */
	function bytes(value: number): string {
		return `${Math.round(value).toLocaleString('en-GB')} B`;
	}

	/** A count of days a person can act on. Under ten it keeps a decimal,
	 * because "0 days" and "0.4 days" are different answers. */
	function days(value: number): string {
		const whole = Math.round(value);
		return whole >= 10 ? whole.toLocaleString('en-GB') : value.toFixed(1);
	}

	/** How much of the site's one hard limit is spent.
	 *
	 * `site_bytes` is the committed payload tree and the cap is measured on the
	 * built bundle, which is larger - so this fraction is a floor on the real
	 * one, never the whole of it. The card says so in words rather than leaving
	 * the reader to find `backend/idhazh/contracts/run_manifest.py`.
	 *
	 * Null where no run has recorded a size. Null is not zero: a tree nobody
	 * measured is not an empty tree, and `0.0 MB` beside a 1 GB cap reads as a
	 * site with all of its room left.
	 */
	const payloadBytes = $derived(data.manifests[0]?.siteBytes ?? null);
	const capFraction = $derived(payloadBytes === null ? null : payloadBytes / PAGES_CAP_BYTES);

	/** Published days of room left, at the cost this window measured.
	 *
	 * Windowed, because it is a rate: the median article cost of the last seven
	 * days and of the last ninety are different claims about the future, and a
	 * runway that did not move with the span would be one of them wearing the
	 * other's label.
	 */
	const runway = $derived(
		payloadBytes === null
			? null
			: siteRunway(
					payloadBytes,
					perArticle.median,
					data.itemCeiling,
					data.siteBudgetMb * 1024 * 1024,
					PAGES_CAP_BYTES
				)
	);

	/** What the window added, in the unit the card's own number is in.
	 *
	 * A share is what this used to print, and from the 13,595 bytes of the oldest
	 * committed manifest it read +73,933 percent - and green, on a card where
	 * growth is the thing being watched. */
	const sizeDelta = $derived.by(() => {
		if (windowedSize === null) return `No second measurement in these ${windowDays} days.`;
		return `${windowedSize >= 0 ? 'Up' : 'Down'} ${mb(Math.abs(windowedSize))} over ${windowDays} days.`;
	});

	/** The card takes the hue of what it means. The ceiling is 1 GB (Rule #2), so
	 * three quarters of it is a warning and nine tenths is a fault. */
	const sizeTone = $derived.by(() => {
		if (capFraction === null) return 'neutral' as const;
		if (capFraction >= 0.9) return 'bad' as const;
		if (capFraction >= 0.75) return 'warn' as const;
		return 'neutral' as const;
	});

	/** What the size card says under its number.
	 *
	 * Three states and they are three different facts: nothing measured, measured
	 * but not growing, and growing at a rate a runway can be divided out of.
	 */
	const TREE =
		"Latest run's size. It is the committed payload tree, not the published site: the site is larger, it is what the cap measures, and idhazh site-weight prints its runway after every build.";
	const sizeNote = $derived.by(() => {
		if (payloadBytes === null) {
			return `No run has recorded a size yet, so there is nothing to hold against the 1 GB Pages cap. Over ${windowDays} days.`;
		}
		if (runway === null) {
			return `${TREE} ${sizeDelta} No day in these ${windowDays} days grew the tree over an article it published, so there is no rate and no runway.`;
		}
		return `${TREE} ${sizeDelta} At ${bytes(perArticle.median ?? 0)} an article, ${data.itemCeiling} articles a day would fill this tree to 1 GB in about ${days(runway.toCap)} published days.`;
	});

	/** The same window the server drew with. Both sides derive it from the rows
	 * rather than passing it, so the hydrated chart cannot disagree with the one
	 * already on the page. */
	function failureSeriesFor(rows: TelemetryRow[]) {
		const dates = datesIn(rows);
		if (dates.length === 0) return [];
		return failureSeries(rows, { start: dates[0], end: dates[dates.length - 1] });
	}

	/** A minute count, or a dash where there is no number to print.
	 *
	 * Null means nothing was measured. Printing that as `0.0` would say the
	 * router was free, and printing a per-chart cost of infinity on a day with no
	 * chart would say it was ruinous. Both are answers to a question nobody asked.
	 */
	function minutes(value: number | null): string {
		return value === null ? '-' : value.toFixed(1);
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

	/** Whole units, never a decimal, and never a zero that was really work.
	 *
	 * A measurement that rounds away prints `<1`. Rounded to `0` it would say the
	 * model ran for nothing, which is the one reading the number cannot support.
	 */
	function whole(ms: number | null, per: number): string {
		if (ms === null) return '-';
		const value = Math.round(ms / per);
		return value === 0 && ms > 0 ? '<1' : String(value);
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

	/** The card grid's minimum column, and the room a card leaves inside it.
	 *
	 * A line drawn wider than that overflows the narrowest card the grid can
	 * make. The pad is `--space-4`, which the card spends on each side.
	 */
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

	/** The days the cards' lines cover, oldest first.
	 *
	 * It follows the length of the window above and ends on the newest day the
	 * ledger holds, never where a pan leaves it - the same rule the source table
	 * follows, and the one that makes a rebuild of an old tree draw what that
	 * tree drew. Nothing is fetched: every day is already on the page.
	 */
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

	/** One card's drawn points, and the swap rules that land on them.
	 *
	 * The dates ride along with the values because the two are filtered together:
	 * a rule has to sit on the point that carries it and not on the day beside
	 * it. A swap on the oldest drawn point draws nothing - there is nothing to
	 * its left to have changed from.
	 */
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

	/** What a quality figure is out of, printed beside it.
	 *
	 * On a table row the day's count sat one column away. A card has no row, so
	 * it carries its own denominator or it invites a trend that is not there.
	 * The two cut figures divide by the rows their own flag still answers for,
	 * which can read lower than the day's summaries and is the point of carrying
	 * it separately.
	 */
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

	/** The eleven cards, in the order `COLUMNS` names them.
	 *
	 * Built off `cells` for the same reason the table's body is: a label and the
	 * figure under it cannot drift apart if one list produces both.
	 */
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
	<title>Console &mdash; {data.ui.site_title}</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<section class="py-6" data-surface="operator">
	<h1 class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text">Console</h1>
	<p class="mt-1 text-[0.9375rem] text-text-secondary">
		What the pipeline cost and how well it did, per day, from the committed ledger.
	</p>

	<!-- The window sits above everything it governs, so it is read before the
	     first chart rather than found underneath one. -->
	<WindowControl
		days={windowDays}
		{presets}
		{monthsFor}
		busy={fetching}
		{ready}
		onChange={show}
	/>

	<!-- Six questions, six shapes. A different chart per question is the point:
	     one shape repeated is what made this page read as a single instrument. -->
	<h2 class="console-h2">At a glance</h2>
	<!-- Bars, not a line: a count per day is a discrete quantity, and a line
	     between two days claims a value for the hours in between that nobody
	     counted. Drawn as markup rather than by the engine, so it is complete
	     before any script runs and follows the window with one drawing. -->
	{#snippet publishedBars()}
		<svg
			class="block"
			width={SKYLINE.width}
			height={SKYLINE.height}
			viewBox="0 0 {SKYLINE.width} {SKYLINE.height}"
			role="img"
			aria-label="Charts published each day over {windowDays} days, {skyline.total} in all, busiest day {skyline.busiest}"
			data-published-days={skyline.bars.length}
			data-published-total={skyline.total}
		>
			{#each skyline.bars as bar (bar.date)}
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
	<div class="auto-grid mt-4" style="--auto-grid-min: 17rem" data-glance>
		<KpiCard
			label="Charts published"
			value={String(skyline.total)}
			note="in these {windowDays} days"
			tone="info"
			trend={skyline.empty ? null : publishedBars}
		/>
		<!-- Half windowed, on purpose. The size is a level and the operator wants
		     today's, whatever span he is looking at; only the movement and the
		     runway under it are rates, and a rate has to say what it is over. -->
		{#key windowDays}
			<KpiCard
				label="Site size"
				value={payloadBytes === null ? '-' : mb(payloadBytes)}
				track={capFraction === null
					? null
					: {
							fraction: capFraction,
							caption: `${Math.round(
								(PAGES_CAP_BYTES - (payloadBytes ?? 0)) / 1024 / 1024
							).toLocaleString('en-GB')} MB left of the 1 GB Pages cap`
						}}
				note={sizeNote}
				tone={sizeTone}
				windowed="site-size-movement"
				{windowDays}
			/>
		{/key}
		{#if data.glance.healthSvg}
			<figure class="panel" data-glance-chart="runs">
				<figcaption class="text-[0.75rem] text-text-tertiary">Did the runs finish?</figcaption>
				<Chart
					svg={data.glance.healthSvg}
					option={runHealth(data.manifests).option}
					width={260}
					height={200}
					label="Share of planned items that finished, against those that failed"
				/>
			</figure>
		{/if}
		{#if data.glance.costSvg}
			<figure
				class="panel"
				data-glance-chart="router-cost"
				data-windowed="router-cost"
				data-window-days={windowDays}
			>
				<figcaption class="text-[0.75rem] text-text-tertiary">
					Router minutes per published chart, against the {thresholds.minutesTarget} that retires the
					arm. Over {windowDays} days.
				</figcaption>
				{#if windowDays < thresholds.ruleDays}
					<!-- A median of the wrong span is worse than no median: it is the
					     same figure with a different meaning and nothing on the page to
					     say which one is being read. -->
					<p class="mt-2 text-[0.8125rem] text-text-secondary" data-window-too-narrow="router-cost">
						The rule reads {thresholds.ruleDays} days. Widen the window to see it.
					</p>
				{:else if windowedCost.empty}
					<p class="mt-2 text-[0.8125rem] text-text-secondary" data-window-empty="router-cost">
						No router time was written down in these {windowDays} days.
					</p>
				{:else}
					{#key windowDays}
						<Chart
							svg={data.glance.costSvg}
							option={windowedCost.option}
							width={460}
							height={40}
							label="Median router minutes per published chart against its target, over {windowDays} days"
						/>
					{/key}
				{/if}
			</figure>
		{/if}
	</div>

	<div data-windowed="site-cost-per-item" data-window-days={windowDays}>
		<Panel
			title="What one more article costs"
			note="Bytes the committed payload tree gained on each published day, over the articles that day published. Megabytes a day was the item ceiling wearing a size label - a day gains six times as much when it publishes six times as many articles. This is the part a change to a payload can move. Over {windowDays} days."
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
		<Panel
			title="What is failing, by stage"
			note="Stacked, so the height of a column is the day's total and the bands are what made it up. Grouped bars would answer how big each stage is and lose the total, and the total is half the question. A quiet day and a clean day look different here, which they would not on a percentage scale."
		>
			<Chart
				svg={data.glance.mixSvg}
				option={failureMix(failureSeriesFor(data.telemetryRows)).option}
				width={760}
				height={220}
				label="Failures per day by stage"
			/>
		</Panel>
	{/if}

	<div data-windowed="run-health" data-window-days={windowDays}>
		<Panel
			title="Run health"
			note="The last {windowDays} days, one column per day, oldest on the left, one square per recorded run with run 1 at the bottom. Skipped items are not counted against a run - an article we already published is skipped by design."
		>
			{#if data.grid.length === 0}
				<p class="text-[0.9375rem] text-text-secondary" data-grid="empty">
					No run has recorded a manifest yet. The strip fills as runs publish.
				</p>
			{:else if windowRuns === 0}
				<!-- A different fact from the one above, so a different sentence: the
				     ledger answered, and the answer was nothing in this span. -->
				<p class="text-[0.9375rem] text-text-secondary" data-grid="outside-window">
					No run recorded a manifest in the last {windowDays} days. Widen the window to reach
					further back.
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
					<!-- Left-anchored, and that is not the same question as where an
					     overflowing strip opens. `today_anchor` governs the scroll
					     position; a strip with room to spare simply starts where every
					     other axis on the page starts, so a day keeps the place the
					     operator last saw it in as the window fills. -->
					<div
						class="grid w-max min-w-full items-end justify-start"
						style="grid-template-columns: repeat({windowGrid.length}, {strip_.cell}px); gap: {strip_.gap}px"
						data-grid="days"
					>
						{#each windowGrid as day, index (day.date)}
							<!-- Column-reverse, so run 1 sits on the baseline and later runs stack
							     upward, while the DOM keeps reading run 1 first. -->
							<div
								class="flex flex-col-reverse justify-start"
								style="grid-row: 1; grid-column: {index + 1}; gap: {strip_.gap}px"
								data-day={day.date}
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
									data-axis-label={label.column}
								>
									{label.text}
								</span>
							</div>
						{/each}
					</div>
				</div>

				<ul class="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-[0.75rem] text-text-tertiary">
					{#each KEY as entry (entry.health)}
						<li class="flex items-center gap-2">
							<span class="size-3 shrink-0 rounded-sm" style="background: {COLOUR[entry.health]}"
							></span>
							{entry.text}
						</li>
					{/each}
				</ul>
			{/if}
		</Panel>
	</div>

	<Viewport
		{rows}
		window={viewport}
		config={data.console}
		bands={data.summarizeBands}
		tickDensity={data.chart.tick_density}
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
			The last {cuts.days} days, {cuts.articles}
			{cuts.articles === 1 ? 'article' : 'articles'} between them. An article longer than the cap
			is read from the start and stopped there, so the end never reaches the machine. Sorted by how
			many articles that cost each source - not by the share, because a source with two articles and
			one cut would otherwise lead the table. A source can carry several feeds, so this list and
			"Feeds that failed" below do not name the same things. It follows the length of the window
			above, not where a pan leaves it: the days it reads always end on the newest day the ledger
			holds.
		</p>

		{#if !cuts.measured}
			<p class="mt-4 text-[0.9375rem] text-text-secondary" data-source-cuts="unmeasured">
				Nothing has recorded an article length yet. This fills as runs publish.
			</p>
		{:else if cuts.rows.length === 0}
			<p class="mt-4 text-[0.9375rem] text-text-secondary" data-source-cuts="none">
				No article was cut short in the last {cuts.days} days.
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
	<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-window-exempt="feeds">
		Every feed's result is written down every run. A feed that answered with nothing counts as a
		failure - an empty answer costs the digest the same articles a refused one does. A source
		whose <code>robots.txt</code> says no does not: honouring it is the pipeline working. A feed
		is rested after {data.quarantineAfter} failures in a row, and the count beside each feed is
		that run of failures - the number the pipeline itself rests on, not every failure it has ever
		had. That count does not follow the window above, because a windowed recount would disagree
		with the rest the pipeline actually performed, and two numbers for one decision is worse than
		one long count. The strip of days beside it does follow the window.
	</p>

	{#if data.feedRuns === 0}
		<p class="mt-4 text-[0.9375rem] text-text-secondary" data-feeds="empty">
			No feed result has been recorded yet. The ledger fills as runs collect.
		</p>
	{:else if data.feeds.length === 0}
		<p class="mt-4 text-[0.9375rem] text-text-secondary" data-feeds="clean">
			All {data.feedsChecked} feeds answered across {data.feedRuns}
			{data.feedRuns === 1 ? 'run' : 'runs'}.
		</p>
	{:else}
		<div
			class="console-table mt-3"
			data-windowed="feed-outcomes"
			data-window-days={windowDays}
		>
			<p class="feeds-note">
				Nearest to a rest first, then by how much has gone wrong in total. Each strip is one
				square a day, oldest to newest, over the last {windowDays} days.
			</p>

			<ol class="feed-rows" data-feeds="table">
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

			{#if stripDates.length > 0}
				<div
					class="feed-axis"
					style="inline-size: {stripCell.width}px; grid-template-columns: repeat({stripDates.length}, {stripCell.cell}px); gap: {stripCell.gap}px"
				>
					{#each stripAxis as label (label.column)}
						<div class="feed-axis-slot" style="grid-column: {label.column}">
							<span style={ANCHOR[label.align]} data-feed-axis={label.column}>{label.text}</span>
						</div>
					{/each}
				</div>
			{:else}
				<p class="feeds-note" data-feed-strip-empty>
					No run was recorded in these {windowDays} days, so there is no strip to draw.
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
	/>

	{#if data.modelWork.length === 0 && data.throughputDays.length === 0}
		<p class="mt-10 text-[0.9375rem] text-text-secondary" data-model="empty">
			Nothing has been summarised yet. This fills as days publish.
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
		     state, the way the stage-timing trend above it does, so a window with
		     nothing in it says so instead of taking the heading away with it. -->
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
					changed. Like the source table above, it follows the length of the window and not where
					a pan leaves it.
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
				<!-- The rows behind the shape, on demand - the same trade the failed-item
				     list makes. Nothing is deleted and nothing needs a script: a closed
				     disclosure is complete in the prerendered document, and opening it
				     costs no fetch. -->
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

	{#if data.charts.length > 0}
		<h2 class="console-h2">Charts drawn for articles</h2>
		<div data-windowed="chart-arm" data-window-days={windowDays}>
			<p class="mt-1 text-[0.8125rem] text-text-tertiary">
				Over {thresholds.ruleDays} days with the chart-only gate on, the arm is retired if the
				median day spends more than {thresholds.minutesTarget} router minutes per published chart,
				or puts a chart on fewer than {thresholds.coveragePct}% of the items it published. Over
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
								label="Router minutes per chart"
								valueText={arm.minutes === null ? '-' : arm.minutes.toFixed(1)}
								targetText="Retired above {thresholds.minutesTarget}, on the median day."
								emptyNote="No router time was written down in these {windowDays} days."
							/>
							<Sparkline
								marks={arm.minutesTrend}
								width={220}
								height={30}
								label="Router minutes per chart, day by day, over {arm.minutesDays} measured days"
							/>
						</div>
						<div class="arm-figure" data-arm-figure="coverage">
							<TargetBar
								marks={arm.coverageMarks}
								label="Published items with a chart"
								valueText={arm.coverage === null ? '-' : `${Math.round(arm.coverage)}%`}
								targetText="Retired below {thresholds.coveragePct}%, on the median day."
								emptyNote="No day in these {windowDays} days published anything to put a chart on."
							/>
							<Sparkline
								marks={arm.coverageTrend}
								width={220}
								height={30}
								label="Share of published items carrying a chart, day by day, over {arm.coverageDays} measured days"
							/>
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
					label="Where items go between the router reaching one and a chart being published, across the window. Every drop leaves the flow as its own branch, and a branch is as wide as the number of items in it."
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
				One row per day, newest first. Reached is every item the router looked at. Asked the model
				is the part it sent a request for: an item whose own numbers cannot fill a chart is
				answered without one. Charts drafted is what the model asked for, and charts published is
				what survived the checks that run after it answers. A dash means no router time was
				written down, so there is no rate to divide, and zero reached means nothing committed says
				what the router did - it never ran, or its manifest is older than these counts.
			</p>
			<div class="console-table mt-3" data-charts="table">
				<table class="w-full text-[0.8125rem]">
					<thead class="text-text-tertiary">
						<tr class="border-b border-rule">
							<th class="py-2 text-start font-normal">Day</th>
							<th class="py-2 text-end font-normal">Reached</th>
							<th class="py-2 text-end font-normal">Asked the model</th>
							<th class="py-2 text-end font-normal">Charts drafted</th>
							<th class="py-2 text-end font-normal">Charts published</th>
							<th class="py-2 text-end font-normal">Items published</th>
							<th class="py-2 text-end font-normal">Router minutes</th>
							<th class="py-2 text-end font-normal">Minutes per chart</th>
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
/* The console is instrumentation, so it takes tint and elevation and no
   display face, no gradient and no illustration. What it was missing was an
   edge: headings and tables on bare background give the eye nothing to group
   by, and every section ends up weighing the same as every other. */
.console-h2 {
margin-top: var(--space-8);
font-size: var(--text-lg);
font-weight: 600;
color: var(--color-text);
}

.console-table {
overflow-x: auto;
padding: var(--space-4);
border: 1px solid var(--color-rule);
border-radius: var(--radius-lg);
background: var(--color-surface);
box-shadow: var(--shadow-sm);
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

/* The rows are on demand, and the control that opens them is a native
   disclosure - so it works with no script, takes keyboard focus for free, and
   says which state it is in without a second label. */
.console-panel,
.console-disclosure {
padding: var(--space-4);
border: 1px solid var(--color-rule);
border-radius: var(--radius-lg);
background: var(--color-surface);
box-shadow: var(--shadow-sm);
}

.console-summary {
cursor: pointer;
min-block-size: 1.75rem;
font-size: var(--text-sm);
line-height: var(--leading-sm);
color: var(--color-accent);
}

.console-summary:focus-visible {
outline: 2px solid var(--color-accent);
outline-offset: 2px;
border-radius: var(--radius-sm);
}

/* The table brings its own frame everywhere else on the page. Inside the
   disclosure it would be a box in a box. */
.console-disclosure .console-table {
padding: 0;
border: 0;
border-radius: 0;
background: none;
box-shadow: none;
}

/* The header row stays put while the body scrolls, which is what makes a
   thirty-row table readable without a second glance at the top. */
.console-table :global(thead th) {
position: sticky;
top: 0;
z-index: 1;
background: var(--color-surface);
}

.feeds-note {
margin: 0 0 var(--space-3);
font-size: var(--text-xs);
line-height: var(--leading-xs);
color: var(--color-text-tertiary);
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