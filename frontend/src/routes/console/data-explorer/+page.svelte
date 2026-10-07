
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { ask, askColumns, askCost, startAfresh, type AskResult, type Column, type DateStamp, type FetchCost, type LedgerName, type Row, type SpanCost, type SpanGap } from '$lib/data/ledger';
	import Panel from '$lib/components/Panel.svelte';
	import ChoiceTiles from '$lib/components/ChoiceTiles.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import Notice from '$lib/components/Notice.svelte';
	import { explorerIdleSentence, explorerMissingSentence, explorerQuietSentence, explorerUnansweredNote, explorerUnreachableSentence, refusedSentence } from '$lib/console/waiting';
	import { shortDate } from '$lib/format';
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
	import { describeCutDays, describeDaysRead } from '$lib/console/explorer/days-read';
	import { gapLines } from '$lib/console/explorer/gaps';
	import { size, statusSentence } from '$lib/console/explorer/status';
	import { explorerAddress, parseExplorerAddress, LINK_TOO_LONG_NOTICE } from '$lib/console/explorer/address';
	import { keepRecentRun, keepSavedQuestion, forgetSavedQuestion, suggestedSaveName, type KeptQuestion, type RecentRun } from '$lib/console/explorer/keep';
	import { fetchRegistry, flattenRegistry, type LedgerRegistry, type RegistryLedger } from '$lib/console/explorer/registry';
	import type { ExplorerExample } from '$lib/server/config';
	import { isDay, LEDGER_NAMES, type CutDays, type UnansweredDays } from '$lib/data/slice-shapes';
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
	let cost = $state<SpanCost>({ files: 0, bytes: 0, unpackedDays: [], cut: [], through: {} });
	let lastMs = $state<number | null>(null);
	let lastRead = $state<FetchCost | null>(null);
	let result = $state<AskResult | null>(null);
	let orderedRows = $state<Row[]>([]);
	let ledgerColumns = $state<Column[]>([]);
	let runSpan = $state<{ from: DateStamp; to: DateStamp } | null>(null);
	let wide = $state(false);
	let ledgersOpen = $state(false);
	let columnsOpen = $state(false);
	let readoutBand = $state(0);
	let savedQuestions = $state<KeptQuestion[]>([]);
	let recentRuns = $state<RecentRun[]>([]);
	let keepNotice = $state<string | null>(null);
	let linkNotices = $state<string[]>([]);
	let copyNotice = $state('');
	let storageWorks = $state(true);
	let storageNoticeDismissed = $state(false);
	let selectedShapeType = $state<ExplorerChartType | null>(null);
	let activeResultTab = $state<'table' | 'chart'>('table');
	let saving = $state(false);
	let draftName = $state('');
	let nameField = $state<HTMLInputElement | null>(null);
	let saveButton = $state<HTMLButtonElement | null>(null);
	let answerOffscreen = $state(false);

	const ledgers = $derived<RegistryLedger[]>(flattenRegistry(registry));
	const selectedPublished = $derived(selected.filter((name) => published.includes(name)));
	const columnLabel = $derived('Ledger columns');
	const answerRows = $derived(result !== null && result.state === 'ok' ? (result.rows as Row[]) : []);
	const answerColumns = $derived(result !== null && result.state === 'ok' ? result.columns : []);
	const noticeText = $derived([keepNotice, copyNotice, !storageWorks && !storageNoticeDismissed ? 'This browser keeps nothing.' : ''].filter(Boolean).join(' '));
	const persistentNotice = $derived(!storageWorks && !storageNoticeDismissed);
	const readoutLines = $derived(config.readout_lines[readoutBand] ?? config.readout_lines[0]);
	const editorLines = $derived(config.editor_lines_shown[wide ? 1 : 0]);
	const statusText = $derived(statusLine());
	const statusTone = $derived(result?.state === 'unreachable' ? 'warn' : 'neutral');
	const answerLink = $derived(result !== null && !running && answerOffscreen ? '#data-explorer-rows' : '');
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

	function emptyLedgerLines(): string {
		const lines = selected
			.map((ledger) => ({ ledger, through: cost.through[ledger] }))
			.filter((entry): entry is { ledger: LedgerName; through: string } => entry.through !== undefined && fromDay !== '' && entry.through < fromDay)
			.map((entry) => `Nothing in ${entry.ledger} after ${shortDate(entry.through)}.`);
		return lines.join(' ');
	}

	function statusLine(): string {
		if (keepNotice !== null) return statusSentence({ state: 'notice', notice: keepNotice });
		if (linkNotices.length > 0) return statusSentence({ state: 'link', linkNotices });
		if (running) {
			return statusSentence(lastRead === null ? { state: 'running-fetch', files: cost.files, bytes: cost.bytes } : { state: 'running-query' });
		}
		if (costing) return statusSentence({ state: 'costing' });
		if (result?.state === 'ok' && lastRead !== null) {
			return statusSentence({ state: 'answered', ms: lastMs, read: lastRead });
		}
		if (result?.state === 'quiet' && lastRead !== null) {
			return statusSentence({ state: 'quiet', ms: lastMs, read: lastRead });
		}
		if (result?.state === 'refused') return statusSentence({ state: 'refused' });
		if (result?.state === 'missing') return statusSentence({ state: 'missing', ledger: result.ledger });
		if (result?.state === 'unreachable') return statusSentence({ state: result.fault === 'engine' ? 'unreachable-engine' : 'unreachable-files' });
		const empty = emptyLedgerLines();
		return `${statusSentence({ state: 'idle', files: cost.files, bytes: cost.bytes, ledgers: selected.length, days: spanDays(), firstRun: lastMs === null })}${empty ? ` ${empty}` : ''}`;
	}
	function siteFromText(): string {
		const span = runSpan;
		if (result === null || (result.state !== 'ok' && result.state !== 'quiet') || span === null) return '';
		return result.cut.map((one) => describeCutDays(one, span.to)).join(' ');
	}
	function selectResultTab(tab: 'table' | 'chart') {
		activeResultTab = tab;
	}
	function resultTabKey(event: KeyboardEvent) {
		if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
			event.preventDefault();
			activeResultTab = activeResultTab === 'table' ? 'chart' : 'table';
			void tick().then(() => document.getElementById(`explorer-tab-${activeResultTab}`)?.focus());
		}
	}
	function toggle(name: LedgerName) {
		selected = selected.includes(name) ? selected.filter((one) => one !== name) : [...selected, name];
		void updateCostAndColumns();
	}
	function pick(example: ExplorerExample) {
		selected = example.ledgers.filter((name): name is LedgerName => ledgers.some((ledger) => ledger.name === name));
		const days = presets.includes(example.days) ? example.days : windowDays;
		windowDays = days;
		toDay = todayUtc();
		fromDay = addDays(toDay, 1 - days);
		sql = example.sql;
		void updateCostAndColumns();
	}
	function pickSaved(question: KeptQuestion) {
		selected = question.ledgers.filter((name): name is LedgerName => ledgers.some((ledger) => ledger.name === name));
		if (question.from !== undefined && question.end !== undefined) setSpan(question.from, question.end);
		else setWindow(presets.includes(question.days) ? question.days : windowDays);
		sql = question.statement;
		void updateCostAndColumns();
	}
	function pickRun(run: RecentRun) {
		selected = run.ledgers.filter((name): name is LedgerName => ledgers.some((ledger) => ledger.name === name));
		if (run.from !== undefined && run.end !== undefined) setSpan(run.from, run.end);
		else setWindow(presets.includes(run.days) ? run.days : windowDays);
		sql = run.statement;
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
		if (!isDay(value)) return null;
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
			storageNoticeDismissed = false;
			return [];
		}
	}

	function writeStored<T>(key: string, value: readonly T[]) {
		try {
			localStorage.setItem(key, JSON.stringify(value));
			storageWorks = true;
			storageNoticeDismissed = false;
		} catch {
			storageWorks = false;
			storageNoticeDismissed = false;
		}
	}

	async function replaceAddress(): Promise<boolean> {
		const address = await explorerAddress({
			basePath: location.pathname,
			ledgers: selected,
			days: windowDays,
			statement: sql,
			maxBytes: config.link_max_bytes,
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
			copyNotice = 'Copied the link. Opening it fills the editor and runs nothing.';
		} catch {
			copyNotice = 'This browser did not let the page write to the clipboard.';
		}
	}

	async function copyQuestion() {
		try {
			await navigator.clipboard.writeText(sql);
			copyNotice = 'Copied the question.';
		} catch {
			copyNotice = 'This browser did not let the page write to the clipboard.';
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

	// Save hands focus to the name field with the suggestion selected, so typing replaces it;
	// Keep and Cancel hand it back to Save, so it never falls to the page.
	async function startSaving() {
		draftName = suggestedSaveName(sql, config.save_name_max_chars);
		saving = true;
		await tick();
		nameField?.focus();
		nameField?.select();
	}

	async function stopSaving() {
		saving = false;
		await tick();
		saveButton?.focus();
	}

	function keepDraft() {
		if (!draftName.trim()) return;
		saveQuestion(draftName);
		void stopSaving();
	}

	function forget(question: KeptQuestion) {
		savedQuestions = [...forgetSavedQuestion(savedQuestions, question.id)];
		writeStored(SAVED_KEY, savedQuestions);
	}

	async function updateCostAndColumns() {
		if (!ready) return;
		const picked = selectedPublished;
		if (picked.length === 0) {
			cost = { files: 0, bytes: 0, unpackedDays: [], cut: [], through: {} };
			ledgerColumns = [];
			return;
		}
		costing = true;
		try {
			const nextSpan = span();
			cost = await askCost(picked, nextSpan.from, nextSpan.to);
			const described: Column[] = [];
			for (const ledger of picked) {
				for (const column of await askColumns(ledger, config.max_fetch_bytes)) described.push({ name: `${ledger}.${column.name}`, type: column.type });
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
		lastRead = null;
		const started = performance.now();
		try {
			const answer = await ask({ ledgers: selected, from: nextSpan.from, to: nextSpan.to, sql, maxChars: config.query_max_chars, maxRows: config.max_rows, maxFetchBytes: config.max_fetch_bytes });
			lastMs = Math.round(performance.now() - started);
			// The window goes with its answer, so the lines under the answer change only on a run.
			runSpan = nextSpan;
			result = answer;
			selectedShapeType = null;
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
		let previousWide = query.matches;
		const sync = () => {
			wide = query.matches;
			if (wide !== previousWide) {
				ledgersOpen = wide;
				columnsOpen = wide;
				previousWide = wide;
			}
			const width = window.innerWidth;
			readoutBand = width < data.frame.breakpoints_px[0] ? 0 : width < data.frame.breakpoints_px[1] ? 1 : width < data.frame.breakpoints_px[2] ? 2 : 3;
		};
		sync();
		ledgersOpen = wide;
		columnsOpen = wide;
		query.addEventListener('change', sync);
		addEventListener('resize', sync);
		const answerRegion = document.querySelector('[data-workbench-region="answer"]');
		const answerObserver = answerRegion === null ? null : new IntersectionObserver(([entry]) => {
			answerOffscreen = !entry.isIntersecting && entry.boundingClientRect.top > 0;
		});
		if (answerRegion !== null) answerObserver?.observe(answerRegion);
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
			answerObserver?.disconnect();
		};
	});
</script>

<Notice text={noticeText} durationMs={config.notice_ms} persistent={persistentNotice} onClose={() => { copyNotice = ''; keepNotice = null; if (!storageWorks) storageNoticeDismissed = true; }} />

<div class="workbench" style={`--idle-height:${data.console.chart_height}px;--editor-lines:${editorLines};--readout-lines:${readoutLines}`}>
<Panel id="data-explorer-ask" title="Your question">
	<div class="question-panel">
		<div data-workbench-region="questions">
			<QuestionStrip examples={config.examples} {published} saved={savedQuestions} shown={config.strip_shown} onPick={pick} onPickSaved={pickSaved} onForget={forget} />
			<div class="question-links">
				<HistoryList runs={recentRuns} onPick={pickRun} />
				<a class="how-to" href={`${data.docsBase}/blob/main/docs/how-to/query-a-ledger-from-the-console.md`}><Icon id="docs" /> Read the Data explorer how-to</a>
			</div>
		</div>
		<div class="question-grid" class:wide>
			<details data-workbench-region="ledgers" class="rail-region" bind:open={ledgersOpen}>
				<summary>Ledgers: {selected.length}</summary>
				<LedgerList ledgers={ledgers} selected={selected} {published} through={cost.through} spanFrom={fromDay} {filter} onToggle={toggle} onFilter={(value) => (filter = value)} onRefresh={refreshRegistry} {refreshing} />
			</details>
			<div class="editor-stack">
				{#if registryError}<p class="state warn">{registryError}</p>{/if}
				<div data-workbench-region="editor">
					<div class="editor-head">
						<label for="explorer-sql"><Icon id="query-editor" /> DuckDB SQL</label>
						<WindowControl
							days={windowDays}
							presets={presets}
							busy={costing || running}
							ready={ready}
							onChange={setWindow}
						/>
						<div class="date-fields">
							<label>From (UTC)<input type="date" value={fromDay} min={minReachDay()} max={toDay < todayUtc() ? toDay : todayUtc()} oninput={(event) => changeFrom(event.currentTarget)} onchange={(event) => changeFrom(event.currentTarget)} /></label>
							<label>To (UTC)<input type="date" value={toDay} min={fromDay > minReachDay() ? fromDay : minReachDay()} max={todayUtc()} oninput={(event) => changeTo(event.currentTarget)} onchange={(event) => changeTo(event.currentTarget)} /></label>
						</div>
						<div class="editor-actions" data-explorer-actions>
							{#if saving}
								<label>Name <input bind:this={nameField} bind:value={draftName} maxlength={config.save_name_max_chars} /></label>
								<button type="button" onclick={keepDraft} disabled={!draftName.trim()}><Icon id="saved" /> Keep</button>
								<button type="button" onclick={stopSaving}>Cancel</button>
							{:else}
								<button type="button" bind:this={saveButton} onclick={startSaving} disabled={!storageWorks || sql.trim() === ''}><Icon id="saved" /> Save</button>
								<button type="button" onclick={copyLink}><Icon id="share-link" /> Copy link</button>
								{#if linkNotices.includes(LINK_TOO_LONG_NOTICE)}<button type="button" class="copy-question" onclick={copyQuestion}><Icon id="copy" /> Copy question</button>{/if}
							{/if}
							<!-- Last, so nothing that changes to its left moves it. -->
							<button type="button" class="run-button" aria-label={running ? 'Running' : 'Run'} aria-keyshortcuts="Control+Enter Meta+Enter" disabled={initializing} aria-disabled={initializing || running || selected.length === 0 || sql.trim() === ''} aria-busy={running} onclick={() => { if (!initializing && !running && selected.length > 0 && sql.trim() !== '') void run(); }}>
								<Icon id="query-run" />
								<span class="run-words"><span class:hidden-word={running}>Run</span><span class:hidden-word={!running}>Running</span></span>
								<span class="run-shortcut">Ctrl+Enter</span>
							</button>
						</div>
					</div>
					<QueryEditor value={sql} maxChars={config.query_max_chars} lines={editorLines} onInput={(value) => { sql = value; if (linkNotices.some((notice) => notice.includes('came from a link'))) linkNotices = []; }} onRun={run} />
				</div>
				<RunStatus text={statusText} lines={readoutLines} tone={statusTone} href={answerLink} files={lastRead?.files ?? cost.files} bytes={lastRead?.bytes ?? cost.bytes} />
			</div>
			<details data-workbench-region="columns" class="rail-region" bind:open={columnsOpen}>
				<summary>{columnLabel} ({ledgerColumns.length})</summary>
				<ColumnList columns={ledgerColumns} label={columnLabel} />
			</details>
		</div>
	</div>
</Panel>

{#snippet shapeActions()}
	{#if shapeChoices.length > 1}
		<fieldset class="shape-actions">
			<legend class="sr-only">Draw it as</legend>
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

<!-- Where an answer starts when its window began earlier: grey for each ledger whose earlier days
     are not on this site, amber for days the repository could not give it. -->
{#snippet startNotes(cut: readonly CutDays[], unanswered: readonly UnansweredDays[], lastDay: DateStamp)}
	{#each cut as one (one.ledger)}{' '}{describeCutDays(one, lastDay)}{/each}{#if unanswered.length > 0}{' '}<span class="warn" data-explorer-unanswered>{explorerUnansweredNote(unanswered)}</span>{/if}
{/snippet}

<div class="result-region" data-workbench-region="answer">
	<div class="result-tabs" role="tablist" aria-label="Answer view" tabindex="-1" onkeydown={resultTabKey}>
		<button id="explorer-tab-table" type="button" role="tab" aria-selected={activeResultTab === 'table'} aria-controls="data-explorer-rows" tabindex={activeResultTab === 'table' ? 0 : -1} onclick={() => selectResultTab('table')}>Table</button>
		<button id="explorer-tab-chart" type="button" role="tab" aria-selected={activeResultTab === 'chart'} aria-controls="data-explorer-shape" tabindex={activeResultTab === 'chart' ? 0 : -1} onclick={() => selectResultTab('chart')}>Chart</button>
		<div class="result-actions">
			{#if activeResultTab === 'table' && result !== null && result.state === 'ok'}
				<CopyAnswer columns={answerColumns} rows={orderedRows.length > 0 ? orderedRows : answerRows} onMessage={(text) => (copyNotice = text)} />
			{:else if activeResultTab === 'chart'}
				{@render shapeActions()}
			{/if}
		</div>
	</div>
	<div id="data-explorer-rows" data-console-panel-id="data-explorer-rows" role="tabpanel" aria-labelledby="explorer-tab-table" hidden={activeResultTab !== 'table'}>
		<h2 class="sr-only">The answer</h2>
		{#key running ? 'loading' : result?.state ?? 'idle'}
			{#if running}
				<div class="answer-state shimmer" data-state="loading"></div>
			{:else if result === null}
				<div class="answer-state" data-explorer-idle>{explorerIdleSentence()}</div>
			{:else if result.state === 'ok'}
				<AnswerTable columns={result.columns} rows={result.rows as Row[]} capped={result.capped} maxRows={config.max_rows} pageSize={config.row_page} cellMaxCh={config.cell_max_ch} barSpreadShare={config.bar_spread_share} spanText={runSpan ? describeDaysRead(result.readFrom, runSpan.to) : ''} siteFromText={siteFromText()} unansweredText={result.unanswered.length > 0 ? explorerUnansweredNote(result.unanswered) : ''} gapLines={gapLines(result.gaps)} onOrderChange={(rows) => (orderedRows = rows)} />
			{:else if result.state === 'quiet'}
				<div class="answer-state" data-state="quiet">{explorerQuietSentence()}{#if runSpan}{@render startNotes(result.cut, result.unanswered, runSpan.to)}{/if}{@render gapNotes(result.gaps)}</div>
			{:else if result.state === 'missing'}
				<div class="answer-state" data-state="missing">{explorerMissingSentence(result.ledger, published.includes(result.ledger))}</div>
			{:else if result.state === 'unreachable'}
				<div class="answer-state warn" data-state="unreachable">{explorerUnreachableSentence(result.ledger, result.at, result.fault)}</div>
			{:else if result.state === 'refused'}
				<div class="answer-state" data-state="refused">{refusedSentence(result.because)}{#if result.because.kind === 'engine-error'}<pre>{result.because.message}</pre>{/if}</div>
			{/if}
		{/key}
	</div>
	<div id="data-explorer-shape" data-console-panel-id="data-explorer-shape" data-workbench-region="chart" role="tabpanel" aria-labelledby="explorer-tab-chart" hidden={activeResultTab !== 'chart'}>
		<h2 class="sr-only">The answer, drawn</h2>
		{#key running ? 'loading' : result?.state ?? 'idle'}
			{#if running}
				<div class="answer-state shimmer" data-state="loading"></div>
			{:else if result === null}
				<div class="answer-state" data-explorer-idle>If the answer holds a number, it is drawn here.</div>
			{:else if result.state === 'ok'}
				<div class="chart-body"><ShapePanel columns={result.columns} rows={result.rows as Row[]} lostDays={result.gaps.flatMap((gap) => gap.lostDays)} bounds={shapeBounds} height={data.console.chart_height} selectedType={selectedShapeType} /></div>
			{:else if result.state === 'quiet'}
				<div class="answer-state" data-state="quiet">No rows, so nothing to draw.</div>
			{:else if result.state === 'refused'}
				<div class="answer-state" data-state="refused">The question did not run, so nothing to draw.</div>
			{:else}
				<div class="answer-state" class:warn={result.state === 'unreachable'} data-state={result.state}>{result.state === 'missing' ? 'Part of the data is not on this site, so nothing to draw.' : result.state === 'unreachable' ? 'The data could not be fetched, so nothing to draw.' : 'The answer did not arrive, so nothing to draw.'}</div>
			{/if}
		{/key}
	</div>
</div>
</div>

<style>
	/* The workbench is a tool, so it has the whole window and no card edge: the
	   strip's rule above it is its top edge, and a border at the window's edge
	   would frame nothing. */
	.workbench {
		overflow-x: clip;
		background: var(--color-bg);
	}

	.workbench > :global([data-console-panel-id]) {
		background: var(--color-surface);
		min-block-size: 0;
	}

	.question-panel { display: grid; }
	:global([data-workbench-region='editor'] [data-window-control] .choice-tiles) {
		gap: 0;
	}

	:global([data-workbench-region='editor'] [data-window-control] .choice-tile) {
		min-block-size: var(--workbench-control);
		min-inline-size: var(--workbench-control);
		border-radius: 0;
	}

	:global([data-workbench-region='editor'] [data-window-control] .choice-tile:first-child) {
		border-start-start-radius: var(--radius-md);
		border-end-start-radius: var(--radius-md);
	}

	:global([data-workbench-region='editor'] [data-window-control] .choice-tile:last-child) {
		border-start-end-radius: var(--radius-md);
		border-end-end-radius: var(--radius-md);
	}

	.date-fields {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
		align-items: end;
		min-inline-size: 0;
		overflow: hidden;
	}

	.date-fields label,
	.editor-actions label {
		display: flex;
		align-items: center;
		gap: var(--space-1);
		min-block-size: var(--workbench-control);
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
		max-inline-size: 100%;
		min-inline-size: 0;
		min-block-size: var(--workbench-control);
		border: 1px solid var(--color-rule-strong);
		border-radius: var(--radius-md);
		background: var(--color-surface);
		color: var(--color-text);
		padding-inline: var(--space-3);
		font: inherit;
	}

	:global([data-workbench-region='editor'] [data-window-control]),
	:global([data-workbench-region='questions'] .question-strip button),
	:global([data-workbench-region='questions'] .question-strip summary),
	:global([data-workbench-region='questions'] .history-list summary) {
		min-block-size: var(--workbench-control);
	}

	/* The strip takes the room the links leave and stays one line from 640 px, so a saved
	   question folds an example away instead of making the row taller. */
	:global([data-workbench-region='questions'] .question-strip) {
		flex: 1 1 0;
		min-inline-size: 0;
		margin-block: 0;
	}

	:global([data-workbench-region='questions'] .question-strip button) {
		min-inline-size: 0;
		max-inline-size: 100%;
		overflow: visible;
	}

	.run-button {
		display: flex;
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
		flex-wrap: nowrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2);
		min-block-size: calc(var(--workbench-control) + 2 * var(--space-1));
		padding-inline: var(--space-3);
		border-block-end: 1px solid var(--color-rule);
	}

	/* History's list hangs from this group's end, so nothing here may clip it. */
	.question-links {
		flex: none;
		position: relative;
		display: flex;
		flex: 0 0 auto;
		align-items: center;
		gap: var(--space-2);
		min-inline-size: 0;
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
	.state { margin: 0; padding-inline: var(--space-3); color: var(--color-text-secondary); }
	.gap-note { margin: var(--space-1) 0 0; }
	.warn { color: var(--band-low); }
	.answer-state { min-block-size: 0; block-size: 100%; display: grid; place-items: center; padding: var(--space-6); color: var(--color-text-secondary); background: var(--tint-neutral); }
	.answer-state pre { max-inline-size: 100%; overflow-x: auto; white-space: pre; font-family: var(--font-data); color: var(--code-string); }
	.shimmer { background: linear-gradient(90deg, var(--color-surface) 0%, var(--color-surface-raised) 50%, var(--color-surface) 100%); }
	.question-grid.wide { grid-template-columns: minmax(12rem, 1fr) minmax(0, 4fr) minmax(12rem, 1fr); grid-template-rows: 1fr; }

	/* A region's content never sets its size: a long ledger list, a long
	   question or a thousand rows scroll inside the region that holds them. */
	[data-workbench-region='ledgers'],
	[data-workbench-region='columns'] {
		contain: size;
		min-block-size: 0;
		overflow: auto;
		border-inline-end: 1px solid var(--color-rule);
		padding: var(--space-3);
	}

	.rail-region > summary {
		display: none;
		min-block-size: var(--workbench-control);
		align-items: center;
		padding-inline: var(--space-3);
		color: var(--color-text);
		font-size: var(--text-sm);
		list-style: none;
	}

	.rail-region > summary::-webkit-details-marker {
		display: none;
	}

	[data-workbench-region='columns'] {
		border-inline: 1px solid var(--color-rule) 0;
	}

	[data-workbench-region='editor'] {
		padding: var(--space-3);
	}

	.editor-head {
		min-block-size: var(--workbench-control);
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2);
		color: var(--color-text-tertiary);
		font-size: var(--text-xs);
		font-weight: 600;
		letter-spacing: var(--tracking-label);
		text-transform: uppercase;
	}

	/* One line: the words at its start are cut short before any button moves
	   or wraps, because a heading line that wraps after a click moves the
	   region under it. */
	.editor-head > label {
		flex: 0 1000 auto;
		min-inline-size: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.editor-actions {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		margin-inline-start: auto;
		flex: 0 0 min(100%, 32rem);
		justify-content: flex-end;
	}

	.editor-actions > :global(*) {
		flex: none;
	}

	/* While a question is named, the name field is the one part of the group
	   that gives way, so Keep, Cancel and Run keep their size and place. It
	   starts from nothing and takes the room the buttons leave; the field's
	   percentage width lets it shrink to its 3rem floor. */
	.editor-actions > label {
		flex: 1 1 0;
	}

	.editor-actions label input {
		flex: 1 1 auto;
		inline-size: 100%;
		min-inline-size: 3rem;
	}

	.editor-actions button,
	.result-actions :global(button),
	.result-actions :global(.choice-tile) {
		font-size: var(--text-sm);
		font-weight: 400;
		letter-spacing: normal;
		text-transform: none;
	}

	.editor-actions .run-button {
		font-weight: 600;
	}

	.result-region {
		contain: size;
		display: grid;
		grid-template-rows: var(--workbench-control) minmax(0, 1fr);
		min-block-size: 0;
		border-block-start: 1px solid var(--color-rule);
		background: var(--color-bg);
	}

	.result-tabs {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2);
		padding-inline: var(--space-3);
		border-block-end: 1px solid var(--color-rule);
		min-inline-size: 0;
	}

	.result-tabs > [role='tab'] {
		min-block-size: var(--workbench-control);
		border: 0;
		border-block-end: 3px solid transparent;
		border-radius: 0;
		background: transparent;
		color: var(--color-text-secondary);
		font-size: var(--text-sm);
		font-weight: 600;
	}

	.result-tabs > [role='tab'][aria-selected='true'] {
		border-block-end-color: var(--chart-1);
		color: var(--color-text);
	}

	.result-actions {
		margin-inline-start: auto;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: flex-end;
		gap: var(--space-2);
		min-inline-size: 0;
	}

	.result-region > [role='tabpanel'] {
		min-block-size: 0;
		display: grid;
		background: var(--color-surface);
	}

	.result-region > [role='tabpanel'][hidden] {
		display: none;
	}

	.chart-body {
		min-block-size: 0;
		overflow: auto;
		padding: 0 var(--space-3) var(--space-3);
	}

	.shape-actions { border: 0; margin: 0; padding: 0; min-inline-size: 0; }
	.shape-actions :global(.choice-tile) { min-block-size: var(--workbench-control); }

	/* From the wide breakpoint the workbench fills the window: the question
	   above, the answer and the chart side by side below, each half taking the
	   share the other leaves. The value matches `frame.breakpoints_px[1]`, which
	   a media query cannot read. */
	@media (min-width: 1024px) {
		/* `min-block-size: 0` hands the split to the two `1fr` rows: each half
		   keeps its own smallest size, and only a window shorter than both
		   together makes the page scroll. Left to its content, the box would ask
		   for twice the larger half, because two equal rows size to their larger
		   minimum. */
		.workbench {
			flex: 1 1 0;
			min-block-size: 0;
			display: grid;
			grid-template-columns: minmax(0, 1fr);
			grid-template-rows: minmax(max-content, 1fr) minmax(0, 1fr);
		}

		.workbench > :global([data-console-panel-id='data-explorer-ask']) {
			grid-column: 1 / -1;
		}

		.question-panel {
			block-size: 100%;
			grid-template-rows: auto minmax(0, 1fr);
		}

		[data-workbench-region='ledgers'] > :global(.ledger-list),
		[data-workbench-region='columns'] > :global(.column-list) {
			block-size: 100%;
			min-block-size: 0;
		}

		.editor-stack {
			display: flex;
			flex-direction: column;
			min-block-size: 0;
			overflow: hidden;
		}

		.editor-stack > .state,
		.editor-stack > :global([data-workbench-region='status']) {
			flex: none;
		}

		[data-workbench-region='editor'] {
			flex: 1 1 0;
			display: grid;
			grid-template-rows: auto 1fr;
		}

		.result-region { min-block-size: 0; }
	}

	/* Below it the regions stack in one column and the page scrolls: their
	   smallest useful sizes add up to more than one screen. */
	@media (max-width: 1023px) {
		.run-shortcut {
			display: none;
		}
		[data-workbench-region='ledgers'],
		[data-workbench-region='columns'] {
			block-size: var(--workbench-control);
			padding: 0;
			overflow: visible;
			border-inline: 0;
			border-block: 1px solid var(--color-rule);
		}

		.rail-region > summary {
			display: flex;
		}

		.rail-region[open] {
			block-size: calc(var(--workbench-control) + var(--editor-lines) * var(--workbench-field-leading) + 2 * var(--space-3));
			overflow: auto;
		}

		/* The question is rounded up to a whole pixel, because the answer under it
		   is one window tall and the browser scrolls and sizes the page in whole
		   pixels. Its text lines are not whole pixels tall, so left to its content
		   it ends between two pixels: the answer could never fill the window
		   exactly, and the page's foot would lie past the last pixel a scroll
		   reaches. A browser without `calc-size()` keeps the content's height. */
		.workbench > :global([data-console-panel-id='data-explorer-ask']) {
			block-size: calc-size(auto, round(up, size, 1px));
		}

		.rail-region[open] > :global(.ledger-list),
		.rail-region[open] > :global(.column-list) {
			padding: var(--space-3);
		}

		.rail-region:not([open]) > :global(.ledger-list),
		.rail-region:not([open]) > :global(.column-list) {
			display: none;
		}
		.result-region { min-block-size: 100svh; }
	}

	@media (max-width: 639px) {
		[data-workbench-region='questions'] {
			flex-wrap: wrap;
			align-items: stretch;
			display: grid;
			grid-template-columns: minmax(0, 1fr) auto;
		}
		:global([data-workbench-region='questions'] .question-strip) {
			grid-column: 1 / -1;
			inline-size: 100%;
			flex-basis: 100%;
		}
		.question-links,
		.how-to {
			grid-column: 1 / -1;
			min-inline-size: 0;
			inline-size: 100%;
			flex-basis: 100%;
		}
		.question-links {
			flex-wrap: nowrap;
		}
		:global([data-workbench-region='questions'] .question-strip summary),
		:global([data-workbench-region='questions'] .history-list summary),
		:global([data-workbench-region='questions'] .history-list),
		.how-to {
			box-sizing: border-box;
			block-size: var(--workbench-control);
			white-space: nowrap;
		}
		:global([data-workbench-region='questions'] .question-strip summary),
		.how-to {
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.date-fields {
			display: grid;
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
		.editor-head {
			flex-wrap: wrap;
		}
		.editor-actions {
			flex: 1 1 100%;
			flex-wrap: wrap;
			justify-content: flex-end;
		}
		/* Run holds its place at the end of the group's first line in every state: the
		   name field and Copy question take a whole line of their own beneath it, so a
		   wider face can never push Run down, and a name has the phone's full width. */
		.editor-actions > label,
		.editor-actions > .copy-question {
			order: 1;
			flex: 1 1 100%;
		}
	}
</style>
