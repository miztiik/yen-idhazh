<script lang="ts">
	/** Draws the Data explorer's Chart tab in three rows: the role row, where a pill for each role
	 * of the chart shows the column it holds; the drawing; and the foot, which says what the drawing
	 * leaves out.
	 *
	 * Room is set by the width band, the pointer and the answer, never by the chart or its columns:
	 * the role row holds a slot for each role of the chart with the most roles, empty slots included,
	 * and the foot reserves room for each note the answer can give, so a change of chart or column
	 * redraws inside boxes that do not move. The plot is drawn at the drawing's measured width and
	 * height, and the plot and the foot together are never shorter than `console.chart_height`; the
	 * page never gives the drawing less room than its figure, that plot, its readout and its
	 * comparison need, so a short window scrolls the page and never the plot. Jony's layout of
	 * 2026-10-07 and his rulings of 2026-10-08.
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
	import { partsOfOne } from '$lib/charts/d3/partsOfOne';
	import PartsOfOne from '$lib/charts/d3/PartsOfOne.svelte';
	import { tileStrip } from '$lib/charts/d3/tileStrip';
	import TileStrip from '$lib/charts/d3/TileStrip.svelte';
	import { flow } from '$lib/charts/d3/flow';
	import Flow from '$lib/charts/d3/Flow.svelte';
	import { factsOf, readoutOf } from '$lib/charts/readout';
	import { emptyState } from '$lib/charts/d3/empty';
	import { rank } from '$lib/charts/rank';
	import RankedList from '$lib/components/RankedList.svelte';
	import ColumnPicker from '$lib/console/explorer/ColumnPicker.svelte';
	import { MOST_ROLES, SERIES_TOKENS, type ExplorerChartType, type RoleId } from '$lib/console/explorer/chart-roles';
	import { IN_THE_ANSWER, chartNotes, chooseDateSeriesDays, numericValue, readTruthValue, type ExplorerChart, type ExplorerShape, type ExplorerShapeBounds } from './shape';
	import { printCell } from './answer';

	let {
		chart,
		columns,
		rows,
		lostDays,
		bounds,
		floorHeight,
		noteCount = 0,
		slotsPerLine = MOST_ROLES,
		capped = false,
		maxRows,
		narrowBelow = 0,
		onRoles,
		placeholder = null
	}: {
		chart: ExplorerChart;
		columns: readonly Column[];
		rows: readonly Row[];
		lostDays: readonly DateStamp[];
		bounds: ExplorerShapeBounds;
		/** The height the plot and the foot share, `console.chart_height`: the plot is never shorter
		 *  than this less the foot. */
		floorHeight: number;
		/** The notes the answer can give, which the foot reserves room for: `countChartNotes`. */
		noteCount?: number;
		/** The role row's slots on one line at this width, the band's `explorer_role_slots_per_line`. */
		slotsPerLine?: number;
		capped?: boolean;
		maxRows: number;
		/** The first configured frame breakpoint; zero keeps server-only callers wide. */
		narrowBelow?: number;
		onRoles: (type: ExplorerChartType, role: RoleId, values: string[]) => void;
		/** What the drawing holds while there is no answer to draw: a state's sentence or its shimmer. */
		placeholder?: Snippet | null;
	} = $props();

	let box = $state<HTMLDivElement | null>(null);
	let stack = $state<HTMLDivElement | null>(null);
	let drawing = $state<HTMLDivElement | null>(null);
	let foot = $state<HTMLDivElement | null>(null);
	let chartWidth = $state(760);
	let chartHeight = $state(untrack(() => floorHeight));
	let nodeWidth = $state(0);
	let nodeGap = $state(0);

	const slots = Array.from({ length: MOST_ROLES }, (_, index) => index);
	const active = $derived(chart.shape);
	const notes = $derived(placeholder === null ? chartNotes(active, bounds, capped, maxRows) : []);
	// The drawing and the foot are drawn again, never moved, when the chart or a column changes.
	const drawingKey = $derived(JSON.stringify([placeholder === null, chart.type, chart.roles.map((state) => state.chosen)]));
	const flowDrawing = $derived.by(() => {
		if (active.kind !== 'chart' || active.type !== 'flow') return null;
		const stages = rows.map((row) => ({ label: text(row, active.stageColumn), arrived: numericValue(row, active.arrivedColumn) as number, left: numericValue(row, active.wentOnColumn) as number, drops: active.droppedColumns.map((column) => ({ label: column, count: numericValue(row, column) as number })) }));
		return flow(stages, { frame: frame(chartWidth, chartHeight), narrow: chartWidth < narrowBelow || nodeWidth === 0, nodeWidth, nodeGap, includeCountsStatus: true });
	});

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
		if (next.type === 'rankedList' || next.type === 'partsOfOne') return next.mainFigure === null ? `${rows.length} rows` : `${next.mainFigure.label}: ${text({ [next.mainFigure.column]: next.mainFigure.value }, next.mainFigure.column)} ${next.mainFigure.column}`;
		if (next.type === 'pairedScatter') return next.mainFigure;
		if (next.type === 'tileStrip') {
			const days = chooseDateSeriesDays(next.dateColumn, rows, lostDays);
			return `"${next.markColumn}" was true on ${days.filter(({ row }) => row !== null && readTruthValue(row, next.markColumn) === true).length} of ${days.length} UTC ${days.length === 1 ? 'day' : 'days'}`;
		}
		if (next.type === 'flow' && flowDrawing?.kind === 'stepped' && flowDrawing.countsConsistent === false) {
			const last = rows[rows.length - 1];
			return `${text(last, next.stageColumn)}: ${text(last, next.wentOnColumn)} ${next.wentOnColumn}`;
		}
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
	 *  figure, the readout and the comparison have theirs. Its box, edge included, is never under
	 *  `console.chart_height` less the foot's height, so the plot and the foot share that height; the
	 *  result region's floor gives the drawing exactly that much, so at the floor the two meet and
	 *  nothing scrolls. A fit is floored to a whole pixel, so a drawing does not resize itself again
	 *  and again. */
	function measure() {
		if (drawing !== null) chartWidth = Math.max(1, Math.floor(drawing.getBoundingClientRect().width));
		if (box === null || stack === null) return;
		const style = getComputedStyle(box);
		const rootPixels = parseFloat(getComputedStyle(document.documentElement).fontSize);
		const readSpacingPixels = (token: string) => {
			const value = style.getPropertyValue(token).trim();
			return parseFloat(value) * (value.endsWith('rem') ? rootPixels : value.endsWith('em') ? parseFloat(style.fontSize) : 1);
		};
		nodeWidth = readSpacingPixels('--space-3');
		nodeGap = readSpacingPixels('--space-2');
		const room = box.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
		const rest = stack.getBoundingClientRect().height - chartHeight;
		// What the plot's box holds beside the height it was drawn at: its edge.
		const plot = drawing?.querySelector('svg[data-chart-type]') ?? null;
		const edge = plot === null ? 0 : plot.getBoundingClientRect().height - Number(plot.getAttribute('height') ?? chartHeight);
		const least = floorHeight - (foot?.getBoundingClientRect().height ?? 0) - edge;
		const next = Math.max(least, Math.floor(room - rest));
		if (Math.abs(next - chartHeight) >= 1) chartHeight = next;
	}

	$effect(() => {
		const watched = [box, stack, drawing, foot].filter((node): node is HTMLDivElement => node !== null);
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
			<div class="role-slot" data-role-slot={index} style={`--slots-to-end:${slotsPerLine - (index % slotsPerLine)}`}>
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
						{#if active.type === 'partsOfOne'}
							{@const drawn = rows.slice(0, active.rowsDrawn)}
							{@const parts = partsOfOne(drawn.map((row) => ({ label: text(row, active.labelColumn), parts: active.barColumns.flatMap((column) => { const value = numericValue(row, column); return value === null ? [] : [{ label: column, value }]; }) })), { order: active.barColumns, overlapping: true, tokens: SERIES_TOKENS.slice(0, active.barColumns.length) })}
							{@const records = drawn.map((row) => factsOf(text(row, active.labelColumn), active.barColumns.map((column, index) => ({ label: column, value: numericValue(row, column), format: (n) => text({ [column]: n }, column), swatch: `var(${SERIES_TOKENS[index]})` })), 'null'))}
							<PartsOfOne geometry={parts} empty={emptyState('quiet', 'No rows to draw.')} name="data-explorer-shape" label={`Side by side: ${[active.labelColumn, ...active.barColumns].join(', ')}`} width={chartWidth} height={chartHeight} readout={records} />
							{#if active.moreRows > 0}<p data-shape-tail>{active.moreRows} more {active.moreRows === 1 ? 'row is' : 'rows are'} in the table.</p>{/if}
							<p data-comparison={active.comparison}>{active.comparison}.</p>
						{:else if active.type === 'tileStrip'}
							{@const days = chooseDateSeriesDays(active.dateColumn, rows, lostDays)}
							{@const tiles = tileStrip(days.map(({ day, row }) => { const value = row === null ? null : readTruthValue(row, active.markColumn); return { date: day, state: value === null ? 'absent' : value ? 'fired' : 'quiet' }; }))}
							{@const tileReadout = readoutOf({ type: 'tileStrip', columns: days.map(({ day }) => `${day} UTC`), series: [{ label: active.markColumn, swatch: 'var(--chart-1)', values: days.map(({ row }) => { const value = row === null ? null : readTruthValue(row, active.markColumn); return value === null ? null : String(value); }), format: String }], notMeasured: 'null', resting: 'last' })}
							<div data-model-rule="no" data-model-rule-none="this page does not know which settings changed inside your span">
								<TileStrip geometry={tiles} empty={emptyState('quiet', 'No rows to draw.')} name="data-explorer-shape" label={`Which days: ${active.dateColumn}, ${active.markColumn}`} width={chartWidth} height={chartHeight} readout={tileReadout} stateWords={{ fired: 'true', quiet: 'false', absent: 'null' }} />
							</div>
							<p data-comparison={active.comparison}>{active.comparison}.</p>
						{:else if active.type === 'flow'}
							{@const records = rows.map((row) => factsOf(text(row, active.stageColumn), [active.arrivedColumn, active.wentOnColumn, ...active.droppedColumns].map((column) => ({ label: column, value: numericValue(row, column), format: (n) => text({ [column]: n }, column) })), 'null'))}
							<Flow geometry={flowDrawing} empty={emptyState('quiet', 'No rows to draw.')} name="data-explorer-shape" label={`Flow: ${[active.stageColumn, active.arrivedColumn, active.wentOnColumn, ...active.droppedColumns].join(', ')}`} width={chartWidth} height={chartHeight} readout={records} tooltips={false} />
							<p data-comparison={active.comparison}>{active.comparison}.</p>
						{:else if active.type === 'dateSeries'}
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
							<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
							<div tabindex="0" role="group" aria-label={`Spread readout: ${active.valueColumn}`} data-chart-readout-focus>
								<Distribution geometry={distribution(values, { frame: plotFrame, minValues: bounds.fleetMinRows, valueTicks: 4 })} empty={emptyState('too-few', tooFew(active) ?? 'Too few rows.')} name="data-explorer-shape" label={`Spread: ${active.valueColumn}`} width={chartWidth} height={chartHeight} />
							</div>
							<p data-comparison={active.comparison}>{active.comparison}.</p>
						{/if}
					</div>
				</div>
			{/if}
		{/key}
	</div>
	<div class="chart-foot" class:reserved={noteCount > 0} data-chart-foot bind:this={foot} style={`--chart-notes:${noteCount}`}>
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
	   so the row is the same height whichever chart is chosen. Its height is the page's
	   `--role-row-height`, which the result region's floor counts too. */
	.role-row {
		--role-gap: var(--space-3);
		box-sizing: border-box;
		display: grid;
		grid-template-columns: repeat(var(--role-slots), minmax(0, 1fr));
		grid-auto-rows: var(--workbench-control);
		column-gap: var(--role-gap);
		row-gap: var(--space-1);
		block-size: var(--role-row-height);
		padding: var(--space-1) var(--space-3);
	}

	/* The room from a slot's start to its line's end, in the units of the slot's own width, so a
	   pill's list knows its widest box before it is first laid out. */
	.role-slot {
		--pill-list-room: calc(var(--slots-to-end) * (100% + var(--role-gap)) - var(--role-gap));
		min-inline-size: 0;
	}

	/* Its own content never sizes the drawing. A plot is drawn at the box's height, and the page's
	   floor gives the box room for its figure, plot, readout and comparison, so a plot never
	   scrolls here; a ranked list longer than the box, a list and not a plot, still does. */
	.chart-body {
		contain: size;
		min-block-size: 0;
		overflow: auto;
		padding: 0 var(--space-3) var(--space-3);
	}

	/* The foot reserves `console.explorer_chart_note_lines` lines for the band, set as `--note-lines`
	   by the page, for each note the answer can give, and no room at all when it can give none, so
	   the drawing then reaches the panel's foot. A change of chart or column changes only its text,
	   and a longer note scrolls inside it. */
	.chart-foot {
		box-sizing: border-box;
		block-size: 0;
		overflow-y: auto;
		scrollbar-width: thin;
		scrollbar-color: var(--color-rule-strong) transparent;
		color: var(--color-text-secondary);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
	}

	.chart-foot.reserved {
		block-size: calc(var(--chart-notes) * var(--note-lines) * var(--leading-sm) + 2 * var(--space-1));
		padding: var(--space-1) var(--space-3);
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

	/* The figure and the comparison take the page's own line tokens, which the result region's
	   floor counts, so their lines are known before they are drawn. */
	.shape-stack .shape-lede {
		color: var(--color-text);
		font-size: var(--text-xl);
		font-weight: 700;
		line-height: var(--lede-line);
	}

	.shape-stack [data-comparison] {
		line-height: var(--comparison-line);
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
