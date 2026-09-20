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
	title="Shards of the newest run"
	note="What is broken, one row per shard, ranked by how long its job took. It answers whether a slow day was the work or the machine without leaving the row: a long clock at a normal read rate and a high item count is a lot of articles, and a long clock at a quarter of its neighbour's read rate, with load past the host's cores and swap falling, is the machine."
	wide
>
	<ShardBoard {board} {timeoutMinutes} />
</Panel>
