<script lang="ts">
	/** How near the runner's memory ceiling one run got, item by item.
	 *
	 * The board is the panel: everything this file adds is the heading and the
	 * sentence that says which grain answers which question.
	 */
	import Panel from '$lib/components/Panel.svelte';
	import MemoryBoard from '$lib/components/MemoryBoard.svelte';
	import type { MemoryBoardView } from '$lib/charts/machine';

	let { board }: { board: MemoryBoardView } = $props();
</script>

<Panel
	heading="h3"
	id="memory-board"
	title="How close an article came to using up the machine's memory"
	note="One article can take the machine to its floor while the part of the run it sits in reads as normal, and how little the kernel had left is what decides whether a bigger model fits - one mark an item of the newest run."
	wide
>
	<MemoryBoard {board} />
</Panel>
