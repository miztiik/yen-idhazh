<script lang="ts">
	/** Draw task stops and repairs without confusing previews with work that landed. */
	import type { Snippet } from 'svelte';
	import { gardenerWakeQuery } from '$lib/console/queries/operations';
	import { rangeFor, retryAsks, routeReach, sliceOnce, type Range } from '$lib/console/queries/window';
	import { evidenceOf, rowsOf, type Answer } from '$lib/console/voices/record';
	import { readSession } from '$lib/data/read-session';
	import { longDate } from '$lib/format';
	import { gardenerOutcomeLanes, gardenerReports } from './gardener-reports';

	let { calendar, day, presets, plot }: {
		calendar: readonly string[]; day: string; presets: readonly number[];
		plot: Snippet<[ReturnType<typeof gardenerOutcomeLanes>]>;
	} = $props();
	const empty = gardenerReports([]);
	let reading = $state.raw<{ answer: Answer; range: Range | null; reports: typeof empty }>({
		answer: 'pending', range: null, reports: empty
	});
	let retry = $state(0);
	const reports = $derived(reading.reports);
	const tasks = $derived(reports.byDay.get(day) ?? []);
	const exceptions = $derived(tasks.filter((task) => !task.dryRun && (task.stop !== 'exhausted' || task.recovery.length > 0)));
	const cleanup = $derived(tasks.filter(({ task }) => task === 'workflow-artifacts' || task === 'workflow-runs'));
	const notes = $derived(evidenceOf(reading.answer, reading.range));
	const lanes = $derived(gardenerOutcomeLanes(calendar, reports.byDay));
	const bounds = $derived(reading.range);
	const faultLabel = (value: string) => value === 'packed-file-unreadable' ? 'Packed file unreadable' : value.replaceAll('-', ' ');

	$effect(() => {
		void retry;
		let active = true;
		const session = readSession();
		reading = { answer: 'pending', range: null, reports: empty };
		async function load() {
			const reach = await routeReach([gardenerWakeQuery.ledger]);
			if (!active || session !== readSession()) return;
			const request = rangeFor(gardenerWakeQuery, Math.max(...presets), reach, presets);
			const range = 'from' in request ? request : null;
			const answer = 'from' in request ? await sliceOnce(gardenerWakeQuery, request) : request;
			if (!active || session !== readSession()) return;
			const next = gardenerReports(rowsOf(answer));
			if (next.ignored || next.partial) console.warn('[gardener] Some published task or recovery reports could not be read.');
			reading = { answer, range, reports: next };
		}
		void load().catch((error: unknown) => {
			if (!active || session !== readSession()) return;
			console.warn('[gardener] The published task record could not be read.', error);
			reading = { answer: { state: 'unreachable' }, range: null, reports: empty };
		});
		return () => { active = false; };
	});
</script>

{@render plot(lanes)}
{#if reading.answer === 'pending'}
	<p class="note" role="status">Checking packed task reports.</p>
{:else if reading.answer.state === 'unreachable' || reading.answer.state === 'missing'}
	<p class="note">{reading.answer.state === 'unreachable' ? 'Task reports could not be read.' : 'No packed task reports are available.'}
		{#if reading.answer.state === 'unreachable'}
			<button type="button" onclick={() => { retryAsks([gardenerWakeQuery]); retry += 1; }}>Retry task reports</button>
		{/if}
	</p>
{/if}
{#if bounds && (bounds.from > calendar[0] || bounds.to < calendar[calendar.length - 1])}
	<p class="note">Task report dates checked: {longDate(bounds.from)} to {longDate(bounds.to)} UTC.</p>
{/if}
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
						{#if task.fault} / {faultLabel(task.fault)}{/if}
						{#each task.recovery as note}<span class="detail">{note.label}: {note.subject}.</span>{/each}
						{#if task.resume}<span class="detail">Resume from {task.resume}.</span>{/if}
					</li>
				{/each}
			</ul>
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
				{#if task.dryRun}<div class="note">Nothing was removed.{#if task.through} Preview checked through {longDate(task.through)} UTC.{/if}</div>{/if}
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
	summary, button { cursor: pointer; }
	.cleanup { border-block-start: 1px solid var(--color-rule); padding-block: var(--space-2); }
	.cleanup p { display: grid; grid-template-columns: max-content minmax(0, 1fr) auto; gap: var(--space-2); align-items: center; }
	meter { inline-size: 100%; accent-color: var(--chart-marker); }
</style>
