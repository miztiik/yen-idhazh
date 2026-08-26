<script lang="ts">
	/** Which commit a reader is looking at.
	 *
	 * Two adjacent facts that are never merged: the run that produced the data,
	 * and the commit that produced the site. They move independently, and a
	 * single line claiming both would be wrong half the time.
	 */
	import { base } from '$app/paths';
	import { clockUtc, longDate } from '$lib/format';

	/** The four facts this footer prints, and nothing else.
	 *
	 * It used to take the whole day. The footer sits on every page, so the whole
	 * day travelled on the root layout and was inlined into every page with it -
	 * including the ones that show no articles at all.
	 */
	interface DayFacts {
		date: string;
		run: { n: number; at: string } | null;
		items_failed: number;
		retention_window_months: number;
	}

	let { facts, repoUrl }: { facts: DayFacts | null; repoUrl: string } = $props();

	const commit = __BUILD_COMMIT__;
	const builtOn = __BUILD_DATE__;
	const short = $derived(commit.slice(0, 7));
	const retention = $derived(
		facts && facts.retention_window_months > 0
			? `Days older than ${facts.retention_window_months} months are removed.`
			: 'Nothing is deleted.'
	);
</script>

<footer class="mt-16 border-t border-rule pt-8 pb-12 text-[0.8125rem] text-text-tertiary">
	<p>Every summary is checked against the article it came from. Where the check went badly, the item says so.</p>

	{#if facts && facts.run}
		<p class="mt-2">
			Run {facts.run.n} of {longDate(facts.date)}, {clockUtc(facts.run.at)}.
		</p>
	{/if}

	{#if facts && facts.items_failed > 0}
		<p class="mt-1">
			We skipped {facts.items_failed} stories today because we could not read enough of the page to
			summarize them fairly.
		</p>
	{/if}

	<p class="mt-1">
		Built from git &mdash;
		{#if commit === 'dev'}
			<span>dev</span>
		{:else}
			<a
				href="{repoUrl}/commit/{commit}"
				title={commit}
				target="_blank"
				rel="noopener noreferrer"
				class="text-accent hover:underline">{short}</a
			>
		{/if}
		&mdash; deployed {builtOn}
	</p>

	<p class="mt-1">{retention}</p>

	<nav class="mt-4 flex flex-wrap gap-4" aria-label="Site">
		<a href="{base}/archive/" class="text-accent hover:underline">Archive</a>
		<a href="{base}/console/" class="text-accent hover:underline">Console</a>
		<a href={repoUrl} target="_blank" rel="noopener noreferrer" class="text-accent hover:underline">
			Source code
		</a>
	</nav>
</footer>
