<script lang="ts">
	/** Three lines: where to go, what built this, and why an item can say it is
	 * unsure.
	 *
	 * It used to print six blocks, two of them about today's run. The footer is
	 * on every page, so a stamp about today sat eight screens below a page that
	 * shows no day at all - and on the pages that do show one, `DayNotice` was
	 * already saying it. Both facts live beside the day now.
	 */
	import Icon from '$lib/icons/Icon.svelte';
	import { base } from '$app/paths';

	/** The one fact this footer takes from the day, and nothing else.
	 *
	 * Whatever the root layout hands down is inlined into every prerendered
	 * page, including `/404` and `/evals/`, which render no day.
	 */
	interface DayFacts {
		retention_window_months: number;
	}

	let { facts, repoUrl }: { facts: DayFacts | null; repoUrl: string } = $props();

	const commit = __BUILD_COMMIT__;
	const builtOn = __BUILD_DATE__;
	const short = $derived(commit.slice(0, 7));
	// The knob is `retention.image_months`, and the job it drives may delete a
	// rendered chart and nothing else - never a day, never a story, never a link
	// (docs/architecture/publishing/layout.md). This line used to say days were
	// removed, which promised the opposite of what the code does.
	const retention = $derived(
		facts && facts.retention_window_months > 0
			? `Charts older than ${facts.retention_window_months} months are deleted.`
			: 'Nothing is deleted.'
	);
</script>

<footer class="mt-16 border-t border-rule pt-8 pb-12 text-sm text-text-tertiary">
	<nav class="flex flex-wrap gap-4" aria-label="Site">
		<a href="{base}/archive/" class="inline-flex items-center gap-1.5 text-accent hover:underline">
			<Icon id="archive" size={14} />Archive
		</a>
		<a href="{base}/console/" class="inline-flex items-center gap-1.5 text-accent hover:underline">
			<Icon id="console" size={14} />Console
		</a>
		<a href={repoUrl} target="_blank" rel="noopener noreferrer" class="text-accent hover:underline">
			Source code
		</a>
	</nav>

	<p class="mt-4">
		Built from git
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
		{/if}, deployed {builtOn}. {retention}
	</p>

	<p class="mt-2 text-xs">
		Every summary is checked against the article it came from. Where the check went badly, the item
		says so.
	</p>
</footer>
