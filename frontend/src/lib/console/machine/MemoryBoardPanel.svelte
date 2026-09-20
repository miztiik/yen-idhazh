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

	let {
		board,
		span,
		windowDays
	}: {
		board: MemoryBoardView;
		span: FigureSpan;
		windowDays: number;
	} = $props();
</script>

<Panel
	heading="h3"
	title="How near the runner's ceiling this run got, item by item"
	note="What the model server held, what it left the kernel, and how long the queue was - one mark an item, with the per-shard maxima and the window's span a grain switch away. The item grain is the one a per-shard maximum cannot show: one item can take the machine most of the way to its ceiling while its shard's figure reads as a normal run."
	wide
>
	<MemoryBoard {board} {span} {windowDays} />
</Panel>
