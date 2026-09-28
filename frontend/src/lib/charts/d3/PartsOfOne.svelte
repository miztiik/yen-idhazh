<script lang="ts">
	/** Draws a `partsOfOne` geometry: each row one track, its parts laid along it in a fixed order.
	 *
	 * Markup, not paths: a part is a length along a track, and a length is what
	 * CSS draws best. Stacked parts sit end to end; overlapping parts are
	 * brackets that each start at the origin, one above the next, so none
	 * hides another and no row claims a total the parts do not make. The key
	 * names every part in order, because a hue is never the only thing that
	 * says which part is which.
	 */
	import EmptyState from './EmptyState.svelte';
	import type { EmptyDrawing } from './empty';
	import type { PartsGeometry } from './partsOfOne';

	let {
		geometry,
		empty,
		name,
		label,
		width,
		height
	}: {
		geometry: PartsGeometry | null;
		empty: EmptyDrawing;
		name: string;
		label: string;
		width: number;
		height: number;
	} = $props();
</script>

{#if geometry === null}
	<EmptyState drawing={empty} {height} {width} {name} {label} />
{:else}
	<div
		class="parts"
		data-chart-type="partsOfOne"
		data-chart-name={name}
		data-parts-overlapping={geometry.overlapping ? 'yes' : 'no'}
	>
		<ul class="parts-key" aria-label="{label} - the parts, in order">
			{#each geometry.key as part (part.label)}
				<li><span class="swatch" style="background: var({part.token})"></span>{part.label}</li>
			{/each}
		</ul>
		<ol class="parts-rows" aria-label={label}>
			{#each geometry.rows as row (row.label)}
				<li class="parts-row">
					<span class="parts-name">{row.label}</span>
					<span class="parts-track" class:overlapping={geometry.overlapping}>
						{#each row.segments as segment (segment.label)}
							<span
								class="parts-segment"
								title="{segment.label}: {segment.value}"
								style="inset-inline-start: {segment.start}; inline-size: {segment.size}; background: var({segment.token})"
							></span>
						{/each}
					</span>
					{#if row.total !== null}<span class="parts-total">{row.total}</span>{/if}
				</li>
			{/each}
		</ol>
	</div>
{/if}

<style>
	.parts {
		display: grid;
		gap: var(--space-3);
	}

	.parts-key {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-3);
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: var(--text-xs);
		color: var(--color-text-secondary);
	}

	.parts-key li {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
	}

	.swatch {
		inline-size: var(--space-3);
		block-size: var(--space-3);
		border-radius: var(--radius-sm);
	}

	.parts-rows {
		display: grid;
		gap: var(--space-2);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.parts-row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 3fr) auto;
		align-items: center;
		gap: var(--space-2);
		font-size: var(--text-sm);
	}

	.parts-name {
		overflow-wrap: anywhere;
	}

	.parts-track {
		position: relative;
		block-size: var(--space-4);
		background: var(--chart-grid);
		border-radius: var(--radius-sm);
	}

	.parts-segment {
		position: absolute;
		inset-block: 0;
	}

	/* A bracket each, stacked one lane apart, so a short part is never under a
	   long one. */
	.parts-track.overlapping {
		block-size: auto;
		min-block-size: var(--space-4);
		display: grid;
		gap: 1px;
	}

	.parts-track.overlapping .parts-segment {
		position: relative;
		inset-block: auto;
		block-size: var(--space-1);
	}

	.parts-total {
		font-variant-numeric: tabular-nums;
		color: var(--color-text-secondary);
	}
</style>
