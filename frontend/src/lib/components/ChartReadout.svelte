<script lang="ts">
	/** The strip a chart prints its hovered column or record into.
	 *
	 * One implementation, because two charts had grown their own and a third
	 * would have made three. Every rule the row settled lives here rather than in
	 * each chart: the strip sits **below** the plot and never over it, so it
	 * cannot cover a mark at any width; it prints **every series at one column**,
	 * so comparing four series costs one hover rather than four; and its entries
	 * **lie side by side**, wrapping to a new line only when the next one does not
	 * fit - never one entry per line stacked under the chart.
	 *
	 * The strip may be as wide as its plot, `chart.readout_max_share` of it. A
	 * share under one wrapped the entries on a phone while the plot still had
	 * room, which is the tall block this layout replaced. Each value keeps the
	 * room its widest reading needs, so stepping from column to column does not
	 * reflow the strip or change the panel's height - and never more room than
	 * the strip is wide, so on a phone a value whose widest reading would not
	 * fit takes the strip's width instead of pushing the page sideways.
	 *
	 * It is the legend as well. A separate legend would print each series colour
	 * and label a second time, and one fact drawn twice is how two of them drift.
	 *
	 * Nothing here needs a script. The resting column is prerendered, so a reader
	 * with JavaScript off still gets one column's numbers in words - which is
	 * what makes the hover an addition rather than the only way to read a value.
	 *
	 * **A strip of one column names no resting column and no keys**, at any
	 * window. There is no other column to rest beside, step to or return to, so
	 * `the newest day` and `Left and Right step through the days` would each need
	 * a second one. The heading is the column alone, and the hint line says
	 * `hintOne` where the strip still has a key or an action, or keeps its room
	 * blank, so no strip changes height with the window. Reader chose the words
	 * and Jony the room, on 2026-10-07.
	 */
	import { readoutCapStyle, type Readout, type ReadoutFacts } from '$lib/charts/readout';
	import { readoutView } from '$lib/charts/readout-view';

	let {
		readout,
		at = null,
		name,
		maxShare,
		resting = false,
		restingNote = '',
		hint = 'Point at a column to read it. Left and Right step through them, Escape returns to the newest.',
		hintOne = '',
		eventRoom = false,
		compact = false
	}: {
		/** What `readoutOf` or `factsOf` built. Null draws nothing at all. */
		readout: Readout | ReadoutFacts | null;
		/** The column a pointer or a key picked, or null for the resting one. A
		 * record chart hands the record it picked as `readout` instead. */
		at?: number | null;
		/** What the strip is of, so a page with several can be told apart. */
		name: string;
		/** `chart.readout_max_share`. */
		maxShare: number;
		/** For a record: true while no record has been picked, so the heading can
		 * say which one it fell back to rather than looking like a choice. A
		 * column strip knows this from `at`. */
		resting?: boolean;
		restingNote?: string;
		/** How to drive the strip, in one sentence under it. Empty prints none,
		 * for a strip whose page says it once for several - eleven cards in one
		 * grid would otherwise print one sentence eleven times. */
		hint?: string;
		/** What the hint line says when the strip holds one column. Empty keeps
		 * the line's room blank, where `hint` prints one at all. */
		hintOne?: string;
		/** Keep room on every column for as many event lines as the busiest
		 * column prints, so stepping onto the one day that has a line does not
		 * grow the strip and push everything under it down. */
		eventRoom?: boolean;
		/** A named, single-series card already identifies its marks. Keep its
		 * date beside the reading and omit a redundant colour key. */
		compact?: boolean;
	} = $props();

	const view = $derived(readoutView(readout, at, resting, eventRoom));
	/** The hint line's words: the keys, what one column still offers, or none. */
	const said = $derived(view?.one ? hintOne : hint);
</script>

{#if view}
	<!-- A container, so a value's kept room can be capped at the strip's own
	     width. The strip already takes its plot's width rather than its
	     contents', so being one changes nothing it draws. -->
	<dl
		class="chart-readout @container mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-text-tertiary"
		class:compact
		style={readoutCapStyle(maxShare)}
		data-readout={name}
		data-readout-shape={view.shape}
		aria-live="polite"
	>
		<!-- Multi-series readings keep their own heading line. A compact card
		     keeps date and reading together, wrapping only when needed. -->
		<dt
			class="font-semibold text-text-secondary"
			class:basis-full={!compact}
			data-readout-day={view.shape === 'columns' ? '' : undefined}
			data-readout-subject={view.shape === 'record' ? '' : undefined}
		>
			{view.heading}{view.resting && !view.one ? restingNote : ''}
		</dt>
		{#each view.entries as entry, index (`${index}:${entry.label}`)}
			<div
				class="readout-entry min-w-0 max-w-full"
				class:held={entry.held}
				aria-hidden={entry.held ? 'true' : undefined}
				data-readout-row={entry.held ? undefined : entry.label}
				data-readout-held={entry.held ? '' : undefined}
			>
				<dd class="readout-label">{#if entry.swatch && !compact}<span class="readout-swatch size-3 rounded-sm" style="background: {entry.swatch}"></span>{'\u00a0'}{/if}{entry.label}</dd>
				{#if entry.value !== ''}
					{'\u00a0'}
					<dd
						class="readout-value tabular-nums text-text-secondary"
						style={entry.reserve > 0 ? `--readout-reserve: ${entry.reserve}ch` : undefined}
					>
						{entry.value}
					</dd>
				{/if}
			</div>
		{/each}
	</dl>
	{#if said !== ''}
		<p class="readout-hint mt-2 text-text-tertiary" data-readout-hint={name}>{said}</p>
	{:else if view.one && hint !== ''}
		<!-- The room the keys took, kept blank and unread, so the panel is the
		     same height at one column as at seven. -->
		<p
			class="held readout-hint mt-2 text-text-tertiary"
			aria-hidden="true"
			data-readout-hint-held={name}
		>
			{'\u00a0'}
		</p>
	{/if}
{/if}

<style>
	.chart-readout, .readout-hint {
		font-size: var(--console-small-size, var(--text-xs));
		line-height: var(--console-small-leading, var(--leading-xs));
		font-weight: var(--console-small-weight, 400);
		letter-spacing: var(--console-small-tracking, normal);
	}
	.chart-readout { padding-block-start: var(--console-control-gap, var(--space-2)); border-block-start: 1px solid var(--color-rule); }
	.compact > dt { min-inline-size: 0; max-inline-size: 100%; overflow-wrap: anywhere; }
	.readout-value { font-family: var(--font-data); color: var(--color-text); }
	.readout-entry {
		overflow-wrap: anywhere;
	}

	.readout-label {
		display: inline;
	}

	.readout-swatch {
		display: inline-block;
		vertical-align: middle;
	}
	:global([data-surface='operator']) .readout-swatch {
		border: 1px solid var(--color-rule-strong);
		box-sizing: border-box;
	}

	.readout-value {
		display: inline-block;
		min-inline-size: min(var(--readout-reserve, 0ch), 100cqi);
		max-inline-size: 100%;
		vertical-align: baseline;
	}

	/* Laid out so the strip keeps its height, never seen and never read out. A
	   rule of its own rather than a utility, so the strip holds its room
	   wherever it is drawn. */
	.held {
		visibility: hidden;
	}
</style>
