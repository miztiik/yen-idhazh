<script lang="ts">
	/** Draws a Records answer with the chart type its columns can honestly support. */
	import type { Column, Row } from '$lib/data/ledger';
	import { tooFewSentence } from '$lib/console/waiting';
	import { chooseExplorerShapes, type ExplorerShape, type ExplorerShapeBounds, type ExplorerChartType } from './shape';
	import { printCell } from './answer';

	let { columns, rows, bounds, height, selectedType = null }: { columns: readonly Column[]; rows: readonly Row[]; bounds: ExplorerShapeBounds; height: number; selectedType?: ExplorerChartType | null } = $props();

	const shapes = $derived(chooseExplorerShapes(columns, rows, bounds));
	const choices = $derived(shapes.filter((shape) => shape.kind === 'chart'));
	const active = $derived(choices.find((shape) => shape.type === selectedType) ?? shapes[0]);
	const note = $derived(noteFor(active));

	function value(row: Row, column: string): number | null {
		const parsed = Number(row[column]);
		return Number.isFinite(parsed) ? parsed : null;
	}

	function valueOrZero(row: Row, column: string): number {
		return value(row, column) ?? 0;
	}

	function text(row: Row, column: string): string {
		const spec = columns.find((one) => one.name === column) ?? { name: column, type: 'VARCHAR' };
		return printCell(spec, row[column]).text;
	}

	function noteFor(next: ExplorerShape): string {
		if (next.kind === 'none') return next.reason;
		if (next.type === 'dateSeries') return `Drawn over time because the answer has a date column.`;
		if (next.type === 'rankedList') return `Drawn ranked because the answer has one text column and one number column.`;
		if (next.type === 'pairedScatter') return `Drawn paired because the answer has two number columns.`;
		return `Drawn as a spread because the answer has one number column.`;
	}

	function lede(next: ExplorerShape): string {
		if (next.kind === 'none') return 'No chart';
		if (next.type === 'dateSeries') {
			const main = next.mainFigure;
			return main === null ? `${rows.length} UTC ${rows.length === 1 ? 'day' : 'days'}` : `${text({ [main.column]: main.value }, { name: main.column, type: 'DOUBLE' }.name)} ${main.column} on ${main.date}`;
		}
		if (next.type === 'rankedList') return next.mainFigure === null ? `${rows.length} rows` : `${next.mainFigure.label}: ${text({ [next.mainFigure.column]: next.mainFigure.value }, next.mainFigure.column)} ${next.mainFigure.column}`;
		if (next.type === 'pairedScatter') return next.mainFigure;
		return next.mainFigure ?? `${rows.length} rows`;
	}

	function tooFew(next: ExplorerShape): string | null {
		if (next.kind === 'none' || !('tooFew' in next) || !next.tooFew) return null;
		if (next.type === 'dateSeries') return tooFewSentence(rows.length, bounds.chartMinRows, 'UTC days');
		if (next.type === 'pairedScatter') return tooFewSentence(rows.length, bounds.fleetMinRows, 'readings');
		if (next.type === 'distribution') return tooFewSentence(rows.length, bounds.fleetMinRows, 'readings');
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
			const row = [...rows].sort((left, right) => valueOrZero(right, next.valueColumn) - valueOrZero(left, next.valueColumn))[0];
			return row ? { subject: text(row, next.labelColumn), facts: [{ label: next.valueColumn, value: text(row, next.valueColumn) }] } : null;
		}
		if (next.type === 'pairedScatter') {
			const row = rows.find((candidate) => value(candidate, next.xColumn) !== null && value(candidate, next.yColumn) !== null);
			if (!row) return null;
			return {
				subject: next.subjectColumn === null ? 'row 1' : text(row, next.subjectColumn),
				facts: [
					{ label: next.xColumn, value: text(row, next.xColumn) },
					{ label: next.yColumn, value: text(row, next.yColumn) }
				]
			};
		}
		const values = rows.map((row) => value(row, next.valueColumn)).filter((one): one is number => one !== null).sort((a, b) => a - b);
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
			<div
				class="date-shape"
				data-chart="data-explorer-shape"
				data-chart-type="dateSeries"
				data-readout-records={rows.length}
				data-model-rule="no"
				data-model-rule-none="this page does not know which settings changed inside your span"
				aria-label={`Over time: ${[active.dateColumn, ...active.seriesColumns].join(', ')}`}
			>
				{#each active.seriesColumns as column, at (column)}
					{@const numericRows = rows.filter((row) => value(row, column) !== null)}
					{@const max = Math.max(1, ...numericRows.map((row) => valueOrZero(row, column)))}
					<div class="series-row" style={`--series:${at + 1}`}>
						<span>{column}</span>
						<ol>
							{#each numericRows as row (String(row[active.dateColumn]))}
								<li style={`block-size:${Math.max(3, (valueOrZero(row, column) / max) * 100)}%`} aria-label={`${text(row, active.dateColumn)}: ${text(row, column)} ${column}`}></li>
							{/each}
						</ol>
					</div>
				{/each}
			</div>
			{#if readout}<dl class="shape-readout" data-readout="data-explorer-shape" data-readout-shape="record"><dt data-readout-subject>{readout.subject}</dt>{#each readout.facts as fact}<div data-readout-row={fact.label}><dd>{fact.label}</dd><dd>{fact.value}</dd></div>{/each}</dl>{/if}
			<p data-comparison={active.comparison}>{active.comparison}.</p>
		{:else if active.type === 'rankedList'}
			{@const ordered = [...rows].filter((row) => value(row, active.valueColumn) !== null).sort((left, right) => valueOrZero(right, active.valueColumn) - valueOrZero(left, active.valueColumn)).slice(0, active.rowsDrawn)}
			{@const max = Math.max(1, ...ordered.map((row) => valueOrZero(row, active.valueColumn)))}
			<div class="ranked-shape" data-chart="data-explorer-shape" data-chart-type="rankedList" data-readout-none="every row prints its own value beside its bar; agreed with Susan">
				{#each ordered as row (String(row[active.labelColumn]))}
					<div class="rank-row">
						<span>{text(row, active.labelColumn)}</span>
						<strong>{text(row, active.valueColumn)}</strong>
						<i style={`inline-size:${(valueOrZero(row, active.valueColumn) / max) * 100}%`}></i>
					</div>
				{/each}
				{#if active.moreRows > 0}<p>{active.moreRows} more rows are in the table.</p>{/if}
			</div>
			{#if readout}<dl class="shape-readout" data-readout="data-explorer-shape" data-readout-shape="record"><dt data-readout-subject>{readout.subject}</dt>{#each readout.facts as fact}<div data-readout-row={fact.label}><dd>{fact.label}</dd><dd>{fact.value}</dd></div>{/each}</dl>{/if}
			<p data-comparison={active.comparison}>{active.comparison}.</p>
		{:else if active.type === 'pairedScatter'}
			<div class="scatter-shape" data-chart="data-explorer-shape" data-chart-type="pairedScatter" data-readout-records={rows.length} aria-label={`Paired: ${active.yColumn} against ${active.xColumn}`}>
				{#each rows.filter((row) => value(row, active.xColumn) !== null && value(row, active.yColumn) !== null) as row, index (index)}
					<span
						style={`inset-inline-start:${Math.min(96, Math.max(4, valueOrZero(row, active.xColumn)))}%;inset-block-end:${Math.min(96, Math.max(4, valueOrZero(row, active.yColumn)))}%`}
						aria-label={`${active.subjectColumn === null ? `row ${index + 1}` : text(row, active.subjectColumn)}: ${active.xColumn} ${text(row, active.xColumn)}, ${active.yColumn} ${text(row, active.yColumn)}`}
					></span>
				{/each}
			</div>
			{#if readout}<dl class="shape-readout" data-readout="data-explorer-shape" data-readout-shape="record"><dt data-readout-subject>{readout.subject}</dt>{#each readout.facts as fact}<div data-readout-row={fact.label}><dd>{fact.label}</dd><dd>{fact.value}</dd></div>{/each}</dl>{/if}
			<p data-comparison={active.comparison}>{active.comparison}.</p>
		{:else}
			{@const values = rows.map((row) => value(row, active.valueColumn)).filter((one): one is number => one !== null).sort((a, b) => a - b)}
			{@const max = Math.max(1, ...values)}
			<div class="spread-shape" data-chart="data-explorer-shape" data-chart-type="distribution" data-readout-records={values.length} aria-label={`Spread: ${active.valueColumn}`}>
				{#each values as one, index (index)}
					<i style={`block-size:${Math.max(3, (one / max) * 100)}%`} aria-label={`${active.valueColumn} ${one}`}></i>
				{/each}
			</div>
			{#if readout}<dl class="shape-readout" data-readout="data-explorer-shape" data-readout-shape="record"><dt data-readout-subject>{readout.subject}</dt>{#each readout.facts as fact}<div data-readout-row={fact.label}><dd>{fact.label}</dd><dd>{fact.value}</dd></div>{/each}</dl>{/if}
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
	.date-shape,
	.ranked-shape,
	.scatter-shape,
	.spread-shape {
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

	.date-shape,
	.spread-shape {
		display: flex;
		align-items: end;
		gap: var(--space-3);
		padding: var(--space-5);
	}

	.series-row {
		flex: 1;
		display: grid;
		gap: var(--space-2);
	}

	.series-row span {
		color: var(--color-text-secondary);
		font-size: var(--text-xs);
	}

	.series-row ol {
		display: flex;
		align-items: end;
		gap: 2px;
		block-size: calc(var(--shape-height) - 4rem);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.series-row li,
	.spread-shape i {
		flex: 1;
		border-radius: var(--radius-full) var(--radius-full) 0 0;
		background: var(--chart-1);
	}

	.ranked-shape {
		display: grid;
		align-content: start;
		gap: var(--space-2);
		padding: var(--space-5);
	}

	.rank-row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: var(--space-2);
	}

	.rank-row i {
		grid-column: 1 / -1;
		block-size: 0.5rem;
		border-radius: var(--radius-full);
		background: var(--chart-1);
	}

	.scatter-shape {
		position: relative;
	}

	.scatter-shape span {
		position: absolute;
		inline-size: 0.5rem;
		block-size: 0.5rem;
		border: 2px solid var(--chart-1);
		border-radius: var(--radius-full);
		transform: translate(-50%, 50%);
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
