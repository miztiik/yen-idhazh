<script lang="ts">
	/** Compile the real duration geometry in the browser, not across a serialized function boundary. */
	import { dateSeries } from '$lib/charts/d3/dateSeries';
	import type { NumberFormatConfig } from '$lib/number-format';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { frame } from '$lib/charts/frame';
	import { emptyState } from '$lib/charts/d3/empty';
	import { SERIES_TOKENS } from '$lib/console/series-tokens';
	let { width, number_format }: { width: number; number_format: NumberFormatConfig } = $props();
	const points = (values: readonly (number | null)[]) => values.map((value, index) => ({ date: `2026-09-0${index + 1}`, value }));
	const geometry = $derived(dateSeries([
		{ label: 'Fetch', token: SERIES_TOKENS.fetch, points: points([2, 0, null]) },
		{ label: 'Summarize', token: SERIES_TOKENS.summarize, points: points([6, 0, null]) }
	], { frame: frame(width, 220), density: 6, valueTicks: 4, number_format, padding: 0.2, stacked: true,
		rule: { declined: 'This fixed fixture has no settings comparison.' },
		reconciliation: {
			elapsed: { label: 'Elapsed time', token: '--color-text-tertiary', points: points([5, 0, null]) },
			overlap: { label: 'Overlap', token: '--color-text-secondary', points: points([3, 0, null]) }
		}
	}));
</script>
<DateSeries {geometry} name="item-time" label="Duration stack and elapsed time"
	empty={emptyState('quiet', 'No measured durations.')} {width} height={220} />
