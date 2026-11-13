<script lang="ts">
	/** Draw ordered runs and read only actual run values through the shared strip. */
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import { AXIS_LABEL_GAP_PX } from '$lib/charts/frame';
	import { pointerReadout, readoutMarks } from '$lib/charts/readout';
	import { ruleDeclaration } from '$lib/charts/d3/model-rule';
	import type { RunSeriesGeometry } from '$lib/charts/d3/runSeries';
	import type { EmptyDrawing } from '$lib/charts/d3/empty';
	import EmptyState from './EmptyState.svelte';

	let { geometry, empty, name, label, width, height, readoutMaxShare }: {
		geometry: RunSeriesGeometry | null;
		empty: EmptyDrawing;
		name: string;
		label: string;
		width: number;
		height: number;
		readoutMaxShare: number;
	} = $props();
	let selected = $state<number | null>(null);
	let readoutRoom = $state({ width: 0, height: 0 });
	const marks = $derived(readoutMarks(geometry?.columns ?? []));
	const showing = $derived(selected !== null && selected < marks.length ? selected : geometry?.readout.resting ?? null);
	const declaration = $derived(geometry === null ? null : ruleDeclaration(geometry.rule));

	/** A shorter reading must not clamp a bottom-of-page viewport and clear its hover. */
	function keepReadoutRoom(node: HTMLDivElement) {
		const observer = new ResizeObserver(() => {
			const { width, height } = node.getBoundingClientRect();
			readoutRoom = { width, height: width === readoutRoom.width ? Math.max(readoutRoom.height, height) : height };
		});
		observer.observe(node);
		return { destroy: () => observer.disconnect() };
	}
</script>

{#if geometry === null}
	<EmptyState drawing={empty} {height} {width} {name} {label} />
{:else}
	{@const box = geometry.frame}
	<div data-readout-columns={geometry.runs.length} data-run-series-selected={showing === null ? undefined : geometry.runs[showing]?.runId}
		data-model-rule={declaration?.value} data-model-rule-name={name} data-model-rule-none={declaration?.none}
		data-model-rule-from={geometry.runs[0]?.date} data-model-rule-to={geometry.runs.at(-1)?.date}>
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<svg class="run-series" viewBox="0 0 {box.width} {box.height}" width={box.width} height={box.height}
			role="img" aria-label={label} tabindex="0" data-chart-type="runSeries" data-chart-name={name}
			use:pointerReadout={{ marks, width: box.width, selected: showing, hover: { name, readout: geometry.readout }, onSelect: (index) => (selected = index) }}>
			{#each geometry.axis.ticks as tick (tick.value)}
				<line x1={box.left} x2={box.right} y1={tick.at} y2={tick.at} stroke="var(--chart-grid)" />
				{#if tick.text}
					<text x={box.left - AXIS_LABEL_GAP_PX} y={tick.at} dy="0.32em" text-anchor="end"
						fill="var(--color-text-tertiary)" font-size={box.labels.fontSize}>{tick.text}</text>
				{/if}
			{/each}
			<line x1={box.left} x2={box.right} y1={box.bottom} y2={box.bottom} stroke="var(--chart-axis)" />
			{#each geometry.ticks as tick (tick.index)}
				<line x1={geometry.columns[tick.index]} x2={geometry.columns[tick.index]}
					y1={box.bottom} y2={box.bottom + AXIS_LABEL_GAP_PX} stroke="var(--chart-axis)" />
				{#if tick.text}
					<text x={geometry.columns[tick.index]} y={box.bottom + AXIS_LABEL_GAP_PX + box.labels.fontSize}
						data-run-axis text-anchor={tick.anchor} fill="var(--color-text-tertiary)"
						font-size={box.labels.fontSize}>{tick.text}</text>
				{/if}
			{/each}
			{#each geometry.lines as trace (trace.label)}
				<path class="trace" class:dashed={trace.dashed} d={trace.path} fill="none" stroke="var({trace.token})"
					data-run-trace={trace.label} />
				{#each trace.points.filter((point) => point.alone || point.column === showing) as point (point.column)}
					<circle cx={point.x} cy={point.y} fill="var({trace.token})" stroke="var(--color-surface)"
						data-run-marker={trace.label} data-run-id={geometry.runs[point.column].runId}
						data-run-value={point.value} />
				{/each}
			{/each}
			{#each geometry.boundaries as boundary (`${boundary.date}/${boundary.kind}`)}
				<line x1={boundary.x} x2={boundary.x} y1={box.top} y2={box.bottom}
					stroke="var(--color-text-tertiary)" class="boundary" class:checker={boundary.kind === 'checker'}
					data-model-rule-line={boundary.date} data-model-rule-kind={boundary.kind} />
			{/each}
			{#if showing !== null}
				<line x1={geometry.columns[showing]} x2={geometry.columns[showing]} y1={box.top} y2={box.bottom}
					stroke="var(--chart-axis)" data-run-guide />
			{/if}
			{#each geometry.lines as trace (trace.label)}
				{#each trace.points.filter((point) => point.warning) as point (point.column)}
					<path class="warning" d="M -1 0 L 0 -1 L 1 0 L 0 1 Z"
						transform="translate({point.x} {point.y}) scale({box.labels.fontSize / 2})"
						fill="var(--color-surface)" stroke="var(--band-medium)" vector-effect="non-scaling-stroke"
						data-token-warning={trace.label} data-run-id={geometry.runs[point.column].runId}
						data-run-value={point.value} />
				{/each}
			{/each}
		</svg>
		<div style:min-block-size="{readoutRoom.height}px">
			<div class="readout-room" use:keepReadoutRoom>
				<ChartReadout readout={geometry.readout} at={selected} {name} maxShare={readoutMaxShare}
					restingNote=", the newest run"
					hint="Point or tap a run. Left/Right step; Home/End jump; Escape returns to the newest run." />
			</div>
		</div>
		{#if 'changes' in geometry.rule && geometry.rule.note !== null}
			<p data-model-rule-empty={geometry.rule.changes.length === 0 ? name : undefined}
				data-model-rule-unread={name}>{geometry.rule.note}</p>
		{/if}
	</div>
{/if}

<style>
	.run-series { display: block; max-inline-size: 100%; block-size: auto; }
	.run-series:focus-visible { outline: var(--console-chart-line-width) solid var(--color-focus); outline-offset: var(--space-1); }
	.trace.dashed, .boundary { stroke-dasharray: calc(var(--console-chart-line-width) * 4) calc(var(--console-chart-line-width) * 2); }
	.boundary.checker { stroke-dasharray: var(--console-chart-line-width) calc(var(--console-chart-line-width) * 2); }
	circle { r: calc(var(--console-chart-line-width) * 2); stroke-width: var(--console-chart-line-width); }
	.warning { stroke-width: var(--console-chart-line-width); }
	.readout-room { display: flow-root; }
</style>
