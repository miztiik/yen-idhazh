<script lang="ts">
	/** Draws a `flow` geometry: the diagram where the panel is wide, the stepped list where it is not.
	 *
	 * Both shapes come out of one call, so they report the same flow. In the
	 * diagram the flow that carried on takes its stage's hue and a loss takes
	 * the same hue fainter - it is the same items going a different way, not a
	 * different kind of thing - and every node is named beside itself with its
	 * count. Optional stage colours add decorative swatches to the list;
	 * tokenless callers keep their unmarked list and monochrome diagram.
	 */
	import { grouped as formatGrouped } from '$lib/charts/series';
	import { useNumberFormat } from '$lib/number-format-context';
	import EmptyState from './EmptyState.svelte';
	import type { EmptyDrawing } from './empty';
	import type { FlowGeometry, SteppedGeometry } from './flow';
	import { factsOf, markReadout, recordsOf, type ReadoutFacts } from '$lib/charts/readout';
	import ChartReadout from '$lib/components/ChartReadout.svelte';

	let {
		geometry,
		empty,
		name,
		label,
		width,
		height,
		readout = null,
		readoutMaxShare = 1
	}: {
		geometry: FlowGeometry | SteppedGeometry | null;
		empty: EmptyDrawing;
		name: string;
		label: string;
		width: number;
		height: number;
		readout?: readonly ReadoutFacts[] | null;
		readoutMaxShare?: number;
	} = $props();
	const numberFormat = useNumberFormat();
	const grouped = (value: number) => formatGrouped(value, numberFormat);
	let selected = $state<number | null>(null);
	const records = $derived(recordsOf(readout ?? (geometry === null ? []
		: geometry.kind === 'stepped'
			? geometry.stages.map((stage) => factsOf(stage.label, [
				{ label: 'Arrived', value: grouped(stage.arrived) },
				{ label: 'Share of reached', value: `${stage.share}%` },
				...stage.drops.map((drop) => ({ label: drop.label, value: `${grouped(drop.count)} (${drop.share}%)` }))
			], 'No recorded stage.'))
			: geometry.nodes.map((node) => factsOf(node.label, [
				{ label: 'Count', value: grouped(node.value) },
				...geometry.ribbons.filter((ribbon) => ribbon.from === node.label)
					.map((ribbon) => ({ label: `To ${ribbon.to}`, value: grouped(ribbon.value) }))
			], 'No recorded stage.')))));

	/** How strongly the flow that carried on and a loss are drawn. Low enough
	 * that a label crossing a ribbon still reads. */
	const CARRIED = 0.55;
	const LOST = 0.28;
	/** Clear pixels between a node and its name. */
	const LABEL_GAP = 4;
</script>

{#if geometry === null}
	<EmptyState drawing={empty} {height} {width} {name} {label} />
{:else if geometry.kind === 'stepped'}
	<div class="stepped" data-chart-type="flow" data-chart-name={name} data-flow-shape="stepped" data-readout-records={readout === null ? undefined : records.length} data-readout-none={readout === null ? 'This kept flow prints its counts without a separate reading strip; agreed with Susan' : undefined}>
		{#if geometry.note}<p class="stepped-note">{geometry.note}</p>{/if}
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<ol class="stepped-stages" aria-label={label} tabindex={readout === null ? undefined : 0} use:markReadout={{ count: records.length, walk: 'list', hover: { name, readout: records }, onSelect: (index) => selected = index }}>
			{#each geometry.stages as stage, index (stage.label)}
				<li data-readout-at={index}>
					<span class="stepped-name">{#if stage.token}<span class="stage-swatch" style:background="var({stage.token})" aria-hidden="true"></span>{/if}{stage.label}</span>
					<span class="stepped-count">{grouped(stage.arrived)} ({stage.share}%)</span>
					{#if stage.drops.length > 0}
						<ul class="stepped-drops">
							{#each stage.drops as drop (drop.label)}
								<li>{#if drop.token}<span class="stage-swatch" style:background="var({drop.token})" style:opacity={LOST} aria-hidden="true"></span>{/if}{drop.label}: {grouped(drop.count)} ({drop.share}%)</li>
							{/each}
						</ul>
					{/if}
				</li>
			{/each}
		</ol>
	</div>
{:else}
	{@const box = geometry.frame}
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<svg
		class="flow"
		viewBox="0 0 {box.width} {box.height}"
		width={box.width}
		height={box.height}
		role="img"
		aria-label={label}
		data-chart-type="flow"
		data-chart-name={name}
		data-flow-shape="diagram"
		data-readout-records={readout === null ? undefined : records.length}
		data-readout-none={readout === null ? 'This kept flow prints its counts without a separate reading strip; agreed with Susan' : undefined}
		tabindex={readout === null ? undefined : 0}
		use:markReadout={{ count: records.length, walk: 'row', hover: { name, readout: records }, onSelect: (index) => selected = index }}
	>
		{#each geometry.ribbons as ribbon, index (index)}
			<path data-readout-at={records.findIndex((record) => record.subject === ribbon.from)} d={ribbon.path} fill="var({ribbon.token ?? '--chart-1'})" fill-opacity={ribbon.drop ? LOST : CARRIED} aria-label={`${ribbon.from} to ${ribbon.to}: ${grouped(ribbon.value)}`}>
			</path>
		{/each}
		{#each geometry.nodes as node, index (index)}
			<rect
				data-readout-at={readout === null ? index : node.drop ? node.column - 1 : node.column}
				x={node.x}
				y={node.y}
				width={node.width}
				height={node.height}
				fill="var({node.token ?? '--chart-1'})"
				fill-opacity={node.drop ? LOST : 1}
			/>
			<text
				data-readout-at={readout === null ? index : node.drop ? node.column - 1 : node.column}
				x={readout !== null && geometry.columns > 1 && node.column === geometry.columns - 1 ? node.x - LABEL_GAP : node.x + node.width + LABEL_GAP}
				y={node.y + node.height / 2}
				text-anchor={readout !== null && geometry.columns > 1 && node.column === geometry.columns - 1 ? 'end' : undefined}
				dy="0.32em"
				fill="var(--color-text)"
				font-size={box.labels.fontSize}>{node.label} {grouped(node.value)}</text
			>
		{/each}
	</svg>
{/if}
{#if geometry !== null && readout !== null}
	<div data-readout-records={records.length}>
		<ChartReadout readout={records[selected ?? 0] ?? null} {name} maxShare={readoutMaxShare} resting={selected === null} hint={geometry.kind === 'stepped' ? 'Point at a stage to read it. Up and Down step through the stages, Escape returns to the first.' : 'Point at a stage to read it. Left and Right step through the stages, Escape returns to the first.'} />
	</div>
{/if}

<style>
	.stepped {
		display: grid;
		gap: var(--space-2);
		font-size: var(--text-sm);
	}

	.stepped-note {
		margin: 0;
		color: var(--color-text-secondary);
	}

	.stepped-stages {
		display: grid;
		gap: var(--space-2);
		margin: 0;
		padding-inline-start: var(--space-5);
	}

	.stepped-name {
		font-weight: 600;
	}

	.stage-swatch {
		display: inline-block;
		inline-size: var(--space-2);
		block-size: var(--space-2);
		margin-inline-end: var(--space-2);
	}

	.stepped-count {
		margin-inline-start: var(--space-2);
		font-variant-numeric: tabular-nums;
	}

	.stepped-drops {
		margin: var(--space-1) 0 0;
		padding-inline-start: var(--space-4);
		color: var(--color-text-secondary);
	}
</style>
