<script lang="ts">
	/** A value against the threshold it is judged by.
	 *
	 * A bare count cannot answer the operator's question. "12 failures" means
	 * nothing until the number that rests a feed is beside it, and "4.1 minutes"
	 * means nothing until the 6 that retires the chart arm is on the same track.
	 * So the threshold is a marker the eye measures against, not a subtraction
	 * the reader performs.
	 *
	 * Markup rather than a chart, because the same bar has to work seventy times
	 * inside a ranked list. The geometry comes from `targetGeometry`, which the
	 * engine-backed target bar also reads, so the two can never disagree about
	 * where the marker sits or what counts as near.
	 */
	import type { TargetMarks } from '../charts/targetbar';

	let {
		marks,
		label,
		valueText,
		targetText,
		emptyNote,
		tone = 'policy'
	}: {
		marks: TargetMarks;
		/** What is being measured. Words, never a ledger column name. */
		label: string;
		/** The value, already formatted with its unit. */
		valueText: string;
		/** What the marker is, as a phrase - `rested at 5 failures`. */
		targetText: string;
		/** What to print when nothing was measured. Absence prints as absence. */
		emptyNote: string;
		/** `health` earns the confidence ramp: quarantine really is good, watch
		 * or bad. `policy` does not - a threshold somebody chose is not a verdict
		 * on the machine, and tinting it would invent one. */
		tone?: 'policy' | 'health';
	} = $props();
</script>

<div
	class="target"
	data-target-bar={label}
	data-target-band={marks.band}
	data-target-tone={tone}
	data-readout-none="one value against one threshold, and both are already in words"
>
	<p class="target-head">
		<span class="target-label">{label}</span>
		<span class="target-value tabular-nums" data-target-cell="value">
			{marks.empty ? '-' : valueText}
		</span>
	</p>

	{#if marks.empty}
		<p class="target-empty" data-target-cell="empty">{emptyNote}</p>
	{:else}
		<div
			class="target-track"
			data-target-cell="track"
			role="img"
			aria-label="{label}: {valueText}, {targetText}."
		>
			<span
				class="target-fill"
				data-target-cell="fill"
				style="inline-size: {marks.valuePercent}"
			></span>
			<!-- The threshold is a line across the track, not a second bar. A bar
			     beside a bar invites the reader to compare lengths and forget which
			     one is the limit. -->
			<span
				class="target-marker"
				data-target-cell="marker"
				style="inset-inline-start: {marks.markerPercent}"
			></span>
		</div>
		<p class="target-foot" data-target-cell="foot">{targetText}</p>
	{/if}
</div>

<style>
	.target {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		min-inline-size: 0;
	}

	.target-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--space-3);
		margin: 0;
	}

	.target-label {
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.target-value {
		font-size: var(--text-lg);
		font-weight: 600;
		color: var(--color-text);
	}

	.target-track {
		position: relative;
		block-size: 14px;
		border-radius: var(--radius-full);
		background: var(--color-surface-sunken);
		overflow: hidden;
	}

	.target-fill {
		display: block;
		block-size: 100%;
		border-radius: var(--radius-full);
		background: var(--chart-1);
	}

	/* Quarantine is a health fact and the row carries the word as well, so this
	   is the one place the confidence ramp is the honest colour. */
	.target[data-target-tone='health'] .target-fill {
		background: var(--band-high);
	}
	.target[data-target-tone='health'][data-target-band='near'] .target-fill {
		background: var(--band-medium);
	}
	.target[data-target-tone='health'][data-target-band='past'] .target-fill {
		background: var(--band-low);
	}

	.target-marker {
		position: absolute;
		inset-block: -1px;
		inline-size: 2px;
		margin-inline-start: -1px;
		background: var(--chart-marker);
	}

	.target-foot,
	.target-empty {
		margin: 0;
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
	}
</style>
