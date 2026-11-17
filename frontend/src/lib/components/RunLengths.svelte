<script lang="ts">
	/** How long the summaries came out, three marks a run.
	 *
	 * This replaces a mark per article. Over the committed ledger that was
	 * thousands of marks, and its dense middle rendered as a solid block - so the
	 * only marks anybody acts on, a summary of three words or one far longer than
	 * the rest, were the ones it hid. The lowest, the middle and the highest of a
	 * run keep both ends and lose the block.
	 *
	 * Per run and never per day. A day holds up to five runs, and a run is one
	 * model reading one set of articles under one set of settings, so it is the
	 * smallest thing on this page that a change can be attributed to.
	 *
	 * Hand-written SVG, so the chart is complete before any script runs.
	 */
	import {
		chartWidth,
		dayTicks,
		linearAxis,
		observeWidth,
		type Margin
	} from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import { pointerReadout, readoutMarks, readoutOf } from '$lib/charts/readout';
	import { shortDate } from '$lib/format';
	import ChartReadout from './ChartReadout.svelte';
	import type { RunLength } from '../../routes/console/model/+page.server';
	import { completeModelRule, ruleDeclaration, ruleEvents, type ModelRule } from '$lib/charts/d3/model-rule';

	let {
		runs,
		width,
		height,
		tickDensity,
		readoutMaxShare = 1,
		rule
	}: {
		/** Oldest first. The chart reads left to right. */
		runs: RunLength[];
		width: number;
		height: number;
		tickDensity: number;
		/** `chart.readout_max_share`. */
		readoutMaxShare?: number;
		rule?: ModelRule;
	} = $props();

	const frame = useChartFrame();
	const MARGIN: Margin = { top: 12, right: 12, bottom: 40, left: 38 };

	let measured = $state<number | null>(null);

	const box = $derived(frame(chartWidth(measured, width), height, MARGIN));

	/** Every length the axis must hold, data only. Split from the axis so a
	 * resize reuses this pass rather than walking the runs again for a new plot
	 * height. */
	const runValues = $derived(runs.flatMap((run) => [run.low, run.high]));
	const fullRule = $derived(rule === undefined ? undefined : completeModelRule(rule, runs.map((run) => run.date)));
	const declaration = $derived(fullRule === undefined ? null : ruleDeclaration(runs.length === 0
		? { declined: 'There are no measured runs on which to place a dated settings change.' }
		: fullRule));
	const boundaries = $derived(fullRule === undefined || 'declined' in fullRule ? [] : fullRule.changes.flatMap((change) => {
		const index = runs.findIndex((run) => run.date === change.date);
		if (index < 0) return [];
		return [{ ...change, at: box.left + pitch * index }];
	}));
	const yAxis = $derived(linearAxis(runValues, [box.bottom, box.top]));
	/** The raw extent of the lengths, bound to the data alone: a resize cannot
	 * move it and a window change can. Published so a test can hold the split. */
	const runExtent = $derived(
		runValues.length === 0 ? '' : `${Math.min(...runValues)},${Math.max(...runValues)}`
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
			yHigh: yAxis.scale(run.high)
		}))
	);

	/** A rule between two neighbouring runs on different models. Everything left
	 * of it ran on the older id. It carries the date and the id and nothing
	 * else - a delta across it would claim the swap caused whatever moved.
	 *
	 * Keyed by the run it precedes rather than by its date: the model can change
	 * between two runs of one day, and two keys of one date would throw at
	 * hydration while the prerendered document looked perfect. */
	const swaps = $derived(
		rule !== undefined ? [] : runs
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

	/** One date label per day, thinned by what the axis has room for. The columns
	 * are the runs, and a day can hold one run or five, so the day-first columns
	 * are not evenly spaced and their own x goes to the helper. A run id is
	 * eighteen characters and there are five of them a day, so the label is the
	 * date. */
	const firsts = $derived(
		runs
			.map((run, index) => ({ run, index }))
			.filter(({ run, index }) => index === 0 || runs[index - 1].date !== run.date)
	);
	const labels = $derived(
		dayTicks(
			firsts.map(({ run }) => run.date),
			{ density: tickDensity, columns: firsts.map(({ index }) => columnX(index)), labels: box.labels }
		).map((tick) => ({
			date: tick.date,
			text: tick.text,
			anchor: tick.anchor,
			x: columnX(firsts[tick.index]?.index ?? 0)
		}))
	);

	/** One run's sentence, kept on its marks as their name. Every word of it is in
	 * the strip at that run: the run id names the day, so the date is not said a
	 * second time. */
	function sentence(run: RunLength): string {
		return `Run ${run.runId}${run.model === null ? '' : `, ${run.model}`}: ${run.items} summaries, shortest ${run.low} words, median (p50) ${run.median}, longest ${run.high}.`;
	}

	/** What a model rule says, on the rule and in the strip on the run it opens. */
	function swapSentence(swap: { model: string; date: string }): string {
		return `The model changed to ${swap.model} on ${shortDate(swap.date)}.`;
	}

	const description = $derived(
		`Summary length per run over ${runs.length} runs, minimum, median (p50) and maximum of each. ` +
			placed.map(({ run }) => sentence(run)).join(' ')
	);

	/** The column a pointer or an arrow key has picked. */
	let selected = $state<number | null>(null);

	/** Three marks a run, printed together. The whole point of the shape is that
	 * the ends move while the middle does not, and reading three marks off one
	 * column by eye against a shared y axis is what the strip removes. It rests on
	 * the newest run, which is the one an operator came for. */
	const readout = $derived.by(() => {
		const words = (value: number) => `${value} words`;
		return readoutOf({
			type: 'dateSeries',
			columns: runs.map(
				(run) => `${run.runId} - ${run.items} ${run.items === 1 ? 'summary' : 'summaries'}`
			),
			series: [
				{ label: 'Shortest', swatch: 'var(--chart-8)', values: runs.map((run) => run.low), format: words },
				{ label: 'Middle', swatch: 'var(--chart-8)', values: runs.map((run) => run.median), format: words },
				{ label: 'Longest', swatch: 'var(--chart-8)', values: runs.map((run) => run.high), format: words },
				{
					label: 'Model',
					swatch: null,
					values: runs.map((run) => run.model),
					format: String
				}
			],
			// The rule is drawn between two runs; its sentence prints on the run it
			// opens, so stepping the runs with a key meets it without a pointer.
			events: {
				lines: runs.map((run) => {
					const swap = swaps.find((one) => one.runId === run.runId);
					return rule === undefined ? (swap === undefined ? [] : [{ label: swapSentence(swap), value: '', swatch: null }]) : ruleEvents(rule, [run.date]).lines?.[0] ?? [];
				})
			},
			notMeasured: 'not recorded',
			resting: 'last'
		});
	});
	const marks = $derived(readoutMarks(placed.map((mark) => mark.x)));
	const guide = $derived(selected === null ? null : (placed[selected]?.x ?? null));
</script>

<div
	class="plot"
	data-run-lengths="chart"
	data-chart-type="dateSeries"
	data-model-rule={declaration?.value}
	data-model-rule-name={rule === undefined ? undefined : 'summary-length'}
	data-model-rule-none={declaration?.none}
	data-model-rule-from={rule === undefined ? undefined : runs[0]?.date}
	data-model-rule-to={rule === undefined ? undefined : runs.at(-1)?.date}
	data-run-lengths-runs={runs.length}
	data-run-domain={runExtent}
	data-readout-columns={readout.columns.length}
>
	<div use:observeWidth={(next) => (measured = next)}>
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<svg
			class="block max-w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
			width={box.width}
			height={box.height}
			viewBox={`0 0 ${box.width} ${box.height}`}
			role="img"
			tabindex="0"
			aria-label={description}
			use:pointerReadout={{
				marks,
				width: box.width,
				hover: { name: 'run-lengths', readout },
				onSelect: (index) => (selected = index)
			}}
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
					font-size={box.labels.fontSize}
					data-tick="y"
				>
					{tick}
				</text>
			{/each}

			{#each swaps as swap (swap.runId)}
				<line
					x1={round(swap.at)}
					x2={round(swap.at)}
					y1={box.top}
					y2={box.bottom}
					stroke="var(--color-text-tertiary)"
					stroke-dasharray="3 3"
					role="img"
					aria-label={swapSentence(swap)}
					data-run-swap={swap.date}
				/>
			{/each}

			{#each boundaries as boundary (`${boundary.date}-${boundary.kind}`)}
				<line x1={boundary.at} x2={boundary.at} y1={box.top} y2={box.bottom}
					stroke="var(--color-text-tertiary)" stroke-dasharray={boundary.kind === 'checker' ? '1 3' : '3 3'}
					data-model-rule-line={boundary.date} data-model-rule-date={boundary.date} data-model-rule-kind={boundary.kind} />
			{/each}

			{#if guide !== null}
				<line
					x1={round(guide)}
					x2={round(guide)}
					y1={box.top}
					y2={box.bottom}
					stroke="var(--color-text-tertiary)"
					stroke-opacity="0.5"
					data-run-lengths="guide"
				/>
			{/if}

			{#each placed as column (column.run.runId)}
				<g
					role="img"
					aria-label={sentence(column.run)}
					data-run-length={column.run.runId}
					data-run-low={column.run.low}
					data-run-median={column.run.median}
					data-run-high={column.run.high}
					data-run-items={column.run.items}
				>
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

			<!-- The mark stays where the date was dropped, so a reader counting runs
			     keeps the grid. -->
			{#each labels as label (label.date)}
				<line
					x1={round(label.x)}
					x2={round(label.x)}
					y1={box.bottom}
					y2={box.bottom + 4}
					stroke="var(--color-text-tertiary)"
					data-day-tick={label.date}
				/>
				{#if label.text}
					<text
						x={round(label.x)}
						y={box.bottom + 16}
						text-anchor={label.anchor}
						fill="var(--color-text-tertiary)"
						font-size={box.labels.fontSize}
						data-day-axis
						data-tick="x"
					>
						{label.text}
					</text>
				{/if}
			{/each}

			<text
				x={box.left}
				y={box.bottom + 30}
				fill="var(--color-text-tertiary)"
				font-size={box.labels.fontSize}
				data-axis-title
			>
				Summary length, words
			</text>
		</svg>
	</div>

	<!-- Below the plot, never over it, and the same strip every chart on this
	     console prints - see `ChartReadout.svelte` for the rules it holds. -->
	<ChartReadout
		{readout}
		at={selected}
		name="run-lengths"
		maxShare={readoutMaxShare}
		restingNote=", the newest run"
		hint="Point at a run to read all three marks. Left and Right step through the runs, Escape returns to the newest."
	/>
</div>

<style>
	.plot {
		margin-top: var(--space-4);
	}
</style>
