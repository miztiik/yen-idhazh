<script lang="ts">
	/** The sentences a route prints about the records it read, before any panel draws from them.
	 *
	 * One sentence a record and a state, never one a panel and never a banner: a
	 * record is what is late, broken or short, and every panel built on it is
	 * empty, stops early or misses the same rows for the same reason. A record
	 * that did not load is a fault, so it takes the warn tint the Hardware route
	 * gives a run it left out; one not packed yet, packed some days short, with a
	 * day it has no record for, or with files set aside unread is a plain note at
	 * body size like the other recording notes (`recording.ts`): each is recorded
	 * and the route carries on. Nothing renders when every record was read whole
	 * and none is late, which is the common case.
	 */
	import type { RecordNote } from '$lib/console/recording';

	let { notes }: { notes: readonly RecordNote[] } = $props();
</script>

{#each notes as note (`${note.kind} ${note.records.join(' ')}`)}
	<p
		class="mt-3 text-[0.9375rem] text-text-secondary"
		class:record-fault={note.kind === 'unreadable'}
		data-record-note={note.kind}
		data-records={note.records.join(' ')}
	>
		{note.text}
	</p>
{/each}

<style>
	.record-fault {
		padding: var(--space-4);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-lg);
		background: var(--tint-warn);
		color: var(--color-text);
	}
</style>
