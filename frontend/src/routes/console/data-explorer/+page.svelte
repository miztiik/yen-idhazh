
<script lang="ts">
	import { onMount } from 'svelte';
	import { ask, askCost, pageHeldBytes, startAfresh, type AskResult, type Column, type DateStamp, type LedgerName, type Row, type SpanCost } from '$lib/data/ledger';
	import Panel from '$lib/components/Panel.svelte';
	import { fillWindowSlot } from '$lib/console/window-slot';
	import { refusedSentence } from '$lib/console/waiting';
	import { shortDate, dayMonth } from '$lib/format';
	import QuestionStrip from '$lib/console/explorer/QuestionStrip.svelte';
	import LedgerList from '$lib/console/explorer/LedgerList.svelte';
	import ColumnList from '$lib/console/explorer/ColumnList.svelte';
	import QueryEditor from '$lib/console/explorer/QueryEditor.svelte';
	import ActionLine from '$lib/console/explorer/ActionLine.svelte';
	import AnswerTable from '$lib/console/explorer/AnswerTable.svelte';
	import { fetchRegistry, flattenRegistry, type LedgerRegistry, type RegistryLedger } from '$lib/console/explorer/registry';
	import type { ExplorerExample } from '$lib/server/config';

	let { data } = $props();

	const published = $derived(data.publishedLedgers as string[]);
	const config = $derived(data.explorer);
	const presets = $derived(data.console.window_presets);
	// svelte-ignore state_referenced_locally
	let windowDays = $state(data.console.default_window_days);
	let ready = $state(false);
	let registry = $state<LedgerRegistry>({ families: [] });
	let registryError = $state<string | null>(null);
	let filter = $state('');
	let selected = $state<LedgerName[]>([]);
	let sql = $state('SELECT count(*) AS rows FROM "published"');
	let costing = $state(false);
	let running = $state(false);
	let refreshing = $state(false);
	let cost = $state<SpanCost>({ files: 0, bytes: 0, unpackedDays: [], through: {} });
	let heldBytes = $state(0);
	let lastMs = $state<number | null>(null);
	let result = $state<AskResult | null>(null);
	let ledgerColumns = $state<Column[]>([]);
	let showAnswerColumns = $state(false);
	let runSpan = $state<{ from: DateStamp; to: DateStamp } | null>(null);

	const ledgers = $derived<RegistryLedger[]>(flattenRegistry(registry));
	const selectedPublished = $derived(selected.filter((name) => published.includes(name)));
	const columns = $derived(showAnswerColumns && result !== null && 'columns' in result ? result.columns : ledgerColumns);
	const columnLabel = $derived(showAnswerColumns ? 'Answer columns' : 'Columns in the selected ledgers');
	const statusLine = $derived(
		`The next question will read ${windowDays} UTC ${windowDays === 1 ? 'day' : 'days'} ending today.`
	);

	function todayUtc(): DateStamp {
		const now = new Date(Date.now());
		return `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}-${String(now.getUTCDate()).padStart(2, '0')}`;
	}
	function addDays(day: DateStamp, delta: number): DateStamp {
		const d = new Date(`${day}T00:00:00Z`);
		d.setUTCDate(d.getUTCDate() + delta);
		return d.toISOString().slice(0, 10);
	}
	function span(): { from: DateStamp; to: DateStamp } {
		const to = todayUtc();
		return { to, from: addDays(to, 1 - windowDays) };
	}
	function quoteLedger(name: LedgerName): string {
		return `"${name.replace(/"/g, '""')}"`;
	}
	function toggle(name: LedgerName) {
		selected = selected.includes(name) ? selected.filter((one) => one !== name) : [...selected, name];
		showAnswerColumns = false;
		void updateCostAndColumns();
	}
	function pick(example: ExplorerExample) {
		selected = example.ledgers.filter((name): name is LedgerName => ledgers.some((ledger) => ledger.name === name));
		windowDays = presets.includes(example.days) ? example.days : windowDays;
		sql = example.sql;
		showAnswerColumns = false;
		void updateCostAndColumns();
	}
	function setWindow(days: number) {
		windowDays = days;
		void updateCostAndColumns();
	}
	function monthsFor(): number { return 0; }

	fillWindowSlot({
		get days() { return windowDays; },
		get presets() { return presets; },
		get busy() { return costing || running; },
		get ready() { return ready; },
		get statusLine() { return statusLine; },
		monthsFor,
		onChange: setWindow
	});

	async function refreshRegistry() {
		refreshing = true;
		registryError = null;
		try {
			await startAfresh();
			heldBytes = 0;
			registry = await fetchRegistry();
			await updateCostAndColumns();
		} catch (error) {
			registryError = error instanceof Error ? error.message : String(error);
		} finally {
			refreshing = false;
		}
	}

	async function updateCostAndColumns() {
		if (!ready) return;
		const picked = selectedPublished;
		if (picked.length === 0) {
			cost = { files: 0, bytes: 0, unpackedDays: [], through: {} };
			ledgerColumns = [];
			return;
		}
		costing = true;
		try {
			const nextSpan = span();
			cost = await askCost(picked, nextSpan.from, nextSpan.to);
			const described: Column[] = [];
			for (const ledger of picked) {
				const day = cost.through[ledger] ?? nextSpan.to;
				const answer = await ask({ ledgers: [ledger], from: day, to: day, sql: `DESCRIBE ${quoteLedger(ledger)}`, maxChars: config.query_max_chars, maxRows: config.max_rows, maxFetchBytes: config.max_fetch_bytes });
				if ((answer.state === 'ok' || answer.state === 'quiet') && 'columns' in answer) {
					for (const column of answer.columns) described.push({ name: `${ledger}.${column.name}`, type: column.type });
				}
			}
			ledgerColumns = described;
		} finally {
			costing = false;
		}
	}

	async function run() {
		if (selected.length === 0) return;
		running = true;
		const nextSpan = span();
		runSpan = nextSpan;
		const started = performance.now();
		try {
			const answer = await ask({ ledgers: selected, from: nextSpan.from, to: nextSpan.to, sql, maxChars: config.query_max_chars, maxRows: config.max_rows, maxFetchBytes: config.max_fetch_bytes });
			lastMs = Math.round(performance.now() - started);
			result = answer;
			showAnswerColumns = answer.state === 'ok' || answer.state === 'quiet';
			if ((answer.state === 'ok' || answer.state === 'quiet') && 'read' in answer) {
				heldBytes = pageHeldBytes();
				lastMs = answer.read.ms;
			}
		} finally {
			running = false;
		}
	}

	onMount(() => {
		ready = true;
		void refreshRegistry();
	});
</script>

<p class="cross-link"><a href="/console/">Back to the pipeline console.</a> Records reads the ledgers directly, after you choose the days and press Run.</p>

<Panel id="data-explorer-ask" title="Ask the records" note="Pick ledgers, write one read-only DuckDB SQL statement, and run it in this browser.">
	<div class="question-panel" style={`--rail:${config.rail_rem}rem`}>
		<QuestionStrip examples={config.examples} onPick={pick} />
		<div class="question-grid">
			<LedgerList ledgers={ledgers} selected={selected} {published} {filter} onToggle={toggle} onFilter={(value) => (filter = value)} onRefresh={refreshRegistry} {refreshing} />
			<div class="editor-stack">
				{#if registryError}<p class="state warn">{registryError}</p>{/if}
				<QueryEditor value={sql} maxChars={config.query_max_chars} minLines={config.editor_lines[0]} maxLines={config.editor_lines[1]} onInput={(value) => (sql = value)} />
				<ActionLine files={cost.files} bytes={cost.bytes} {heldBytes} ms={lastMs} busy={running || costing} disabled={selected.length === 0 || sql.trim() === ''} onRun={run} />
			</div>
			<ColumnList columns={columns} label={columnLabel} />
		</div>
	</div>
</Panel>

<Panel id="data-explorer-rows" title="The answer" wide>
	{#if result === null}
		<div class="answer-state" data-explorer-idle>Press Run and the answer appears here, as a table.</div>
	{:else if running}
		<div class="answer-state shimmer" data-state="loading"></div>
	{:else if result.state === 'ok'}
		<div class="answer-note">{#if runSpan}Read from {windowDays} UTC days, {dayMonth(runSpan.from)} to {shortDate(runSpan.to)}.{/if}</div>
		<AnswerTable columns={result.columns} rows={result.rows as Row[]} capped={result.capped} maxRows={config.max_rows} pageSize={config.row_page} tableMaxVh={config.table_max_vh} cellMaxCh={config.cell_max_ch} barSpreadShare={config.bar_spread_share} />
	{:else if result.state === 'quiet'}
		<div class="answer-state" data-state="quiet">Your question ran and matched no rows.</div>
	{:else if result.state === 'missing'}
		<div class="answer-state" data-state="missing">{published.includes(result.ledger) ? `${result.ledger} has no days on this site yet.` : `${result.ledger} is not on this site yet, so nothing was asked of it.`}</div>
	{:else if result.state === 'unreachable'}
		<div class="answer-state warn" data-state="unreachable">{result.fault === 'engine' ? 'The query engine did not start in this browser. A current version of Chrome, Edge, Firefox or Safari runs it.' : result.fault === null ? `${result.ledger ?? 'The ledger'} for ${result.at ?? 'that day'} did not arrive, so the question did not run.` : `No file on this site holds ${result.ledger ?? 'the ledger'} for ${result.at ?? 'that day'}.`}</div>
	{:else if result.state === 'refused'}
		<div class="answer-state" data-state="refused">{refusedSentence(result.because)}{#if result.because.kind === 'engine-error'}<pre>{result.because.message}</pre>{/if}</div>
	{/if}
</Panel>

<style>
	.cross-link { margin: var(--space-4) 0; color: var(--color-text-secondary); }
	.cross-link a { color: var(--color-accent-strong); }
	.question-panel { display: grid; gap: var(--space-4); }
	.question-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-4); }
	.editor-stack { display: grid; gap: var(--space-4); align-content: start; }
	.state, .answer-note { margin: 0; color: var(--color-text-secondary); }
	.warn { color: var(--band-low); }
	.answer-state { min-block-size: var(--chart-height, 220px); display: grid; place-items: center; padding: var(--space-6); color: var(--color-text-secondary); background: var(--tint-neutral); border: 1px solid var(--color-rule); border-radius: var(--radius-md); }
	.answer-state pre { max-inline-size: 100%; overflow-x: auto; white-space: pre; font-family: var(--font-data); color: var(--code-string); }
	.shimmer { background: linear-gradient(90deg, var(--color-surface) 0%, var(--color-surface-raised) 50%, var(--color-surface) 100%); }
	@media (min-width: 1024px) { .question-grid { grid-template-columns: minmax(12rem, var(--rail)) minmax(0, 1fr) minmax(12rem, var(--rail)); } }
</style>
