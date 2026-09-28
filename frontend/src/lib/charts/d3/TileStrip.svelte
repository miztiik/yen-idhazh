<script lang="ts">
	/** Draws a `tileStrip` geometry: one tile a day at one fixed height, in three states.
	 *
	 * An empty dashed cell is a day nobody recorded, an outlined tile is a day
	 * recorded quiet, and a filled tile is a day that fired, so each state reads
	 * differently from a metre away and an absence never passes for a clean day.
	 * The strip is the same height whether or not anything fired, so the page
	 * does not reflow on the morning something goes wrong. It carries no
	 * headline: the panel leads with the finding in words and the strip is the
	 * evidence.
	 */
	import EmptyState from './EmptyState.svelte';
	import type { EmptyDrawing } from './empty';
	import type { Tile, TileGeometry } from './tileStrip';

	let {
		geometry,
		empty,
		name,
		label,
		width,
		height
	}: {
		geometry: TileGeometry | null;
		empty: EmptyDrawing;
		name: string;
		label: string;
		width: number;
		height: number;
	} = $props();

	function titleOf(tile: Tile): string {
		if (tile.state === 'absent') return `${tile.date}: not recorded`;
		const reading = tile.reading === null ? '' : `, ${tile.reading}`;
		return `${tile.date}: ${tile.state}${reading}`;
	}
</script>

{#if geometry === null}
	<EmptyState drawing={empty} {height} {width} {name} {label} />
{:else}
	<ol
		class="tiles"
		data-chart-type="tileStrip"
		data-chart-name={name}
		aria-label="{label} - {geometry.counts.fired} fired, {geometry.counts.quiet} quiet, {geometry
			.counts.absent} not recorded"
	>
		{#each geometry.tiles as tile (tile.date)}
			<li class="tile {tile.state}" data-tile-state={tile.state} title={titleOf(tile)}></li>
		{/each}
	</ol>
{/if}

<style>
	.tiles {
		display: flex;
		gap: 2px;
		block-size: var(--space-5);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.tile {
		flex: 1 1 0;
		min-inline-size: 2px;
		box-sizing: border-box;
		border-radius: var(--radius-sm);
	}

	.tile.absent {
		border: 1px dashed var(--chart-axis);
	}

	.tile.quiet {
		border: 1px solid var(--chart-1);
	}

	.tile.fired {
		background: var(--chart-1);
	}
</style>
