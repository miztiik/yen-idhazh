<script lang="ts">
	/** Draws the Data explorer's Chart tab in three rows: the role row, where a pill for each role
	 * of the chart shows the column it holds; the drawing; and the foot, which says what the drawing
	 * leaves out.
	 *
	 * Room is set by the width band and the pointer, never by the chart or its columns: the role row
	 * holds a slot for each role of the chart with the most roles, empty slots included, and the foot
	 * reserves the status bar's lines, so a change of chart or column redraws inside boxes that do
	 * not move. The plot is drawn at the drawing's measured width and height, and never shorter than
	 * `console.chart_height`; a shorter box scrolls. Jony's layout of 2026-10-07.
	 */
	import { untrack, type Snippet } from 'svelte';
	import type { Column, DateStamp, Row } from '$lib/data/ledger';
	import { tooFewSentence } from '$lib/console/waiting';
	import { frame } from '$lib/charts/frame';
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { distribution } from '$lib/charts/d3/distribution';
	import Distribution from '$lib/charts/d3/Distribution.svelte';
	import { pairedScatter } from '$lib/charts/d3/pairedScatter';
	import PairedScatter from '$lib/charts/d3/PairedScatter.svelte';
	import { readoutOf } from '$lib/charts/readout';
	import { emptyState } from '$lib/charts/d3/empty';
	import { rank } from '$lib/charts/rank';
	import RankedList from '$lib/components/RankedList.svelte';
	import ColumnPicker from '$lib/console/explorer/ColumnPicker.svelte';
	import { MOST_ROLES, SERIES_TOKENS, type ExplorerChartType, type RoleId } from '$lib/console/explorer/chart-roles';
	import { IN_THE_ANSWER, chartNotes, chooseDateSeriesDays, numericValue, type ExplorerChart, type ExplorerShape, type ExplorerShapeBounds } from './shape';
	import { printCell } from './answer';

	let {
		chart,
		columns,
		rows,
		lostDays,
		bounds,
		floorHeight,
		capped = false,
		maxRows,
		onRoles,
		placeholder = null
	}: {
		chart: ExplorerChart;
		columns: readonly Column[];
		rows: readonly Row[];
		lostDays: readonly DateStamp[];
		bounds: ExplorerShapeBounds;
		/** The fewest pixels a plot is drawn tall, `console.chart_height`. */
		floorHeight: number;
		capped?: boolean;
		maxRows: number;
		onRoles: (type: ExplorerChartType, role: RoleId, values: string[]) => void;
		/** What the drawing holds while there is no answer to draw: a state's sentence or its shimmer. */
		placeholder?: Snippet | null;
	} = $props();

	let box = $state<HTMLDivElement | null>(null);
	let stack = $state<HTMLDivElement | null>(null);
	let drawing = $state<HTMLDivElement | null>(null);
	let chartWidth = $state(760);
	let chartHeight = $state(untrack(() => floorHeight));

	const slots = Array.from({ length: MOST_ROLES }, (_, index) => index);
	const active = $derived(chart.shape);
	const notes = $derived(placeholder === null ? chartNotes(active, bounds, capped, maxRows) : []);
	// The drawing and the foot are drawn again, never moved, when the chart or a column changes.
	const drawingKey = $derived(JSON.stringify([placeholder === null, chart.type, chart.roles.map((state) => state.chosen)]));

	function text(row: Row, column: string): string {
		const spec = columns.find((one) => one.name === column) ?? { name: column, type: 'VARCHAR' };
		return printCell(spec, row[column]).text;
	}

	function lede(next: ExplorerShape): string {
		if (next.kind === 'none') return 'No chart';
		if (next.type === 'dateSeries') {
			const main = next.mainFigure;
			return main === null ? `${next.days} UTC ${next.days === 1 ? 'day' : 'days'}` : `${text({ [main.column]: main.value }, main.column)} ${main.column} on ${main.date}`;
		}
		if (next.type === 'rankedList') return next.mainFigure === null ? `${rows.length} rows` : `${next.mainFigure.label}: ${text({ [next.mainFigure.column]: next.mainFigure.value }, next.mainFigure.column)} ${next.mainFigure.column}`;
		if (next.type === 'pairedScatter') return next.mainFigure;
		return next.mainFigure ?? `${rows.length} rows`;
	}

	function tooFew(next: ExplorerShape): string | null {
		if (next.kind === 'none' || !('tooFew' in next) || !next.tooFew) return null;
		if (next.type === 'dateSeries') return tooFewSentence(next.days, bounds.chartMinRows, 'UTC days', IN_THE_ANSWER);
		if (next.type === 'pairedScatter') {
			return next.readings < bounds.fleetMinRows
				? tooFewSentence(next.readings, bounds.fleetMinRows, 'readings', IN_THE_ANSWER)
				: tooFewSentence(next.subjects, bounds.bandwidthMinKinds, 'names', IN_THE_ANSWER);
		}
		if (next.type === 'distribution') return tooFewSentence(next.readings, bounds.fleetMinRows, 'readings', IN_THE_ANSWER);
		return null;
	}

	function readoutFor(next: ExplorerShape): { subject: string; facts: { label: string; value: string }[] } | null {
		if (next.kind === 'none' || next.type !== 'rankedList') return null;
		const row = [...rows].filter((candidate) => numericValue(candidate, next.valueColumn) !== null).sort((left, right) => (numericValue(right, next.valueColumn) ?? 0) - (numericValue(left, next.valueColumn) ?? 0))[0];
		return row ? { subject: text(row, next.labelColumn), facts: [{ label: next.valueColumn, value: text(row, next.valueColumn) }] } : null;
	}

	/** The plot's width is the drawing's, and its height whatever the drawing has left once the main
	 *  figure, the readout and the comparison have theirs, never under the floor. Each reading is
	 *  floored to a whole pixel, so a drawing does not resize itself again and again. */
	function measure() {
		if (drawing !== null) chartWidth = Math.max(1, Math.floor(drawing.getBoundingClientRect().width));
		if (box === null || stack === null) return;
		const style = getComputedStyle(box);
		const room = box.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
		const rest = stack.getBoundingClientRect().height - chartHeight;
		const next = Math.max(floorHeight, Math.floor(room - rest));
		if (Math.abs(next - chartHeight) >= 1) chartHeight = next;
	}

	$effect(() => {
		const watched = [box, stack, drawing].filter((node): node is HTMLDivElement => node !== null);
		if (watched.length === 0) return;
		const observer = new ResizeObserver(() => measure());
		for (const node of watched) observer.observe(node);
		untrack(measure);
		return () => observer.disconnect();
	});
</script>

<div class="shape-panel">
	<div class="role-row" data-chart-roles>
		{#each slots as index (index)}
			{@const state = chart.roles[index]}
			<div class="role-slot" data-role-slot={index}>
				{#if state !== undefined && chart.type !== null}
					{@const type = chart.type}
					{#key `${type}:${state.role.id}`}
						<ColumnPicker role={state.role} options={state.options} chosen={state.chosen} max={SERIES_TOKENS.length} onChange={(values) => onRoles(type, state.role.id, values)} />
					{/key}
				{/if}
			</div>
		{/each}
	</div>
	<div class="chart-body" data-chart-drawing bind:this={box} style={`--shape-height:${chartHeight}px;--floor-height:${floorHeight}px`}>
		{#key drawingKey}
			{#if placeholder !== null}
				{@render placeholder()}
			{:else if active.kind === 'none'}
				<div class="shape-none" data-shape-none>{active.reason}</div>
			{:else if tooFew(active)}
				<div class="shape-none" data-state="too-few">{tooFew(active)}</div>
			{:else}
				{@const readout = readoutFor(active)}
				<div class="shape-stack" bind:this={stack}>
					<p class="shape-lede" data-lede>{lede(active)}</p>
					<div class="shape-drawing" bind:this={drawing}>
						{#if active.type === 'dateSeries'}
							{@const plotFrame = frame(chartWidth, chartHeight)}
							{@const seriesColumns = active.seriesColumns}
							{@const days = chooseDateSeriesDays(active.dateColumn, rows, lostDays)}
							{@const dateGeometry = dateSeries(seriesColumns.map((column, index) => ({ label: column, token: SERIES_TOKENS[index] ?? SERIES_TOKENS[0], points: days.map(({ day, row }) => ({ date: day, value: row === null ? null : numericValue(row, column) })) })), { frame: plotFrame, density: 6, valueTicks: 4, padding: 0.25 })}
							{@const dateReadout = readoutOf({ type: 'dateSeries', columns: days.map(({ day }) => day), series: seriesColumns.map((column, index) => ({ label: column, swatch: `var(${SERIES_TOKENS[index] ?? SERIES_TOKENS[0]})`, values: days.map(({ row }) => (row === null ? null : numericValue(row, column))), format: (n) => text({ [column]: n }, column) })), notMeasured: 'No number for this day', resting: 'last' })}
							<div data-model-rule="no" data-model-rule-none="this page does not know which settings changed inside your span">
								<DateSeries geometry={dateGeometry} empty={emptyState('quiet', 'No rows to draw.')} name="data-explorer-shape" label={`Over time: ${[active.dateColumn, ...active.seriesColumns].join(', ')}`} width={chartWidth} height={chartHeight} readout={dateReadout} />
							</div>
							<p data-comparison={active.comparison}>{active.comparison}.</p>
						{:else if active.type === 'rankedList'}
							{@const ranked = rank(rows.map((row) => ({ key: text(row, active.labelColumn), value: numericValue(row, active.valueColumn) ?? Number.NaN, row: { label: text(row, active.labelColumn), value: text(row, active.valueColumn) } })), active.rowsDrawn)}
							<RankedList caption={`Ranked by ${active.valueColumn}`} {ranked} maxText={`${text({ [active.valueColumn]: ranked.max }, active.valueColumn)} ${active.valueColumn}`} unmeasuredNote="No rows carried a number to rank." emptyNote="No rows carried a number to rank." tail={active.moreRows > 0 ? `${active.moreRows} more ${active.moreRows === 1 ? 'row is' : 'rows are'} in the table.` : null} />
							{#if readout}<dl class="shape-readout" data-readout="data-explorer-shape" data-readout-shape="record"><dt data-readout-subject>{readout.subject}</dt>{#each readout.facts as fact}<div data-readout-row={fact.label}><dd>{fact.label}</dd><dd>{fact.value}</dd></div>{/each}</dl>{/if}
							<p data-comparison={active.comparison}>{active.comparison}.</p>
						{:else if active.type === 'pairedScatter'}
							{@const plotFrame = frame(chartWidth, chartHeight)}
							{@const points = rows.flatMap((row, index) => numericValue(row, active.xColumn) === null || numericValue(row, active.yColumn) === null ? [] : [{ label: active.subjectColumn === null ? `row ${index + 1}` : text(row, active.subjectColumn), x: numericValue(row, active.xColumn) as number, y: numericValue(row, active.yColumn) as number }])}
							<PairedScatter geometry={pairedScatter(points, { frame: plotFrame, minRows: bounds.fleetMinRows, minSubjects: bounds.bandwidthMinKinds, valueTicks: 4 })} empty={emptyState('too-few', tooFew(active) ?? 'Too few rows.')} name="data-explorer-shape" label={`Paired: ${active.yColumn} against ${active.xColumn}`} width={chartWidth} height={chartHeight} />
							<p data-comparison={active.comparison}>{active.comparison}.</p>
						{:else}
							{@const plotFrame = frame(chartWidth, chartHeight)}
							{@const values = rows.map((row) => numericValue(row, active.valueColumn)).filter((one): one is number => one !== null)}
							<Distribution geometry={distribution(values, { frame: plotFrame, minValues: bounds.fleetMinRows, valueTicks: 4 })} empty={emptyState('too-few', tooFew(active) ?? 'Too few rows.')} name="data-explorer-shape" label={`Spread: ${active.valueColumn}`} width={chartWidth} height={chartHeight} />
							<p data-comparison={active.comparison}>{active.comparison}.</p>
						{/if}
					</div>
				</div>
			{/if}
		{/key}
	</div>
	<div class="chart-foot" data-chart-foot>
		{#key drawingKey}
			{#each notes as note (note)}<p class="shape-foot" data-shape-foot>{note}</p>{/each}
		{/key}
	</div>
</div>

<style>
	/* Three rows in the tab panel's whole height: the role row and the foot keep the room their
	   band gives them, and the drawing takes the rest. */
	.shape-panel {
		display: grid;
		grid-template-rows: auto minmax(0, 1fr) auto;
		block-size: 100%;
		min-block-size: 0;
		min-inline-size: 0;
	}

	/* One slot for each role of the chart with the most roles, a fixed number to a line by band,
	   so the row is the same height whichever chart is chosen. */
	.role-row {
		box-sizing: border-box;
		display: grid;
		grid-template-columns: repeat(var(--role-slots), minmax(0, 1fr));
		grid-auto-rows: var(--workbench-control);
		column-gap: var(--space-3);
		row-gap: var(--space-1);
		block-size: calc(var(--role-lines) * var(--workbench-control) + (var(--role-lines) - 1) * var(--space-1) + 2 * var(--space-1));
		padding: var(--space-1) var(--space-3);
	}

	.role-slot {
		min-inline-size: 0;
	}

	/* Its own content never sizes the drawing: a chart taller than the box scrolls inside it. */
	.chart-body {
		contain: size;
		min-block-size: 0;
		overflow: auto;
		padding: 0 var(--space-3) var(--space-3);
	}

	/* The foot reserves the status bar's lines in every band; a longer note scrolls inside it. */
	.chart-foot {
		box-sizing: border-box;
		block-size: calc(var(--readout-lines) * var(--leading-sm) + 2 * var(--space-1));
		overflow-y: auto;
		scrollbar-width: thin;
		scrollbar-color: var(--color-rule-strong) transparent;
		padding: var(--space-1) var(--space-3);
		color: var(--color-text-secondary);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
	}

	.shape-stack {
		display: grid;
		gap: var(--space-3);
		min-inline-size: 0;
	}

	.shape-drawing {
		min-inline-size: 0;
		overflow: auto;
	}

	.shape-stack p,
	.chart-foot p {
		margin: 0;
		color: var(--color-text-secondary);
	}

	.shape-stack .shape-lede {
		color: var(--color-text);
		font-size: var(--text-xl);
		font-weight: 700;
	}

	.shape-none,
	:global(.date-series),
	:global(.distribution),
	:global(.paired-scatter),
	:global(.ranked) {
		min-block-size: var(--shape-height);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-surface);
	}

	/* A drawing that says why it draws nothing fills the box, and never falls under a chart's height. */
	.shape-none {
		box-sizing: border-box;
		display: grid;
		place-items: center;
		min-block-size: max(100%, var(--floor-height));
		padding: var(--space-6);
		color: var(--color-text-secondary);
		font-size: var(--text-sm);
		text-align: center;
	}

	.shape-readout {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2) var(--space-4);
		margin: 0;
		color: var(--color-text-secondary);
		font-size: var(--text-xs);
	}

	.shape-readout dt {
		flex-basis: 100%;
		font-weight: 600;
	}

	.shape-readout div {
		display: flex;
		gap: var(--space-1);
	}

	.shape-readout dd {
		margin: 0;
	}
</style>
