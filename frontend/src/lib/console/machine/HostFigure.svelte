<script lang="ts">
	/** One figure of the host panel: a reading, and the window it is read against.
	 *
	 * The panel hands in one formatter, so this run's reading and both ends of
	 * the span are written the same way. Three numbers formatted three ways are
	 * three facts a reader converts before they can be compared, and that
	 * comparison is what the track exists to make free.
	 *
	 * A band and an upright, drawn as boxes with CSS lengths: a track needs no
	 * coordinate system, so it needs no drawing surface either. The maths is in
	 * `$lib/charts/span-track`, where a second panel can reach it; the `data-host`
	 * vocabulary is this panel's, which is why this sits beside the panel.
	 *
	 * The type scale below repeats the panel's own, because component styles are
	 * scoped and a figure drawn here has to sit beside one written in the page
	 * without reading as a different kind of thing.
	 */
	import type { SpanTrack } from '$lib/charts/span-track';

	let {
		name,
		label,
		track,
		format,
		windowDays,
		note
	}: {
		/** The figure's key, which the panel's oracles read off the wrapper. */
		name: string;
		/** The figure's name, above the reading. */
		label: string;
		track: SpanTrack;
		/** How to write a reading. One function for every number here. */
		format: (value: number) => string;
		windowDays: number;
		/** What the figure means, in one line. */
		note?: string;
	} = $props();
</script>

<div
	class="figure"
	data-host={name}
	data-host-value={track.value ?? ''}
	data-host-span-low={track.low ?? ''}
	data-host-span-high={track.high ?? ''}
	data-host-span-scale={track.spanned ? track.scale : ''}
	data-host-span-from={track.from}
	data-host-span-out-of={track.outOf}
	data-host-span={track.spanned ? (track.drawn ? 'drawn' : 'printed') : 'unread'}
>
	<dt>{label}</dt>
	<dd>
		{#if track.value === null}
			<span class="absent" data-host-note="absent">Not recorded on this run.</span>
		{:else}
			{format(track.value)}
		{/if}

		{#if !track.spanned}
			<span class="unit" data-host-note="unread">
				No run in these {windowDays} days recorded a span for it, so there is nothing to read this
				run against.
			</span>
		{:else}
			<div
				class="track"
				role="img"
				aria-label="{label}: {track.value === null
					? 'not recorded this run'
					: format(track.value)}, against {format(track.low)} to {format(
					track.high
				)} over these {windowDays} days"
			>
				{#if track.drawn}
					<span
						class="band"
						data-host-mark="band"
						style="inset-inline-start: {track.start}; inline-size: {track.length}"
					></span>
				{:else}
					<span class="band flat" data-host-mark="band" style="inset-inline-start: {track.start}"
					></span>
				{/if}
				{#if track.value !== null}
					<span class="now" data-host-mark="now" style="inset-inline-start: {track.at}"></span>
				{/if}
			</div>
			<span class="unit" data-host-note="span">
				Over these {windowDays} days: {format(track.low)} to {format(track.high)}, on
				{track.from} of {track.outOf} runs. The track runs to {format(track.scale)}, the band is that
				span, and the upright is this run's own mark on it.
				{#if !track.drawn}
					<span data-host-note="mark"
						>The two ends sit closer together than a pixel of that track, so the band is a mark
						rather than a length.</span
					>
				{/if}
			</span>
		{/if}
		{#if note}
			<span class="unit">{note}</span>
		{/if}
	</dd>
</div>

<style>
	dt {
		font-size: var(--text-xs);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
	}

	dd {
		margin: var(--space-1) 0 0;
		font-size: var(--text-base);
		color: var(--color-text);
	}

	.track {
		position: relative;
		block-size: 1.5rem;
		margin-block-start: var(--space-2);
		border-radius: var(--radius-sm);
		background: var(--color-surface-sunken);
		overflow: hidden;
	}

	.band {
		position: absolute;
		inset-block: 0.375rem;
		background: var(--chart-3);
		border-radius: var(--radius-sm);
	}

	.band.flat {
		inline-size: 2px;
		margin-inline-start: -1px;
	}

	.now {
		position: absolute;
		inset-block: 0;
		inline-size: 2px;
		margin-inline-start: -1px;
		background: var(--color-text);
	}

	.unit {
		display: block;
		margin-top: var(--space-1);
		font-size: var(--text-xs);
		line-height: var(--leading-sm);
		color: var(--color-text-tertiary);
	}

	.absent {
		color: var(--color-text-tertiary);
	}
</style>
