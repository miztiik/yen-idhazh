<script lang="ts">
	/** The operator's page. Not a reader's.
	 *
	 * It answers three questions and refuses to answer any others: how long each
	 * stage took, how faithful the summaries were, and how big the site is
	 * getting. Every number is read from the committed ledger - nothing here is
	 * derived at read time, which is what stops today's code quietly restating
	 * yesterday's figures.
	 *
	 * Bars are plain divs. A charting library to draw ten rectangles would
	 * outweigh the data it draws.
	 */
	import { base } from '$app/paths';

	let { data } = $props();

	const stages = [
		{ key: 'fetchMs', label: 'fetch', colour: 'var(--band-low)' },
		{ key: 'extractMs', label: 'extract', colour: 'var(--band-medium)' },
		{ key: 'summarizeMs', label: 'summarize', colour: 'var(--accent)' },
		{ key: 'scoreMs', label: 'score', colour: 'var(--band-high)' }
	] as const;

	const worst = $derived(
		Math.max(
			1,
			...data.days.flatMap((day) => stages.map((stage) => day[stage.key] as number))
		)
	);

	function seconds(ms: number): string {
		return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`;
	}

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
	</p>

	{#if data.days.length === 0}
		<p class="mt-8 text-[0.9375rem] text-text-secondary">
			Nothing has been scored yet. The ledger fills as days publish.
		</p>
	{:else}
		<h2 class="mt-8 text-[1.0625rem] font-semibold text-text">Median seconds per item, by stage</h2>
		<p class="mt-1 text-[0.8125rem] text-text-tertiary">
			Median, not mean: one very slow host would otherwise describe the whole day. Only
			<em>summarize</em> moves when the model changes - the rest is the open web and our own extractor.
		</p>

		<div class="mt-4 space-y-5">
			{#each data.days as day (day.date)}
				<div>
					<div class="flex items-baseline justify-between text-[0.8125rem]">
						<a href="{base}/{day.date}/" class="text-accent hover:underline">{day.date}</a>
						<span class="text-text-tertiary">{day.items} scored</span>
					</div>
					<div class="mt-1 space-y-1">
						{#each stages as stage (stage.key)}
							{@const value = day[stage.key] as number}
							<div class="flex items-center gap-2 text-[0.75rem]">
								<span class="w-20 shrink-0 text-text-tertiary">{stage.label}</span>
								<div class="h-3 flex-1 overflow-hidden rounded-sm bg-surface">
									<div
										class="h-full rounded-sm"
										style="width: {Math.max((value / worst) * 100, value > 0 ? 1 : 0)}%; background: {stage.colour}"
									></div>
								</div>
								<span class="w-16 shrink-0 text-end tabular-nums text-text-secondary">
									{seconds(value)}
								</span>
							</div>
						{/each}
					</div>
				</div>
			{/each}
		</div>

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
					{#each data.days as day (day.date)}
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

		{#if data.manifests.length > 0}
			<h2 class="mt-10 text-[1.0625rem] font-semibold text-text">Runs</h2>
			<p class="mt-1 text-[0.8125rem] text-text-tertiary">
				Run-level facts live in the manifest, never in an item row. The site has a 1 GB
				ceiling; this is the number that says how close it is.
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
	{/if}
</section>
