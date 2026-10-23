<script lang="ts">
	import type { sourceHealth } from './source-health';
	import VoicesPanel from './VoicesPanel.svelte';
	import RankedList from '../../components/RankedList.svelte';
	import RecordFrame from './RecordFrame.svelte';
	let { census, width, height }: { census: ReturnType<typeof sourceHealth>; width: number; height: number } = $props();
</script>
<VoicesPanel id="source-health" title="Sources we may ask, and what they yield" question="what happened"
	comparison="each source's yield against the best source's" reason="permissions and one run's census are not a model trend">
	{#if census === null}
		<div data-source-health="absent"><RecordFrame panelState="missing" {width} {height} name="source-health" label="Source census" kind="rankedList">{#snippet children()}{/snippet}</RecordFrame></div>
	{:else if census.view.sources.length === 0}
		<div data-source-health="empty"><RecordFrame panelState="quiet" {width} {height} name="source-health" label="Source census" kind="rankedList">{#snippet children()}{/snippet}</RecordFrame></div>
	{:else}
		<p data-lede data-source-health-lead data-source-health-sources={census.view.sources.length} data-source-health-withheld={census.withheld}>{census.headline}</p>
		<p class="notes" data-window-exempt="source-health">Permission, answering, retirement and yield are four separate facts. They come from run {census.view.run_id}, not the window control. Yield spans {census.view.complete_dates} complete days, {census.view.first_date ?? 'no first day recorded'} to {census.view.last_date ?? 'no last day recorded'}.</p>
		<div class="evidence" data-source-health="states">
			<table>
				<thead><tr><th>Fact</th><th>State</th><th>Sources</th><th>What it withholds</th></tr></thead>
				<tbody>
					{#each census.permission as fact (fact.id)}<tr data-source-state="permission-{fact.id}"><td>Permission</td><td>{fact.label}</td><td data-source-state-count>{fact.count}</td><td>{fact.withheld}</td></tr>{/each}
					{#each census.availability as fact (fact.id)}<tr data-source-state="availability-{fact.id}"><td>Reading</td><td>{fact.label}</td><td data-source-state-count>{fact.count}</td><td>{fact.withheld}</td></tr>{/each}
					<tr data-source-state="retirement-retired"><td>Retirement</td><td>the server said the address is gone</td><td data-source-state-count>{census.retired}</td><td>no run asks this address again until its configured address changes</td></tr>
				</tbody>
			</table>
		</div>
		{#if census.notes.length === 0}
			<p class="notes" data-source-health="clear">Every source is allowed to be asked and answering, so there is nothing to name.</p>
		{:else}
			<div data-source-health="notes" data-source-health-drawn={census.notes.length}>
				<table>
					<thead><tr><th>Source</th><th>Desk</th><th>Current limitation</th><th>Offered</th><th>Published</th></tr></thead>
					<tbody>{#each census.notes as note (note.source_id)}
						<tr data-source-note={note.source_id}><td>{note.title}<br/><small data-source-note-id>{note.source_id}</small></td><td>{note.vertical}</td><td data-source-note-withheld>{note.withheld}</td><td>{note.opportunities}</td><td>{note.publications}</td></tr>
					{/each}</tbody>
				</table>
			</div>
			{#if census.hidden > 0}<p class="notes" data-source-health-more>{census.hidden} more sources have a limitation, none ranked above the last row here.</p>{/if}
		{/if}
		<div class="evidence" data-source-health-record={census.view.yield_readable ? 'measured' : 'short'} data-source-health-days={census.view.complete_dates}>
			{#if census.view.complete_dates > 0}<p class="notes">Over {census.view.complete_dates} complete {census.view.complete_dates === 1 ? 'day' : 'days'}, sources were offered {census.totals.offered} addresses and published {census.totals.published}. {census.totals.failures} source-owned failures stay in those offered counts. {#if !census.view.yield_readable}These are counts and not a rate.{/if}</p>{/if}
			<RankedList caption="Source yield" geometry={census.geometry} maxText={census.maxText}
				measured={census.view.complete_dates > 0} unmeasuredNote="No day has finished with a planned article on it, so there is no publishing record yet."
				emptyNote="No source has a publication to compare against the best source." />
		</div>
		<p class="notes" data-source-health-basis>An offer is one planned address on a complete day, counted once however many runs tried it. Today is not counted. Source-owned failures are shown beside offered and published, never subtracted from either. {#if !census.view.yield_readable}The record is under the {census.view.min_complete_days} complete days a yield judgement needs; these are counts, not a rate.{/if}</p>
	{/if}
</VoicesPanel>
