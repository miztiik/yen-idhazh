<script lang="ts">
	import { writtenTypeCounts, type VisualAttemptDay } from '$lib/console/pipelines/visual-attempts';
	import type { AttemptRead } from '$lib/console/pipelines/attempt-notes';

	let { days, read, notes }: {
		days: VisualAttemptDay[]; read: AttemptRead; notes: string[];
	} = $props();
	const pairs = $derived(writtenTypeCounts(days));
	const untyped = $derived(days.reduce((total, day) => total + day.untypedWritten, 0));
	const written = $derived(pairs.reduce((total, pair) => total + pair.count, 0));
	const largest = $derived(Math.max(0, ...pairs.map((pair) => pair.count)));
	const attemptLabel = (count: number) => `${count} ${count === 1 ? 'attempt' : 'attempts'}`;
</script>

<div data-visual-attempt-view="written" data-record-incomplete={read !== 'read' || notes.length > 0 || untyped > 0 ? '' : undefined}>
	<p>The planned type compared with the successfully written type. Written means a visual file was made, not necessarily published or kept by a person.</p>
	{#each notes as note}<p data-record-note>{note}</p>{/each}
	{#if read === 'read'}
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
</div>

<style>
	.counts { list-style: none; padding: 0; margin: 0; }
	.counts li { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-2) var(--space-3); padding-block: var(--space-2); border-block-end: 1px solid var(--color-rule); }
	.label { overflow-wrap: anywhere; }
	.number { font-variant-numeric: tabular-nums; }
	.bar { grid-column: 1 / -1; block-size: var(--space-2); background: var(--chart-1); border-radius: var(--radius-sm); }
</style>
