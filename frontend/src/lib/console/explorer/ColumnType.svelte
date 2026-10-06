<script lang="ts">
	// A column's engine type, printed in lower case and painted with the colour token of its family.
	import { typeColour } from '$lib/console/explorer/type-colour';
	let { type }: { type: string } = $props();
</script>

<span class="column-type" data-column-type style:color="var({typeColour(type)})">{type.toLowerCase()}</span>

<style>
	.column-type { font-family: var(--font-data); font-size: var(--text-xs); font-weight: 400; overflow-wrap: anywhere; }
</style>
