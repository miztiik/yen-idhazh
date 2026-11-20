<script lang="ts">
	import type { TimeWindow } from '$lib/charts/viewport';
	import { coverageException, utcSpan } from '$lib/console/window-coverage';

	let { span, common, source }: { span: TimeWindow | null; common: TimeWindow | null; source?: string } = $props();
	const reason = $derived(span === null ? null : coverageException(span, common));
</script>

{#if span !== null && reason !== null}
	<p data-coverage-exception data-range-from={span.start} data-range-to={span.end}>
		<strong>{source ? `${source} - ` : ''}{reason}:</strong> {utcSpan(span)}.
	</p>
{/if}

<style>
	p { margin-block: var(--space-2); color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-sm); }
	strong { font-weight: 600; }
</style>
