<script lang="ts">
	/** What is holding the machine's memory, one day at a time.
	 *
	 * The arithmetic and the reasons are in `memory-held.ts`. Everything this
	 * file adds is the drawing: segments a reader may add, two brackets drawn
	 * overlapping so that they cannot be, and the swap ruled underneath on a
	 * scale of its own.
	 *
	 * **The brackets are not inside the held segment, and that is measured.** The
	 * model server's resident set is larger than everything the kernel calls held
	 * on **375 of 378 committed rows, measured 2026-09-21** - a median of 75.5
	 * percent of the machine against 52.3 percent held. So a bracket is drawn
	 * against the whole bar from its origin, which is what makes *at most* a true
	 * word: most of the difference is the mapped weight file, resident in the
	 * server and reclaimable by the kernel at the same time.
	 */
	import Panel from '$lib/components/Panel.svelte';
	import { memoryHeldWithin, type MemoryHeldRecord } from '$lib/console/machine/memory-held';

	let {
		record,
		start,
		end,
		days
	}: {
		record: MemoryHeldRecord;
		start: string;
		end: string;
		days: number;
	} = $props();

	const view = $derived(memoryHeldWithin(record, start, end));
</script>

<Panel
	heading="h3"
	id="memory-held"
	title="What is holding the machine's memory"
	note="The two parts of the bar add up to the machine and the two brackets under it do not, which is why they are drawn overlapping rather than side by side - one bar for the tightest moment of each day, over the last {days} days."
	wide
>
	{#if view.empty}
		<p class="empty" data-machine-panel-empty="memory-held">
			{#if record.firstDate === null}
				No day this ledger holds recorded what the machine itself had, so there is nothing to
				split up. Read over {record.daysRead} days.
			{:else}
				No day in these {days} days recorded what the machine itself had. The reading begins on
				{record.firstDate}.
			{/if}
		</p>
	{:else}
		<ul class="days" data-memory-days={view.days.length}>
			{#each view.days as day (day.date)}
				<li class="day" data-memory-day={day.date} data-memory-shape={day.shape}>
					<p class="when">
						<time datetime={day.date}>{day.date}</time>
						<span class="inline-quiet">
							at its tightest moment, in
							<span data-memory-item={day.itemId}>{day.itemId}</span>, on a
							{day.totalFigure} machine
						</span>
					</p>

					<div
						class="bar"
						role="img"
						data-memory-bar={day.date}
						data-memory-total={day.totalBytes}
						data-memory-scale={day.scaleBytes}
						aria-label={day.segments
							.map((segment) => `${segment.label}, ${segment.figure}`)
							.join('; ')}
					>
						{#each day.segments as segment (segment.key)}
							<span
								class="segment {segment.key}"
								style="width: {segment.width}"
								data-memory-segment={segment.key}
								data-memory-bytes={segment.bytes}
							></span>
						{/each}
						{#if day.overBytes > 0}
							<span
								class="edge"
								style="inset-inline-start: {day.machineWidth}"
								data-memory-machine-edge={day.machineWidth}
							></span>
						{/if}
					</div>

					<ul class="keys">
						{#each day.segments as segment (segment.key)}
							<li>
								<span class="swatch {segment.key}"></span>
								{segment.label} <strong>{segment.figure}</strong>
							</li>
						{/each}
					</ul>

					{#if day.overBytes > 0}
						<p class="disagree" data-memory-over-bytes={day.overBytes}>
							These parts run <strong>{day.overFigure}</strong> past the machine. The two own-memory
							readings were taken as the article finished and what the kernel reported was taken a
							moment later, so the two disagree by that much. The bar is drawn past its edge rather
							than trimmed, because trimming it would delete the finding.
						</p>
					{/if}

					{#if day.brackets.length > 0}
						<div class="brackets" data-memory-brackets={day.brackets.length}>
							{#if day.overlapBytes > 0}
								<span
									class="shared"
									style="width: {day.overlapWidth}"
									data-memory-overlap={day.overlapBytes}
								></span>
							{/if}
							{#each day.brackets as bracket (bracket.key)}
								<p class="bracket" data-memory-bracket={bracket.key}>
									<span
										class="reach {bracket.key}"
										style="width: {bracket.width}"
										data-memory-bracket-bar={bracket.key}
									></span>
									<span class="tag">{bracket.label} <strong>{bracket.figure}</strong></span>
								</p>
							{/each}
						</div>
						{#if day.overlapBytes > 0}
							<p class="overlap">
								The tinted stretch is the {day.overlapFigure} both brackets claim at once. Adding them
								would count it twice.
							</p>
						{/if}
					{/if}

					{#if day.swap !== null}
						<p class="swap" data-memory-swap-used={day.swap.usedBytes}>
							<span class="swap-track">
								<span class="swap-fill" style="width: {day.swap.width}"></span>
							</span>
							{#if day.swap.none}
								Nothing had been pushed out to disk, out of {day.swap.totalFigure} the machine keeps
								for it.
							{:else}
								<strong>{day.swap.usedFigure}</strong> had been pushed out to disk, out of
								{day.swap.totalFigure} the machine keeps for it.
							{/if}
						</p>
					{/if}
				</li>
			{/each}
		</ul>

		<p class="reads" data-memory-shapes="{view.fourShape}/{view.twoShape}">
			{#if view.fourShape > 0 && view.twoShape > 0}
				{view.fourShape} of these days split the held part into what each process holds on its own;
				the other {view.twoShape} draw one held part, because the run that wrote them recorded no
				such reading.
			{:else if view.fourShape > 0}
				Every day here splits the held part into what each process holds on its own.
			{:else}
				Every day here draws one held part rather than splitting it, because no run that wrote
				these days recorded what each process holds on its own.
			{/if}
		</p>

		<p class="reads">
			The weight file is read off disk rather than loaded into memory, so its pages sit inside the
			model server's bracket and inside the part the kernel can take back, at the same moment. That
			is the one thing this panel cannot separate: the two brackets may not be added to each other,
			and neither may be added to a part of the bar.
		</p>

		{#if record.firstDate !== null}
			<p class="reads" data-memory-begins={record.firstDate}>
				The machine's own reading begins on {record.firstDate}, over {record.daysRead} days of
				ledger; a day before it draws no bar rather than an empty one.
			</p>
		{/if}
	{/if}
</Panel>

<style>
	.empty,
	.reads,
	.overlap,
	.inline-quiet {
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.empty,
	.reads {
		margin: var(--space-3) 0 0;
	}

	.overlap {
		margin: var(--space-2) 0 0;
	}

	.days {
		margin: var(--space-3) 0 0;
		padding: 0;
		list-style: none;
		display: grid;
		gap: var(--space-5);
	}

	.when {
		margin: 0 0 var(--space-2);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text);
	}

	.bar {
		position: relative;
		display: flex;
		height: var(--space-5);
		border-radius: var(--radius-sm);
		overflow: hidden;
		background: var(--color-surface-sunken);
	}

	.segment {
		display: block;
		height: 100%;
	}

	.segment.free,
	.swatch.free {
		background: var(--color-surface-sunken);
		box-shadow: inset 0 0 0 1px var(--color-rule);
	}

	.segment.held,
	.swatch.held,
	.segment.server,
	.swatch.server {
		background: var(--chart-1);
	}

	.segment.worker,
	.swatch.worker {
		background: var(--chart-3);
	}

	.segment.rest,
	.swatch.rest {
		background: var(--chart-4);
	}

	/* Where the parts ran past the machine, this is where the machine ended. */
	.edge {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 2px;
		background: var(--color-text);
	}

	.keys {
		margin: var(--space-2) 0 0;
		padding: 0;
		list-style: none;
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2) var(--space-4);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.swatch {
		display: inline-block;
		width: 0.75rem;
		height: 0.75rem;
		margin-inline-end: var(--space-2);
		border-radius: 2px;
		vertical-align: -0.1rem;
	}

	.brackets {
		position: relative;
		margin: var(--space-3) 0 0;
	}

	/* What both brackets claim at once, drawn across both rows so the overlap is
	   something a reader sees rather than something they are told. */
	.shared {
		position: absolute;
		inset-block: 0;
		inset-inline-start: 0;
		background: var(--tint-warn);
		border-inline-end: 1px dashed var(--color-rule-strong);
	}

	.bracket {
		position: relative;
		margin: 0 0 var(--space-2);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.reach {
		display: block;
		height: 4px;
		border-radius: 2px;
		border-inline-start: 2px solid var(--color-text);
		border-inline-end: 2px solid var(--color-text);
		background: var(--color-rule-strong);
	}

	.tag {
		display: block;
		margin-top: 2px;
	}

	.disagree {
		margin: var(--space-2) 0 0;
		padding: var(--space-2) var(--space-3);
		border-radius: var(--radius-sm);
		background: var(--tint-warn);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text);
	}

	.swap {
		margin: var(--space-2) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.swap-track {
		display: block;
		height: 4px;
		margin-bottom: 2px;
		border-radius: 2px;
		background: var(--color-surface-sunken);
		box-shadow: inset 0 0 0 1px var(--color-rule);
	}

	.swap-fill {
		display: block;
		height: 100%;
		border-radius: 2px;
		background: var(--color-text-tertiary);
	}
</style>
