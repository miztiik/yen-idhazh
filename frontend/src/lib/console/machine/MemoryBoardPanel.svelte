<script lang="ts">
	/** How near the runner's memory ceiling one run got, item by item.
	 *
	 * The board is the panel: everything this file adds is the heading and the
	 * sentence that says which grain answers which question.
	 */
	import Panel from '$lib/components/Panel.svelte';
	import MemoryBoard from '$lib/components/MemoryBoard.svelte';
	import type { MemoryBoardView } from '$lib/charts/machine';
	import type { FigureSpan } from '$lib/charts/span-track';
	import type { SettingsMoved } from '$lib/console/settings-moved';

	let {
		board,
		span,
		moved,
		start,
		end,
		windowDays
	}: {
		board: MemoryBoardView;
		span: FigureSpan;
		/** What the run record says moved, over the whole page's reach. The panel
		 * keeps the days inside its own span, because the figure a change can
		 * mislead a reader about - the lowest run to the highest - is a figure about
		 * that span and no other. */
		moved: readonly SettingsMoved[];
		start: string;
		end: string;
		windowDays: number;
	} = $props();

	const inSpan = $derived(moved.filter((one) => one.date >= start && one.date <= end));
</script>

<Panel
	heading="h3"
	id="memory-board"
	title="How close an article came to using up the machine's memory"
	note="One article can take the machine to its ceiling while the part of the run it sits in reads as normal, which is what decides whether a bigger model fits - one mark an item of the newest run."
	wide
>
	<MemoryBoard {board} {span} moved={inSpan} {windowDays} />
</Panel>
