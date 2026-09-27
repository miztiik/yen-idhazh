<script lang="ts">
	/** Draws a `flow` geometry: the diagram where the panel is wide, the stepped list where it is not.
	 *
	 * Both shapes come out of one call, so they report the same flow. In the
	 * diagram the flow that carried on takes its stage's hue and a loss takes
	 * the same hue fainter - it is the same items going a different way, not a
	 * different kind of thing - and every node is named beside itself with its
	 * count. The list is words and numbers only; where the counts are not one
	 * flow it says so above them.
	 */
	import { AXIS_LABEL_PX } from '$lib/charts/frame';
	import { grouped } from '$lib/charts/series';
	import EmptyState from './EmptyState.svelte';
	import type { EmptyDrawing } from './empty';
	import type { FlowGeometry, SteppedGeometry } from './flow';

	let {
		geometry,
		empty,
		name,
		label,
		width,
		height
	}: {
		geometry: FlowGeometry | SteppedGeometry | null;
		empty: EmptyDrawing;
		name: string;
		label: string;
		width: number;
		height: number;
	} = $props();

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
	<div class="stepped" data-chart-type="flow" data-chart-name={name} data-flow-shape="stepped">
		{#if geometry.note}<p class="stepped-note">{geometry.note}</p>{/if}
		<ol class="stepped-stages" aria-label={label}>
			{#each geometry.stages as stage (stage.label)}
				<li>
					<span class="stepped-name">{stage.label}</span>
					<span class="stepped-count">{grouped(stage.arrived)} ({stage.share}%)</span>
					{#if stage.drops.length > 0}
						<ul class="stepped-drops">
							{#each stage.drops as drop (drop.label)}
								<li>{drop.label}: {grouped(drop.count)} ({drop.share}%)</li>
							{/each}
						</ul>
					{/if}
				</li>
			{/each}
		</ol>
	</div>
{:else}
	{@const box = geometry.frame}
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
	>
		{#each geometry.ribbons as ribbon, index (index)}
			<path d={ribbon.path} fill="var(--chart-1)" fill-opacity={ribbon.drop ? LOST : CARRIED}>
				<title>{ribbon.from} to {ribbon.to}: {grouped(ribbon.value)}</title>
			</path>
		{/each}
		{#each geometry.nodes as node, index (index)}
			<rect
				x={node.x}
				y={node.y}
				width={node.width}
				height={node.height}
				fill="var(--chart-1)"
				fill-opacity={node.drop ? LOST : 1}
			/>
			<text
				x={node.x + node.width + LABEL_GAP}
				y={node.y + node.height / 2}
				dy="0.32em"
				fill="var(--color-text)"
				font-size={AXIS_LABEL_PX}>{node.label} {grouped(node.value)}</text
			>
		{/each}
	</svg>
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
