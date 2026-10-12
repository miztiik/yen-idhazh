<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { Row, LedgerReach, SliceResult } from '../../data/ledger';
	import { rangeFor, type PanelQuery, type Range, type RouteReach } from '../queries/window';
	import EmptyState from '../../charts/d3/EmptyState.svelte';
	import { recordEmptyState } from '../../charts/d3/empty';
	import { modelSlice } from './slice';
	import { noRecordSentence, setAsideSentence } from '../recording';

	let { queries, reach, preset, presets, retry, height, width, name, onAnswer, children }: {
		queries: readonly PanelQuery[]; reach: RouteReach | null; preset: number; presets: readonly number[];
		retry: number; height: number; width: number; name: string;
		onAnswer: (name: string, answer: SliceResult | LedgerReach | 'pending') => void;
		children: Snippet<[readonly Row[][], Range]>;
	} = $props();
	let rows = $state<Row[][]>([]);
	let range = $state<Range | null>(null);
	let panelState = $state<'loading' | 'ready' | 'quiet' | 'missing' | 'unreachable'>('loading');
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
			return { selected, answer: 'from' in selected ? await modelSlice(query, selected) : selected };
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
			notes = results.flatMap(({ answer, selected }, index) => {
				if ((answer.state !== 'ok' && answer.state !== 'quiet') || !('rows' in answer) || !('from' in selected)) return [];
				const lines: string[] = [];
				const first = Object.values(currentReach.ledgers).flatMap((ledger) => ledger?.state === 'ok' ? [ledger.first] : []).sort()[0];
				if (first !== undefined && answer.first > first) lines.push(`Recorded from ${answer.first}; earlier days on this page have no ${asked[index].ledger} record.`);
				if (answer.lostDays.length) lines.push(noRecordSentence('This record', answer.lostDays, (days) => `these figures do not show ${days}`));
				const aside = setAsideSentence('This record', asked[index].ledger, answer.setAside, 'these figures');
				if (aside !== null) lines.push(aside);
				return lines;
			});
		});
		return () => { current = false; };
	});
</script>

<div data-readout-fetched={queries.map((query) => query.ledger).join(' ')} data-model-query={name}
	data-query-state={panelState} data-query-asked={range?.asked} data-window-days={range?.days}
	data-range-from={range?.from} data-range-to={range?.to}>
	{#if panelState === 'ready'}
		{#if range !== null}
			{@render children(rows, range)}
		{/if}
	{:else}
		<EmptyState drawing={recordEmptyState(panelState)} {height} {width} {name} label={name} />
	{/if}
	{#each notes as note}<p data-record-note>{note}</p>{/each}
</div>
