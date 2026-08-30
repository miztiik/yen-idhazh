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
	import type { Snippet } from 'svelte';
	import type { EChartsOption } from 'echarts';

	let {
		label,
		value,
		note = null,
		line = null,
		tone = 'neutral',
		movement = null,
		trend = null,
		trendSvg = null,
		trendOption = null,
		windowed = null,
		windowDays = null
	}: {
		label: string;
		/** Already formatted. The card never does arithmetic on a number. */
		value: string;
		note?: string | null;
		/** What the figure means, in one sentence, under everything else.
		 *
		 * A table header has room for a label and nothing else, so an explanation
		 * put there is a paragraph in a column. A card has a body. */
		line?: string | null;
		tone?: 'neutral' | 'info' | 'good' | 'warn' | 'bad';
		/** Signed share, e.g. 0.12 for up 12 percent. Null prints nothing. */
		movement?: number | null;
		/** A trend drawn as markup, for a grid of cards that all want one.
		 *
		 * Eleven engine-backed sparklines is eleven chart instances and a lazy chunk
		 * on a page that already renders complete without one. Where both are given
		 * the engine wins, because it is the one that carries a domain. */
		trend?: Snippet | null;
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
	<p class="kpi-label" data-kpi-label>{label}</p>
	<p class="kpi-value tabular-nums" data-kpi-value>{value}</p>
	{#if trendSvg && trendOption}
		<div class="kpi-trend">
			<Chart svg={trendSvg} option={trendOption} width={220} height={34} label="{label}, recent trend" />
		</div>
	{:else if trend}
		<div class="kpi-trend">{@render trend()}</div>
	{/if}
	{#if movement !== null || note}
		<p class="kpi-foot">
			{#if movement !== null}
				<span class="kpi-move" data-direction={arrow}>{percent}</span>
			{/if}
			{#if note}<span class="kpi-note" data-kpi-note>{note}</span>{/if}
		</p>
	{/if}
	{#if line}<p class="kpi-line" data-kpi-line>{line}</p>{/if}
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

	.kpi-foot {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-2);
		margin: 0;
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}

	/* Last and quietest. The figure is what the operator came for; this is what
	   they read once, the first time. */
	.kpi-line {
		margin: 0;
		font-size: var(--text-xs);
		line-height: 1.45;
		color: var(--color-text-secondary);
	}

	.kpi-move[data-direction='up'] {
		color: var(--band-high);
	}
	.kpi-move[data-direction='down'] {
		color: var(--chart-4);
	}
</style>
