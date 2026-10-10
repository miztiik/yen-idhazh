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
	import { tileWindow } from '$lib/charts/d3/tileStrip';
	import { chartWidth, dayTicks, observeWidth } from '$lib/charts/frame';
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
		tileMinPx,
		showAxis = true,
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
		tileMinPx?: number;
		showAxis?: boolean;
		stateWords?: Record<Tile['state'], string>;
	} = $props();
	let selected = $state<number | null>(null);
	let measured = $state<number | null>(null);
	const visible = $derived(geometry === null ? null : tileWindow(geometry, chartWidth(measured, width), tileMinPx));
	const endpoints = $derived(visible === null || visible.tiles.length === 0 ? [] : dayTicks(
		[visible.tiles[0].date, visible.tiles[visible.tiles.length - 1].date],
		{ density: 2, columns: [0, chartWidth(measured, width)] }
	));
	$effect(() => {
		if (selected !== null && visible !== null &&
			(selected < visible.offset || selected >= visible.offset + visible.tiles.length)) selected = null;
	});

	function titleOf(tile: Tile): string {
		if (tile.state === 'absent') return `${tile.date}: ${stateWords.absent}`;
		const reading = tile.reading === null ? '' : `, ${tile.reading}`;
		return `${tile.date}: ${stateWords[tile.state]}${reading}`;
	}
</script>

{#if geometry === null}
	<EmptyState drawing={empty} {height} {width} {name} {label} />
{:else}
	<div use:observeWidth={(value) => measured = value} data-readout-columns={readout === null ? undefined : readout.columns.length}
		data-readout-none={readout === null ? 'This kept tile strip has no separate reading strip; agreed with Susan' : undefined}>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<ol
		class="tiles"
		data-chart-type="tileStrip"
		data-chart-name={name}
		aria-label="{label} - {geometry.counts.fired} {stateWords.fired}, {geometry.counts.quiet} {stateWords.quiet}, {geometry.counts.absent} {stateWords.absent}"
		tabindex={readout === null ? undefined : 0}
		use:markReadout={{ count: visible?.tiles.length ?? 0, selected: selected === null ? null : selected - (visible?.offset ?? 0), walk: 'row', onSelect: (index) => selected = index === null ? null : index + (visible?.offset ?? 0) }}
	>
		{#each visible?.tiles ?? [] as tile, index (tile.date)}
			<li class="tile {tile.state}" style:min-inline-size={tileMinPx === undefined ? undefined : `${tileMinPx}px`} data-tile-state={tile.state} data-readout-at={readout === null ? undefined : index} aria-label={titleOf(tile)}></li>
		{/each}
	</ol>
	{#if tileMinPx !== undefined && showAxis}
		<div class="tile-axis" data-tile-axis>{#each endpoints as tick (tick.index)}<span>{tick.text}</span>{/each}</div>
	{/if}
	{#if visible?.overflow}<p class="tile-overflow" data-tile-overflow>{visible.overflow}</p>{/if}
	{#if readout !== null}
		<ChartReadout {readout} at={selected} {name} maxShare={readoutMaxShare} hint="Point at a UTC day to read it. Left and Right step through the days, Escape returns to the newest." restingNote=", the newest UTC day" />
	{/if}
	</div>
{/if}

<style>
	.tile-axis { display: flex; justify-content: space-between; color: var(--color-text-tertiary); font-size: var(--text-xs); }
	.tile-overflow { margin: var(--space-2) 0 0; color: var(--color-text-secondary); font-size: var(--text-xs); }
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
