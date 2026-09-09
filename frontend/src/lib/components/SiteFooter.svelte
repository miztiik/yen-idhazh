<script lang="ts">
	/** Where to go, and nothing else.
	 *
	 * It printed six blocks in August and three until this row. What went is
	 * everything a later build or a later day could change: the commit and the
	 * build date, and the promise about what is deleted, which was read off the
	 * newest day. The footer is on every page, so each of those rewrote the bytes
	 * of every page on the site whenever anything published.
	 */
	import Icon from '$lib/icons/Icon.svelte';
	import { base } from '$app/paths';

	let { repoUrl }: { repoUrl: string } = $props();
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
</footer>
