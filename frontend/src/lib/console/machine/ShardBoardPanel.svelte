<script lang="ts">
	/** Whether a slow day was the work or the machine, read one shard at a time.
	 *
	 * The board is the panel: everything this file adds is the heading and the
	 * sentence that says what the rows are for.
	 */
	import Panel from '$lib/components/Panel.svelte';
	import ShardBoard from '$lib/components/ShardBoard.svelte';
	import type { ShardBoardView } from '$lib/charts/machine';

	let {
		board,
		timeoutMinutes
	}: {
		board: ShardBoardView;
		timeoutMinutes: number;
	} = $props();
</script>

<Panel
	heading="h3"
	id="shard-board"
	title="Which parts of the last run took longest"
	note="A long clock at a normal read rate is a lot of articles and a long clock at a quarter of that rate is the machine, and the two have different fixes - one row a shard of the newest run."
	wide
>
	<ShardBoard {board} {timeoutMinutes} />
</Panel>
