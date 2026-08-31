<script lang="ts">
	/** The hardware the model ran on, and how much it varied.
	 *
	 * The pipeline has written one row per shard per run to
	 * `state/runtime-counters.csv` since 2026-08-26 and, until this page, nothing
	 * had ever drawn a cell of it. That is not a cosmetic gap. Measured on the
	 * committed ledger, the fastest shard of a single run read its prompts 4.31x
	 * faster than the slowest shard of the SAME run, and every throughput figure
	 * this project has quoted was an average taken across that spread. So the
	 * shard is the unit on this page and every run figure carries how many shards
	 * it was made from.
	 *
	 * **Every figure here reads one fixed span**, `console.default_window_days`.
	 * This route has no days control yet - the choice on Pipelines and Model
	 * governs nothing here - so the span is stated in words instead of offered as
	 * a control. A figure whose span a reader cannot see is worse than one he
	 * cannot change, and the bound is what stops a chart growing a column per run
	 * forever.
	 *
	 * **Absence is drawn as absence.** `job_seconds` and `cpu_model` are empty on
	 * 24 of the 54 committed rows and the three host cells on 34 of them, because
	 * each landed on a day after the ledger started. Every one of those prints a
	 * dash or a sentence, never a zero: a server that read no tokens and a scrape
	 * that never happened are different facts.
	 */
	import { base } from '$app/paths';
	import Chart from '$lib/charts/Chart.svelte';
	import ConsoleBand from '$lib/components/ConsoleBand.svelte';
	import ConsoleNav from '$lib/components/ConsoleNav.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import RateControl from '$lib/components/RateControl.svelte';
	import ShapeSwitch from '$lib/components/ShapeSwitch.svelte';
	import ShardBoard from '$lib/components/ShardBoard.svelte';
	import TargetBar from '$lib/components/TargetBar.svelte';
	import {
		cacheChart,
		cacheColumns,
		clockColumns,
		clocksChart,
		costOf,
		gib,
		money,
		percentileChart,
		percentileColumns,
		tokenChart,
		RUNNER_MEMORY_BYTES
	} from '$lib/charts/machine';
	import { grouped } from '$lib/charts/series';
	import { columnStrip } from '$lib/charts/frame';
	import { targetMarks } from '$lib/charts/targetbar';
	import type { StackShape } from '$lib/charts/stacked';

	let { data } = $props();

	// The option a live chart hydrates from is rebuilt here rather than handed
	// over by `load`. Everything a load returns is serialised into the prerendered
	// document, and an option carries the magenta sentinels `toCssVariables` swaps
	// out of the SVG - so passing one across would ship a colour no reader may
	// ever see, and `charts.spec.ts` fails the build over exactly that. The server
	// draws the SVG; the browser redraws from the same numbers.
	//
	// The cache chart is the one that takes a shape. The server drew stacked, so
	// the first paint matches the prerendered document; picking `Lines` redraws
	// the identical values with no transform between them.
	let cacheShape = $state<StackShape>('bars');
	const cacheOption = $derived(cacheChart(data.cacheDays, cacheShape).option);
	const clocksOption = $derived(clocksChart(data.clocks.pairs).option);
	const percentileOption = $derived(percentileChart(data.percentiles.curves).option);
	const inputOption = $derived(
		tokenChart(data.tokens, (run) => run.input, 'prompt tokens', '--chart-1').option
	);
	const outputOption = $derived(
		tokenChart(data.tokens, (run) => run.output, 'written tokens', '--chart-4').option
	);

	// The strips under every chart that has a column to land on. Built here from
	// the same arrays the options are, so a column the strip prints and a column
	// the chart drew can never be two different columns.
	const cacheStrip = $derived(cacheColumns(data.cacheDays));
	const clockStrip = $derived(clockColumns(data.clocks.pairs));
	const percentileStrip = $derived(percentileColumns(data.percentiles.curves));
	/** The insets `percentileChart` draws its grid at. The strip's column centres
	 * are computed from them, so a pointer and the strip agree. */
	const PERCENTILE_GRID = { left: 60, right: 44 };
	/** The same, for the two token charts. */
	const TOKEN_GRID = { left: 62, right: 12 };
	/** One series each, and each still earns a strip: a run id is turned 45
		* degrees on the axis and thinned when the runs crowd, so the bar a pointer
		* is on is the one place its run and its count can be read together. */
	const tokenRuns = $derived(data.tokens.map((run) => run.runId));
	const inputStrip = $derived(
		columnStrip(tokenRuns, [
			{
				label: 'Prompt tokens',
				colour: 'var(--chart-1)',
				value: (index) => grouped(data.tokens[index]?.input ?? 0)
			},
			{
				label: 'Items that reported both counts',
				colour: '',
				value: (index) => grouped(data.tokens[index]?.items ?? 0)
			}
		])
	);
	const outputStrip = $derived(
		columnStrip(tokenRuns, [
			{
				label: 'Written tokens',
				colour: 'var(--chart-4)',
				value: (index) => grouped(data.tokens[index]?.output ?? 0)
			},
			{
				label: 'Items that reported both counts',
				colour: '',
				value: (index) => grouped(data.tokens[index]?.items ?? 0)
			}
		])
	);

	// One shared rate for every cost figure below. It starts at the configured
	// pair so the first paint matches the prerendered document, and `RateControl`
	// replaces it on mount if the operator has typed one before. Deliberately not
	// derived: after mount the operator owns these two numbers, not the payload.
	// svelte-ignore state_referenced_locally
	let inputRate = $state(data.rate.inputPerMillion);
	// svelte-ignore state_referenced_locally
	let outputRate = $state(data.rate.outputPerMillion);
	let rateSource = $state<'configured' | 'yours'>('configured');

	const rate = $derived({
		currency: data.rate.currency,
		inputPerMillion: inputRate,
		outputPerMillion: outputRate
	});
	const inputCost = $derived(costOf({ input: data.tokenTotals.input, output: 0 }, rate));
	const outputCost = $derived(costOf({ input: 0, output: data.tokenTotals.output }, rate));
	const totalCost = $derived(inputCost + outputCost);
	const perArticle = $derived(
		data.tokenTotals.items === 0 ? null : totalCost / data.tokenTotals.items
	);
	const memory = $derived(
		targetMarks(data.host.peakRss?.value ?? null, RUNNER_MEMORY_BYTES, 'lower-is-better')
	);
</script>

<svelte:head>
	<title>Console: Machine &mdash; {data.ui.site_title}</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<section class="py-6" data-surface="operator" data-console-route="machine">
	<h1 class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text">Console</h1>
	<p class="mt-1 text-[0.9375rem] text-text-secondary">
		The hardware the model ran on, and how much it varied between runs.
	</p>

	<ConsoleBand band={data.band}>
		{#snippet window()}
			<!-- No control, and the sentence says what governs the figures instead.
			     A control that governs nothing is worse than an absent one: it
			     answers a click by changing nothing and leaves the operator to work
			     out why. -->
			<p class="mt-5 text-[0.8125rem] text-text-tertiary" data-band-window="none">
				Every figure on this route reads a fixed {data.window.days} days, {data.window.start} to
				{data.window.end}. There is no days control here yet; the one on
				<a class="text-accent hover:underline" href="{base}/console/">Pipelines</a>
				and
				<a class="text-accent hover:underline" href="{base}/console/model/">Model</a>
				governs those two and is remembered between them.
			</p>
		{/snippet}
	</ConsoleBand>
	<ConsoleNav routes={data.routes} active="machine" />

	<!-- One sentence, no chart. It is what stops this route reading as a page
	     about a machine nothing ran on. -->
	<p class="console-carry" data-console-carry="pipelines">
		{data.carries.machine}
		<a class="carry-link" href="{base}/console/">Pipelines &rarr;</a>
	</p>

	<p class="mt-4 text-[0.9375rem] text-text-secondary" data-machine="intro">
		{data.runsRead === 0
			? `No run in these ${data.window.days} days committed a counters row.`
			: `${data.runsRead} ${data.runsRead === 1 ? 'run' : 'runs'} in these ${data.window.days} days committed counters the model server wrote itself.`}
		Every figure below is the model server's own count, read at build time and published nowhere.
	</p>

	<!-- What the recording was doing, before anything says what it recorded.
	     None of these is an error and none is styled as one: each states a fact
	     about the instrument, at body size, in the route it governs. A day the
	     scrape never ran and a day the machine did nothing draw the same gap,
	     and only a sentence can tell them apart. -->
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
	{#if data.recording.startedMidWindow}
		<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="started">
			{data.recording.startedMidWindow}
		</p>
	{/if}
	{#if data.recording.scoresOnly}
		<p class="mt-3 text-[0.9375rem] text-text-secondary" data-recording="scores-only">
			{data.recording.scoresOnly}
		</p>
	{/if}

	{#if data.refused.length > 0}
		<!-- Named, never dropped. A run count that quietly excludes one is a run
		     count nobody can check, and the cause is a real defect in how the
		     ledger is merged rather than a rendering choice. -->
		<div class="refused" data-machine-refused={data.refused.length}>
			<p class="refused-head">
				{data.refused.length}
				{data.refused.length === 1 ? 'run is' : 'runs are'} left out of every figure on this page.
			</p>
			<ul>
				{#each data.refused as run (run.runId)}
					<li data-refused-run={run.runId}>
						<strong>{run.runId}</strong> holds {run.rows} rows: {run.why}. Summing them would
						report a machine that never existed, so nothing here reads the run at all.
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	<Panel
		title="Shards of the newest run"
		note="One row per shard, ranked by how long its job took. It answers whether a slow day was the work or the machine: a long bar at a normal read rate is a lot of articles, and a long bar at a quarter of its neighbour's read rate is the host."
		wide
	>
		<ShardBoard board={data.board} timeoutMinutes={data.shardTimeoutMinutes} />
	</Panel>

	<Panel
		title="Reading against writing"
		note="Two rows over the same shards: how the model server's seconds split, and how its tokens split. Read the mismatch between them - that is the price of a written token."
	>
		{#if data.split.empty}
			<p class="empty" data-machine-panel-empty="reading-writing">
				No shard of the newest run reported all four counters, so there is nothing to split.
			</p>
		{:else}
			<div class="splits" data-reading-writing={data.split.runId}>
				{#each data.split.rows as row (row.label)}
					<div class="split-row" data-split-row={row.label} data-split-read-pct={row.readPct}>
						<p class="split-head">
							<span>{row.label}</span>
							<span class="tabular-nums">{row.totalText}</span>
						</p>
						<div
							class="track"
							role="img"
							aria-label="{row.label}: {row.readText} reading against {row.writeText} writing, {row.readPct} percent of it reading."
						>
							<span class="seg read" style="inline-size: {row.readWidth}"></span>
							<span class="seg write" style="inline-size: {row.writeWidth}"></span>
						</div>
						<p class="split-legend">
							<span class="key read"></span>reading {row.readText} ({row.readPct}%)
							<span class="key write"></span>writing {row.writeText} ({100 - row.readPct}%)
						</p>
					</div>
				{/each}
			</div>
			<p class="reads" data-reading-writing-sentence>
				Reading took {data.split.rows[0].readPct} percent of the seconds and
				{data.split.rows[1].readPct} percent of the tokens.
				{#if data.split.readTokensPerSecond !== null && data.split.writeTokensPerSecond !== null}
					Reading runs at {data.split.readTokensPerSecond.toFixed(2)} tokens a second and writing at
					{data.split.writeTokensPerSecond.toFixed(2)}, so a written token costs
					<strong>{(data.split.writeCostRatio ?? 0).toFixed(1)}x</strong> a read one.
				{/if}
				Over {data.split.from} of the run's {data.split.outOf} shards.
			</p>
		{/if}
	</Panel>

	<Panel
		title="Prompt cache"
		note="Prompt tokens the server read, against the ones it reused instead of reading. Read whether a bigger cache would save wall clock."
	>
		{#if data.cacheSvg === null}
			<p class="empty" data-machine-panel-empty="cache">
				No run in these {data.window.days} days reported both a read count and a cached count, so there
				is no split to draw.
			</p>
		{:else}
			<Chart
				svg={data.cacheSvg}
				option={cacheOption}
				width={data.chart.width_px}
				height={data.chart.height_px}
				label="Prompt tokens per day, split into the tokens the model server read and the tokens it served from its own cache. One column is one day."
				columns={cacheStrip}
				readoutName="cache"
				readoutMaxShare={data.chart.readout_max_share}
				restingNote=", the newest day"
				hint="Point at a day to read both halves. Left and Right step through the days, Escape returns to the newest."
			/>
			<!-- Stacked says how many prompt tokens the day needed; lines say whether
			     the read half fell while the cached half rose. One array, two shapes,
			     nothing re-shaped between them. -->
			<ShapeSwitch bind:shape={cacheShape} name="cache" label="How to draw the prompt cache" />
			<!-- No threshold marker and no tint. Nobody has agreed a floor for this,
			     and a tint would invent one and publish it. -->
			<ul class="shares" data-cache-days>
				{#each data.cacheDays as day (day.date)}
					<li data-cache-day={day.date} data-cache-pct={day.cachedPct ?? ''}>
						<strong>{day.date}</strong>: the cache covered {day.cachedPct}% of the
						{grouped(day.read + day.cached)} prompt tokens
						{day.runs === 1 ? 'that run' : `those ${day.runs} runs`} needed.
					</li>
				{/each}
			</ul>
		{/if}
	</Panel>

	<Panel
		title="Context headroom"
		note="The longest sequence each run saw, prompt and answer together, against the window the server was given. This is the panel that says whether raising the truncation cap is even possible."
	>
		{#if data.context.length === 0}
			<p class="empty" data-machine-panel-empty="context">
				No run in these {data.window.days} days recorded a longest sequence.
			</p>
		{:else}
			<div class="bars" data-context-window={data.contextWindow}>
				{#each data.context as bar (bar.runId)}
					<div data-context-run={bar.runId} data-context-longest={bar.longest ?? ''}>
						<TargetBar
							marks={bar.marks}
							label={bar.runId}
							valueText="{grouped(bar.longest ?? 0)} tokens"
							targetText="of the {grouped(data.contextWindow)}-token window - {bar.usedPct}% used, {grouped(
								bar.spare ?? 0
							)} spare, over {bar.from} of {bar.outOf} shards"
							emptyNote="This run recorded no sequence length."
						/>
					</div>
				{/each}
			</div>
		{/if}
	</Panel>

	<Panel
		title="Do the two clocks agree"
		note="Prompt tokens a second, counted twice: once by the item ledger and once by the model server itself. The runtime ledger was created for this check and nothing performed it on a screen. A day where the two disagree is a day whose rates cannot be trusted."
	>
		{#if data.clocksSvg === null}
			<p class="empty" data-machine-panel-empty="clocks">
				One of the two instruments recorded nothing for the newest run, so there is nothing to
				compare. That is a missing reading, not an agreement.
			</p>
		{:else}
			<Chart
				svg={data.clocksSvg}
				option={clocksOption}
				width={data.chart.width_px}
				height={data.chart.height_px}
				label="Prompt tokens a second as the item ledger counted them, beside the same figure as the model server counted it, per {data
					.clocks.grain}."
				columns={clockStrip}
				readoutName="clocks"
				readoutMaxShare={data.chart.readout_max_share}
				restingNote=", the last one"
				hint="Point at a {data.clocks.grain} to read both instruments. Left and Right step through them, Escape returns to the last."
			/>
			<ul class="shares" data-clock-pairs={data.clocks.grain}>
				{#each data.clocks.pairs as pair (pair.label)}
					<li data-clock-pair={pair.label} data-clock-gap={pair.gapPct?.toFixed(2) ?? ''}>
						<strong>{pair.label}</strong>:
						{#if pair.gapPct === null}
							one of the two instruments recorded nothing here.
						{:else}
							the ledger reads {(pair.ledger ?? 0).toFixed(2)} and the server
							{(pair.server ?? 0).toFixed(2)} tokens a second -
							<strong>{pair.gapPct.toFixed(2)}% apart</strong>,
							{pair.agrees ? 'inside' : 'past'} the {data.clocksTolerancePct}% the reconciliation
							audit allows.
						{/if}
					</li>
				{/each}
			</ul>
			<p class="reads" data-clock-grain={data.clocks.grain}>
				{#if data.clocks.grain === 'shard'}
					Compared per shard: all {data.clocks.itemRows} item rows of this run carry a shard.
				{:else}
					Compared per run, not per shard: {data.clocks.shardRows} of
					{data.clocks.itemRows} item rows of this run carry a shard, and a shard the ledger cannot
					name cannot be matched to the server that ran it.
				{/if}
			</p>
		{/if}
	</Panel>

	<Panel
		title="The host under the newest run"
		note="What the machine and the server did outside the model call. Each figure carries its ceiling: a counter without one is not a measurement."
	>
		<dl class="host">
			<div data-host="processors">
				<dt>Processors drawn</dt>
				<dd>
					{#if data.host.cpuModels === null || data.host.cpuModels.value === null}
						<span class="absent">Not recorded on this run.</span>
					{:else}
						{data.host.cpuModels.value.join('; ')}
						<span class="unit">
							over {data.host.cpuModels.from} of {data.host.cpuModels.outOf} shards
						</span>
					{/if}
				</dd>
			</div>

			<div data-host="cpu-busy" data-host-value={data.host.cpuBusy?.value ?? ''}>
				<dt>Least busy shard</dt>
				<dd>
					{#if data.host.cpuBusy === null || data.host.cpuBusy.value === null}
						<span class="absent">Not recorded on this run.</span>
					{:else}
						{data.host.cpuBusy.value.toFixed(2)}% of every processor second
						<span class="unit">
							Near 100 is the expected reading, so the gap is the share of that shard's job spent
							waiting rather than computing. Over these {data.window.days} days the lowest reading ran
							{(data.host.cpuBusySpan.low ?? 0).toFixed(2)}% to
							{(data.host.cpuBusySpan.high ?? 0).toFixed(2)}%, on
							{data.host.cpuBusySpan.from} of {data.host.cpuBusySpan.outOf} runs.
						</span>
					{/if}
				</dd>
			</div>

			<div data-host="peak-memory" data-host-value={data.host.peakRss?.value ?? ''}>
				<dt>Peak memory</dt>
				<dd>
					{#if data.host.peakRss === null || data.host.peakRss.value === null}
						<span class="absent">Not recorded on this run.</span>
					{:else}
						<TargetBar
							marks={memory}
							label="llama-server high-water mark"
							valueText={gib(data.host.peakRss.value)}
							targetText="of the runner's {gib(RUNNER_MEMORY_BYTES)} - {Math.round(
								(data.host.peakRss.value / RUNNER_MEMORY_BYTES) * 100
							)}%"
							emptyNote="This run recorded no memory high-water mark."
						/>
						<span class="unit">
							Highest over these {data.window.days} days: {gib(data.host.peakRssSpan.high)}, on
							{data.host.peakRssSpan.from} of {data.host.peakRssSpan.outOf} runs.
						</span>
					{/if}
				</dd>
			</div>

			<div data-host="model-load" data-host-value={data.host.modelLoad?.value ?? ''}>
				<dt>Opening the weights</dt>
				<dd>
					{#if data.host.modelLoad === null || data.host.modelLoad.value === null}
						<span class="absent">Not recorded on this run.</span>
					{:else}
						{grouped(Math.round(data.host.modelLoad.value))} ms on its slowest shard
						<span class="unit">
							Over these {data.window.days} days: {grouped(
								Math.round(data.host.modelLoadSpan.low ?? 0)
							)} to {grouped(Math.round(data.host.modelLoadSpan.high ?? 0))} ms, on
							{data.host.modelLoadSpan.from} of {data.host.modelLoadSpan.outOf} runs.
						</span>
					{/if}
				</dd>
			</div>

			<!-- One line of text, not a chart. It reads 1.0 on every row the ledger
			     holds because `models.inference.n_parallel` is 1, and it earns a
			     chart the day that knob moves. -->
			<div data-host="batching" data-batching={data.batching.highest ?? ''}>
				<dt>Batching</dt>
				<dd>
					{#if data.batching.highest === null}
						<span class="absent">No run in this span reported slots per decode.</span>
					{:else if data.batching.highest <= 1}
						Off; every decode served one request.
						<span class="unit">
							1.0 slot a decode on all {data.batching.from} of {data.batching.outOf} runs that
							reported it.
						</span>
					{:else}
						Up to {data.batching.highest.toFixed(2)} slots a decode.
						<span class="unit">Over {data.batching.from} of {data.batching.outOf} runs.</span>
					{/if}
				</dd>
			</div>
		</dl>
	</Panel>

	<Panel
		title="The shape of a run's latency"
		note="One curve per run, never pooled between them - two runs of one day draw different processors. Read two curves that cross: a tail changing shape is what no single figure says."
	>
		{#if data.percentileSvg === null}
			<p class="empty" data-machine-panel-empty="percentiles">
				{#if data.percentiles.date === null}
					No day in these {data.window.days} days recorded an item timing.
				{:else}
					No run on {data.percentiles.date} timed {data.percentiles.floor} items, which is the floor
					below which a p99 is just the last item.
				{/if}
			</p>
		{:else}
			<Chart
				svg={data.percentileSvg}
				option={percentileOption}
				width={data.chart.width_px}
				height={data.chart.height_px}
				label="Per-item model time at the 50th, 75th, 90th, 95th and 99th percentile, one line per run of {data
					.percentiles.date}."
				columns={percentileStrip}
				readoutName="percentiles"
				readoutMaxShare={data.chart.readout_max_share}
				grid={PERCENTILE_GRID}
				restingNote=", the slowest one in a hundred"
				hint="Point at a percentile to read every run at it. Left and Right step through them, Escape returns to p99."
			/>
			<p class="reads" data-percentile-note>
				{data.percentiles.curves.length}
				{data.percentiles.curves.length === 1 ? 'run' : 'runs'} of
				<strong>{data.percentiles.date}</strong>. The value is <code>summarize_ms</code>, the whole
				model call for one item, and a percentile is interpolated linearly between the two nearest
				ranks - at about a hundred items the nearest-rank rule and this one disagree by more than
				the difference between two runs, so the rule is named rather than assumed.
				{#if data.percentiles.tooFew.length > 0}
					{data.percentiles.tooFew.length}
					{data.percentiles.tooFew.length === 1 ? 'run' : 'runs'} timed fewer than
					{data.percentiles.floor} items and {data.percentiles.tooFew.length === 1 ? 'is' : 'are'}
					printed rather than drawn:
					{data.percentiles.tooFew.map((run) => `${run.runId} (${run.items})`).join(', ')}.
				{/if}
				{#if data.percentiles.shardRows === data.percentiles.itemRows && data.percentiles.itemRows > 0}
					Every item row of this day carries a shard, so a curve per shard is possible; twenty
					overlaid curves is not a chart, so the shard is the unit of the board above and of the
					clock check.
				{:else}
					{data.percentiles.shardRows} of {data.percentiles.itemRows} item rows of this day carry a
					shard, so the curve is per run.
				{/if}
			</p>
			<ul class="sr-only" data-percentile-values>
				{#each data.percentiles.curves as curve (curve.runId)}
					<li data-percentile-run={curve.runId}>
						{curve.runId}, {curve.items} items:
						{curve.points
							.map((point) => `p${point.percentile} ${(point.ms / 1000).toFixed(1)}s`)
							.join(', ')}.
					</li>
				{/each}
			</ul>
		{/if}
	</Panel>

	<Panel
		title="Tokens per run"
		note="Prompt tokens and written tokens, one bar per run. They are different quantities with different prices, so each carries its own axis."
	>
		{#if data.inputSvg === null || data.outputSvg === null}
			<p class="empty" data-machine-panel-empty="tokens">
				No run in these {data.window.days} days recorded both a prompt count and a written count.
			</p>
		{:else}
			<div class="pair">
				<figure class="pane" data-token-chart="input">
					<figcaption>Prompt tokens</figcaption>
					<Chart
						svg={data.inputSvg}
						option={inputOption}
						width={data.chart.width_px}
						height={data.chart.height_px}
						label="Prompt tokens each run sent to the model. One bar is one run."
						columns={inputStrip}
						readoutName="tokens-input"
						readoutMaxShare={data.chart.readout_max_share}
						grid={TOKEN_GRID}
						restingNote=", the last run"
						hint="Point at a run to read it. Left and Right step through them, Escape returns to the last."
					/>
				</figure>
				<figure class="pane" data-token-chart="output">
					<figcaption>Written tokens</figcaption>
					<Chart
						svg={data.outputSvg}
						option={outputOption}
						width={data.chart.width_px}
						height={data.chart.height_px}
						label="Tokens each run's answers were made of. One bar is one run."
						columns={outputStrip}
						readoutName="tokens-output"
						readoutMaxShare={data.chart.readout_max_share}
						grid={TOKEN_GRID}
						restingNote=", the last run"
						hint="Point at a run to read it. Left and Right step through them, Escape returns to the last."
					/>
				</figure>
			</div>
			<p class="reads" data-token-totals>
				{grouped(data.tokenTotals.input)} prompt tokens and {grouped(data.tokenTotals.output)}
				written, over {data.tokens.length}
				{data.tokens.length === 1 ? 'run' : 'runs'} and {grouped(data.tokenTotals.items)} items.
			</p>
		{/if}
	</Panel>

	<Panel
		title="What this would have cost somewhere else"
		note="A counterfactual, never a bill. Nothing bills us - Actions minutes are free on a public repository - which is why the wall clock alone cannot say whether the runner time was a good trade. Priced at a hosted provider's rate, it can."
		tone="info"
	>
		{#if data.tokens.length === 0}
			<p class="empty" data-machine-panel-empty="cost">
				No run in these {data.window.days} days recorded a token count, so there is nothing to price.
			</p>
		{:else}
			<RateControl configured={data.rate} bind:inputRate bind:outputRate bind:source={rateSource} />

			<dl class="cost" data-cost-figures data-cost-source={rateSource}>
				<div data-cost="input">
					<dt>Reading the prompts</dt>
					<dd class="tabular-nums">{money(inputCost, rate.currency, 2)}</dd>
				</div>
				<div data-cost="output">
					<dt>Writing the answers</dt>
					<dd class="tabular-nums">{money(outputCost, rate.currency, 2)}</dd>
				</div>
				<div data-cost="total">
					<dt>These {data.window.days} days</dt>
					<dd class="tabular-nums">{money(totalCost, rate.currency, 2)}</dd>
				</div>
				<div data-cost="per-article">
					<dt>An article</dt>
					<dd class="tabular-nums">
						{perArticle === null ? '-' : money(perArticle, rate.currency, 4)}
					</dd>
				</div>
			</dl>

			<p class="reads" data-cost-basis>
				What {data.tokens.length}
				{data.tokens.length === 1 ? 'run' : 'runs'} would have cost at that rate, if a hosted
				provider had done the work instead of the runner. It is not an amount owed and no invoice
				exists. The wall clock is the real budget and the shard board above draws it; this figure is
				the second unit, and it says whether that clock was worth spending.
			</p>
		{/if}
	</Panel>
</section>

<style>
	.empty {
		margin: var(--space-2) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

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

	.refused ul,
	.shares {
		margin: 0;
		padding-inline-start: var(--space-5);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.shares {
		margin-top: var(--space-3);
	}

	.splits {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	.split-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--space-3);
		margin: 0 0 var(--space-1);
		font-size: var(--text-sm);
		color: var(--color-text-secondary);
	}

	.track {
		display: flex;
		block-size: 18px;
		border-radius: var(--radius-full);
		background: var(--color-surface-sunken);
		overflow: hidden;
	}

	.seg {
		display: block;
		block-size: 100%;
	}

	.seg.read {
		background: var(--chart-1);
	}

	.seg.write {
		background: var(--chart-4);
	}

	.split-legend {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1) var(--space-3);
		margin: var(--space-1) 0 0;
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}

	.key {
		display: inline-block;
		inline-size: 10px;
		block-size: 10px;
		border-radius: 2px;
		margin-inline-end: 4px;
	}

	.key.read {
		background: var(--chart-1);
	}

	.key.write {
		background: var(--chart-4);
	}

	.reads {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.bars {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
		gap: var(--space-4) var(--space-5);
	}

	.host {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
		gap: var(--space-4) var(--space-5);
		margin: 0;
	}

	.host dt {
		font-size: var(--text-xs);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
	}

	.host dd {
		margin: var(--space-1) 0 0;
		font-size: var(--text-base);
		color: var(--color-text);
	}

	.unit {
		display: block;
		margin-top: var(--space-1);
		font-size: var(--text-xs);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}

	.absent {
		color: var(--color-text-tertiary);
	}

	.pair {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
		gap: var(--space-5);
	}

	.pane {
		margin: 0;
		min-inline-size: 0;
	}

	.pane figcaption {
		font-size: var(--text-xs);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
	}

	.cost {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
		gap: var(--space-4) var(--space-5);
		margin: var(--space-4) 0 0;
	}

	.cost dt {
		font-size: var(--text-xs);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
	}

	.cost dd {
		margin: var(--space-1) 0 0;
		font-size: var(--text-lg);
		font-weight: 600;
		color: var(--color-text);
	}
</style>
