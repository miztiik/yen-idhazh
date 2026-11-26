<script lang="ts">
	/** Show what a recorded wake reported without turning a task report into a write receipt. */
	import { gardenerRecoveries } from '$lib/data/ledger';
	import { readSession } from '$lib/data/read-session';
	import { gardenerWakeQuery } from '$lib/console/queries/pipelines';
	import { rangeFor, retryAsks, routeReach, sliceOnce, type Range } from '$lib/console/queries/window';
	import { evidenceOf, rowsOf, type Answer } from '$lib/console/voices/record';
	import { gardenerWakes, recoveryNotes, removalReport, utcTime } from './gardener-activity';
	import { longDate } from '$lib/format';
	import type { SliceResult } from '$lib/data/ledger';

	let { days, presets }: { days: number; presets: readonly number[] } = $props();
	const empty = gardenerWakes([]);
	let reading = $state.raw<{ answer: Answer; range: Range | null; history: ReturnType<typeof gardenerWakes> }>({
		answer: 'pending', range: null, history: empty
	});
	let chosen = $state('');
	let expanded = $state(false);
	let retryCount = $state(0);
	let recovery = $state.raw<SliceResult | null>(null);

	const latest = $derived(reading.history.wakes[0]);
	const selected = $derived(reading.history.wakes.find((wake) => wake.key === chosen) ?? latest);
	const notes = $derived(evidenceOf(reading.answer, reading.range));
	const repairs = $derived(recoveryNotes(recovery?.rows ?? []));

	$effect(() => {
		const span = days;
		void retryCount;
		let active = true;
		const session = readSession();
		reading = { answer: 'pending', range: null, history: empty };
		async function load() {
			const reach = await routeReach([gardenerWakeQuery.ledger]);
			if (!active || session !== readSession()) return;
			const request = rangeFor(gardenerWakeQuery, span, reach, presets);
			const range = 'from' in request ? request : null;
			const answer = 'from' in request ? await sliceOnce(gardenerWakeQuery, request) : request;
			if (!active || session !== readSession()) return;
			const history = gardenerWakes(rowsOf(answer));
			if (history.ignored > 0) console.warn(`[gardener] ${history.ignored} invalid task reports were not drawn.`);
			reading = { answer, range, history };
		}
		void load().catch((error: unknown) => {
			if (!active || session !== readSession()) return;
			console.warn('[gardener] The published wake record could not be read.', error);
			reading = { answer: { state: 'unreachable' }, range: null, history: empty };
		});
		return () => { active = false; };
	});

	$effect(() => {
		const wake = selected;
		if (!expanded || !wake) return;
		const session = readSession();
		let active = true;
		recovery = null;
		async function load() {
			if (!wake) return;
			const result = await gardenerRecoveries(wake.from, wake.to, wake.runId, wake.attempt);
			if (!active || session !== readSession()) return;
			recovery = result;
		}
		void load().catch((error: unknown) => {
			if (!active || session !== readSession() || !wake) return;
			console.warn('[gardener] Recovery reports could not be read.', error);
			recovery = { state: 'unreachable', rows: [], at: wake.from, fault: null };
		});
		return () => { active = false; };
	});
</script>

<div class="wake">
	<h4>Latest recorded wake in the selected window</h4>
	{#if reading.answer === 'pending'}
		<p class="note" role="status">Loading Gardener task reports.</p>
	{:else if reading.answer.state === 'unreachable' || reading.answer.state === 'missing'}
		<p class="note">{reading.answer.state === 'missing' ? 'Task reports are not published yet.' : 'Task reports did not arrive.'}
			{#if reading.answer.state === 'unreachable'}
				<button type="button" class="control" onclick={() => { retryAsks([gardenerWakeQuery]); retryCount += 1; }}>Retry task reports</button>
			{/if}
		</p>
	{:else if latest}
		<p>Last reported shard finished work: <strong><time datetime={latest.workEnded}>{utcTime(latest.workEnded)}</time></strong>.</p>
		<p class="note">Of {latest.tasks.length} task reports: {latest.countStops.map((item) => `${item.count} ${item.label.toLowerCase()}`).join(', ')}.</p>
	{:else}
		<p class="note">No wake is recorded in this window. This does not establish that Gardener did not run.</p>
	{/if}
	{#if reading.range}<p class="note">Task record covers {longDate(reading.range.from)} to {longDate(reading.range.to)} UTC.</p>{/if}
	{#each notes as note (note)}<p class="note">{note}</p>{/each}
	{#if reading.history.ignored > 0}<p class="note">Some task reports could not be read.</p>{/if}
</div>
{#if selected}
	<details ontoggle={(event) => expanded = event.currentTarget.open}>
		<summary>Task reports and recoveries</summary>
		{#if reading.history.wakes.length > 1}
			<label>Recorded wake
				<select class="control" value={selected.key} onchange={(event) => chosen = event.currentTarget.value}>
					{#each reading.history.wakes as wake (wake.key)}
						<option value={wake.key}>{utcTime(wake.workEnded)}; {wake.runId}, attempt {wake.attempt}</option>
					{/each}
				</select>
			</label>
		{:else}<p class="note">{selected.runId}, attempt {selected.attempt}.</p>{/if}
		<ul class="reports">
			{#each selected.tasks as task}
				<li><strong>{task.task}</strong>: {task.status}{task.fault === null ? '' : ` (${task.fault.replaceAll('-', ' ')})`}.
					<span class="note">{task.job}, shard {task.shard}. {#if task.resume}Resume from {task.resume}.{/if}</span></li>
			{/each}
		</ul>
		{#if expanded}
			{#if recovery === null}<p class="note" role="status">Loading recovery notes.</p>
			{:else if recovery.state === 'unreachable' || recovery.state === 'missing'}<p class="note">Recovery notes did not arrive.</p>
			{:else}
				{#if repairs.partial || recovery.lostDays.length || Object.keys(recovery.setAside).length}<p class="note">Some recovery evidence is unavailable.</p>{/if}
				{#if repairs.reports.length}
					<ul class="reports" aria-label="Recovery notes">
						{#each repairs.reports as repair}<li>{repair.task}: {repair.label} ({repair.subject}).</li>{/each}
					</ul>
				{:else}<p class="note">No recovery notes in the reports read for this wake.</p>{/if}
			{/if}
		{/if}
	</details>
	<details>
		<summary>Removal reports</summary>
		<p class="note">Previews did not remove anything. Compaction reports can include superseded inputs and moved files, not just expiry.</p>
		<ul class="reports">
			{#each [...selected.tasks].sort((a, b) => Number(b.task.startsWith('workflow-')) - Number(a.task.startsWith('workflow-')) || a.task.localeCompare(b.task)) as task}
				<li><strong>{task.task}</strong>: {removalReport(task)}
					{#if task.bytes && task.task === 'workflow-artifacts'}{task.bytes.toLocaleString('en')} {task.dryRun ? 'bytes in preview' : 'reported bytes freed'}.{/if}</li>
			{/each}
		</ul>
	</details>
{/if}

<style>
	.wake { border-block-start: 1px solid var(--color-rule); padding-block-start: var(--space-3); }
	h4, p { margin-block: 0 var(--space-1); }
	.note { color: var(--color-text-secondary); font-size: var(--console-small-size); overflow-wrap: anywhere; }
	.reports { margin-block: var(--space-2); padding-inline-start: var(--space-4); overflow-wrap: anywhere; }
	label { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--space-2); }
	summary { cursor: pointer; min-block-size: var(--console-control-min-height); }
	.control { max-inline-size: 100%; min-block-size: var(--console-control-min-height); color: inherit; background: var(--color-surface); border: 1px solid var(--color-rule-strong); border-radius: var(--console-control-radius); padding-inline: var(--console-control-padding-inline); font: inherit; }
</style>
