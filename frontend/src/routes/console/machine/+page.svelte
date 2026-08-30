<script lang="ts">
	/** The hardware the model ran on.
	 *
	 * This route ships almost empty and that is correct, not an oversight. The
	 * pipeline has written `state/runtime-counters.csv` since 2026-08-26 and no
	 * page has ever drawn a cell of it, so for four days every throughput figure
	 * this project quoted was taken on hardware whose read speed varied by more
	 * than 2x inside a single run with no surface on which anyone could notice.
	 * `$lib/server/runtime-counters.ts` can read it since 2026-08-30; the panels
	 * that render what it reads are the rows after this one.
	 *
	 * A route that hid itself until it had data would be a route nobody knew to
	 * check. So it says what is missing, once at the top and once per panel, and
	 * each panel is the slot the reader for that ledger lands in.
	 */
	import { base } from '$app/paths';
	import ConsoleBand from '$lib/components/ConsoleBand.svelte';
	import ConsoleNav from '$lib/components/ConsoleNav.svelte';
	import Panel from '$lib/components/Panel.svelte';

	let { data } = $props();

	/** What each panel will answer, and what it is waiting on.
	 *
	 * Named here rather than left to a later row, because the names are the
	 * whole content of the page today: an operator who reads them knows which
	 * questions the counters can answer and that none of them is answered yet.
	 */
	const PANELS: { id: string; title: string; note: string; empty: string }[] = [
		{
			id: 'shards',
			title: 'Shards of the newest run',
			note: 'One row per shard, ranked by how long its job took.',
			empty:
				'Nothing is drawn here yet. The run ledger records a job clock and a processor name per shard, and no panel reads either.'
		},
		{
			id: 'reading-writing',
			title: 'Reading against writing',
			note: 'How the model server split its time between reading a prompt and writing an answer.',
			empty:
				'Nothing is drawn here yet. Reading took 63.8 percent of one measured run, and no page says so.'
		},
		{
			id: 'cache',
			title: 'Prompt cache',
			note: 'Prompt tokens the server never had to read again.',
			empty: 'Nothing is drawn here yet. The counter is recorded and nothing reads it.'
		},
		{
			id: 'context',
			title: 'Context headroom',
			note: 'The longest sequence a run saw, against the window it was given.',
			empty:
				'Nothing is drawn here yet. The longest sequence on record used 60 percent of the window, and no page says how much is spare.'
		},
		{
			id: 'clocks',
			title: 'Shard clocks against the timeout',
			note: 'What each shard spent, against the minutes it is allowed.',
			empty:
				'Nothing is drawn here yet. The slowest shard on record used 47 percent of its timeout.'
		}
	];
</script>

<svelte:head>
	<title>Console: Machine &mdash; {data.ui.site_title}</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<section class="py-6" data-surface="operator" data-console-route="machine">
	<h1 class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text">Console</h1>
	<p class="mt-1 text-[0.9375rem] text-text-secondary">
		The hardware the model ran on, and how much it varied between runs.
	</p>

	<ConsoleBand band={data.band}>
		{#snippet window()}
			<!-- No control. Nothing on this route is windowed yet, and a control that
			     governs nothing is worse than an absent one: it answers a click by
			     changing nothing and leaves the operator to work out why. -->
			<p class="mt-5 text-[0.8125rem] text-text-tertiary" data-band-window="none">
				Nothing on this route is windowed yet, so the days control is not drawn here. It is on
				<a class="text-accent hover:underline" href="{base}/console/">Pipelines</a>
				and
				<a class="text-accent hover:underline" href="{base}/console/model/">Model</a>, and the
				choice is remembered between them.
			</p>
		{/snippet}
	</ConsoleBand>
	<ConsoleNav routes={data.routes} active="machine" />

	<!-- One sentence, no chart. It is what stops this route reading as a page
	     about a machine nothing ran on. -->
	<p class="console-carry" data-console-carry="pipelines">
		{data.carries.machine}
		<a class="carry-link" href="{base}/console/">Pipelines &rarr;</a>
	</p>

	<h2 class="console-h2">Nothing here is drawn yet</h2>
	<p class="mt-1 text-[0.9375rem] text-text-secondary" data-machine="empty">
		The pipeline writes one row per shard per run to <code>state/runtime-counters.csv</code>, and
		no panel on this site has ever read one. That is why this route exists before its panels do:
		the counters are the only record of how much the hardware under a run varied, and a route that
		waited until it had a chart would be a route nobody knew to come back to. Each panel below
		names the question it will answer.
	</p>

	{#each PANELS as panel (panel.id)}
		<Panel title={panel.title} note={panel.note}>
			<p class="mt-2 text-[0.8125rem] text-text-secondary" data-machine-panel-empty={panel.id}>
				{panel.empty}
			</p>
		</Panel>
	{/each}
</section>
