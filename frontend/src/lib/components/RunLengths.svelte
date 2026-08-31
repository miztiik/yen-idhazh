<script lang="ts">
	/** How long the summaries came out, three marks a run.
	 *
	 * This replaces a mark per article. Over the committed ledger that was
	 * thousands of marks, and its dense middle rendered as a solid block - so the
	 * only marks anybody acts on, a summary of three words or one twice the
	 * length that was asked for, were the ones it hid. The lowest, the middle and
	 * the highest of a run keep both ends and lose the block.
	 *
	 * Per run and never per day. A day holds up to five runs, and a run is one
	 * model reading one set of articles under one set of settings, so it is the
	 * smallest thing on this page that a change can be attributed to.
	 *
	 * **The band is what the run's own articles were asked for**, read through
	 * each article's own length rather than off the setting: an article's length
	 * picks its band, so a run of short pieces is asked for less than a run of
	 * long ones. Its two bounds print beside the chart, because a shaded band
	 * with no printed bound cannot be checked.
	 *
	 * Hand-written SVG, so the chart is complete before any script runs.
	 */
	import { chartWidth, frame, linearAxis, observeWidth, type Margin } from '$lib/charts/frame';
	import { dayMonth } from '$lib/format';
	import type { RunLength } from '../../routes/console/model/+page.server';

	let {
		runs,
		width,
		height,
		tickDensity
	}: {
		/** Oldest first. The chart reads left to right. */
		runs: RunLength[];
		width: number;
		height: number;
		tickDensity: number;
	} = $props();

	const MARGIN: Margin = { top: 12, right: 12, bottom: 40, left: 38 };

	let measured = $state<number | null>(null);

	const box = $derived(frame(chartWidth(measured, width), height, MARGIN));

	const yAxis = $derived(
		linearAxis(
			runs.flatMap((run) => [
				run.low,
				run.high,
				...(run.askLow === null ? [] : [run.askLow]),
				...(run.askHigh === null ? [] : [run.askHigh])
			]),
			[box.bottom, box.top]
		)
	);

	/** One column per run, whatever the calendar did. Runs are not evenly spaced
	 * in time and drawing them as if they were would be a second claim the data
	 * does not make; the date labels below say which day each column is. */
	const pitch = $derived(runs.length === 0 ? box.innerWidth : box.innerWidth / runs.length);

	function columnX(index: number): number {
		return box.left + pitch * (index + 0.5);
	}

	function round(value: number): number {
		return Math.round(value * 10) / 10;
	}

	/** The widest each mark may be without two runs touching. */
	const markWidth = $derived(Math.max(3, Math.min(14, pitch - 3)));

	const placed = $derived(
		runs.map((run, index) => ({
			run,
			index,
			x: columnX(index),
			yLow: yAxis.scale(run.low),
			yMedian: yAxis.scale(run.median),
			yHigh: yAxis.scale(run.high),
			band:
				run.askLow === null || run.askHigh === null
					? null
					: { y: yAxis.scale(run.askHigh), height: Math.max(1, yAxis.scale(run.askLow) - yAxis.scale(run.askHigh)) }
		}))
	);

	/** The narrowest and the widest ask across everything drawn. Printed beside
	 * the chart, so the shaded region is a number a reader can check. */
	const askLow = $derived(
		runs.map((run) => run.askLow).filter((words): words is number => words !== null)
	);
	const askHigh = $derived(
		runs.map((run) => run.askHigh).filter((words): words is number => words !== null)
	);
	const ask = $derived(
		askLow.length === 0 || askHigh.length === 0
			? null
			: { low: Math.min(...askLow), high: Math.max(...askHigh) }
	);

	/** A rule between two neighbouring runs on different models. Everything left
	 * of it ran on the older id. It carries the date and the id and nothing
	 * else - a delta across it would claim the swap caused whatever moved.
	 *
	 * Keyed by the run it precedes rather than by its date: the model can change
	 * between two runs of one day, and two keys of one date would throw at
	 * hydration while the prerendered document looked perfect. */
	const swaps = $derived(
		runs
			.map((run, index) => ({ run, index }))
			.filter(
				({ run, index }) =>
					index > 0 &&
					run.model !== null &&
					runs[index - 1].model !== null &&
					run.model !== runs[index - 1].model
			)
			.map(({ run, index }) => ({
				runId: run.runId,
				at: box.left + pitch * index,
				model: run.model as string,
				date: run.date
			}))
	);

	/** One date label per day, thinned to the configured density. A run id is
	 * eighteen characters and there are five of them a day. */
	const labels = $derived(
		(() => {
			const firsts = runs
				.map((run, index) => ({ run, index }))
				.filter(({ run, index }) => index === 0 || runs[index - 1].date !== run.date);
			const step = Math.max(1, Math.ceil(firsts.length / Math.max(1, tickDensity)));
			return firsts
				.filter((_, position) => position % step === 0)
				.map(({ run, index }) => ({ date: run.date, x: columnX(index) }));
		})()
	);

	function sentence(run: RunLength): string {
		const asked =
			run.askLow === null || run.askHigh === null
				? 'No article in it recorded a length, so no ask can be read.'
				: `Asked for ${run.askLow} to ${run.askHigh} words.`;
		return `Run ${run.runId} on ${run.date}${run.model === null ? '' : `, ${run.model}`}: ${run.items} summaries, shortest ${run.low} words, middle ${run.median}, longest ${run.high}. ${asked}`;
	}

	const description = $derived(
		`Summary length per run over ${runs.length} runs, lowest, middle and highest of each. ` +
			(ask === null ? '' : `The shaded band is the ${ask.low} to ${ask.high} words the articles were asked for. `) +
			placed.map(({ run }) => sentence(run)).join(' ')
	);
</script>

<div class="plot" data-run-lengths="chart" data-run-lengths-runs={runs.length}>
	<div use:observeWidth={(next) => (measured = next)}>
		<svg
			class="block max-w-full"
			width={box.width}
			height={box.height}
			viewBox={`0 0 ${box.width} ${box.height}`}
			role="img"
			aria-label={description}
		>
			{#each yAxis.ticks as tick (tick)}
				<line
					x1={box.left}
					x2={box.right}
					y1={round(yAxis.scale(tick))}
					y2={round(yAxis.scale(tick))}
					stroke="var(--color-rule)"
				/>
				<text
					x={box.left - 6}
					y={round(yAxis.scale(tick)) + 3}
					text-anchor="end"
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-tick="y"
				>
					{tick}
				</text>
			{/each}

			<!-- The ask, drawn under the marks so a mark sits on top of it. Not on
			     the confidence ramp: a band is what we asked for, not a fault line. -->
			{#each placed as column (column.run.runId)}
				{#if column.band}
					<rect
						x={round(column.x - markWidth / 2)}
						y={round(column.band.y)}
						width={round(markWidth)}
						height={round(column.band.height)}
						fill="var(--chart-1)"
						opacity="0.18"
						data-run-band={column.run.runId}
					/>
				{/if}
			{/each}

			{#each swaps as swap (swap.runId)}
				<line
					x1={round(swap.at)}
					x2={round(swap.at)}
					y1={box.top}
					y2={box.bottom}
					stroke="var(--color-text-tertiary)"
					stroke-dasharray="3 3"
					data-run-swap={swap.date}
				>
					<title>The model changed to {swap.model} on {swap.date}.</title>
				</line>
			{/each}

			{#each placed as column (column.run.runId)}
				<g
					data-run-length={column.run.runId}
					data-run-low={column.run.low}
					data-run-median={column.run.median}
					data-run-high={column.run.high}
					data-run-items={column.run.items}
				>
					<title>{sentence(column.run)}</title>
					<line
						x1={round(column.x)}
						x2={round(column.x)}
						y1={round(column.yHigh)}
						y2={round(column.yLow)}
						stroke="var(--chart-8)"
						stroke-width="1.5"
						data-run-cell="range"
					/>
					<line
						x1={round(column.x - markWidth / 2)}
						x2={round(column.x + markWidth / 2)}
						y1={round(column.yMedian)}
						y2={round(column.yMedian)}
						stroke="var(--chart-8)"
						stroke-width="2.5"
						data-run-cell="median"
					/>
				</g>
			{/each}

			<line x1={box.left} x2={box.right} y1={box.bottom} y2={box.bottom} stroke="var(--color-rule)" />

			{#each labels as label (label.date)}
				<text
					x={round(label.x)}
					y={box.bottom + 14}
					text-anchor="middle"
					fill="var(--color-text-tertiary)"
					font-size="10"
					data-tick="x"
				>
					{dayMonth(label.date)}
				</text>
			{/each}

			<text
				x={box.left}
				y={box.bottom + 30}
				fill="var(--color-text-tertiary)"
				font-size="10"
				data-axis-title
			>
				Summary length, words
			</text>
		</svg>
	</div>

	<!-- The band's own numbers. A shaded region nobody can read a bound off is a
	     decoration, and this one is a setting somebody chose. -->
	{#if ask}
		<p class="mt-2 text-[0.75rem] text-text-tertiary" data-run-ask>
			<span class="band-key" aria-hidden="true"></span>
			We ask for between <span data-run-ask-low>{ask.low}</span> and
			<span data-run-ask-high>{ask.high}</span> words. Which end depends on how long the article
			is, so a run of short pieces is asked for less than a run of long ones.
		</p>
	{:else}
		<p class="mt-2 text-[0.75rem] text-text-tertiary" data-run-ask="unmeasured">
			No article in these runs recorded a length, so the band we asked for cannot be read.
		</p>
	{/if}
</div>

<style>
	.plot {
		margin-top: var(--space-4);
	}

	/* The same fill the band is drawn in, so the sentence names the region it is
	   about rather than leaving a reader to guess which shading it means. */
	.band-key {
		display: inline-block;
		width: 0.75rem;
		height: 0.75rem;
		margin-inline-end: 0.25rem;
		border-radius: 2px;
		background: var(--chart-1);
		opacity: 0.18;
		vertical-align: -1px;
	}
</style>
