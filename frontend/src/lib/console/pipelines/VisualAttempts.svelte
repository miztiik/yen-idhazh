<script lang="ts">
	import { writtenTypeCounts, type VisualAttemptDay } from '$lib/console/pipelines/visual-attempts';
	import type { AttemptRead } from '$lib/console/pipelines/attempt-notes';

	let { days, read, notes, kind }: {
		days: VisualAttemptDay[]; read: AttemptRead; notes: string[]; kind: 'refusals' | 'written';
	} = $props();
	const pairs = $derived(writtenTypeCounts(days));
	const untyped = $derived(days.reduce((total, day) => total + day.untypedWritten, 0));
	const written = $derived(pairs.reduce((total, pair) => total + pair.count, 0));
	const largest = $derived(Math.max(0, ...pairs.map((pair) => pair.count)));
	const largestRefusal = $derived(Math.max(0, ...days.flatMap((day) => day.refusals.map((refusal) => refusal.count))));
	const attemptLabel = (count: number) => `${count} ${count === 1 ? 'attempt' : 'attempts'}`;
</script>

<div data-visual-attempt-view={kind} data-record-incomplete={read !== 'read' || notes.length > 0 || (kind === 'written' && untyped > 0) ? '' : undefined}>
	{#if kind === 'refusals'}
		<p>Counts of the first failed plan check recorded on each UTC day, including plans later written. These are not counts of all omitted visuals.</p>
	{:else}
		<p>The planned type compared with the successfully written type. Written means a visual file was made, not necessarily published or kept by a person.</p>
	{/if}
	{#each notes as note}<p data-record-note>{note}</p>{/each}
	{#if read === 'read'}
		{#if kind === 'refusals'}
			{#if days.length === 0}
				<p data-empty={notes.length > 0 ? 'incomplete' : 'quiet'}>No visual attempt is recorded in this window.</p>
			{:else}
				<ol class="days">
					{#each days as day (day.date)}
						<li>
							<h4><time datetime={day.date}>{day.date} UTC</time> <span>{attemptLabel(day.attempts)} recorded</span></h4>
							{#if day.refusals.length === 0}
								<p>No failed plan check is recorded on this day.</p>
							{:else}
								<ul class="counts">
									{#each day.refusals as refusal (refusal.reason)}
										<li data-refusal-date={day.date} data-refusal-reason={refusal.reason} data-count={refusal.count}>
											<span class="label">Failed check: {refusal.reason.replaceAll('_', ' ')}</span><span class="number">{attemptLabel(refusal.count)}</span>
											<span class="bar" style:inline-size="{refusal.count / largestRefusal * 100}%" aria-hidden="true"></span>
										</li>
									{/each}
								</ul>
							{/if}
						</li>
					{/each}
				</ol>
			{/if}
		{:else}
			<p>Written attempts with both types recorded: {written}.</p>
			{#if untyped > 0}<p data-record-note>Written attempts with no recorded type: {untyped}. They are excluded from this comparison. The comparison is incomplete.</p>{/if}
			{#if pairs.length === 0}
				<p data-empty={untyped > 0 || notes.length > 0 ? 'incomplete' : 'quiet'}>No recorded written type can be compared in this window.</p>
			{:else}
				<ul class="counts">
					{#each pairs as pair (`${pair.planned}/${pair.rendered}`)}
						<li data-planned-type={pair.planned} data-rendered-type={pair.rendered} data-count={pair.count}>
							<span class="label">Planned {pair.planned.replaceAll('_', ' ') || 'not recorded'} -> written {pair.rendered.replaceAll('_', ' ')}</span>
							<span class="number">{attemptLabel(pair.count)}</span>
							<span class="bar" style:inline-size="{pair.count / largest * 100}%" aria-hidden="true"></span>
						</li>
					{/each}
				</ul>
			{/if}
		{/if}
	{/if}
</div>

<style>
	.days, .counts { list-style: none; padding: 0; margin: 0; }
	.days > li { margin-block-start: var(--space-5); }
	h4 { display: flex; flex-wrap: wrap; gap: var(--space-3); }
	h4 span { font-weight: normal; color: var(--color-text-muted); }
	.counts li { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-2) var(--space-3); padding-block: var(--space-2); border-block-end: 1px solid var(--color-rule); }
	.label { overflow-wrap: anywhere; }
	.number { font-variant-numeric: tabular-nums; }
	.bar { grid-column: 1 / -1; block-size: var(--space-2); background: var(--chart-1); border-radius: var(--radius-sm); }
</style>
