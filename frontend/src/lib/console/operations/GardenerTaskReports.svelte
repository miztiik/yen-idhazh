<script lang="ts">
	/** Draw task stops and repairs without confusing previews with work that landed. */
	import type { Snippet } from 'svelte';
	import { evidenceOf, rowsOf } from '$lib/console/voices/record';
	import { longDate } from '$lib/format';
	import { gardenerFaultLabel, gardenerOutcomeLanes, gardenerReports } from './gardener-reports';
	import type { OperationReading } from './operation-reads.svelte';

	let { calendar, day, reading, plot }: {
		calendar: readonly string[]; day: string; reading: OperationReading;
		plot: Snippet<[ReturnType<typeof gardenerOutcomeLanes>]>;
	} = $props();
	const reports = $derived(gardenerReports(rowsOf(reading.answer)));
	const tasks = $derived(reports.byDay.get(day) ?? []);
	const exceptions = $derived(tasks.filter((task) => !task.dryRun && (task.stop !== 'exhausted' || task.recovery.length > 0)));
	const cleanup = $derived(tasks.filter(({ task }) => task === 'workflow-artifacts' || task === 'workflow-runs'));
	const notes = $derived(evidenceOf(reading.answer, reading.range));
	const unavailable = $derived(reading.answer !== 'pending' && reading.answer.state === 'unreachable');
	const lanes = $derived(gardenerOutcomeLanes(calendar, reports.byDay,
		reading.answer === 'pending' ? 'Checking reports' : unavailable ? 'Reports unavailable' : 'No task report'));
	$effect(() => {
		if (reports.ignored || reports.partial) console.warn('[gardener] Some published task or recovery reports could not be read.');
	});
</script>

{@render plot(lanes)}
{#if reports.partial || reports.ignored}<p class="note">Task and recovery evidence is partial.</p>{/if}
{#each notes as note (note)}<p class="note">{note}</p>{/each}
{#if exceptions.length || cleanup.length}
	<details>
		<summary>Task details for {longDate(day)} UTC</summary>
		{#if exceptions.length}
			<ul class="reports">
				{#each exceptions as task (`${task.runId}/${task.attempt}/${task.job}/${task.shard}/${task.task}`)}
					<li>
						<strong>{task.task}</strong>
						{#if task.stop !== 'exhausted'} / {task.stop === 'ceiling' ? 'Limit reached' : task.stop}{/if}
						{#if task.fault} / {gardenerFaultLabel(task.fault)}{/if}
						{#each task.recovery as note}<span class="detail">{note.label}: {note.subject}.</span>{/each}
						{#if task.resume}<span class="detail">Resume from {task.resume}.</span>{/if}
					</li>
				{/each}
			</ul>
			{#if exceptions.some((task) => task.fault === 'packed-file-unreadable')}
				<p class="note">A pack needed for a retry or late input was missing or could not be read, so Gardener deferred that work.</p>
			{/if}
		{/if}
		{#each cleanup as task (`${task.runId}/${task.attempt}/${task.job}/${task.shard}/${task.task}`)}
			{@const label = task.task === 'workflow-artifacts' ? 'Workflow artifacts' : 'Workflow runs'}
			{@const counts = [
				{ label: 'Checked', value: task.checked },
				{ label: 'Matched', value: task.selected },
				{ label: task.dryRun ? 'Would remove' : 'Reported removed', value: task.deleted }
			]}
			<section class="cleanup">
				<h4>{label} / {task.dryRun ? 'Preview' : 'Cleanup report'}</h4>
				{#each counts as item (item.label)}
					<p><span>{item.label}</span>
						{#if item.value !== null && task.checked !== null && task.checked > 0 && item.value <= task.checked}
							<meter aria-label={item.label} min="0" max={task.checked} value={item.value}></meter>
						{:else}<span></span>{/if}
						<strong>{item.value?.toLocaleString('en') ?? 'Not recorded'}</strong>
					</p>
				{/each}
				{#if task.dryRun}<p class="note">Nothing was removed.{task.through ? ` Preview checked through ${longDate(task.through)} UTC.` : ''}</p>{/if}
				{#if !task.dryRun && task.bytes !== null && task.task === 'workflow-artifacts'}
					<div class="note">{task.bytes.toLocaleString('en')} bytes reported freed.</div>
				{/if}
			</section>
		{/each}
	</details>
{/if}

<style>
	p, h4 { margin: 0; }
	.note, details { color: var(--color-text-secondary); font-size: var(--console-small-size); }
	.reports { margin-block: var(--space-1) var(--space-2); padding-inline-start: var(--space-4); }
	.detail { display: block; }
	summary { cursor: pointer; }
	.cleanup { border-block-start: 1px solid var(--color-rule); padding-block: var(--space-2); }
	.cleanup p { display: grid; grid-template-columns: max-content minmax(0, 1fr) auto; gap: var(--space-2); align-items: center; }
	meter { appearance: none; inline-size: 100%; block-size: var(--space-2); background: var(--color-surface-sunken); }
	meter::-webkit-meter-bar { background: var(--color-surface-sunken); border: 0; border-radius: 0; }
	meter::-webkit-meter-optimum-value { background: var(--operation-written); }
	meter::-moz-meter-bar { background: var(--operation-written); }
</style>
