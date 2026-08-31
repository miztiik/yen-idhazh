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
	 *
	 * A trend arrives one of two ways. An engine-backed pair (a server-drawn SVG
	 * and the option that redraws it) is right where the shape needs a scale and
	 * an axis. Markup is right where it does not: it costs no chunk, it follows
	 * the page's window with no second drawing on the server, and it is finished
	 * before any script runs.
	 */
	import Chart from '$lib/charts/Chart.svelte';
	import { percentOf } from '$lib/charts/rank';
	import { movementVerdict, type MovementPolarity } from '$lib/charts/theme';
	import type { EChartsOption } from 'echarts';
	import type { Snippet } from 'svelte';

	let {
		label,
		value,
		note = null,
		line = null,
		tone = 'neutral',
		movement = null,
		polarity = 'no-agreed-direction',
		track = null,
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
		/** Which direction is the good one for THIS measure. The card never guesses
		 * it: the default says nobody agreed, which paints neutral and says so. */
		polarity?: MovementPolarity;
		/** How full something is, and what it is full of. A level against a limit
		 * that will not move is a length the eye reads without arithmetic - and
		 * the caption is required, because a bar with no named limit says only
		 * that a bar exists. */
		track?: { fraction: number; caption: string } | null;
		/** A trend drawn as markup, in the card's own trend slot.
		 *
		 * Eleven engine-backed sparklines is eleven chart instances and a lazy chunk
		 * on a page that already renders complete without one, so a grid of cards
		 * takes this one and it wins where both are given. */
		trend?: Snippet | null;
		trendSvg?: string | null;
		trendOption?: EChartsOption | null;
		/** Names the card as following the page's time window. Null where it does
		 * not, which is most of them - only a rate has a span. */
		windowed?: string | null;
		windowDays?: number | null;
	} = $props();

	const percent = $derived(
		movement === null ? '' : `${movement >= 0 ? '+' : ''}${Math.round(movement * 100)}%`
	);
	const verdict = $derived(movementVerdict(movement, polarity));
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
	{#if trend}
		<div class="kpi-trend">{@render trend()}</div>
	{:else if trendSvg && trendOption}
		<div class="kpi-trend">
			<Chart svg={trendSvg} option={trendOption} width={220} height={34} label="{label}, recent trend" />
		</div>
	{/if}
	{#if movement !== null || note}
		<p class="kpi-foot">
			{#if movement !== null}
				<span
					class="kpi-move"
					data-movement={movement.toFixed(4)}
					data-polarity={polarity}
					data-movement-verdict={verdict}
					data-movement-paint="color">{percent}</span
				>
				<!-- Susan, 2026-08-31: a movement nobody agreed a direction for is a
				     fact, not a verdict, and the card has to SAY that rather than
				     leave a grey number the reader has to interpret. -->
				{#if polarity === 'no-agreed-direction'}
					<span class="kpi-move-note" data-movement-note={label}>no target</span>
				{/if}
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

	/* Last and quietest. The figure is what the operator came for; this is what
	   they read once, the first time. */
	.kpi-line {
		margin: 0;
		font-size: var(--text-xs);
		line-height: 1.45;
		color: var(--color-text-secondary);
	}

	/* The movement pair, never the confidence ramp. Green there means "it
	   worked"; a summary that got 3 percent slower is not broken, and painting
	   it in --band-low is how an operator learns to ignore --band-low. The sign
	   and the arrow direction carry the same fact, so the colour is never the
	   only signal. */
	.kpi-move[data-movement-verdict='good'] {
		color: var(--movement-good);
	}
	.kpi-move[data-movement-verdict='bad'] {
		color: var(--movement-bad);
	}
	.kpi-move[data-movement-verdict='neutral'] {
		color: var(--color-text-secondary);
	}

	.kpi-move-note {
		color: var(--color-text-tertiary);
	}
</style>
