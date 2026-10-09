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
	import {
		readoutCapStyle,
		type Readout,
		type ReadoutFacts,
		type ReadoutLine
	} from '$lib/charts/readout';

	let {
		readout,
		at = null,
		name,
		maxShare,
		resting = false,
		restingNote = '',
		hint = 'Point at a column to read it. Left and Right step through them, Escape returns to the newest.',
		hintOne = '',
		eventRoom = false
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
	} = $props();

	interface Entry {
		label: string;
		value: string;
		swatch: string | null;
		/** The characters the widest reading of this entry needs, or zero. */
		reserve: number;
		/** Room held for an event line this column does not have: laid out, never
		 * seen and never read out. */
		held?: boolean;
	}

	/** The widest reading a series prints, so the strip keeps room for it. A
	 * missing reading prints the not-measured word only on a column another
	 * series measured: a column nothing measured prints the word once, in place
	 * of every entry, so it holds no room in any of them. */
	function widest(
		values: readonly (string | null)[],
		missing: string,
		counted: readonly boolean[]
	): number {
		return values.reduce(
			(most, value, column) => Math.max(most, (value ?? (counted[column] ? missing : '')).length),
			0
		);
	}

	/** What the strip prints: a heading and its entries, in either shape. `one`
	 * is a strip of one column, which names no resting column and no keys. */
	const view = $derived.by(
		(): {
			shape: 'columns' | 'record';
			heading: string;
			resting: boolean;
			one: boolean;
			entries: Entry[];
		} | null => {
			if (readout === null) return null;
			if ('subject' in readout) {
				return {
					shape: 'record',
					heading: readout.subject,
					resting,
					one: false,
					entries: readout.facts.map((fact) => ({
						label: fact.label,
						value: fact.value ?? readout.notMeasured,
						swatch: fact.swatch,
						reserve: fact.reserve ?? 0
					}))
				};
			}
			if (readout.columns.length === 0) return null;
			const column = Math.min(readout.columns.length - 1, Math.max(0, at ?? readout.resting));
			const counted = readout.columns.map((_, index) =>
				readout.series.some((one) => one.values[index] !== null)
			);
			const measured = counted[column] ?? false;
			const series: Entry[] = measured
				? readout.series.map((one) => ({
						label: one.note === undefined ? one.label : `${one.label} (${one.note})`,
						value: one.values[column] ?? readout.notMeasured,
						swatch: one.swatch,
						reserve: widest(one.values, readout.notMeasured, counted)
					}))
				: [
						{
							label: readout.notMeasuredAt[column] ?? readout.notMeasured,
							value: '',
							swatch: null,
							reserve: 0
						}
					];
			const events = readout.events[column] ?? [];
			// A column nothing measured already says so in one sentence, so it does
			// not say "nothing" a second time in the events' own words. An event
			// that did happen on it - a setting moved on a day nobody measured -
			// still prints.
			const none: Entry[] =
				measured && events.length === 0 && readout.eventsNone !== ''
					? [{ label: readout.eventsNone, value: '', swatch: null, reserve: 0 }]
					: [];
			// The widest whole line any column prints - its label and its value -
			// held once for each line this column is short of the busiest. A column
			// with its own "none" sentence already holds a line, so it holds nothing
			// more.
			const most = eventRoom ? Math.max(0, ...readout.events.map((lines) => lines.length)) : 0;
			const roomiest = readout.events
				.flat()
				.reduce<ReadoutLine | null>(
					(best, line) =>
						best === null || line.label.length + line.value.length > best.label.length + best.value.length
							? line
							: best,
					null
				);
			const held: Entry[] =
				readout.eventsNone === '' && roomiest !== null
					? Array.from({ length: Math.max(0, most - events.length) }, () => ({
							label: roomiest.label,
							value: roomiest.value,
							swatch: roomiest.swatch,
							reserve: 0,
							held: true
						}))
					: [];
			return {
				shape: 'columns',
				heading: readout.columns[column],
				resting: at === null,
				one: readout.columns.length === 1,
				entries: [...series, ...events.map((line) => ({ ...line, reserve: 0 })), ...none, ...held]
			};
		}
	);
	/** The hint line's words: the keys, what one column still offers, or none. */
	const said = $derived(view?.one ? hintOne : hint);
</script>

{#if view}
	<!-- A container, so a value's kept room can be capped at the strip's own
	     width. The strip already takes its plot's width rather than its
	     contents', so being one changes nothing it draws. -->
	<dl
		class="@container mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-[0.75rem] text-text-tertiary"
		style={readoutCapStyle(maxShare)}
		data-readout={name}
		data-readout-shape={view.shape}
		aria-live="polite"
	>
		<!-- The heading takes a line of its own, so the entries after it start at
		     the same place on every column and the eye does not hunt for them. -->
		<dt
			class="basis-full font-semibold text-text-secondary"
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
				<dd class="readout-label">{#if entry.swatch}<span class="readout-swatch size-3 rounded-sm" style="background: {entry.swatch}"></span>{'\u00a0'}{/if}{entry.label}</dd>
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
		<p class="mt-2 text-[0.75rem] text-text-tertiary" data-readout-hint={name}>{said}</p>
	{:else if view.one && hint !== ''}
		<!-- The room the keys took, kept blank and unread, so the panel is the
		     same height at one column as at seven. -->
		<p
			class="held mt-2 text-[0.75rem] text-text-tertiary"
			aria-hidden="true"
			data-readout-hint-held={name}
		>
			{'\u00a0'}
		</p>
	{/if}
{/if}

<style>
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
