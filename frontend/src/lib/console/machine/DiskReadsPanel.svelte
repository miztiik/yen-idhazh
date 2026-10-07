<script lang="ts">
	/** Whether the machine took the model's memory back.
	 *
	 * The finding is the sentence at the top; the two strips under it are the
	 * evidence. The upper strip is how often the model had to wait for the disk
	 * to hand back memory it already had, one tile a day. The lower strip is how
	 * far the memory the machine keeps disk copies in fell on that same day, on
	 * the same date axis - a day that waited a lot while those copies collapsed
	 * is the machine reclaiming, and a day that waited a lot while they held
	 * steady is something else and wants a different fix.
	 *
	 * The strips keep their height whether or not a day fired, so the panel does
	 * not grow a block of red the first time something goes wrong - the reader
	 * looks at the same shape every morning and only the marks change.
	 */
	import Panel from '$lib/components/Panel.svelte';
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import { gib } from '$lib/charts/machine';
	import { markReadout, readoutOf } from '$lib/charts/readout';
	import { grouped } from '$lib/charts/series';
	import type { DiskReadDay, DiskReads } from '$lib/console/machine/disk-reads';
	import { countDays, nameSpan } from '$lib/console/span-words';
	import { shortDate } from '$lib/format';

	let {
		reads,
		days,
		windowDays,
		readoutMaxShare
	}: {
		reads: DiskReads;
		/** Days the span covers, for the prose. */
		days: number;
		/** The preset the control is on, for the window check. */
		windowDays: number;
		/** `chart.readout_max_share`. */
		readoutMaxShare: number;
	} = $props();

	/** The tallest bar on the read strip. Every bar is a share of it, so one
	 * loud day does not make every other day look the same size. */
	const worstReads = $derived(
		reads.days.reduce((most, day) => Math.max(most, day.reads ?? 0), 0)
	);

	/** A recorded day always draws something, so a quiet day is a mark rather
	 * than a blank the eye reads as missing. */
	function readShare(day: DiskReadDay): number {
		if (day.reads === null) return 0;
		if (worstReads <= 0) return 8;
		return Math.max(8, Math.round((100 * day.reads) / worstReads));
	}

	function copiesShare(day: DiskReadDay): number {
		if (day.copiesFell === null) return 0;
		return Math.max(6, Math.round(100 * day.copiesFell));
	}

	/** Which sentence the panel leads with. Four, because "nothing recorded it"
	 * and "it recorded nothing" are different facts and a reader who is told the
	 * wrong one acts on a machine that is fine. */
	const verdict = $derived(
		reads.days.length === 0
			? 'empty'
			: reads.recorded === 0
				? 'unrecorded'
				: reads.worst !== null
					? 'fired'
					: 'quiet'
	);

	const finding = $derived.by(() => {
		if (verdict === 'empty') {
			return `No article in ${nameSpan(days)} left a row to read, so there is nothing to say either way.`;
		}
		if (verdict === 'unrecorded') {
			return `Nothing in ${nameSpan(days)} counted whether the model waited on the disk for memory it already had, so the quiet strip below is a missing instrument rather than a quiet machine.`;
		}
		// One day has no worst day and no share of the days that counted, so at one
		// day the finding names the day once.
		if (verdict === 'fired' && reads.worst !== null) {
			const waited = `The model waited on the disk ${grouped(reads.reads)} times for memory it already had`;
			return days === 1
				? `${waited}, on ${reads.worst.date}.`
				: `${waited}, worst on ${reads.worst.date} at ${grouped(reads.worst.reads ?? 0)}, over the ${reads.recorded} of ${countDays(days)} that counted.`;
		}
		return days === 1
			? `In ${nameSpan(days)}, the model never once had to wait on the disk for memory it already had.`
			: `Over the ${reads.recorded} of ${countDays(days)} that counted, the model never once had to wait on the disk for memory it already had.`;
	});

	/** What the runs themselves recorded about holding the model's memory down.
	 * Read off the rows, never written here: a panel that printed the setting it
	 * expected would keep saying it after somebody changed it. */
	const pinning = $derived(
		reads.pinning.held + reads.pinning.loose === 0
			? 'silent'
			: reads.pinning.loose === 0
				? 'held'
				: reads.pinning.held === 0
					? 'loose'
					: 'mixed'
	);

	const pinningSays = $derived.by(() => {
		const { held, loose } = reads.pinning;
		if (pinning === 'silent') {
			return `No run in ${nameSpan(days)} recorded whether the model's memory was held down, so whether the machine was even allowed to take it back is unknown.`;
		}
		if (pinning === 'held') {
			return `All ${held} runs that recorded it held the model's memory down, so the machine was not allowed to take it back.`;
		}
		if (pinning === 'loose') {
			return `None of the ${loose} runs that recorded it held the model's memory down, so the machine was free to take it back at any moment.`;
		}
		return `${held} of the ${held + loose} runs that recorded it held the model's memory down and ${loose} did not.`;
	});

	/** Rows that counted but sat first on their shard. A server that has just
	 * started reads its own memory in, so those waits are the server arriving
	 * and they are left out - and what that costs is printed rather than left
	 * for somebody to find in the code. */
	const excluded = $derived(reads.days.reduce((total, day) => total + day.excluded, 0));

	function readTitle(day: DiskReadDay): string {
		if (day.reads === null) return `${shortDate(day.date)}: nothing counted it`;
		return `${shortDate(day.date)}: ${grouped(day.reads)} waits over ${day.counted} articles`;
	}

	function copiesTitle(day: DiskReadDay): string {
		if (day.copiesFell === null) return `${shortDate(day.date)}: no reading`;
		return `${shortDate(day.date)}: ${gib(day.copiesHigh)} down to ${gib(day.copiesLow)}`;
	}

	/** The fill a day's read tile is drawn in, and its state in words, so the
	 * strip names the colour rather than leaving it to be learned. */
	const STATE: Record<DiskReadDay['state'], { fill: string | null; words: string }> = {
		unrecorded: { fill: null, words: 'nothing counted whether the model waited' },
		quiet: { fill: 'var(--fill-high)', words: 'the model never waited on the disk' },
		fired: { fill: 'var(--fill-low)', words: 'the model waited on the disk' }
	};

	/** The day a pointer, a key or a tap has picked, or null for the resting one. */
	let picked = $state<number | null>(null);

	/** Both tracks at one day. It rests on the worst day the finding names, and on
	 * the newest day where nothing fired. */
	const readout = $derived(
		readoutOf({
			type: 'tileStrip',
			columns: reads.days.map((day) => shortDate(day.date)),
			series: [
				{
					label: 'Waits for the disk',
					swatch: null,
					values: reads.days.map((day) => day.reads ?? 'nothing counted it'),
					format: (waits: number, column: number) =>
						`${grouped(waits)} waits over ${reads.days[column]?.counted ?? 0} articles`
				},
				{
					label: 'Disk copies fell',
					swatch: 'var(--fill-medium)',
					values: reads.days.map((day) => (day.copiesFell === null ? 'no reading' : day.copiesHigh)),
					format: (high: number, column: number) =>
						`${gib(high)} down to ${gib(reads.days[column]?.copiesLow ?? null)}`
				}
			],
			events: {
				lines: reads.days.map((day) => [
					{ label: 'That day', value: STATE[day.state].words, swatch: STATE[day.state].fill }
				])
			},
			notMeasured: 'No article left a row on this day',
			resting:
				reads.worst === null
					? 'last'
					: Math.max(
							0,
							reads.days.findIndex((day) => day.date === reads.worst?.date)
						)
		})
	);
</script>

<div
	data-windowed="machine-disk-reads"
	data-window-days={windowDays}
	data-readout-columns={reads.days.length > 0 ? reads.days.length : undefined}
	data-readout-none={reads.days.length > 0
		? undefined
		: 'no article in these days left a row, so there is no day to read; agreed with Susan'}
>
	<Panel
		heading="h3"
		id="disk-reads"
		title="Whether the machine took the model's memory back"
		note="A wait for the disk is memory the machine handed to something else, and the disk copies it was holding that day say whether it was taken or never there - {windowDays ===
		1
			? `one tile for ${nameSpan(windowDays)}`
			: `one tile a day, over ${nameSpan(windowDays)}`}."
	>
		<p class="finding" data-disk-read-finding={verdict}>{finding}</p>

		{#if reads.days.length === 0}
			<p class="aside" data-machine-panel-empty="disk-reads">
				The strip below stays at its height so the panel does not change shape the day a row
				arrives.
			</p>
		{/if}

		<!-- One tab stop for both tracks: a day is one column across the two, so
		     pointing at either tile of a day, or stepping with Left and Right,
		     reads that day in the strip below. -->
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<div
			class="strip"
			tabindex="0"
			role="group"
			aria-label="Waits for the disk and disk copies, one day a column. Left and Right read a day, Escape returns to rest."
			use:markReadout={{
				count: reads.days.length,
				walk: 'row',
				onSelect: (index) => (picked = index),
				selected: picked
			}}
		>
			<ol class="track" data-disk-read-track aria-label="Waits for the disk, one tile a day">
				{#each reads.days as day, index (day.date)}
					<li
						class="tile {day.state}"
						data-readout-at={index}
						data-readout-picked={picked === index ? 'yes' : undefined}
						data-disk-read-day={day.date}
						data-disk-read-state={day.state}
						data-disk-reads={day.reads ?? ''}
						data-disk-read-counted={day.counted}
						aria-label={readTitle(day)}
					>
						<span class="mark" style="block-size: {readShare(day)}%"></span>
					</li>
				{/each}
			</ol>
			<p class="legend">Waits for the disk</p>

			<ol
				class="track"
				data-disk-copies-track
				aria-label="How far the machine's disk copies fell, the same days"
			>
				{#each reads.days as day, index (day.date)}
					<li
						class="tile {day.copiesFell === null ? 'unrecorded' : 'copies'}"
						data-readout-at={index}
						data-readout-picked={picked === index ? 'yes' : undefined}
						data-disk-copies-day={day.date}
						data-disk-copies-fell={day.copiesFell === null ? '' : day.copiesFell.toFixed(4)}
						data-disk-copies-high={day.copiesHigh ?? ''}
						data-disk-copies-low={day.copiesLow ?? ''}
						aria-label={copiesTitle(day)}
					>
						<span class="mark" style="block-size: {copiesShare(day)}%"></span>
					</li>
				{/each}
			</ol>
			<p class="legend">
				How far the memory holding disk copies fell{#if reads.days.length > 0}, {reads.days[0]
						.date} to {reads.days[reads.days.length - 1].date}{/if}
			</p>
		</div>

		{#if reads.days.length > 0}
			<ChartReadout
				{readout}
				at={picked}
				name="disk-reads"
				maxShare={readoutMaxShare}
				restingNote={reads.worst === null ? ', the newest day' : ', the worst day'}
				hint="Point at a day to read both tracks. Left and Right step through the days, Escape returns to the worst."
			/>
		{/if}

		<p class="aside" data-disk-read-pinning={pinning}>{pinningSays}</p>

		{#if excluded > 0}
			<p class="aside" data-disk-read-excluded={excluded}>
				{grouped(excluded)}
				{excluded === 1 ? 'article is' : 'articles are'} left out for sitting first on a shard, where a
				wait is the server reading its own memory in rather than the machine taking it back - so a
				reclaim inside a first article is invisible here.
			</p>
		{/if}
	</Panel>
</div>

<style>
	.finding {
		margin: var(--space-2) 0 var(--space-3);
		font-size: var(--text-base);
		line-height: var(--leading-base);
		color: var(--color-text);
	}

	/* Fixed, so the panel is the same shape on a quiet morning and on a bad one.
	   Two tracks, two legends, and the block never grows. */
	.strip {
		display: grid;
		gap: var(--space-1);
		padding: var(--space-3);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-sm);
		background: var(--color-surface-sunken);
	}

	.track {
		display: flex;
		align-items: flex-end;
		justify-content: flex-start;
		gap: 3px;
		block-size: 56px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	/* Capped, so a span holding five days draws five tiles rather than five
	   slabs. A tile is a day, and a day does not get wider because the ledger
	   holds fewer of them. */
	.tile {
		position: relative;
		flex: 1 1 0;
		min-inline-size: 3px;
		max-inline-size: 26px;
		block-size: 100%;
		display: flex;
		align-items: flex-end;
		border-radius: var(--radius-sm);
	}

	.mark {
		inline-size: 100%;
		border-radius: var(--radius-sm);
	}

	/* Three marks, and each one says a different thing from a metre away: an
	   outlined box nobody filled in, a low bar sitting on the floor, a tall bar. */
	.tile.unrecorded {
		border: 1px dashed var(--color-rule);
	}

	.tile.unrecorded .mark {
		background: none;
	}

	.tile.quiet .mark {
		background: var(--fill-high);
	}

	.tile.fired .mark {
		background: var(--fill-low);
	}

	.tile.copies .mark {
		background: var(--fill-medium);
	}

	.legend {
		margin: 0;
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-secondary);
	}

	.aside {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
	/* The day the strip below is reading, on both tracks at once. */
	.tile[data-readout-picked] {
		outline: 1px solid var(--color-focus);
		outline-offset: 1px;
	}

	.strip:focus-visible {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}
</style>
