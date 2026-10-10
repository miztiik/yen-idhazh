<script lang="ts">
	/** A console panel that exists only to prove the sufficiency gates.
	 *
	 * It draws the real panel frame, the real trend and the real empty states,
	 * and every attribute a gate reads is set from its props. One set of props
	 * clears every gate a selector can decide; each bad set moves exactly one
	 * thing a real panel could get wrong. Nothing under `frontend/src/` imports
	 * it: a spec compiles it for the server and mounts it with the real tokens.
	 */
	import Panel from '$lib/components/Panel.svelte';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import type { SeriesGeometry } from '$lib/charts/d3/dateSeries';
	import type { EmptyDrawing } from '$lib/charts/d3/empty';

	let {
		id,
		title,
		note,
		geometry,
		empty,
		lede,
		ledes = 1,
		comparison,
		ruleNote,
		plotShare = 1,
		plotTinted = false
	}: {
		id: string;
		title: string;
		note: string;
		/** The trend, or null to draw `empty` where it would be. */
		geometry: SeriesGeometry | null;
		empty: EmptyDrawing;
		/** The one figure meant to land first. */
		lede: string;
		/** How many elements carry `data-lede`. One is right. */
		ledes?: number;
		/** The comparison the panel declares, or null for none. */
		comparison: string | null;
		/** The sentence saying no setting changed inside the span, or null to
		 * leave the trend with no settings-change declaration at all. */
		ruleNote: string | null;
		/** The share of the panel's width the plot is drawn across. */
		plotShare?: number;
		/** A ground of its own under the plot, which a real panel must not have. */
		plotTinted?: boolean;
	} = $props();

	const trend = $derived(`${id}-trend`);
	const copies = $derived(Array.from({ length: ledes }, (_, at) => at));
</script>

<Panel {title} {id} {note}>
	<div class="witness-body" data-comparison={comparison ?? undefined}>
		{#if geometry !== null}
			{#each copies as at (at)}
				<p class="witness-lede" data-lede>{lede}</p>
			{/each}
		{/if}
		<div
			class="witness-plot"
			class:tinted={plotTinted}
			style="inline-size: {plotShare * 100}%"
		>
			<DateSeries
				geometry={geometry === null ? null : { ...geometry, rule: { changes: [], note: ruleNote } }}
				{empty}
				name={trend}
				label="Minutes to write one summary, one day at a time"
				width={geometry?.frame.width ?? 760}
				height={geometry?.frame.height ?? 220}
			/>
		</div>
	</div>
</Panel>

<style>
	.witness-lede {
		margin: 0 0 var(--space-3);
		font-size: var(--text-3xl);
		font-weight: 600;
		line-height: 1.1;
		color: var(--color-text);
	}

	/* The trend is drawn at one authored width and scaled to its column, so the
	   share a gate measures is the share this wrapper is given. */
	.witness-plot :global(svg) {
		display: block;
		inline-size: 100%;
		block-size: auto;
	}

	.witness-plot.tinted {
		background: var(--color-surface-sunken);
	}

</style>
