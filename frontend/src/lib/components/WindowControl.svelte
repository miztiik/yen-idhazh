<script lang="ts">
	/** How many days the console is showing, and what a wider window costs.
	 *
	 * One control for the whole page. Six controls would invite six windows, and
	 * two charts on different windows cannot be compared - which is the question
	 * an operator came here to ask.
	 *
	 * It sits below the band and above the first panel it governs. Inside the
	 * band it was a control in a panel it does not govern: the band's three facts
	 * are the same at every preset and say so twice in their own source.
	 *
	 * Radio buttons rather than a menu: four options, all four on the page, so
	 * the cost of the wide one is readable without opening anything. And a short
	 * list rather than a slider, because every span is a different number of
	 * month files to fetch and most of the spans between these four look the
	 * same once drawn.
	 */
	let {
		days,
		presets,
		monthsFor,
		busy = false,
		ready = false,
		onChange
	}: {
		days: number;
		presets: number[];
		/** Month files a preset would fetch that are not already in hand. */
		monthsFor: (days: number) => number;
		busy?: boolean;
		/** False until a browser has run. The control does nothing before that,
		 * so it says so instead of accepting a click it cannot honour. */
		ready?: boolean;
		onChange: (days: number) => void;
	} = $props();

	const pending = $derived(monthsFor(days));
	const priced = $derived(presets.some((preset) => monthsFor(preset) > 0));

	function files(count: number): string {
		return count === 1 ? '1 month' : `${count} months`;
	}

	const status = $derived.by(() => {
		if (!ready) {
			return `This control needs JavaScript. Every windowed section below is showing ${days} days.`;
		}
		if (busy) return `Fetching ${files(pending)}.`;
		const shown = `Every windowed section below is showing ${days} days.`;
		return priced ? `${shown} A month count on a preset is what picking it will fetch.` : shown;
	});
</script>

<fieldset
	class="window-control"
	data-window-control
	data-window-days={days}
	data-window-busy={busy ? 'true' : 'false'}
	aria-busy={busy}
	aria-describedby="window-control-status"
>
	<legend class="window-legend">Days shown</legend>

	<!-- The four tiles and the sentence about them on one line where there is
	     room. Stacked, this control cost 125px of the first viewport on a desktop
	     and 195px on a phone, for four words and a radio group. -->
	<div class="window-body">
		<div class="segments">
			{#each presets as preset (preset)}
				<label class="segment" data-window-preset={preset} data-selected={preset === days}>
					<input
						class="segment-input"
						type="radio"
						name="console-window"
						value={preset}
						checked={preset === days}
						disabled={!ready}
						onchange={() => onChange(preset)}
					/>
					<span class="segment-days">{preset} days</span>
					{#if monthsFor(preset) > 0}
						<!-- The price, before it is paid. A wider window is not free: it
						     pulls a month file per month it reaches back into. -->
						<span class="segment-cost" data-window-preset-cost={preset}>
							+{files(monthsFor(preset))}
						</span>
					{/if}
				</label>
			{/each}
		</div>

		<p id="window-control-status" class="window-status" data-window-status>{status}</p>
	</div>
</fieldset>

<style>
	.window-control {
		margin-top: var(--space-4);
		padding: var(--space-3) var(--space-4) var(--space-4);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
		box-shadow: var(--shadow-sm);
	}

	.window-legend {
		padding-inline: var(--space-2);
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}

	/* One line where there is room, two where there is not. The sentence is what
	   says which span is in force, so it sits beside the tiles rather than under
	   them - and a column too narrow for both stacks it back. */
	.window-body {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2) var(--space-4);
	}

	.segments {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
	}

	/* A segment is the target, not the dot beside it. The whole tile is
	   clickable and the tile is what carries the selected state, so a thumb has
	   something the size of a thumb to hit. */
	.segment {
		position: relative;
		display: flex;
		min-height: 2.75rem;
		flex-direction: column;
		justify-content: center;
		gap: 2px;
		padding: var(--space-2) var(--space-4);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-surface);
		cursor: pointer;
	}

	.segment[data-selected='true'] {
		border-color: var(--color-accent);
		background: var(--color-tint-accent);
	}

	.segment:has(.segment-input:disabled) {
		cursor: default;
		opacity: 0.55;
	}

	/* The ring is on the tile, because the input itself is a 1px square. */
	.segment:has(.segment-input:focus-visible) {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}

	.segment-input {
		position: absolute;
		width: 1px;
		height: 1px;
		margin: -1px;
		overflow: hidden;
		clip-path: inset(50%);
	}

	.segment-days {
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--color-text);
	}

	.segment-cost {
		font-size: var(--text-xs);
		color: var(--color-text-tertiary);
	}

	.window-status {
		flex: 1 1 15rem;
		margin: 0;
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
	}
</style>
