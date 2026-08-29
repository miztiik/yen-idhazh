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
	import { axisLabels, CELL_PX, GAP_PX, type LabelAlign } from '$lib/charts/run-history';
	import { grouped } from '$lib/charts/series';
	import StageTimings from '$lib/components/StageTimings.svelte';
	import ThroughputTrend from '$lib/components/ThroughputTrend.svelte';
	import Viewport from '$lib/components/Viewport.svelte';
	import type { Health, ModelDay } from './+page.server';

	let { data } = $props();

	let strip = $state<HTMLDivElement | null>(null);

	// The same three tokens the confidence bands use. A run that went well and a
	// summary that scored well should not be two different greens.
	const COLOUR: Record<Health, string> = {
		green: 'var(--band-high)',
		amber: 'var(--band-medium)',
		red: 'var(--band-low)'
	};

	const KEY = $derived([
		{ health: 'green' as Health, text: 'ran clean' },
		{ health: 'amber' as Health, text: 'worth a look' },
		{ health: 'red' as Health, text: `failed, or under ${data.floorPct}% published` }
	]);

	const totalRuns = $derived(data.grid.reduce((count, day) => count + day.squares.length, 0));
	const axis = $derived(axisLabels(data.grid.map((day) => day.date)));

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

	function mb(bytes: number): string {
		return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
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

<section class="py-6">
	<h1 class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text">Console</h1>
	<p class="mt-1 text-[0.9375rem] text-text-secondary">
		What the pipeline cost and how well it did, per day, from the committed ledger.
		{data.totalRows} scored {data.totalRows === 1 ? 'item' : 'items'} on record.
		{data.itemHealthRows} item-health {data.itemHealthRows === 1 ? 'row' : 'rows'} on record.
	</p>

	<h2 class="mt-8 text-[1.0625rem] font-semibold text-text">Run health</h2>
	<p class="mt-1 text-[0.8125rem] text-text-tertiary">
		One column per day, oldest to newest, one square per recorded run with run 1 at the bottom.
		Skipped items are not counted against a run - an article we already published is skipped by
		design.
	</p>

	{#if totalRuns === 0}
		<p class="mt-4 text-[0.9375rem] text-text-secondary" data-grid="empty">
			No run has recorded a manifest yet. The strip fills as runs publish.
		</p>
	{:else}
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<div
			class="mt-4 overflow-x-auto pb-1"
			role="region"
			tabindex="0"
			aria-label="Run health history, oldest to newest"
			bind:this={strip}
			data-run-history
		>
			<div
				class="grid w-max min-w-full items-end justify-end"
				style="grid-template-columns: repeat({data.grid.length}, {CELL_PX}px); gap: {GAP_PX}px"
				data-grid="days"
			>
				{#each data.grid as day, index (day.date)}
					<!-- Column-reverse, so run 1 sits on the baseline and later runs stack
					     upward, while the DOM keeps reading run 1 first. -->
					<div
						class="flex flex-col-reverse justify-start"
						style="grid-row: 1; grid-column: {index + 1}; gap: {GAP_PX}px"
						data-day={day.date}
					>
						{#each day.squares as square (square.runId)}
							<span
								class="rounded-sm"
								style="width: {CELL_PX}px; height: {CELL_PX}px; background: {COLOUR[
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

	<Viewport
		initialRows={data.telemetryRows}
		availableMonths={data.telemetryMonths}
		today={data.today}
		config={data.console}
		compressionPoints={data.compression}
		bands={data.summarizeBands}
		unplotted={data.unplotted}
	/>

	<h2 class="mt-10 text-[1.0625rem] font-semibold text-text">Sources cut short most often</h2>
	<p class="mt-1 text-[0.8125rem] text-text-tertiary">
		The last {data.sourceCuts.days} days. An article longer than the cap is read from the start and
		stopped there, so the end never reaches the machine. Sorted by how many articles that cost each
		source - not by the share, because a source with two articles and one cut would otherwise lead
		the table. A source can carry several feeds, so this list and "Feeds that failed" below do not
		name the same things.
	</p>

	{#if !data.sourceCuts.measured}
		<p class="mt-4 text-[0.9375rem] text-text-secondary" data-source-cuts="unmeasured">
			Nothing has recorded an article length yet. This fills as runs publish.
		</p>
	{:else if data.sourceCuts.rows.length === 0}
		<p class="mt-4 text-[0.9375rem] text-text-secondary" data-source-cuts="none">
			No article was cut short in the last {data.sourceCuts.days} days.
		</p>
	{:else}
		<div class="mt-3 overflow-x-auto" data-source-cuts="table">
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
					{#each data.sourceCuts.rows as source (source.sourceId)}
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

		{#if data.sourceCuts.moreSources > 0}
			<p class="mt-3 text-[0.8125rem] text-text-tertiary" data-source-cuts-more>
				{data.sourceCuts.moreSources} more sources had {data.sourceCuts.moreCuts} cuts between them.
			</p>
		{/if}
		{#if data.sourceCuts.cost}
			<!-- What the next move of the cap would buy. A count of cut articles says
			     the cap fired; how much it removed says whether raising it is worth
			     anything, and the n is what makes it a measurement. -->
			<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-source-cuts-cost>
				{data.sourceCuts.cost.n} articles were cut short. Half of them lost more than {grouped(
					data.sourceCuts.cost.median
				)} words each, and the longest lost {grouped(data.sourceCuts.cost.max)}.
			</p>
		{/if}
	{/if}

	<h2 class="mt-10 text-[1.0625rem] font-semibold text-text">Feeds that failed</h2>
	<p class="mt-1 text-[0.8125rem] text-text-tertiary">
		Every feed's result is written down every run. A feed that answered with nothing counts as a
		failure - an empty answer costs the digest the same articles a refused one does. A source
		whose <code>robots.txt</code> says no does not: honouring it is the pipeline working. A feed
		is rested after {data.quarantineAfter} failures.
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
		<div class="mt-3 overflow-x-auto" data-feeds="table">
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
							<td class="py-2 ps-6 text-text-secondary">
								{feed.lastOutcome}{feed.lastDetail ? ` - ${feed.lastDetail}` : ''}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	<StageTimings
		days={data.timingDays}
		height={data.console.chart_height}
		width={data.console.chart_width}
	/>

	{#if data.modelWork.length === 0 && data.throughputDays.length === 0}
		<p class="mt-10 text-[0.9375rem] text-text-secondary" data-model="empty">
			Nothing has been summarised yet. This fills as days publish.
		</p>
	{:else}
		<div data-model-section>
			<h2 class="mt-10 text-[1.0625rem] font-semibold text-text">What the model did</h2>
			<p class="mt-1 text-[0.8125rem] text-text-tertiary">
				Every figure is that day's own articles, measured the day it ran. The articles change
				every day, so a dip can be the news rather than the model. Fixed benchmark figures are
				not here - they are in the
				<a href={data.measurementsReference} class="text-accent hover:underline" rel="noreferrer"
					>measurements write-up</a
				>.
			</p>

			{#if data.throughputDays.length > 0}
				<ThroughputTrend
					days={data.throughputDays}
					height={data.console.chart_height}
					width={data.console.chart_width}
					reference={data.throughputReference}
				/>
			{/if}

			{#if data.modelWork.length > 0}
				<div class="mt-6 overflow-x-auto" data-model="table">
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
		<h2 class="mt-10 text-[1.0625rem] font-semibold text-text">Runs and site size</h2>
		<p class="mt-1 text-[0.8125rem] text-text-tertiary">
			Run-level facts live in the manifest, never in an item row. Planned and failed are summed
			across the day's runs; the site size is the last run's measurement, not their total. The
			site has a 1 GB ceiling; this is the number that says how close it is.
		</p>
		<div class="mt-3 overflow-x-auto">
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
		<h2 class="mt-10 text-[1.0625rem] font-semibold text-text">Charts drawn for articles</h2>
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
		<div class="mt-3 overflow-x-auto" data-charts="table">
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
