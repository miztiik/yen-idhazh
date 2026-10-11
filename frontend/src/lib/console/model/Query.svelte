<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { Row, LedgerReach, SliceResult } from '../../data/ledger';
	import { rangeFor, sliceOnce, type PanelQuery, type Range, type RouteReach } from '../queries/window';
	import Reserved from '../../components/Reserved.svelte';
	import type { PanelState } from '../waiting';

	let { queries, reach, preset, presets, retry, height, width, name, onAnswer, children }: {
		queries: readonly PanelQuery[]; reach: RouteReach | null; preset: number; presets: readonly number[];
		retry: number; height: number; width: number; name: string;
		onAnswer: (name: string, answer: SliceResult | LedgerReach | 'pending') => void;
		children: Snippet<[readonly Row[][], Range]>;
	} = $props();
	let rows = $state<Row[][]>([]);
	let range = $state<Range | null>(null);
	let panelState = $state<PanelState>('loading');
	let notes = $state<string[]>([]);
	$effect(() => {
		const currentReach = reach;
		const currentPreset = preset;
		const revision = retry;
		const asked = queries;
		if (currentReach === null) return;
		void revision;
		let current = true;
		panelState = 'loading';
		rows = [];
		notes = [];
		onAnswer(name, 'pending');
		void Promise.all(asked.map(async (query) => {
			const selected = rangeFor(query, currentPreset, currentReach, presets);
			return { selected, answer: 'from' in selected ? await sliceOnce(query, selected) : selected };
		})).then((results) => {
			if (!current) return;
			const answers = results.map(({ answer }) => answer);
			const worst = answers.find((a) => a.state === 'unreachable') ?? answers.find((a) => a.state === 'missing') ??
				answers.find((a) => a.state === 'ok') ?? answers[0];
			onAnswer(name, worst);
			panelState = worst.state === 'ok' ? 'ready' : worst.state;
			const selected = results.find((r) => 'from' in r.selected)?.selected;
			range = selected !== undefined && 'from' in selected ? selected : null;
			rows = answers.map((answer) => 'rows' in answer ? answer.rows : []);
			notes = results.flatMap(({ answer, selected }) => {
				if (answer.state !== 'ok' || !('rows' in answer) || !('from' in selected)) return [];
				const lines: string[] = [];
				if (answer.first > selected.from) lines.push(`Recorded from ${answer.first}.`);
				if (answer.lostDays.length) lines.push(`${answer.lostDays.length} recorded days were lost.`);
				const unread = Object.values(answer.setAside).reduce((a, b) => a + b, 0);
				if (unread) lines.push(`${unread} files were set aside unread; these figures may be short.`);
				return lines;
			});
		});
		return () => { current = false; };
	});
</script>

<div data-readout-fetched={queries.map((query) => query.ledger).join(' ')} data-model-query={name}>
	<Reserved record {panelState} {height} {width} {name} label={name}>
		{#if range !== null}
			{@render children(rows, range)}
			{#each notes as note}<p data-record-note>{note}</p>{/each}
		{/if}
	</Reserved>
</div>
