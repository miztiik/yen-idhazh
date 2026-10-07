<script lang="ts">
	/** Draws a Data explorer answer with the chart type its columns can honestly support. */
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
	import { chooseDateSeriesDays, chooseExplorerShapes, numericValue, type ExplorerShape, type ExplorerShapeBounds, type ExplorerChartType } from './shape';
	import { printCell } from './answer';

	let { columns, rows, lostDays, bounds, height, selectedType = null }: { columns: readonly Column[]; rows: readonly Row[]; lostDays: readonly DateStamp[]; bounds: ExplorerShapeBounds; height: number; selectedType?: ExplorerChartType | null } = $props();

	const shapes = $derived(chooseExplorerShapes(columns, rows, bounds));
	const choices = $derived(shapes.filter((shape) => shape.kind === 'chart'));
	const active = $derived(choices.find((shape) => shape.type === selectedType) ?? shapes[0]);
	const note = $derived(noteFor(active));
	const chartTokens = ['--chart-1', '--chart-2', '--chart-3', '--chart-4'] as const;

	function text(row: Row, column: string): string {
		const spec = columns.find((one) => one.name === column) ?? { name: column, type: 'VARCHAR' };
		return printCell(spec, row[column]).text;
	}

	function noteFor(next: ExplorerShape): string {
		if (next.kind === 'none') return next.reason;
		if (next.type === 'dateSeries') {
			const why = `Drawn over time because the answer has a date column.`;
			return next.rowsWithNoDay === 0 ? why : `${why} ${rowsWithNoDaySentence(next.rowsWithNoDay, next.dateColumn)}`;
		}
		if (next.type === 'rankedList') return `Drawn ranked because the answer has one text column and one number column.`;
		if (next.type === 'pairedScatter') return `Drawn paired because the answer has two number columns.`;
		return `Drawn as a spread because the answer has one number column.`;
	}

	/** The rows a date chart does not draw because their day is NULL, which the table prints as `null`. */
	function rowsWithNoDaySentence(count: number, dateColumn: string): string {
		return count === 1
			? `1 row holds null in the column "${dateColumn}", so the chart does not draw it. It is in the table.`
			: `${count} rows hold null in the column "${dateColumn}", so the chart does not draw them. They are in the table.`;
	}

	function lede(next: ExplorerShape): string {
		if (next.kind === 'none') return 'No chart';
		if (next.type === 'dateSeries') {
			const main = next.mainFigure;
			return main === null ? `${next.days} UTC ${next.days === 1 ? 'day' : 'days'}` : `${text({ [main.column]: main.value }, { name: main.column, type: 'DOUBLE' }.name)} ${main.column} on ${main.date}`;
		}
		if (next.type === 'rankedList') return next.mainFigure === null ? `${rows.length} rows` : `${next.mainFigure.label}: ${text({ [next.mainFigure.column]: next.mainFigure.value }, next.mainFigure.column)} ${next.mainFigure.column}`;
		if (next.type === 'pairedScatter') return next.mainFigure;
		return next.mainFigure ?? `${rows.length} rows`;
	}

	function tooFew(next: ExplorerShape): string | null {
		if (next.kind === 'none' || !('tooFew' in next) || !next.tooFew) return null;
		if (next.type === 'dateSeries') return tooFewSentence(next.days, bounds.chartMinRows, 'UTC days');
		if (next.type === 'pairedScatter') {
			return next.readings < bounds.fleetMinRows
				? tooFewSentence(next.readings, bounds.fleetMinRows, 'readings')
				: tooFewSentence(next.subjects, bounds.bandwidthMinKinds, 'subjects');
		}
		if (next.type === 'distribution') return tooFewSentence(next.readings, bounds.fleetMinRows, 'readings');
		return null;
	}

	function readoutFor(next: ExplorerShape): { subject: string; facts: { label: string; value: string }[] } | null {
		if (next.kind === 'none') return null;
		if (next.type === 'dateSeries') {
			const row = [...rows].sort((left, right) => String(right[next.dateColumn]).localeCompare(String(left[next.dateColumn])))[0];
			if (!row) return null;
			return { subject: text(row, next.dateColumn), facts: next.seriesColumns.map((column) => ({ label: column, value: text(row, column) })) };
		}
		if (next.type === 'rankedList') {
			const row = [...rows].filter((candidate) => numericValue(candidate, next.valueColumn) !== null).sort((left, right) => (numericValue(right, next.valueColumn) ?? 0) - (numericValue(left, next.valueColumn) ?? 0))[0];
			return row ? { subject: text(row, next.labelColumn), facts: [{ label: next.valueColumn, value: text(row, next.valueColumn) }] } : null;
		}
		if (next.type === 'pairedScatter') {
			const row = rows.find((candidate) => numericValue(candidate, next.xColumn) !== null && numericValue(candidate, next.yColumn) !== null);
			if (!row) return null;
			return {
				subject: next.subjectColumn === null ? 'row 1' : text(row, next.subjectColumn),
				facts: [
					{ label: next.xColumn, value: text(row, next.xColumn) },
					{ label: next.yColumn, value: text(row, next.yColumn) }
				]
			};
		}
		const values = rows.map((row) => numericValue(row, next.valueColumn)).filter((one): one is number => one !== null).sort((a, b) => a - b);
		if (values.length === 0) return null;
		return { subject: next.valueColumn, facts: [{ label: 'middle', value: String(values[Math.floor(values.length / 2)]) }] };
	}
</script>

<div class="shape-panel" style={`--shape-height:${height}px`}>
	<p class="shape-note">{note}</p>
	{#if active.kind === 'none'}
		<div class="shape-none" data-shape-none>{active.reason}</div>
	{:else if tooFew(active)}
		<div class="shape-none" data-state="too-few">{tooFew(active)}</div>
	{:else}
		<p class="shape-lede" data-lede>{lede(active)}</p>
		{@const readout = readoutFor(active)}
		{#if active.type === 'dateSeries'}
			{@const box = frame(760, height)}
			{@const seriesColumns = active.seriesColumns}
			{@const days = chooseDateSeriesDays(active.dateColumn, rows, lostDays)}
			{@const dateGeometry = dateSeries(seriesColumns.map((column, index) => ({ label: column, token: chartTokens[index] ?? '--chart-1', points: days.map(({ day, row }) => ({ date: day, value: row === null ? null : numericValue(row, column) })) })), { frame: box, density: 6, valueTicks: 4, padding: 0.25 })}
			{@const dateReadout = readoutOf({ type: 'dateSeries', columns: days.map(({ day }) => day), series: seriesColumns.map((column, index) => ({ label: column, swatch: `var(--chart-${index + 1})`, values: days.map(({ row }) => (row === null ? null : numericValue(row, column))), format: (n) => text({ [column]: n }, column) })), notMeasured: 'No number for this day', resting: 'last' })}
			<div data-model-rule="no" data-model-rule-none="this page does not know which settings changed inside your span">
				<DateSeries geometry={dateGeometry} empty={emptyState('quiet', 'No rows to draw.')} name="data-explorer-shape" label={`Over time: ${[active.dateColumn, ...active.seriesColumns].join(', ')}`} width={760} {height} readout={dateReadout} />
			</div>
			<p data-comparison={active.comparison}>{active.comparison}.</p>
		{:else if active.type === 'rankedList'}
			{@const ranked = rank(rows.map((row) => ({ key: text(row, active.labelColumn), value: numericValue(row, active.valueColumn) ?? Number.NaN, row: { label: text(row, active.labelColumn), value: text(row, active.valueColumn) } })), active.rowsDrawn)}
			<RankedList caption={`Ranked by ${active.valueColumn}`} {ranked} maxText={`${text({ [active.valueColumn]: ranked.max }, active.valueColumn)} ${active.valueColumn}`} unmeasuredNote="No rows carried a number to rank." emptyNote="No rows carried a number to rank." tail={active.moreRows > 0 ? `${active.moreRows} more ${active.moreRows === 1 ? 'row is' : 'rows are'} in the table.` : null} />
			{#if readout}<dl class="shape-readout" data-readout="data-explorer-shape" data-readout-shape="record"><dt data-readout-subject>{readout.subject}</dt>{#each readout.facts as fact}<div data-readout-row={fact.label}><dd>{fact.label}</dd><dd>{fact.value}</dd></div>{/each}</dl>{/if}
			<p data-comparison={active.comparison}>{active.comparison}.</p>
		{:else if active.type === 'pairedScatter'}
			{@const box = frame(760, height)}
			{@const points = rows.flatMap((row, index) => numericValue(row, active.xColumn) === null || numericValue(row, active.yColumn) === null ? [] : [{ label: active.subjectColumn === null ? `row ${index + 1}` : text(row, active.subjectColumn), x: numericValue(row, active.xColumn) as number, y: numericValue(row, active.yColumn) as number }])}
			<PairedScatter geometry={pairedScatter(points, { frame: box, minRows: bounds.fleetMinRows, minSubjects: bounds.bandwidthMinKinds, valueTicks: 4 })} empty={emptyState('too-few', tooFew(active) ?? 'Too few rows.')} name="data-explorer-shape" label={`Paired: ${active.yColumn} against ${active.xColumn}`} width={760} {height} />
			<p data-comparison={active.comparison}>{active.comparison}.</p>
		{:else}
			{@const box = frame(760, height)}
			{@const values = rows.map((row) => numericValue(row, active.valueColumn)).filter((one): one is number => one !== null)}
			<Distribution geometry={distribution(values, { frame: box, minValues: bounds.fleetMinRows, valueTicks: 4 })} empty={emptyState('too-few', tooFew(active) ?? 'Too few rows.')} name="data-explorer-shape" label={`Spread: ${active.valueColumn}`} width={760} {height} />
			<p data-comparison={active.comparison}>{active.comparison}.</p>
		{/if}
	{/if}
</div>

<style>
	.shape-panel {
		display: grid;
		gap: var(--space-3);
	}

	.shape-note,
	.shape-panel p {
		margin: 0;
		color: var(--color-text-secondary);
	}

	.shape-lede {
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

	.shape-none {
		display: grid;
		place-items: center;
		padding: var(--space-6);
		color: var(--color-text-secondary);
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
