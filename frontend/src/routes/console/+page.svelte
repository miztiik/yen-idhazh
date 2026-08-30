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
	import { axisLabels, cellFor, type LabelAlign } from '$lib/charts/run-history';
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
	import Chart from '$lib/charts/Chart.svelte';
	import { chartFlow, FLOW_HEIGHT } from '$lib/charts/chart-flow';
	import {
		failureMix,
		publishedTrend,
		routerCost,
		runHealth,
		ROUTER_MINUTES_TARGET,
		RULE_WINDOW_DAYS,
		siteGrowth,
		sizeTrend
	} from '$lib/charts/glance';
	import ThroughputTrend from '$lib/components/ThroughputTrend.svelte';
	import Viewport from '$lib/components/Viewport.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import type { Health, ModelDay } from './+page.server';

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
	const windowedCost = $derived(routerCost(data.charts.filter((day) => inWindow(day.date))));
	const windowedSize = $derived(
		sizeTrend(data.manifests.filter((run) => inWindow(run.date)), windowDays)
	);

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

	function mb(bytes: number): string {
		return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
	}

	/** The card takes the hue of what it means. The ceiling is 1 GB (Rule #2), so
	 * three quarters of it is a warning and nine tenths is a fault. */
	const SITE_CEILING = 1024 * 1024 * 1024;
	const sizeTone = $derived.by(() => {
		const bytes = data.manifests[0]?.siteBytes ?? 0;
		if (bytes >= SITE_CEILING * 0.9) return 'bad' as const;
		if (bytes >= SITE_CEILING * 0.75) return 'warn' as const;
		return 'neutral' as const;
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

	/** A word count with its thousands grouped, or a dash where none was taken.
	 *
	 * Null is the state this exists for: a run before 2026-08-28 measured no
	 * length at all, and printing that as `0` would say the source publishes
	 * nothing - which is the opposite of what the column is asked.
	 */
	function words(value: number | null): string {
		return value === null ? '-' : grouped(value);
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
</script>

<svelte:head>
	<title>Console &mdash; {data.ui.site_title}</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<section class="py-6" data-surface="operator">
	<h1 class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text">Console</h1>
	<p class="mt-1 text-[0.9375rem] text-text-secondary">
		What the pipeline cost and how well it did, per day, from the committed ledger.
		{data.totalRows} scored {data.totalRows === 1 ? 'item' : 'items'} on record.
		{data.itemHealthRows} item-health {data.itemHealthRows === 1 ? 'row' : 'rows'} on record.
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
	<div class="auto-grid mt-4" style="--auto-grid-min: 17rem" data-glance>
		<KpiCard
			label="Charts published"
			value={String(data.charts.reduce((sum, day) => sum + day.published, 0))}
			note="over the days on record"
			tone="info"
			movement={data.glance.publishedMovement}
			trendSvg={data.glance.publishedSvg}
			trendOption={publishedTrend(data.charts).option}
		/>
		<!-- Half windowed, on purpose. The size is a level and the operator wants
		     today's, whatever span he is looking at; only the movement under it is
		     a rate, and a rate has to say what it is over. -->
		{#key windowDays}
			<KpiCard
				label="Site size"
				value={mb(data.manifests[0]?.siteBytes ?? 0)}
				note="1 GB ceiling. Latest run's size; movement over {windowDays} days."
				tone={sizeTone}
				windowed="site-size-movement"
				{windowDays}
				movement={windowedSize.empty ? null : windowedSize.movement}
				trendSvg={windowedSize.empty ? null : data.glance.sizeSvg}
				trendOption={windowedSize.empty ? null : windowedSize.option}
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
					Router minutes per published chart, against the {ROUTER_MINUTES_TARGET} that retires the
					arm. Over {windowDays} days.
				</figcaption>
				{#if windowDays < RULE_WINDOW_DAYS}
					<!-- A median of the wrong span is worse than no median: it is the
					     same figure with a different meaning and nothing on the page to
					     say which one is being read. -->
					<p class="mt-2 text-[0.8125rem] text-text-secondary" data-window-too-narrow="router-cost">
						The rule reads {RULE_WINDOW_DAYS} days. Widen the window to see it.
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

	{#if data.glance.growthSvg}
		<Panel
			title="Where the site's size came from"
			note="Megabytes added or removed each day, starting from the oldest day on record. The ceiling is a rate problem, not a level problem, so what matters is which days added what."
		>
			<Chart
				svg={data.glance.growthSvg}
				option={siteGrowth(data.manifests).option}
				width={760}
				height={220}
				label="Megabytes added or removed each day"
			/>
		</Panel>
	{/if}

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
		<p class="mt-1 text-[0.8125rem] text-text-tertiary">
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
			<div class="console-table mt-3" data-source-cuts="table">
				<table class="w-full text-[0.8125rem]">
					<thead class="text-text-tertiary">
						<tr class="border-b border-rule">
							<th class="py-2 text-start font-normal">Source</th>
							<th class="py-2 text-end font-normal">Cut short</th>
							<th class="py-2 text-end font-normal">Articles</th>
							<th class="py-2 text-end font-normal">Share cut</th>
							<!-- A length ending where a count ends reads as one more count. The
							     gap is what says this column measures something else. -->
							<th class="py-2 ps-6 text-end font-normal">Longest article, words</th>
						</tr>
					</thead>
					<tbody>
						{#each cuts.rows as source (source.sourceId)}
							<tr class="border-b border-rule" data-source-cut={source.sourceId}>
								<td class="py-2">{source.sourceId}</td>
								<td class="py-2 text-end tabular-nums" data-source-cell="cut">{source.cut}</td>
								<td class="py-2 text-end tabular-nums" data-source-cell="articles"
									>{source.articles}</td
								>
								<td class="py-2 text-end tabular-nums" data-source-cell="share"
									>{percent(source.sharePct)}</td
								>
								<td class="py-2 ps-6 text-end tabular-nums" data-source-cell="longest"
									>{words(source.longestWords)}</td
								>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			{#if cuts.moreSources > 0}
				<p class="mt-3 text-[0.8125rem] text-text-tertiary" data-source-cuts-more>
					{cuts.moreSources} more sources had {cuts.moreCuts} cuts between them.
				</p>
			{/if}
			{#if cuts.cost}
				<!-- What the next move of the cap would buy. A count of cut articles says
				     the cap fired; how much it removed says whether raising it is worth
				     anything, and the n is what makes it a measurement. -->
				<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-source-cuts-cost>
					{cuts.cost.n} articles were cut short. Half of them lost more than {grouped(
						cuts.cost.median
					)} words each, and the longest lost {grouped(cuts.cost.max)}.
				</p>
			{/if}
		{/if}
	</div>

	<h2 class="console-h2">Feeds that failed</h2>
	<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-window-exempt="feeds">
		Every feed's result is written down every run. A feed that answered with nothing counts as a
		failure - an empty answer costs the digest the same articles a refused one does. A source
		whose <code>robots.txt</code> says no does not: honouring it is the pipeline working. A feed
		is rested after {data.quarantineAfter} failures. This section does not follow the window
		above: it counts every run on record, because that is what the pipeline counted when it
		decided to rest a feed, and two numbers for one decision is worse than one long count.
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
		<div class="console-table mt-3" data-feeds="table">
			<table class="w-full text-[0.8125rem]">
				<thead class="text-text-tertiary">
					<tr class="border-b border-rule">
						<th class="py-2 text-start font-normal">Feed</th>
						<th class="py-2 text-end font-normal">Failed</th>
						<th class="py-2 text-end font-normal">Asked</th>
						<!-- A number ending at the same pixel a sentence begins reads as one
						     word. The gap is what separates the count from the reason. -->
						<th class="py-2 ps-6 text-start font-normal">Last result</th>
					</tr>
				</thead>
				<tbody>
					{#each data.feeds as feed (feed.feedId)}
						<tr class="border-b border-rule" data-feed={feed.feedId}>
							<td class="py-2">
								{feed.feedId}
								{#if feed.nearQuarantine}
									<span class="ms-2 text-[0.6875rem] text-band-low" data-rested>rested</span>
								{/if}
							</td>
							<td class="py-2 text-end tabular-nums">{feed.failures}</td>
							<td class="py-2 text-end tabular-nums">{feed.attempts}</td>
							<td class="py-2 ps-6 text-text-secondary" data-feed-result>
								{feed.lastResult}{feed.lastDetail ? ` - ${feed.lastDetail}` : ''}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
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

			{#if data.modelWork.length > 0}
				<div class="console-table mt-6" data-model="table">
					<table class="w-full text-[0.8125rem]">
						<thead class="text-text-tertiary">
							<tr class="border-b border-rule">
								<th class="py-2 pe-4 text-start align-bottom font-normal">Day</th>
								{#each COLUMNS as column (column.key)}
									<th class="py-2 ps-4 text-end align-bottom font-normal">
										<!-- The sentence is bounded rather than left to the column, so a
										     nine-column table wraps its explanations instead of growing
										     past the width an operator can read. -->
										<span class="ms-auto block max-w-[10rem]">
											{column.label}
											{#if column.line}
												<span class="mt-0.5 block text-[0.6875rem] leading-snug"
													>{column.line}</span
												>
											{/if}
										</span>
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
			{/if}
		</div>
	{/if}

	{#if data.manifests.length > 0}
		<h2 class="console-h2">Runs and site size</h2>
		<p class="mt-1 text-[0.8125rem] text-text-tertiary">
			Run-level facts live in the manifest, never in an item row. Planned and failed are summed
			across the day's runs; the site size is the last run's measurement, not their total. The
			site has a 1 GB ceiling; this is the number that says how close it is.
		</p>
		<div class="console-table mt-3">
			<table class="w-full text-[0.8125rem]">
				<thead class="text-text-tertiary">
					<tr class="border-b border-rule">
						<th class="py-2 text-start font-normal">Day</th>
						<th class="py-2 text-end font-normal">Runs</th>
						<th class="py-2 text-end font-normal">Planned</th>
						<th class="py-2 text-end font-normal">Failed</th>
						<th class="py-2 text-end font-normal">Site</th>
						<th class="py-2 text-end font-normal">Files</th>
					</tr>
				</thead>
				<tbody>
					{#each data.manifests as run (run.date)}
						<tr class="border-b border-rule">
							<td class="py-2">{run.date}</td>
							<td class="py-2 text-end tabular-nums">{run.runs}</td>
							<td class="py-2 text-end tabular-nums">{run.planned}</td>
							<td class="py-2 text-end tabular-nums">{run.failed}</td>
							<td class="py-2 text-end tabular-nums">{mb(run.siteBytes)}</td>
							<td class="py-2 text-end tabular-nums">{run.siteFiles}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	{#if data.charts.length > 0}
		<h2 class="console-h2">Charts drawn for articles</h2>
		<p class="mt-1 text-[0.8125rem] text-text-tertiary">
			What the router cost and what it published, one row per day, newest first. Reached is every
			item the router looked at. Asked the model is the part it sent a request for: an item whose
			own numbers cannot fill a chart is answered without one. Charts drafted is what the model
			asked for, and charts published is what survived the checks that run after it answers. A
			dash means no router time was written down, so there is no rate to divide, and zero
			reached means nothing committed says what the router did - it never ran, or its manifest
			is older than these counts. Over 14 days with the chart-only gate on, the arm is retired
			if the median day spends more than 6 router minutes per published chart, or puts a chart
			on fewer than 5% of the items it published.
		</p>
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
		<div class="console-table mt-3" data-charts="table">
			<table class="w-full text-[0.8125rem]">
				<thead class="text-text-tertiary">
					<tr class="border-b border-rule">
						<th class="py-2 text-start font-normal">Day</th>
						<th class="py-2 text-end font-normal">Reached</th>
						<th class="py-2 text-end font-normal">Asked the model</th>
						<th class="py-2 text-end font-normal">Charts drafted</th>
						<th class="py-2 text-end font-normal">Charts published</th>
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

/* The header row stays put while the body scrolls, which is what makes a
   thirty-row table readable without a second glance at the top. */
.console-table :global(thead th) {
position: sticky;
top: 0;
z-index: 1;
background: var(--color-surface);
}
</style>