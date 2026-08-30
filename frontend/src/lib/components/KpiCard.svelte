<script lang="ts">
	/** One number, its label, its movement, its tint.
	 *
	 * The unit the console was missing. A table row makes a reader scan for the
	 * number that matters; a card puts it at reading size with its own name
	 * beside it, and the tint says whether it is a fact, a warning or a fault
	 * without spending a sentence on it.
	 *
	 * The sparkline is optional and secondary. Where there is no history the
	 * card is still a card - an empty plot area with a dash in it is worse than
	 * no plot at all.
	 */
	import Chart from '$lib/charts/Chart.svelte';
	import { percentOf } from '$lib/charts/rank';
	import type { EChartsOption } from 'echarts';

	let {
		label,
		value,
		note = null,
		tone = 'neutral',
		movement = null,
		track = null,
		trendSvg = null,
		trendOption = null,
		windowed = null,
		windowDays = null
	}: {
		label: string;
		/** Already formatted. The card never does arithmetic on a number. */
		value: string;
		note?: string | null;
		tone?: 'neutral' | 'info' | 'good' | 'warn' | 'bad';
		/** Signed share, e.g. 0.12 for up 12 percent. Null prints nothing. */
		movement?: number | null;
		/** How full something is, and what it is full of. A level against a limit
		 * that will not move is a length the eye reads without arithmetic - and
		 * the caption is required, because a bar with no named limit says only
		 * that a bar exists. */
		track?: { fraction: number; caption: string } | null;
		trendSvg?: string | null;
		trendOption?: EChartsOption | null;
		/** Names the card as following the page's time window. Null where it does
		 * not, which is most of them - only a rate has a span. */
		windowed?: string | null;
		windowDays?: number | null;
	} = $props();

	const arrow = $derived(movement === null ? '' : movement >= 0 ? 'up' : 'down');
	const percent = $derived(
		movement === null ? '' : `${movement >= 0 ? '+' : ''}${Math.round(movement * 100)}%`
	);
</script>

<div
	class="kpi"
	data-kpi={label}
	data-tone={tone}
	data-windowed={windowed}
	data-window-days={windowDays}
>
	<p class="kpi-label">{label}</p>
	<p class="kpi-value tabular-nums">{value}</p>
	{#if track}
		<div
			class="kpi-track"
			data-kpi-track={label}
			data-kpi-fraction={track.fraction.toFixed(6)}
			role="img"
			aria-label="{label}: {value}, {track.caption}."
		>
			<span class="kpi-track-fill" style="inline-size: {percentOf(track.fraction)}"></span>
		</div>
		<p class="kpi-track-caption" data-kpi-caption={label}>{track.caption}</p>
	{/if}
	{#if trendSvg && trendOption}
		<div class="kpi-trend">
			<Chart svg={trendSvg} option={trendOption} width={220} height={34} label="{label}, recent trend" />
		</div>
	{/if}
	<p class="kpi-foot">
		{#if movement !== null}
			<span class="kpi-move" data-direction={arrow}>{percent}</span>
		{/if}
		{#if note}<span class="kpi-note">{note}</span>{/if}
	</p>
</div>

<style>
	.kpi {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		padding: var(--space-4);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-lg);
		background: var(--tint-neutral);
		box-shadow: var(--shadow-sm);
	}

	/* The panel takes the hue of what it means, which is the same rule the
	   confidence marks follow. */
	.kpi[data-tone='info'] {
		background: var(--tint-info);
	}
	.kpi[data-tone='good'] {
		background: var(--tint-good);
	}
	.kpi[data-tone='warn'] {
		background: var(--tint-warn);
	}
	.kpi[data-tone='bad'] {
		background: var(--tint-bad);
	}

	.kpi-label {
		margin: 0;
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}

	.kpi-value {
		margin: 0;
		font-size: var(--text-2xl);
		line-height: var(--leading-2xl);
		font-weight: 600;
		color: var(--color-text);
	}

	.kpi-trend {
		margin-block: var(--space-1);
	}

	/* The same track the target bars draw, minus the marker: this limit is the
	   whole length of the bar rather than a line across it. */
	.kpi-track {
		position: relative;
		block-size: 10px;
		margin-block-start: var(--space-1);
		border-radius: var(--radius-full);
		background: var(--color-surface-sunken);
		overflow: hidden;
	}

	.kpi-track-fill {
		display: block;
		block-size: 100%;
		/* A minimum, so a level far under its limit is still a mark on the track
		   rather than an empty bar that reads as nothing measured. */
		min-inline-size: 2px;
		border-radius: var(--radius-full);
		background: var(--chart-1);
	}

	.kpi[data-tone='warn'] .kpi-track-fill {
		background: var(--fill-medium);
	}
	.kpi[data-tone='bad'] .kpi-track-fill {
		background: var(--fill-low);
	}

	.kpi-track-caption {
		margin: 0;
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}

	.kpi-foot {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-2);
		margin: 0;
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}

	.kpi-move[data-direction='up'] {
		color: var(--band-high);
	}
	.kpi-move[data-direction='down'] {
		color: var(--chart-4);
	}
</style>
