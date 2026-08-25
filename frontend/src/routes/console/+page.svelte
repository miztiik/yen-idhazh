<script lang="ts">
	/** The operator's page. Not a reader's.
	 *
	 * It answers four questions and refuses to answer any others: did the runs
	 * work, which feeds are broken, how long each stage took, and how big the
	 * site is getting. Every number is read from the committed ledger - nothing
	 * here is derived at read time, which is what stops today's code quietly
	 * restating yesterday's figures.
	 *
	 * The run grid stays static. The telemetry viewport and the timing trend are
	 * hand-written SVG, so the console still reads with JavaScript off.
	 */
	import { base } from '$app/paths';
	import { axisLabels, CELL_PX, GAP_PX, type LabelAlign } from '$lib/charts/run-history';
	import StageTimings from '$lib/components/StageTimings.svelte';
	import ThroughputTrend from '$lib/components/ThroughputTrend.svelte';
	import Viewport from '$lib/components/Viewport.svelte';
	import type { Health } from './+page.server';

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
	/>

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

	{#if data.timingDays.length === 0}
		<p class="mt-10 text-[0.9375rem] text-text-secondary">
			No item timing has been recorded yet. The item-health ledger fills as runs publish.
		</p>
	{:else}
		<StageTimings days={data.timingDays} height={data.console.chart_height} />
	{/if}

	{#if data.throughputDays.length > 0}
		<ThroughputTrend
			days={data.throughputDays}
			height={data.console.chart_height}
			width={data.console.chart_width}
			reference={data.throughputReference}
		/>
	{/if}

	{#if data.scoreDays.length === 0}
		<p class="mt-10 text-[0.9375rem] text-text-secondary">
			Nothing has been scored yet. The score ledger fills as days publish.
		</p>
	{:else}
		<h2 class="mt-10 text-[1.0625rem] font-semibold text-text">Confidence and size</h2>
		<div class="mt-3 overflow-x-auto">
			<table class="w-full text-[0.8125rem]">
				<thead class="text-text-tertiary">
					<tr class="border-b border-rule text-start">
						<th class="py-2 text-start font-normal">Day</th>
						<th class="py-2 text-end font-normal">Mean faithfulness</th>
						<th class="py-2 text-end font-normal">High</th>
						<th class="py-2 text-end font-normal">Medium</th>
						<th class="py-2 text-end font-normal">Low</th>
					</tr>
				</thead>
				<tbody>
					{#each data.scoreDays as day (day.date)}
						<tr class="border-b border-rule">
							<td class="py-2">{day.date}</td>
							<td class="py-2 text-end tabular-nums">{day.meanHhem.toFixed(3)}</td>
							<td class="py-2 text-end tabular-nums">{day.bands.high}</td>
							<td class="py-2 text-end tabular-nums">{day.bands.medium}</td>
							<td class="py-2 text-end tabular-nums">{day.bands.low}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	{#if data.manifests.length > 0}
		<h2 class="mt-10 text-[1.0625rem] font-semibold text-text">Runs</h2>
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
</section>
