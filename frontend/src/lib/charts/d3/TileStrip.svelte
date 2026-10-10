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
	import { markReadout, type Readout } from '$lib/charts/readout';
	import ChartReadout from '$lib/components/ChartReadout.svelte';

	let {
		geometry,
		empty,
		name,
		label,
		width,
		height,
		readout = null,
		readoutMaxShare = 1,
		stateWords = { fired: 'fired', quiet: 'quiet', absent: 'not recorded' }
	}: {
		geometry: TileGeometry | null;
		empty: EmptyDrawing;
		name: string;
		label: string;
		width: number;
		height: number;
		readout?: Readout | null;
		readoutMaxShare?: number;
		stateWords?: Record<Tile['state'], string>;
	} = $props();
	let selected = $state<number | null>(null);

	function titleOf(tile: Tile): string {
		if (tile.state === 'absent') return `${tile.date}: ${stateWords.absent}`;
		const reading = tile.reading === null ? '' : `, ${tile.reading}`;
		return `${tile.date}: ${stateWords[tile.state]}${reading}`;
	}
</script>

{#if geometry === null}
	<EmptyState drawing={empty} {height} {width} {name} {label} />
{:else}
	<div data-readout-columns={readout === null ? undefined : readout.columns.length}>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<ol
		class="tiles"
		data-chart-type="tileStrip"
		data-chart-name={name}
		aria-label="{label} - {geometry.counts.fired} {stateWords.fired}, {geometry.counts.quiet} {stateWords.quiet}, {geometry.counts.absent} {stateWords.absent}"
		tabindex={readout === null ? undefined : 0}
		use:markReadout={{ count: geometry.tiles.length, walk: 'row', onSelect: (index) => selected = index }}
	>
		{#each geometry.tiles as tile, index (tile.date)}
			<li class="tile {tile.state}" data-tile-state={tile.state} data-readout-at={readout === null ? undefined : index} title={readout === null ? titleOf(tile) : undefined}></li>
		{/each}
	</ol>
	{#if readout !== null}
		<ChartReadout {readout} at={selected} {name} maxShare={readoutMaxShare} hint="Point at a UTC day to read it. Left and Right step through the days, Escape returns to the newest." restingNote=", the newest UTC day" />
	{/if}
	</div>
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
