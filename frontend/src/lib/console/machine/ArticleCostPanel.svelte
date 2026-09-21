<script lang="ts">
	/** What one article costs the machine, as three prices with their ranges.
	 *
	 * An operator arrives at this page about to change something - the prompt,
	 * the model, or how many articles a day runs - and wants the bill before he
	 * pays it. A run total divided by the item count cannot disagree with the
	 * run total, so it answers nothing; these three are measured per article and
	 * printed as ranges, because the cheap article and the dear one are a long
	 * way apart and a single number reports neither end.
	 */
	import Panel from '$lib/components/Panel.svelte';
	import { seconds } from '$lib/charts/machine';
	import { grouped } from '$lib/charts/series';
	import {
		costTrack,
		runnerHourSeconds,
		type ArticleCost,
		type CostFigure
	} from '$lib/console/machine/article-cost';
	import type { ChartConfig } from '$lib/server/config';

	let {
		cost,
		days,
		windowDays,
		chart
	}: {
		cost: ArticleCost;
		days: number;
		windowDays: number;
		chart: ChartConfig;
	} = $props();

	/** Mebibytes, signed, because an article that gives memory back is a reading
	 * and printing it unsigned would turn a fall into a rise. */
	function mib(bytes: number | null): string {
		if (bytes === null) return '-';
		const value = bytes / 1024 / 1024;
		const sign = value > 0 ? '+' : value < 0 ? '-' : '';
		return `${sign}${grouped(Number(Math.abs(value).toFixed(1)))} MiB`;
	}

	/** How many articles a runner-hour buys at the middle figure.
	 *
	 * A share of an hour was the first thing printed here and it rounds to `0.0%`
	 * the moment an article is cheap, which reads as free. A count answers the
	 * question an operator actually came with - how many more of these fit in the
	 * hour I am paying for - and it never degenerates.
	 */
	function fits(hour: number, each: number): string {
		const many = hour / each;
		return many < 10 ? many.toFixed(1) : grouped(Math.round(many));
	}

	const processor = $derived(cost.processorSeconds);
	const model = $derived(cost.modelSeconds);
	const memory = $derived(cost.addedBytes);
	const hour = $derived(runnerHourSeconds(cost.processors));
	const tracks = $derived({
		processor: costTrack(processor, chart.width_px),
		model: costTrack(model, chart.width_px),
		memory: costTrack(memory, chart.width_px)
	});

	/** Which of the three states a figure is in. `unresolved` is the one worth
	 * separating: the item ledger answered and the second instrument did not, so
	 * the absence belongs to the machine record rather than to the article. */
	function state(figure: CostFigure): 'measured' | 'unresolved' | 'unrecorded' {
		if (figure.from > 0) return 'measured';
		return figure.outOf > 0 ? 'unresolved' : 'unrecorded';
	}
</script>

<div data-windowed="machine-article-cost" data-window-days={windowDays}>
	<Panel
		heading="h3"
		id="article-cost"
		title="What one article costs the machine"
		note="Processor time, added memory and model time for a single article, so a change to the prompt, the model or how many articles a day runs can be priced before the run that pays for it - over the last {windowDays} days."
	>
		<ul class="costs">
			<li
				data-article-cost="processor"
				data-cost-state={state(processor)}
				data-cost-low={processor.low ?? ''}
				data-cost-mid={processor.mid ?? ''}
				data-cost-high={processor.high ?? ''}
				data-cost-from={processor.from}
				data-cost-outof={processor.outOf}
				data-cost-processors={cost.processors.join(' ')}
			>
				<p class="name">Processor time</p>
				{#if processor.mid === null}
					<p class="value">-</p>
					<p class="reach">
						{#if processor.outOf > 0}
							{grouped(processor.outOf)} articles over these {days} days recorded the share of the
							processors they kept busy, and no machine record over the same days says how many
							processors that share was taken across, so this is a dash rather than a figure
							worked out from the runner we usually get.
						{:else}
							No article over these {days} days recorded both the share of the processors it kept
							busy and how long it ran, so there is no processor time to work out.
						{/if}
					</p>
				{:else}
					<p class="value" data-article-cost-value="processor">{seconds(processor.mid)}</p>
					{#if tracks.processor}
						<div
							class="track"
							data-cost-band={tracks.processor.drawn ? 'drawn' : 'none'}
							aria-hidden="true"
						>
							{#if tracks.processor.drawn}
								<span
									class="band"
									style="inset-inline-start:{tracks.processor.start};inline-size:{tracks
										.processor.length}"
								></span>
							{/if}
							<span class="mid" style="inset-inline-start:{tracks.processor.at}"></span>
						</div>
					{/if}
					<p class="reach">
						The middle article of {grouped(processor.from)}, which is the ones a machine record
						could be matched to out of {grouped(processor.outOf)} that recorded a busy share and a
						clock; the cheapest took {seconds(processor.low)} and the dearest {seconds(
							processor.high
						)}.
					</p>
					{#if hour !== null && processor.mid > 0}
						<p class="against">
							One hour of this runner supplies {grouped(hour)} processor-seconds across its {cost
								.processors.length === 1
								? `${cost.processors[0]} processors`
								: `smallest machine's ${Math.min(...cost.processors)} processors`}, which is {fits(
								hour,
								processor.mid
							)} articles at the middle figure above.
						</p>
					{/if}
				{/if}
			</li>

			<li
				data-article-cost="memory"
				data-cost-state={state(memory)}
				data-cost-low={memory.low ?? ''}
				data-cost-mid={memory.mid ?? ''}
				data-cost-high={memory.high ?? ''}
				data-cost-from={memory.from}
				data-cost-outof={memory.outOf}
				data-cost-shards={cost.shards}
			>
				<p class="name">Added memory</p>
				{#if memory.mid === null}
					<p class="value">-</p>
					<p class="reach">
						No shard over these {days} days recorded the model server's memory for two articles in a
						row, so there is no step from one article to the next to measure.
					</p>
				{:else}
					<p class="value" data-article-cost-value="memory">{mib(memory.mid)}</p>
					{#if tracks.memory}
						<div
							class="track"
							data-cost-band={tracks.memory.drawn ? 'drawn' : 'none'}
							aria-hidden="true"
						>
							{#if tracks.memory.drawn}
								<span
									class="band"
									style="inset-inline-start:{tracks.memory.start};inline-size:{tracks.memory
										.length}"
								></span>
							{/if}
							<span class="zero" style="inset-inline-start:{tracks.memory.zero}"></span>
							<span class="mid" style="inset-inline-start:{tracks.memory.at}"></span>
						</div>
					{/if}
					<p class="reach">
						The middle step of {grouped(memory.from)} taken inside {grouped(cost.shards)}
						{cost.shards === 1 ? 'shard' : 'shards'}; the largest fall was {mib(memory.low)} and the
						largest rise {mib(memory.high)}.
					</p>
					<p class="against">
						This is what the model server's memory did from one article of a shard to the next, not
						what it holds - a step below the zero mark is memory the server gave back, and a step is
						only ever taken between neighbours of one shard, because a new shard starts a new server
						and the first reading of it would be a restart rather than an article.
					</p>
				{/if}
			</li>

			<li
				data-article-cost="model"
				data-cost-state={state(model)}
				data-cost-low={model.low ?? ''}
				data-cost-mid={model.mid ?? ''}
				data-cost-high={model.high ?? ''}
				data-cost-from={model.from}
				data-cost-outof={model.outOf}
			>
				<p class="name">Model time</p>
				{#if model.mid === null}
					<p class="value">-</p>
					<p class="reach">
						No article over these {days} days recorded what the model spent reading its prompt and writing
						its reply.
					</p>
				{:else}
					<p class="value" data-article-cost-value="model">{seconds(model.mid)}</p>
					{#if tracks.model}
						<div
							class="track"
							data-cost-band={tracks.model.drawn ? 'drawn' : 'none'}
							aria-hidden="true"
						>
							{#if tracks.model.drawn}
								<span
									class="band"
									style="inset-inline-start:{tracks.model.start};inline-size:{tracks.model.length}"
								></span>
							{/if}
							<span class="mid" style="inset-inline-start:{tracks.model.at}"></span>
						</div>
					{/if}
					<p class="reach">
						The middle article of {grouped(model.from)}; the quickest took {seconds(model.low)} and the
						slowest {seconds(model.high)}.
					</p>
					<p class="against">
						Reading the prompt and writing the reply, as the model server itself timed them and added
						them up over whatever work the article needed.
					</p>
				{/if}
			</li>
		</ul>

		<p class="cannot" data-article-cost-open="memory-half">
			What this cannot say is which half of the model's work the added memory belongs to - the
			prompt it read, or the reply it wrote. One memory reading taken at each call boundary, instead
			of a single reading when the article ended, would settle it.
		</p>
		<p class="read" data-article-cost-rows={cost.rowsRead}>
			Read over {grouped(cost.rowsRead)} article rows of the item ledger.
		</p>
	</Panel>
</div>

<style>
	.costs {
		display: grid;
		gap: var(--space-4);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	@media (min-width: 60rem) {
		.costs {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
	}

	.costs > li {
		padding: var(--space-3);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-surface-sunken);
	}

	.name {
		margin: 0;
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--color-text-secondary);
	}

	.value {
		margin: var(--space-1) 0 0;
		font-size: var(--text-xl);
		font-weight: 600;
		font-variant-numeric: tabular-nums;
		color: var(--color-text);
	}

	/* The band is the two ends, the upright is the middle article, and the zero
	   mark is on the one track whose readings go below it. Drawn rather than
	   written out, because two ranges can be compared by looking and two
	   sentences cannot. */
	.track {
		position: relative;
		block-size: 10px;
		margin: var(--space-2) 0;
		border-radius: var(--radius-sm);
		background: var(--color-surface);
		box-shadow: inset 0 0 0 1px var(--color-rule);
	}

	.band {
		position: absolute;
		inset-block: 2px;
		border-radius: var(--radius-sm);
		background: var(--color-chart-1);
		opacity: 0.55;
	}

	.mid {
		position: absolute;
		inset-block: 0;
		inline-size: 2px;
		margin-inline-start: -1px;
		background: var(--color-accent-strong);
	}

	.zero {
		position: absolute;
		inset-block: -2px;
		inline-size: 1px;
		background: var(--color-rule-strong);
	}

	.reach,
	.against,
	.cannot,
	.read {
		margin: var(--space-2) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.against,
	.read {
		color: var(--color-text-tertiary);
	}

	.cannot {
		padding-top: var(--space-3);
		border-top: 1px solid var(--color-rule);
	}
</style>
