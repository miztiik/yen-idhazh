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
	import { gib } from '$lib/charts/machine';
	import { grouped } from '$lib/charts/series';
	import type { DiskReadDay, DiskReads } from '$lib/console/machine/disk-reads';

	let {
		reads,
		days,
		windowDays
	}: {
		reads: DiskReads;
		/** Days the span covers, for the prose. */
		days: number;
		/** The preset the control is on, for the window check. */
		windowDays: number;
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
			return `No article in these ${days} days left a row to read, so there is nothing to say either way.`;
		}
		if (verdict === 'unrecorded') {
			return `Nothing in these ${days} days counted whether the model waited on the disk for memory it already had, so the quiet strip below is a missing instrument rather than a quiet machine.`;
		}
		if (verdict === 'fired' && reads.worst !== null) {
			return `The model waited on the disk ${grouped(reads.reads)} times for memory it already had, worst on ${reads.worst.date} at ${grouped(reads.worst.reads ?? 0)}, over the ${reads.recorded} of these ${days} days that counted.`;
		}
		return `Over the ${reads.recorded} of these ${days} days that counted, the model never once had to wait on the disk for memory it already had.`;
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
		const { held, loose, silent } = reads.pinning;
		if (pinning === 'silent') {
			return `None of the ${silent} runs in these ${days} days recorded whether the model's memory was held down, so whether the machine was even allowed to take it back is unknown.`;
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
		if (day.reads === null) return `${day.date}: nothing counted it`;
		return `${day.date}: ${grouped(day.reads)} waits over ${day.counted} articles`;
	}

	function copiesTitle(day: DiskReadDay): string {
		if (day.copiesFell === null) return `${day.date}: no reading`;
		return `${day.date}: ${gib(day.copiesHigh)} down to ${gib(day.copiesLow)}`;
	}
</script>

<div data-windowed="machine-disk-reads" data-window-days={windowDays}>
	<Panel
		heading="h3"
		id="disk-reads"
		title="Whether the machine took the model's memory back"
		note="A wait for the disk is memory the machine handed to something else, and the disk copies it was holding that day say whether it was taken or never there - one tile a day, over the last {windowDays} days."
	>
		<p class="finding" data-disk-read-finding={verdict}>{finding}</p>

		{#if reads.days.length === 0}
			<p class="aside" data-machine-panel-empty="disk-reads">
				The strip below stays at its height so the panel does not change shape the day a row
				arrives.
			</p>
		{/if}

		<div class="strip">
			<ol class="track" data-disk-read-track aria-label="Waits for the disk, one tile a day">
				{#each reads.days as day (day.date)}
					<li
						class="tile {day.state}"
						data-disk-read-day={day.date}
						data-disk-read-state={day.state}
						data-disk-reads={day.reads ?? ''}
						data-disk-read-counted={day.counted}
						title={readTitle(day)}
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
				{#each reads.days as day (day.date)}
					<li
						class="tile {day.copiesFell === null ? 'unrecorded' : 'copies'}"
						data-disk-copies-day={day.date}
						data-disk-copies-fell={day.copiesFell === null ? '' : day.copiesFell.toFixed(4)}
						data-disk-copies-high={day.copiesHigh ?? ''}
						data-disk-copies-low={day.copiesLow ?? ''}
						title={copiesTitle(day)}
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

		<p class="aside" data-disk-read-pinning={pinning}>{pinningSays}</p>

		{#if excluded > 0}
			<p class="aside" data-disk-read-excluded={excluded}>
				{grouped(excluded)}
				{excluded === 1 ? 'article was' : 'articles were'} left out because it was the first on its
				shard, where a wait is the server reading its own memory in rather than the machine taking
				it back - so a reclaim inside a first article is invisible here.
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
		gap: 2px;
		block-size: 56px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.tile {
		position: relative;
		flex: 1 1 0;
		min-inline-size: 3px;
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
</style>
