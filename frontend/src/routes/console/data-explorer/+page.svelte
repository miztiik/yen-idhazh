
<script lang="ts">
	import { onMount } from 'svelte';
	import { ask, askCost, pageHeldBytes, startAfresh, type AskResult, type Column, type DateStamp, type FetchCost, type LedgerName, type Row, type SpanCost } from '$lib/data/ledger';
	import Panel from '$lib/components/Panel.svelte';
	import ChoiceTiles from '$lib/components/ChoiceTiles.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import { explorerIdleSentence, explorerMissingSentence, explorerQuietSentence, explorerUnreachableSentence, refusedSentence } from '$lib/console/waiting';
	import { shortDate, dayMonth } from '$lib/format';
	import QuestionStrip from '$lib/console/explorer/QuestionStrip.svelte';
	import LedgerList from '$lib/console/explorer/LedgerList.svelte';
	import ColumnList from '$lib/console/explorer/ColumnList.svelte';
	import QueryEditor from '$lib/console/explorer/QueryEditor.svelte';
	import ActionLine from '$lib/console/explorer/ActionLine.svelte';
	import AnswerTable from '$lib/console/explorer/AnswerTable.svelte';
	import CopyAnswer from '$lib/console/explorer/CopyAnswer.svelte';
	import HistoryList from '$lib/console/explorer/HistoryList.svelte';
	import ShapePanel from '$lib/console/explorer/ShapePanel.svelte';
	import { chooseExplorerShapes, type ExplorerChartType } from '$lib/console/explorer/shape';
	import { explorerAddress, parseExplorerAddress, LINK_TOO_LONG_NOTICE } from '$lib/console/explorer/address';
	import { keepRecentRun, keepSavedQuestion, forgetSavedQuestion, suggestedSaveName, type KeptQuestion, type RecentRun } from '$lib/console/explorer/keep';
	import { fetchRegistry, flattenRegistry, type LedgerRegistry, type RegistryLedger } from '$lib/console/explorer/registry';
	import type { ExplorerExample } from '$lib/server/config';
	import { LEDGER_NAMES } from '$lib/data/slice-shapes';
	import Icon from '$lib/icons/Icon.svelte';

	let { data } = $props();

	const published = $derived(data.publishedLedgers as string[]);
	const config = $derived(data.explorer);
	const presets = $derived(data.console.window_presets);
	// svelte-ignore state_referenced_locally
	let windowDays = $state(data.console.default_window_days);
	let fromDay = $state('');
	let toDay = $state('');
	let ready = $state(false);
	let registry = $state<LedgerRegistry>({ families: [] });
	let registryError = $state<string | null>(null);
	let filter = $state('');
	let selected = $state<LedgerName[]>([]);
	let sql = $state('SELECT count(*) AS rows FROM "published"');
	let costing = $state(false);
	let running = $state(false);
	let refreshing = $state(false);
	let cost = $state<SpanCost>({ files: 0, bytes: 0, unpackedDays: [], siteFrom: null, through: {} });
	let heldBytes = $state(0);
	let lastMs = $state<number | null>(null);
	let lastRead = $state<FetchCost | null>(null);
	let result = $state<AskResult | null>(null);
	let orderedRows = $state<Row[]>([]);
	let ledgerColumns = $state<Column[]>([]);
	let showAnswerColumns = $state(false);
	let runSpan = $state<{ from: DateStamp; to: DateStamp } | null>(null);
	let wide = $state(false);
	let savedQuestions = $state<KeptQuestion[]>([]);
	let recentRuns = $state<RecentRun[]>([]);
	let keepNotice = $state<string | null>(null);
	let linkNotices = $state<string[]>([]);
	let copiedLink = $state('');
	let storageWorks = $state(true);
	let selectedShapeType = $state<ExplorerChartType | null>(null);

	const ledgers = $derived<RegistryLedger[]>(flattenRegistry(registry));
	const selectedPublished = $derived(selected.filter((name) => published.includes(name)));
	const columns = $derived(showAnswerColumns && result !== null && 'columns' in result ? result.columns : ledgerColumns);
	const columnLabel = $derived(showAnswerColumns ? 'Answer columns' : 'Columns in the selected ledgers');
	const answerRows = $derived(result !== null && result.state === 'ok' ? (result.rows as Row[]) : []);
	const answerColumns = $derived(result !== null && result.state === 'ok' ? result.columns : []);
	const actionNotice = $derived([...linkNotices, keepNotice, copiedLink].filter(Boolean).join(' '));
	const shapeBounds = $derived({
		chartMinRows: config.chart_min_rows,
		rankMax: config.rank_max,
		fleetMinRows: data.console.fleet_min_rows,
		bandwidthMinKinds: data.console.bandwidth_min_kinds,
		seriesFloorShare: config.series_floor_share
	});
	const shapeChoices = $derived(
		result !== null && result.state === 'ok'
			? chooseExplorerShapes(result.columns, result.rows as Row[], shapeBounds).filter((shape) => shape.kind === 'chart')
			: []
	);

	const SAVED_KEY = 'yen-idhazh:data-explorer:saved';
	const HISTORY_KEY = 'yen-idhazh:data-explorer:history';

	function todayUtc(): DateStamp {
		const now = new Date(Date.now());
		return `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}-${String(now.getUTCDate()).padStart(2, '0')}`;
	}
	function addDays(day: DateStamp, delta: number): DateStamp {
		const d = new Date(`${day}T00:00:00Z`);
		d.setUTCDate(d.getUTCDate() + delta);
		return d.toISOString().slice(0, 10);
	}
	function minReachDay(): DateStamp {
		return addDays(todayUtc(), 1 - config.reach_days);
	}
	function setSpan(from: DateStamp, to: DateStamp) {
		const min = minReachDay();
		const max = todayUtc();
		const clampedTo = to > max ? max : to < min ? min : to;
		const clampedFrom = from < min ? min : from > clampedTo ? clampedTo : from;
		fromDay = clampedFrom;
		toDay = clampedTo;
		windowDays = spanDays();
		void updateCostAndColumns();
	}
	function spanDays(): number {
		if (!fromDay || !toDay) return windowDays;
		return Math.round((Date.parse(`${toDay}T00:00:00Z`) - Date.parse(`${fromDay}T00:00:00Z`)) / 86_400_000) + 1;
	}
	function span(): { from: DateStamp; to: DateStamp } {
		return { from: fromDay, to: toDay };
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
		const days = presets.includes(example.days) ? example.days : windowDays;
		windowDays = days;
		toDay = todayUtc();
		fromDay = addDays(toDay, 1 - days);
		sql = example.sql;
		showAnswerColumns = false;
		void updateCostAndColumns();
	}
	function pickSaved(question: KeptQuestion) {
		selected = question.ledgers.filter((name): name is LedgerName => ledgers.some((ledger) => ledger.name === name));
		if (question.from !== undefined && question.end !== undefined) setSpan(question.from, question.end);
		else setWindow(presets.includes(question.days) ? question.days : windowDays);
		sql = question.statement;
		showAnswerColumns = false;
		void updateCostAndColumns();
	}
	function pickRun(run: RecentRun) {
		selected = run.ledgers.filter((name): name is LedgerName => ledgers.some((ledger) => ledger.name === name));
		if (run.from !== undefined && run.end !== undefined) setSpan(run.from, run.end);
		else setWindow(presets.includes(run.days) ? run.days : windowDays);
		sql = run.statement;
		showAnswerColumns = false;
		void updateCostAndColumns();
	}
	function setWindow(days: number) {
		windowDays = days;
		toDay = todayUtc();
		fromDay = addDays(toDay, 1 - days);
		void updateCostAndColumns();
	}
	async function refreshRegistry() {
		refreshing = true;
		registryError = null;
		try {
			await startAfresh();
			heldBytes = 0;
			registry = await fetchRegistry();
			if (selected.length === 0) {
				const first = config.examples.find((example) => example.ledgers.every((ledger) => published.includes(ledger)));
				if (first !== undefined) {
					selected = first.ledgers.filter((name): name is LedgerName => ledgers.some((ledger) => ledger.name === name));
					setWindow(presets.includes(first.days) ? first.days : windowDays);
					sql = first.sql;
				}
			}
			await updateCostAndColumns();
		} catch (error) {
			registryError = error instanceof Error ? error.message : String(error);
		} finally {
			refreshing = false;
		}
	}

	function parseLedgerList(value: unknown): LedgerName[] | null {
		if (!Array.isArray(value)) return null;
		const allowed = new Set<string>(LEDGER_NAMES);
		const names: LedgerName[] = [];
		for (const item of value) {
			if (typeof item !== 'string' || !allowed.has(item)) return null;
			names.push(item as LedgerName);
		}
		return names;
	}

	function validStatement(value: unknown): string | null {
		return typeof value === 'string' && value.length <= config.query_max_chars ? value : null;
	}

	function validDays(value: unknown): number | null {
		return typeof value === 'number' && Number.isInteger(value) && presets.includes(value) ? value : null;
	}

	function validStoredDay(value: unknown): DateStamp | null {
		if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
		const min = minReachDay();
		const max = todayUtc();
		return value >= min && value <= max ? value : null;
	}

	function validName(value: unknown): string | null {
		return typeof value === 'string' && value.length > 0 && value.length <= config.save_name_max_chars ? value : null;
	}

	function validStoredSaved(value: unknown): KeptQuestion | null {
		if (value === null || typeof value !== 'object') return null;
		const raw = value as Record<string, unknown>;
		const ledgers = parseLedgerList(raw.ledgers);
		const days = validDays(raw.days);
		const statement = validStatement(raw.statement);
		const name = validName(raw.name);
		if (ledgers === null || days === null || statement === null || name === null || typeof raw.id !== 'string' || typeof raw.updatedAt !== 'string') return null;
		const from = validStoredDay(raw.from);
		const end = validStoredDay(raw.end);
		if ((raw.from !== undefined || raw.end !== undefined) && (from === null || end === null || from > end)) return null;
		return { id: raw.id, name, statement, ledgers, days, ...(from !== null && end !== null ? { from, end } : {}), updatedAt: raw.updatedAt };
	}

	function validStoredRun(value: unknown): RecentRun | null {
		if (value === null || typeof value !== 'object') return null;
		const raw = value as Record<string, unknown>;
		const ledgers = parseLedgerList(raw.ledgers);
		const days = validDays(raw.days);
		const statement = validStatement(raw.statement);
		if (ledgers === null || days === null || statement === null || typeof raw.id !== 'string' || typeof raw.askedAt !== 'string' || typeof raw.rows !== 'number' || typeof raw.ms !== 'number') return null;
		const from = validStoredDay(raw.from);
		const end = validStoredDay(raw.end);
		if ((raw.from !== undefined || raw.end !== undefined) && (from === null || end === null || from > end)) return null;
		return { id: raw.id, statement, ledgers, days, ...(from !== null && end !== null ? { from, end } : {}), rows: raw.rows, ms: raw.ms, askedAt: raw.askedAt };
	}

	function readStored<T>(key: string, keep: (value: unknown) => T | null): T[] {
		try {
			const raw = localStorage.getItem(key);
			if (raw === null) return [];
			const parsed = JSON.parse(raw);
			if (!Array.isArray(parsed)) {
				console.info(`Data explorer storage ${key} was not a list and was dropped.`);
				return [];
			}
			const kept: T[] = [];
			for (const entry of parsed) {
				const item = keep(entry);
				if (item === null) console.info(`Data explorer storage ${key} entry was invalid and was dropped.`);
				else kept.push(item);
			}
			return kept;
		} catch {
			storageWorks = false;
			return [];
		}
	}

	function writeStored<T>(key: string, value: readonly T[]) {
		try {
			localStorage.setItem(key, JSON.stringify(value));
			storageWorks = true;
		} catch {
			storageWorks = false;
		}
	}

	async function replaceAddress(): Promise<boolean> {
		const address = await explorerAddress({
			basePath: location.pathname,
			ledgers: selected,
			days: windowDays,
			statement: sql,
			maxBytes: 8192,
			from: presets.includes(spanDays()) && toDay === todayUtc() ? undefined : fromDay,
			end: presets.includes(spanDays()) && toDay === todayUtc() ? undefined : toDay
		});
		history.replaceState(history.state, '', `${address.href}${location.hash}`);
		linkNotices = [...address.notices];
		return address.linkedStatement;
	}

	async function copyLink() {
		await replaceAddress();
		try {
			await navigator.clipboard.writeText(location.href);
			copiedLink = 'Copied the link. Opening it fills the editor and runs nothing.';
		} catch {
			copiedLink = 'This browser did not let the page write to the clipboard.';
		}
	}

	async function copyQuestion() {
		try {
			await navigator.clipboard.writeText(sql);
			copiedLink = 'Copied the question.';
		} catch {
			copiedLink = 'This browser did not let the page write to the clipboard.';
		}
	}

	function saveQuestion(name: string) {
		const next: KeptQuestion = {
			id: `${name.trim().toLowerCase()}:${sql}`,
			name: name.trim(),
			statement: sql,
			ledgers: selected,
			days: windowDays,
			from: fromDay,
			end: toDay,
			updatedAt: new Date(Date.now()).toISOString()
		};
		const kept = keepSavedQuestion(savedQuestions, next, config.saved_max);
		savedQuestions = [...kept.items];
		keepNotice = kept.notice ?? `Saved "${next.name}".`;
		writeStored(SAVED_KEY, savedQuestions);
		void replaceAddress();
	}

	function forget(question: KeptQuestion) {
		savedQuestions = [...forgetSavedQuestion(savedQuestions, question.id)];
		writeStored(SAVED_KEY, savedQuestions);
	}

	async function updateCostAndColumns() {
		if (!ready) return;
		const picked = selectedPublished;
		if (picked.length === 0) {
			cost = { files: 0, bytes: 0, unpackedDays: [], siteFrom: null, through: {} };
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
		await replaceAddress();
		const nextSpan = span();
		runSpan = nextSpan;
		lastRead = null;
		const started = performance.now();
		try {
			const answer = await ask({ ledgers: selected, from: nextSpan.from, to: nextSpan.to, sql, maxChars: config.query_max_chars, maxRows: config.max_rows, maxFetchBytes: config.max_fetch_bytes });
			lastMs = Math.round(performance.now() - started);
			result = answer;
			selectedShapeType = null;
			showAnswerColumns = answer.state === 'ok' || answer.state === 'quiet';
			heldBytes = pageHeldBytes();
			if ((answer.state === 'ok' || answer.state === 'quiet') && 'read' in answer) {
				lastMs = answer.read.ms;
				lastRead = answer.read;
			}
			const rows = answer.state === 'ok' ? answer.rows.length : 0;
			const nextRun: RecentRun = {
				id: new Date(Date.now()).toISOString(),
				statement: sql,
				ledgers: selected,
				days: windowDays,
				from: fromDay,
				end: toDay,
				rows,
				ms: lastMs ?? Math.round(performance.now() - started),
				askedAt: new Date(Date.now()).toISOString()
			};
			recentRuns = [...keepRecentRun(recentRuns, nextRun, config.history_max)];
			writeStored(HISTORY_KEY, recentRuns);
		} finally {
			running = false;
		}
	}

	onMount(() => {
		ready = true;
		setWindow(data.console.default_window_days);
		const query = matchMedia(`(min-width: ${data.frame.breakpoints_px[1]}px)`);
		const sync = () => (wide = query.matches);
		sync();
		query.addEventListener('change', sync);
		void (async () => {
			savedQuestions = readStored<KeptQuestion>(SAVED_KEY, validStoredSaved);
			recentRuns = readStored<RecentRun>(HISTORY_KEY, validStoredRun);
			if (location.search) {
				const parsed = await parseExplorerAddress(location.search, { ledgerNames: LEDGER_NAMES, windowPresets: presets, defaultDays: data.console.default_window_days, today: todayUtc(), reachDays: config.reach_days });
				if (parsed.ledgers.length > 0) selected = [...parsed.ledgers];
				if (parsed.from !== null && parsed.end !== null) setSpan(parsed.from, parsed.end);
				else setWindow(parsed.days);
				sql = parsed.statement;
				linkNotices = [...parsed.notices, ...(parsed.statement ? ['This question came from a link. Read it before you press Run.'] : [])];
			} else if (recentRuns[0] !== undefined) {
				selected = [...recentRuns[0].ledgers];
				if (recentRuns[0].from !== undefined && recentRuns[0].end !== undefined) setSpan(recentRuns[0].from, recentRuns[0].end);
				else setWindow(recentRuns[0].days);
				sql = recentRuns[0].statement;
			}
			await refreshRegistry();
		})();
		return () => query.removeEventListener('change', sync);
	});
</script>

{#snippet questionActions()}
	<button type="button" class="panel-button" onclick={copyLink}><Icon id="share-link" /> Copy link</button>
{/snippet}

<Panel id="data-explorer-ask" title="Your question" note={`One read-only DuckDB statement at a time, up to ${config.query_max_chars} characters.`} actions={questionActions}>
	<div class="question-panel" style={`--rail:${config.rail_rem}rem;--idle-height:${data.console.chart_height}px`}>
		<div class="workbench-toolbar" data-workbench-region="toolbar">
			<WindowControl
				days={windowDays}
				presets={presets}
				busy={costing || running}
				ready={ready}
				onChange={setWindow}
			/>
			<ActionLine files={cost.files} bytes={cost.bytes} {heldBytes} read={lastRead} busy={running || costing} disabled={selected.length === 0 || sql.trim() === ''} notice={actionNotice} from={fromDay} to={toDay} minDay={minReachDay()} maxDay={todayUtc()} saveName={suggestedSaveName(sql, config.save_name_max_chars)} saveNameMaxChars={config.save_name_max_chars} canSave={storageWorks && sql.trim() !== ''} canCopyQuestion={linkNotices.includes(LINK_TOO_LONG_NOTICE)} onRun={run} onSave={saveQuestion} onCopyQuestion={copyQuestion} onDates={setSpan} />
		</div>
		<p class="state">Need help with the syntax? <a href={`${data.docsBase}/blob/main/docs/how-to/query-a-ledger-from-the-console.md`}><Icon id="docs" /> Read the Data explorer how-to.</a></p>
		<div data-workbench-region="questions">
			<QuestionStrip examples={config.examples} {published} saved={savedQuestions} shown={config.strip_shown} onPick={pick} onPickSaved={pickSaved} onForget={forget} />
		</div>
		{#if keepNotice}<p class="state">{keepNotice}</p>{/if}
		{#if !storageWorks}<p class="state warn">This browser is not letting the page keep anything, so Save and the history are off.</p>{/if}
		<div class="question-grid" class:wide>
			<div data-workbench-region="ledgers">
				<LedgerList ledgers={ledgers} selected={selected} {published} {filter} onToggle={toggle} onFilter={(value) => (filter = value)} onRefresh={refreshRegistry} {refreshing} />
			</div>
			<div class="editor-stack">
				{#if registryError}<p class="state warn">{registryError}</p>{/if}
				<div data-workbench-region="editor">
					<QueryEditor value={sql} maxChars={config.query_max_chars} minLines={config.editor_lines_shown[0]} maxLines={config.editor_lines_shown[1]} counterFromShare={config.counter_from_share} onInput={(value) => (sql = value)} onRun={run} />
				</div>
				<HistoryList runs={recentRuns} onPick={pickRun} />
			</div>
			<div data-workbench-region="columns">
				<ColumnList columns={columns} label={columnLabel} />
			</div>
		</div>
	</div>
</Panel>

{#snippet answerActions()}
	{#if result !== null && result.state === 'ok'}
		<CopyAnswer columns={answerColumns} rows={orderedRows.length > 0 ? orderedRows : answerRows} />
	{/if}
{/snippet}

{#snippet shapeActions()}
	{#if shapeChoices.length > 1}
		<fieldset class="shape-actions">
			<legend>Draw it as</legend>
			<ChoiceTiles
				name="explorer-shape"
				items={shapeChoices.map((shape) => ({ value: shape.type, shown: shape.option, spoken: shape.option, icon: shape.icon }))}
				selected={selectedShapeType ?? shapeChoices[0].type}
				tileAttribute="data-shape-choice"
				onChange={(value) => (selectedShapeType = value)}
			/>
		</fieldset>
	{/if}
{/snippet}

<Panel id="data-explorer-rows" title="The answer" wide actions={answerActions}>
	{#if running}
		<div class="answer-state shimmer" data-state="loading"></div>
	{:else if result === null}
		<div class="answer-state" data-explorer-idle>{explorerIdleSentence()}</div>
	{:else if result.state === 'ok'}
			<div class="answer-note">
				{#if runSpan}Read from {spanDays()} UTC days, {dayMonth(runSpan.from)} to {shortDate(runSpan.to)}.{/if}
				{#if result.siteFrom !== null} Days before {shortDate(result.siteFrom)} are not on this site.{/if}
			</div>
		<AnswerTable columns={result.columns} rows={result.rows as Row[]} capped={result.capped} maxRows={config.max_rows} pageSize={config.row_page} tableMaxVh={config.answer_svh} cellMaxCh={config.cell_max_ch} barSpreadShare={config.bar_spread_share} onOrderChange={(rows) => (orderedRows = rows)} />
		{:else if result.state === 'quiet'}
			<div class="answer-state" data-state="quiet">{explorerQuietSentence()}{#if result.siteFrom !== null} Days before {shortDate(result.siteFrom)} are not on this site.{/if}</div>
	{:else if result.state === 'missing'}
		<div class="answer-state" data-state="missing">{explorerMissingSentence(result.ledger, published.includes(result.ledger))}</div>
	{:else if result.state === 'unreachable'}
		<div class="answer-state warn" data-state="unreachable">{explorerUnreachableSentence(result.ledger, result.at, result.fault)}</div>
	{:else if result.state === 'refused'}
		<div class="answer-state" data-state="refused">{refusedSentence(result.because)}{#if result.because.kind === 'engine-error'}<pre>{result.because.message}</pre>{/if}</div>
	{/if}
</Panel>

<Panel id="data-explorer-shape" title="The answer, drawn" wide actions={shapeActions}>
	{#if running}
		<div class="answer-state shimmer" data-state="loading"></div>
	{:else if result === null}
		<div class="answer-state" data-explorer-idle>If the answer holds a number, it is drawn here.</div>
	{:else if result.state === 'ok'}
		<ShapePanel columns={result.columns} rows={result.rows as Row[]} bounds={shapeBounds} height={data.console.chart_height} selectedType={selectedShapeType} />
	{:else if result.state === 'quiet'}
		<div class="answer-state" data-state="quiet">No rows, so nothing to draw.</div>
	{:else if result.state === 'refused'}
		<div class="answer-state" data-state="refused">The question did not run, so nothing to draw.</div>
	{:else}
		<div class="answer-state" data-state={result.state}>The answer did not arrive, so nothing to draw.</div>
	{/if}
</Panel>

<style>
	.question-panel { display: grid; gap: var(--space-4); }
	.workbench-toolbar {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		align-items: stretch;
		gap: var(--space-3);
		padding: var(--space-2);
		border: 1px solid var(--item-edge);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
	}
	.question-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-4); }
	.editor-stack { display: grid; gap: var(--space-4); align-content: start; }
	.state, .answer-note { margin: 0; color: var(--color-text-secondary); }
	.warn { color: var(--band-low); }
	.answer-state { min-block-size: var(--idle-height); display: grid; place-items: center; padding: var(--space-6); color: var(--color-text-secondary); background: var(--tint-neutral); border: 1px solid var(--color-rule); border-radius: var(--radius-md); }
	.answer-state pre { max-inline-size: 100%; overflow-x: auto; white-space: pre; font-family: var(--font-data); color: var(--code-string); }
	.shimmer { background: linear-gradient(90deg, var(--color-surface) 0%, var(--color-surface-raised) 50%, var(--color-surface) 100%); }
	.question-grid.wide { grid-template-columns: minmax(12rem, var(--rail)) minmax(0, 1fr) minmax(12rem, var(--rail)); }
	.panel-button { min-block-size: 2.75rem; border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface); color: var(--color-text); padding-inline: var(--space-3); font-weight: 600; }
	.shape-actions { border: 0; margin: 0; padding: 0; display: grid; gap: var(--space-1); }
	.shape-actions legend { color: var(--color-text-tertiary); font-size: var(--text-xs); }
	@media (max-width: 1023px) {
		.workbench-toolbar {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
