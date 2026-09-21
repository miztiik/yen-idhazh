<script lang="ts">
	/** The hardware the model ran on, and how much it varied.
	 *
	 * The pipeline has written one machine row per shard per run to
	 * `state/host-fingerprint/` and one row per item to `state/item-health/`, and
	 * until this page nothing had ever put the two together. That is not a
	 * cosmetic gap. Measured on the committed ledger, the fastest shard of a
	 * single run read its prompts 4.31x faster than the slowest shard of the SAME
	 * run, and every throughput figure this project has quoted was an average
	 * taken across that spread. So the shard is the unit on this page and every
	 * run figure carries how many shards it was made from.
	 *
	 * **Every figure over a span reads the control above it**, the same 7/14/30/90
	 * the other two routes carry and the same `idhazh:console-window` key, so a
	 * span picked on Pipelines is the span this route opens on. Each span is
	 * answered on the server, because the browser holds no ledger to re-aggregate.
	 *
	 * **A panel about one run does not follow it.** The shard board, the
	 * reading-against-writing split, the clock check and the latency curves are
	 * snapshots of one run or one day, and narrowing a span cannot narrow a
	 * single run. Each names what it is about instead.
	 *
	 * **Absence is drawn as absence.** `job_seconds` and `cpu_model` are empty on
	 * 24 of the 54 committed rows and the three host cells on 34 of them, because
	 * each landed on a day after the ledger started. Every one of those prints a
	 * dash or a sentence, never a zero: a server that read no tokens and a scrape
	 * that never happened are different facts.
	 *
	 * **A panel is a file**, under `$lib/console/machine/`, and this page decides
	 * only which of them run and in what order. The option a live chart hydrates
	 * from is rebuilt inside its own panel rather than handed over by `load`:
	 * everything a load returns is serialised into the prerendered document, and
	 * an option carries the magenta sentinels `toCssVariables` swaps out of the
	 * SVG - so passing one across would ship a colour no reader may ever see, and
	 * `charts.spec.ts` fails the build over exactly that. The server draws the
	 * SVG; the browser redraws from the same numbers.
	 */
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import PanelGroup from '$lib/components/PanelGroup.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import ContextCostPanel from '$lib/console/machine/ContextCostPanel.svelte';
	import CounterfactualCostPanel from '$lib/console/machine/CounterfactualCostPanel.svelte';
	import MachineCardsPanel from '$lib/console/machine/MachineCardsPanel.svelte';
	import MachineSplitPanel from '$lib/console/machine/MachineSplitPanel.svelte';
	import MemoryBoardPanel from '$lib/console/machine/MemoryBoardPanel.svelte';
	import NewestRunTailPanel from '$lib/console/machine/NewestRunTailPanel.svelte';
	import OutsideModelCallPanel from '$lib/console/machine/OutsideModelCallPanel.svelte';
	import PlatformMixPanel from '$lib/console/machine/PlatformMixPanel.svelte';
	import PromptCachePanel from '$lib/console/machine/PromptCachePanel.svelte';
	import ReadAgainstWrittenPanel from '$lib/console/machine/ReadAgainstWrittenPanel.svelte';
	import ShardBoardPanel from '$lib/console/machine/ShardBoardPanel.svelte';
	import TailTrendPanel from '$lib/console/machine/TailTrendPanel.svelte';
	import TwoClocksPanel from '$lib/console/machine/TwoClocksPanel.svelte';

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

	/** Nothing on this route is fetched. Every span it can draw is already
	 * inlined, so no preset costs a month file and none of them is priced. */
	function monthsFor(): number {
		return 0;
	}

	/** Every figure the open span answers, decided on the server for each span
	 * the control offers. The fallback is the span the document was drawn at, so
	 * a stored preset the config no longer offers cannot blank the page. */
	const view = $derived(
		data.windows[String(windowDays)] ?? data.windows[String(data.console.default_window_days)]
	);
</script>

<svelte:head>
	<title>Console: Hardware &mdash; {data.ui.site_title}</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<!-- The title, the strip and the band are the shell and live in
     `../+layout.svelte`. The control stays here because it governs this route's
     panels and nothing above them. -->
<div data-console-panels="machine">
	<WindowControl days={windowDays} {presets} {monthsFor} {ready} onChange={show} />

	<!-- One sentence, no chart. It is what stops this route reading as a page
	     about a machine nothing ran on. -->
	<p class="console-carry" data-console-carry="pipelines">
		{data.carries.machine}
		<a class="carry-link" href="{base}/console/">Pipelines &rarr;</a>
	</p>

	<p
		class="mt-4 text-[0.9375rem] text-text-secondary"
		data-machine="intro"
		data-windowed="machine-runs"
		data-window-days={windowDays}
	>
		{view.runsRead === 0
			? `No run in these ${view.days} days committed a counters row.`
			: `${view.runsRead} ${view.runsRead === 1 ? 'run' : 'runs'} in these ${view.days} days committed counters the model server wrote itself.`}
		{view.start} to {view.end}. Every figure below is the model server's own count, read at build
		time and published nowhere.
	</p>

	<!-- What the recording was doing, before anything says what it recorded.
	     None of these is an error and none is styled as one: each states a fact
	     about the instrument, at body size, in the route it governs. A day the
	     scrape never ran and a day the machine did nothing draw the same gap,
	     and only a sentence can tell them apart. -->
	{#if view.recording.off}
		<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="off">
			{view.recording.off}
		</p>
	{/if}
	{#if view.recording.sampled}
		<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="sampled">
			{view.recording.sampled}
		</p>
	{/if}
	{#if view.recording.startedMidWindow}
		<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="started">
			{view.recording.startedMidWindow}
		</p>
	{/if}
	{#if view.recording.scoresOnly}
		<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="scores-only">
			{view.recording.scoresOnly}
		</p>
	{/if}
	<!-- The machine record is the other instrument on this route, so it gets its
	     own sentences rather than a share of the counters'. Its `off` state is not
	     printed here: the three panels it governs each say it where it bites, and
	     a banner across the page is what the per-instrument design refuses. -->
	{#if view.machineRecord.startedMidWindow}
		<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="machine-started">
			{view.machineRecord.startedMidWindow}
		</p>
	{/if}
	{#if view.machineRecord.recordDestroyed}
		<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="machine-destroyed">
			{view.machineRecord.recordDestroyed}
		</p>
	{/if}

	{#if view.refused.length > 0}
		<!-- Named, never dropped. A run count that quietly excludes one is a run
		     count nobody can check, and the cause is a real defect in how the
		     ledger is merged rather than a rendering choice. It follows the window
		     without declaring it: a clean span renders nothing at all, and a
		     surface that comes and goes cannot report a day count. -->
		<div class="refused" data-machine-refused={view.refused.length}>
			<p class="refused-head">
				{view.refused.length}
				{view.refused.length === 1 ? 'run is' : 'runs are'} left out of every windowed figure on this
				page.
			</p>
			<ul>
				{#each view.refused as run (run.runId)}
					<li data-refused-run={run.runId}>
						<strong>{run.runId}</strong> holds {run.rows} rows: {run.why}. Summing them would
						report a machine that never existed, so nothing here reads the run at all.
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	<!-- The panels each name their own grain in their own subtitle, so the page
	     no longer explains which of them the control above reaches. What is left
	     is the one fact a panel cannot state for itself: which run "the newest
	     run" currently is. -->
	{#if data.newestRunId !== null}
		<p class="mt-4 text-[0.8125rem] text-text-tertiary" data-window-exempt="newest-run">
			The newest run the counters hold is {data.newestRunId}.
		</p>
	{/if}

	<!-- The route's own running order lives in `config/appearance.json`, not in
	     the order these panels happen to be imported in. Each heading names a
	     decision an operator takes rather than a time grain: a grain is a fact
	     about one panel, and a heading that carries it answers no question
	     anybody arrives with. The first panel of the first group is the one that
	     says whether the rest can be trusted. -->
	{#snippet panelFor(id: string)}
		{#if id === 'shard-board'}
			<ShardBoardPanel board={data.board} timeoutMinutes={data.shardTimeoutMinutes} />
		{:else if id === 'memory-board'}
			<MemoryBoardPanel board={data.memory} span={view.peakRssSpan} windowDays={view.days} />
		{:else if id === 'reading-against-writing'}
			<MachineSplitPanel split={data.split} />
		{:else if id === 'prompt-cache'}
			<PromptCachePanel
				cacheDays={view.cacheDays}
				days={view.days}
				{windowDays}
				svg={data.cacheSvg}
				chart={data.chart}
			/>
		{:else if id === 'context-headroom'}
			<ContextCostPanel
				rows={data.series.context}
				start={view.start}
				end={view.end}
				contextWindow={data.contextWindow}
				cost={view.context}
				modelChanges={data.modelChanges}
				chart={data.chart}
				{windowDays}
				days={view.days}
			/>
		{:else if id === 'two-clocks'}
			<TwoClocksPanel
				clocks={data.clocks}
				svg={data.clocksSvg}
				tolerancePct={data.clocksTolerancePct}
				chart={data.chart}
			/>
		{:else if id === 'machine-cards'}
			<MachineCardsPanel machines={data.machines} />
		{:else if id === 'platform-mix'}
			<PlatformMixPanel
				fleet={view.fleet}
				machineRecord={view.machineRecord}
				svg={data.fleetSvg}
				grid={data.fleetGrid}
				chart={data.chart}
				{windowDays}
			/>
		{:else if id === 'outside-the-model-call'}
			<OutsideModelCallPanel
				cpuBusy={data.host.cpuBusy}
				modelLoad={data.host.modelLoad}
				cpuBusySpan={view.cpuBusySpan}
				modelLoadSpan={view.modelLoadSpan}
				parallelSlots={view.parallelSlots}
				chartWidthPx={data.chart.width_px}
				{windowDays}
				days={view.days}
			/>
		{:else if id === 'tail-trend'}
			<TailTrendPanel
				rows={data.series.latency}
				start={view.start}
				end={view.end}
				modelChanges={data.modelChanges}
				chart={data.chart}
				{windowDays}
				days={view.days}
				floor={data.latency.floor}
				tooFew={data.latency.tooFew}
			/>
		{:else if id === 'newest-run-tail'}
			<NewestRunTailPanel
				newestTail={data.newestTail}
				svg={data.percentileSvg}
				floor={data.latency.floor}
				shardRows={data.latency.shardRows}
				itemRows={data.latency.itemRows}
				chart={data.chart}
			/>
		{:else if id === 'read-against-written'}
			<ReadAgainstWrittenPanel
				runs={view.tokens}
				work={view.work}
				totals={view.tokenTotals}
				svg={data.workSvg}
				grid={data.workGrid}
				chart={data.chart}
				{windowDays}
				days={view.days}
			/>
		{:else if id === 'counterfactual-cost'}
			<CounterfactualCostPanel
				runs={view.tokens}
				totals={view.tokenTotals}
				configured={data.rate}
				svg={data.costSvg}
				grid={data.costGrid}
				chart={data.chart}
				{windowDays}
				days={view.days}
			/>
		{/if}
	{/snippet}

	{#each data.panelGroups as group (group.id)}
		<PanelGroup id={group.id} title={group.title} panels={group.panels.length}>
			{#each group.panels as id (id)}{@render panelFor(id)}{/each}
		</PanelGroup>
	{/each}
</div>

<style>
	.refused {
		margin-top: var(--space-4);
		padding: var(--space-4);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-lg);
		background: var(--tint-warn);
	}

	.refused-head {
		margin: 0 0 var(--space-2);
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--color-text);
	}

	.refused ul {
		margin: 0;
		padding-inline-start: var(--space-5);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
</style>
