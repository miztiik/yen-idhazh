
<script lang="ts">
	import { onMount } from 'svelte';
	import { ask, askCost, pageHeldBytes, startAfresh, type AskResult, type Column, type DateStamp, type FetchCost, type LedgerName, type Row, type SpanCost, type SpanGap } from '$lib/data/ledger';
	import Panel from '$lib/components/Panel.svelte';
	import ChoiceTiles from '$lib/components/ChoiceTiles.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import Notice from '$lib/components/Notice.svelte';
	import { megabytes } from '$lib/assist/session';
	import { explorerIdleSentence, explorerMissingSentence, explorerQuietSentence, explorerUnreachableSentence, refusedSentence } from '$lib/console/waiting';
	import { shortDate, dayMonth } from '$lib/format';
	import QuestionStrip from '$lib/console/explorer/QuestionStrip.svelte';
	import LedgerList from '$lib/console/explorer/LedgerList.svelte';
	import ColumnList from '$lib/console/explorer/ColumnList.svelte';
	import QueryEditor from '$lib/console/explorer/QueryEditor.svelte';
	import RunStatus from '$lib/console/explorer/RunStatus.svelte';
	import AnswerTable from '$lib/console/explorer/AnswerTable.svelte';
	import CopyAnswer from '$lib/console/explorer/CopyAnswer.svelte';
	import HistoryList from '$lib/console/explorer/HistoryList.svelte';
	import ShapePanel from '$lib/console/explorer/ShapePanel.svelte';
	import { chooseExplorerShapes, type ExplorerChartType } from '$lib/console/explorer/shape';
	import { gapLines } from '$lib/console/explorer/gaps';
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
	let initializing = $state(true);
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
	let readoutBand = $state(0);
	let savedQuestions = $state<KeptQuestion[]>([]);
	let recentRuns = $state<RecentRun[]>([]);
	let keepNotice = $state<string | null>(null);
	let linkNotices = $state<string[]>([]);
	let copiedLink = $state('');
	let storageWorks = $state(true);
	let selectedShapeType = $state<ExplorerChartType | null>(null);
	let saving = $state(false);
	let draftName = $state('');

	const ledgers = $derived<RegistryLedger[]>(flattenRegistry(registry));
	const selectedPublished = $derived(selected.filter((name) => published.includes(name)));
	const columns = $derived(showAnswerColumns && result !== null && 'columns' in result ? result.columns : ledgerColumns);
	const columnLabel = $derived(showAnswerColumns ? 'Answer columns' : 'Ledger columns');
	const answerRows = $derived(result !== null && result.state === 'ok' ? (result.rows as Row[]) : []);
	const answerColumns = $derived(result !== null && result.state === 'ok' ? result.columns : []);
	const noticeText = $derived([keepNotice, copiedLink, !storageWorks ? 'This browser keeps nothing.' : ''].filter(Boolean).join(' '));
	const persistentNotice = $derived(!storageWorks);
	const readoutLines = $derived(config.readout_lines[readoutBand] ?? config.readout_lines[0]);
	const editorLines = $derived(config.editor_lines_shown[wide ? 1 : 0]);
	const statusText = $derived(`${statusLine()} This page holds ${size(heldBytes)} of fetched files; a reload empties it.`);
	const statusTone = $derived(result?.state === 'unreachable' ? 'warn' : 'neutral');
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
	function changeFrom(input: HTMLInputElement) {
		const next = input.value > toDay ? toDay : input.value;
		input.value = next;
		setSpan(next, toDay);
	}
	function changeTo(input: HTMLInputElement) {
		const next = input.value < fromDay ? fromDay : input.value;
		input.value = next;
		setSpan(fromDay, next);
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

	function plural(count: number, noun: string): string {
		return `${count} ${noun}${count === 1 ? '' : 's'}`;
	}

	function size(bytes: number): string {
		if (bytes > 0 && bytes < 102_400) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
		return `${megabytes(bytes)} MB`;
	}

	function elapsed(ms: number | null): string {
		if (ms === null) return '0 ms';
		return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
	}

	function emptyLedgerLines(): string {
		const lines = selected
			.map((ledger) => ({ ledger, through: cost.through[ledger] }))
			.filter((entry): entry is { ledger: LedgerName; through: string } => entry.through !== undefined && fromDay !== '' && entry.through < fromDay)
			.map((entry) => `Nothing in ${entry.ledger} after ${shortDate(entry.through)}.`);
		return lines.join(' ');
	}

	function statusLine(): string {
		if (keepNotice !== null) return keepNotice;
		if (linkNotices.length > 0) return linkNotices.join(' ');
		if (running) {
			return lastRead === null ? `Fetching ${plural(cost.files, 'file')}, ${size(cost.bytes)}.` : 'Running the question.';
		}
		if (costing) return 'Choosing a ledger fetches one day of it to list its columns.';
		if (result?.state === 'ok' && lastRead !== null) {
			return `Answered in ${elapsed(lastMs)}. Fetched ${plural(lastRead.files, 'file')}, ${size(lastRead.bytes)}; ${lastRead.alreadyHeld} more were already in this page.`;
		}
		if (result?.state === 'quiet' && lastRead !== null) {
			return `Ran in ${elapsed(lastMs)} and matched no rows. Fetched ${plural(lastRead.files, 'file')}, ${size(lastRead.bytes)}.`;
		}
		if (result?.state === 'refused') return 'Did not run. The reason is where the answer would be.';
		if (result?.state === 'missing') return published.includes(result.ledger) ? `Did not run. ${result.ledger} is not on this site yet.` : `Did not run. ${result.ledger} is not on this site yet.`;
		if (result?.state === 'unreachable') return result.fault === 'engine' ? 'Did not run. The query engine did not start.' : 'Did not run. The ledger files could not be fetched.';
		return `Run reads ${plural(cost.files, 'file')}, ${size(cost.bytes)} from ${plural(selected.length, 'ledger')} over ${plural(spanDays(), 'UTC day')}. ${lastMs === null ? 'It also starts the query engine. ' : ''}${emptyLedgerLines()}`;
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

	function startSaving() {
		draftName = suggestedSaveName(sql, config.save_name_max_chars);
		saving = true;
	}

	function keepDraft() {
		if (!draftName.trim()) return;
		saveQuestion(draftName);
		saving = false;
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
				// DESCRIBE answers one row per column of the ledger: its name and its type.
				if (answer.state === 'ok') {
					for (const row of answer.rows) {
						if (typeof row.column_name === 'string') described.push({ name: `${ledger}.${row.column_name}`, type: String(row.column_type ?? '') });
					}
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
		const sync = () => {
			wide = query.matches;
			const width = window.innerWidth;
			readoutBand = width < data.frame.breakpoints_px[0] ? 0 : width < data.frame.breakpoints_px[1] ? 1 : width < data.frame.breakpoints_px[2] ? 2 : 3;
		};
		sync();
		query.addEventListener('change', sync);
		addEventListener('resize', sync);
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
			initializing = false;
		})();
		return () => {
			query.removeEventListener('change', sync);
			removeEventListener('resize', sync);
		};
	});
</script>

<Notice text={noticeText} durationMs={config.notice_ms} persistent={persistentNotice} onClose={() => { copiedLink = ''; keepNotice = null; if (!storageWorks) storageWorks = true; }} />

<div class="workbench" style={`--rail:${config.rail_rem}rem;--idle-height:${data.console.chart_height}px;--answer-size:${config.answer_svh}svh`}>
<Panel id="data-explorer-ask" title="Your question">
	<div class="question-panel">
		<div class="workbench-toolbar" data-workbench-region="toolbar">
			<WindowControl
				days={windowDays}
				presets={presets}
				busy={false}
				ready={ready}
				onChange={setWindow}
			/>
			<div class="date-fields">
				<label>From (UTC)<input type="date" value={fromDay} min={minReachDay()} max={toDay < todayUtc() ? toDay : todayUtc()} oninput={(event) => changeFrom(event.currentTarget)} onchange={(event) => changeFrom(event.currentTarget)} /></label>
				<label>To (UTC)<input type="date" value={toDay} min={fromDay > minReachDay() ? fromDay : minReachDay()} max={todayUtc()} oninput={(event) => changeTo(event.currentTarget)} onchange={(event) => changeTo(event.currentTarget)} /></label>
			</div>
			<button type="button" class="run-button" aria-label={running ? 'Running' : 'Run'} aria-keyshortcuts="Control+Enter Meta+Enter" disabled={initializing} aria-disabled={initializing || running || selected.length === 0 || sql.trim() === ''} aria-busy={running} onclick={() => { if (!initializing && !running && selected.length > 0 && sql.trim() !== '') void run(); }}>
				<Icon id="query-run" />
				<span class="run-words"><span class:hidden-word={running}>Run</span><span class:hidden-word={!running}>Running</span></span>
				<span class="run-shortcut">Ctrl+Enter</span>
			</button>
		</div>
		<div data-workbench-region="questions">
			<QuestionStrip examples={config.examples} {published} saved={savedQuestions} shown={config.strip_shown} onPick={pick} onPickSaved={pickSaved} onForget={forget} />
			<div class="question-links">
				<HistoryList runs={recentRuns} onPick={pickRun} />
				<a class="how-to" href={`${data.docsBase}/blob/main/docs/how-to/query-a-ledger-from-the-console.md`}><Icon id="docs" /> Read the Data explorer how-to</a>
			</div>
		</div>
		<div class="question-grid" class:wide>
			<div data-workbench-region="ledgers">
				<LedgerList ledgers={ledgers} selected={selected} {published} through={cost.through} spanFrom={fromDay} {filter} onToggle={toggle} onFilter={(value) => (filter = value)} onRefresh={refreshRegistry} {refreshing} />
			</div>
			<div class="editor-stack">
				{#if registryError}<p class="state warn">{registryError}</p>{/if}
				<div data-workbench-region="editor">
					<div class="editor-head">
						<strong>DuckDB SQL</strong>
						<div class="editor-actions">
							{#if saving}
								<label>Name <input bind:value={draftName} maxlength={config.save_name_max_chars} /></label>
								<button type="button" onclick={keepDraft} disabled={!draftName.trim()}><Icon id="saved" /> Keep</button>
								<button type="button" onclick={() => (saving = false)}>Cancel</button>
							{:else}
								<button type="button" onclick={startSaving} disabled={!storageWorks || sql.trim() === ''}><Icon id="saved" /> Save</button>
								<button type="button" onclick={copyLink}><Icon id="share-link" /> Copy link</button>
								{#if linkNotices.includes(LINK_TOO_LONG_NOTICE)}<button type="button" onclick={copyQuestion}><Icon id="copy" /> Copy question</button>{/if}
							{/if}
						</div>
					</div>
					<QueryEditor value={sql} maxChars={config.query_max_chars} lines={editorLines} counterFromShare={config.counter_from_share} onInput={(value) => { sql = value; if (linkNotices.some((notice) => notice.includes('came from a link'))) linkNotices = []; }} onRun={run} />
				</div>
				<RunStatus text={statusText} lines={readoutLines} tone={statusTone} href="#data-explorer-rows" files={lastRead?.files ?? cost.files} bytes={lastRead?.bytes ?? cost.bytes} {heldBytes} />
			</div>
			<div data-workbench-region="columns">
				<ColumnList columns={columns} label={columnLabel} />
			</div>
		</div>
	</div>
</Panel>

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

{#snippet gapNotes(gaps: readonly SpanGap[])}
	{#each gapLines(gaps) as line (`${line.ledger} ${line.kind}`)}
		<p class="gap-note" data-explorer-gap={line.kind} data-ledger={line.ledger}>{line.text}</p>
	{/each}
{/snippet}

<Panel id="data-explorer-rows" title="The answer" wide>
	<div class="answer-region" data-workbench-region="answer">
		<div class="region-bar">
			{#if result !== null && result.state === 'ok'}
				<CopyAnswer columns={answerColumns} rows={orderedRows.length > 0 ? orderedRows : answerRows} />
			{/if}
		</div>
	{#key running ? 'loading' : result?.state ?? 'idle'}
		{#if running}
			<div class="answer-state shimmer" data-state="loading"></div>
		{:else if result === null}
			<div class="answer-state" data-explorer-idle>{explorerIdleSentence()}</div>
		{:else if result.state === 'ok'}
				<div class="answer-note">
					{#if runSpan}Read from {spanDays()} UTC days, {dayMonth(runSpan.from)} to {shortDate(runSpan.to)}.{/if}
					{#if result.siteFrom !== null} Days before {shortDate(result.siteFrom)} are not on this site.{/if}
					{@render gapNotes(result.gaps)}
				</div>
			<AnswerTable columns={result.columns} rows={result.rows as Row[]} capped={result.capped} maxRows={config.max_rows} pageSize={config.row_page} cellMaxCh={config.cell_max_ch} barSpreadShare={config.bar_spread_share} onOrderChange={(rows) => (orderedRows = rows)} />
			{:else if result.state === 'quiet'}
				<div class="answer-state" data-state="quiet">{explorerQuietSentence()}{#if result.siteFrom !== null} Days before {shortDate(result.siteFrom)} are not on this site.{/if}{@render gapNotes(result.gaps)}</div>
		{:else if result.state === 'missing'}
			<div class="answer-state" data-state="missing">{explorerMissingSentence(result.ledger, published.includes(result.ledger))}</div>
		{:else if result.state === 'unreachable'}
			<div class="answer-state warn" data-state="unreachable">{explorerUnreachableSentence(result.ledger, result.at, result.fault)}</div>
		{:else if result.state === 'refused'}
			<div class="answer-state" data-state="refused">{refusedSentence(result.because)}{#if result.because.kind === 'engine-error'}<pre>{result.because.message}</pre>{/if}</div>
		{/if}
	{/key}
	</div>
</Panel>

<Panel id="data-explorer-shape" title="The answer, drawn" wide>
	<div class="chart-region" data-workbench-region="chart">
		<div class="region-bar">
			{@render shapeActions()}
		</div>
	{#key running ? 'loading' : result?.state ?? 'idle'}
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
			<div class="answer-state" class:warn={result.state === 'unreachable'} data-state={result.state}>{result.state === 'missing' ? 'Part of the data is not on this site, so nothing to draw.' : result.state === 'unreachable' ? 'The data could not be fetched, so nothing to draw.' : 'The answer did not arrive, so nothing to draw.'}</div>
		{/if}
	{/key}
	</div>
</Panel>
</div>

<style>
	.workbench {
		overflow: clip;
		border: 1px solid var(--item-edge);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
		box-shadow: var(--shadow-sm);
	}

	.question-panel { display: grid; }
	.workbench-toolbar {
		display: grid;
		grid-template-columns: auto minmax(18rem, 1fr) auto;
		align-items: center;
		gap: var(--space-2);
		min-block-size: calc(var(--workbench-control) + 2 * var(--space-1));
		padding: var(--space-1) var(--space-3);
		border-block-end: 1px solid var(--color-rule);
	}

	.date-fields {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
		align-items: end;
	}

	.date-fields label,
	.editor-actions label {
		display: grid;
		gap: var(--space-1);
		color: var(--color-text-tertiary);
		font-size: var(--text-xs);
		font-weight: 600;
		letter-spacing: var(--tracking-label);
		text-transform: uppercase;
	}

	input,
	button,
	.how-to,
	.run-button {
		min-block-size: var(--workbench-control);
		border: 1px solid var(--color-rule-strong);
		border-radius: var(--radius-md);
		background: var(--color-surface);
		color: var(--color-text);
		padding-inline: var(--space-3);
		font: inherit;
	}

	.run-button {
		display: grid;
		grid-template-columns: auto auto auto;
		gap: var(--space-2);
		align-items: center;
		border-color: var(--color-accent);
		background: var(--color-accent);
		color: var(--color-on-accent);
		font-weight: 600;
	}

	.run-button[aria-disabled='true'] {
		opacity: 0.75;
	}

	.run-shortcut {
		font-family: var(--font-data);
		font-size: var(--text-xs);
		font-weight: 400;
	}

	.run-words {
		display: grid;
	}

	.run-words > span {
		grid-area: 1 / 1;
	}

	.hidden-word {
		opacity: 0;
	}

	[data-workbench-region='questions'] {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2);
		min-block-size: calc(var(--workbench-control) + 2 * var(--space-1));
		padding-inline: var(--space-3);
		border-block-end: 1px solid var(--color-rule);
	}

	.question-links {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}

	.how-to {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		text-decoration: none;
		font-size: var(--text-sm);
	}

	.question-grid { display: grid; grid-template-columns: minmax(0, 1fr); }
	.editor-stack { display: grid; align-content: start; }
	.state, .answer-note { margin: 0; color: var(--color-text-secondary); }
	.gap-note { margin: var(--space-1) 0 0; }
	.warn { color: var(--band-low); }
	.answer-state { min-block-size: 0; block-size: 100%; display: grid; place-items: center; padding: var(--space-6); color: var(--color-text-secondary); background: var(--tint-neutral); }
	.answer-state pre { max-inline-size: 100%; overflow-x: auto; white-space: pre; font-family: var(--font-data); color: var(--code-string); }
	.shimmer { background: linear-gradient(90deg, var(--color-surface) 0%, var(--color-surface-raised) 50%, var(--color-surface) 100%); }
	.question-grid.wide { grid-template-columns: minmax(12rem, var(--rail)) minmax(0, 1fr) minmax(12rem, var(--rail)); }
	.question-grid.wide > [data-workbench-region],
	.editor-stack {
		min-block-size: 100%;
	}

	[data-workbench-region='ledgers'],
	[data-workbench-region='columns'] {
		block-size: calc(var(--workbench-control) + var(--workbench-field-leading) * 10 + 2 * var(--space-3));
		min-block-size: 0;
		overflow: auto;
		border-inline-end: 1px solid var(--color-rule);
		padding: var(--space-3);
	}

	[data-workbench-region='columns'] {
		border-inline: 1px solid var(--color-rule) 0;
	}

	[data-workbench-region='editor'] {
		padding: var(--space-3);
	}

	.editor-head,
	.region-bar {
		min-block-size: var(--workbench-control);
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2);
		color: var(--color-text-tertiary);
		font-size: var(--text-xs);
		font-weight: 600;
		letter-spacing: var(--tracking-label);
		text-transform: uppercase;
	}

	.editor-actions {
		display: flex;
		align-items: end;
		gap: var(--space-2);
	}

	.editor-actions button,
	.region-bar :global(button) {
		font-size: var(--text-sm);
		font-weight: 400;
		letter-spacing: normal;
		text-transform: none;
	}

	.answer-region {
		block-size: var(--answer-size);
		display: grid;
		grid-template-rows: var(--workbench-control) auto minmax(0, 1fr);
	}

	.chart-region {
		block-size: calc(var(--workbench-control) + var(--idle-height) + 4rem);
		display: grid;
		grid-template-rows: var(--workbench-control) minmax(var(--idle-height), auto);
		overflow: auto;
	}

	.shape-actions { border: 0; margin: 0; padding: 0; display: grid; gap: var(--space-1); }
	.shape-actions legend { color: var(--color-text-tertiary); font-size: var(--text-xs); }
	@media (max-width: 1023px) {
		.workbench-toolbar {
			grid-template-columns: minmax(0, 1fr);
		}
		[data-workbench-region='questions'] {
			flex-wrap: wrap;
		}
		.run-shortcut {
			display: none;
		}
		[data-workbench-region='ledgers'],
		[data-workbench-region='columns'] {
			border-inline: 0;
			border-block: 1px solid var(--color-rule);
		}
	}
</style>
