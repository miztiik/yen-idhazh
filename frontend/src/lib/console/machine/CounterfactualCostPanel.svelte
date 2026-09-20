<script lang="ts">
	/** What the runner's work would have cost at a hosted provider's rate.
	 *
	 * A counterfactual, never a bill. Nothing bills us - Actions minutes are free
	 * on a public repository - which is why the wall clock alone cannot say
	 * whether the runner time was a good trade, and priced at somebody else's
	 * rate it can.
	 */
	import Chart from '$lib/charts/Chart.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import RateControl from '$lib/components/RateControl.svelte';
	import ShapeSwitch from '$lib/components/ShapeSwitch.svelte';
	import { costOf, money, type CostRate, type RunWork } from '$lib/charts/machine';
	import {
		costChart,
		costColumns,
		costLabel,
		costOverDays,
		COST_SHAPES,
		DEFAULT_COST_SHAPE,
		type CostShape
	} from '$lib/charts/cost';
	import type { ChartConfig } from '$lib/server/config';

	let {
		runs,
		totals,
		configured,
		svg,
		grid,
		chart,
		windowDays,
		days
	}: {
		runs: RunWork[];
		totals: { input: number; output: number; items: number };
		configured: CostRate;
		svg: string | null;
		grid: { left: number; right: number };
		chart: ChartConfig;
		windowDays: number;
		days: number;
	} = $props();

	// One shared rate for every cost figure below. It starts at the configured
	// pair so the first paint matches the prerendered document, and `RateControl`
	// replaces it on mount if the operator has typed one before. Deliberately not
	// derived: after mount the operator owns these two numbers, not the payload.
	// svelte-ignore state_referenced_locally
	let inputRate = $state(configured.inputPerMillion);
	// svelte-ignore state_referenced_locally
	let outputRate = $state(configured.outputPerMillion);
	let rateSource = $state<'configured' | 'yours'>('configured');

	const rate = $derived({
		currency: configured.currency,
		inputPerMillion: inputRate,
		outputPerMillion: outputRate
	});
	const inputCost = $derived(costOf({ input: totals.input, output: 0 }, rate));
	const outputCost = $derived(costOf({ input: 0, output: totals.output }, rate));
	const totalCost = $derived(inputCost + outputCost);
	const perArticle = $derived(totals.items === 0 ? null : totalCost / totals.items);

	// One call, both shapes. The bars and the line are two readings of one array,
	// so the line's last point and the total printed above it are the same
	// arithmetic rather than two derivations that can drift apart.
	const costShapes = $derived(costOverDays(runs, rate, { heightPx: chart.height_px }));
	// The shape the panel opens on. The server drew this one, so the first paint
	// and the radio that is already checked agree before a script has run.
	let costShape = $state<CostShape>(DEFAULT_COST_SHAPE);
	const costOption = $derived(costChart(costShapes, costShape, rate.currency).option);
	const costStrip = $derived(costColumns(costShapes, costShape, rate.currency));
	/** The thinnest band as a share of the tallest day, at one precision, so the
	 * figure the panel prints and the figure the shape was picked on can never be
	 * two readings of one measurement. */
	const costThinnest = $derived(
		costShapes.thinnestShare === null ? null : (costShapes.thinnestShare * 100).toFixed(1)
	);
</script>

<div data-windowed="machine-cost" data-window-days={windowDays}>
	<Panel
		heading="h3"
		id="counterfactual-cost"
		title="What this would have cost somewhere else"
		note="A counterfactual and never a bill: nothing bills us, so the wall clock alone cannot say whether the runner time was a good trade - four figures and one column a day, over the last {windowDays} days."
		tone="info"
	>
		{#if runs.length === 0}
			<p class="empty" data-machine-panel-empty="cost">
				No run in these {days} days recorded a token count, so there is nothing to price.
			</p>
		{:else}
			<RateControl {configured} bind:inputRate bind:outputRate bind:source={rateSource} />

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
					<dt>These {days} days</dt>
					<dd class="tabular-nums">{money(totalCost, rate.currency, 2)}</dd>
				</div>
				<div data-cost="per-article">
					<dt>An article</dt>
					<dd class="tabular-nums">
						{perArticle === null ? '-' : money(perArticle, rate.currency, 4)}
					</dd>
				</div>
			</dl>

			<div
				data-cost-shape={costShape}
				data-cost-days={costShapes.days.length}
				data-cost-running-total={costShapes.runningTotal}
				data-cost-split={costShapes.splitTooThin ? 'printed' : 'drawn'}
				data-cost-thinnest-pct={costThinnest ?? ''}
				data-panel-question="is it working"
			>
				<!-- Top right of its own panel, and radio inputs: two named states a
				     reader can see both of beat one state and a verb. -->
				<div class="units">
					<ShapeSwitch
						bind:shape={costShape}
						name="cost-shape"
						label="Which shape to draw the counterfactual in"
						options={COST_SHAPES}
					/>
				</div>

				{#if costShapes.days.length === 0}
					<p class="empty" data-cost-absent="days">
						No run in these {days} days carries a date, so there is nothing to lay on a
						time axis. The four figures above still hold.
					</p>
				{:else}
					<Chart
						svg={svg ?? ''}
						option={costOption}
						width={chart.width_px}
						height={chart.height_px}
						label={costLabel(costShape, days)}
						columns={costStrip}
						readoutName="counterfactual-cost"
						readoutMaxShare={chart.readout_max_share}
						{grid}
						restingNote=", the newest day"
						hint="Point at a day to read it. Left and Right step through them, Escape returns to the newest."
					/>
				{/if}

				<!-- 19D8's threshold is a measurement, so the panel prints the one it
				     took rather than asserting the bands were safe to draw. -->
				<p class="reads" data-cost-measured>
					{#if costThinnest === null}
						Nothing split in this window, so the columns carry no bands.
					{:else if costShapes.splitTooThin}
						Reading and writing are one column here. The smaller half measures {costThinnest}
						percent of the tallest day, which draws under a pixel, and a band a browser paints
						nothing for teaches a reader the half is zero.
					{:else}
						The smaller half of the busiest day measures {costThinnest} percent of the tallest
						column, so both halves draw as bands rather than as a printed figure.
					{/if}
				</p>
			</div>

			<p class="reads" data-cost-basis>
				What {runs.length}
				{runs.length === 1 ? 'run' : 'runs'} would have cost at that rate, if a hosted
				provider had done the work instead of the runner. It is not an amount owed and no invoice
				exists. The wall clock is the real budget and the shard board above draws it; this figure
				is the second unit, and it says whether that clock was worth spending.
			</p>
		{/if}
	</Panel>
</div>

<style>
	.empty {
		margin: var(--space-2) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.reads {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.units {
		display: flex;
		justify-content: flex-end;
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
