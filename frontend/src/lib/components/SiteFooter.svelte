<script lang="ts">
	/** Which commit a reader is looking at.
	 *
	 * Two adjacent facts that are never merged: the run that produced the data,
	 * and the commit that produced the site. They move independently, and a
	 * single line claiming both would be wrong half the time.
	 */
	import { base } from '$app/paths';
	import { clockUtc, longDate } from '$lib/format';
	import type { DigestDay } from '$lib/payload/types';

	let {
		day,
		repoUrl
	}: { day: DigestDay | null; repoUrl: string } = $props();

	const commit = __BUILD_COMMIT__;
	const builtOn = __BUILD_DATE__;
	const short = $derived(commit.slice(0, 7));
	const lastRun = $derived(day?.runs.at(-1) ?? null);
	const retention = $derived(
		day && day.retention_window_months > 0
			? `Days older than ${day.retention_window_months} months are removed.`
			: 'Nothing is deleted.'
	);
</script>

<footer class="mt-16 border-t border-rule pt-8 pb-12 text-[0.8125rem] text-text-tertiary">
	<p>Every summary is checked against the article it came from. Where the check went badly, the item says so.</p>

	{#if day && lastRun}
		<p class="mt-2">
			Run {lastRun.n} of {longDate(day.date)}, {clockUtc(lastRun.at)}.
		</p>
	{/if}

	{#if day && day.items_failed > 0}
		<p class="mt-1">
			We skipped {day.items_failed} stories today because we could not read enough of the page to
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
