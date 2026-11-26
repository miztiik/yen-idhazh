/** Bind panel reads to staged files and explorer questions to one compact session. */

import { base } from '$app/paths';
import { configuredCatalog } from './configured-catalog';
import { compactBytes, fetchedBytes } from './fetched-bytes';
import { compactWriteReader, type CompactWriteRequest } from './compact-file-writes';
import type { Period } from './compact-index';
import { dropOwnedViews, readAsk, readAskCost, serial } from './ask-reader';
import { readColumns } from './ledger-columns';
import { readReach, type LedgerReach } from './ledger-reach';
import { pageKeeper, type PageKeeper } from './page-keeper';
import { renewReadSession } from './read-session';
import { readSlice } from './slice-reader';
import { questionReader } from './question-reader';
import { TOKEN_HISTORY_COLUMNS, type TokenDeviationOptions } from './token-deviation-query';
import type { LedgerCatalog } from './ledger-catalog';
import type { QueryEngine } from './slice-query';
import { isDay, SliceRequestError, type AskOptions, type AskResult, type Column, type DateStamp, type LedgerName, type SliceOptions, type SliceResult, type SpanCost } from './slice-shapes';

export type { LedgerReach } from './ledger-reach';
export { readSession } from './read-session';
export type { AskFault, AskOptions, AskRefusal, AskResult, Column, DateStamp, FetchCost, LedgerFault, LedgerName, Predicate, Row, SetAsideFiles, SliceOptions, SliceResult, SpanCost, SpanGap } from './slice-shapes';

/** Only the explicit empty test switch may override the committed destination. */
export function explorerBaseUrl(): string {
	const runtime = (globalThis as typeof globalThis & { __ARCHIVE_BASE_URL__?: unknown }).__ARCHIVE_BASE_URL__;
	const archive = runtime === '' ? '' : __ARCHIVE_BASE_URL__;
	return archive || __ASSET_BASE_URL__ || base;
}

export interface LedgerReader {
	question: ReturnType<typeof questionReader>;
	compactWrites(request: CompactWriteRequest): ReturnType<ReturnType<typeof compactWriteReader>['activity']>;
	compactPeriod(ledger: LedgerName, period: Period, covers: string, limits: Pick<CompactWriteRequest, 'maxFiles' | 'maxBytes'>): ReturnType<ReturnType<typeof compactWriteReader>['period']>;
	slice(ledger: LedgerName, options: SliceOptions): Promise<SliceResult>;
	tokenDeviations(from: DateStamp, to: DateStamp, options: TokenDeviationOptions): Promise<SliceResult>;
	ledgerReach(ledger: LedgerName): Promise<LedgerReach>;
	ask(options: AskOptions): Promise<AskResult>;
	askCost(ledgers: readonly LedgerName[], from: DateStamp, to: DateStamp): Promise<SpanCost>;
	askColumns(ledgers: readonly LedgerName[], from: DateStamp, to: DateStamp, maxFetchBytes: number, maxFiles: number): Promise<Column[]>;
	startAfresh(): Promise<void>;
	pageHeldBytes(): number;
}

/** One catalog and one compact source live and expire together. */
export function createLedgerReader(catalog: LedgerCatalog, compactPrefix = explorerBaseUrl()): LedgerReader {
	let kept: PageKeeper | null = null;
	let compact: PageKeeper | null = null;
	let writes: ReturnType<typeof compactWriteReader> | null = null;
	let engine: Promise<QueryEngine> | null = null;
	let closed = false;
	function openEngine(): Promise<QueryEngine> {
		engine ??= import('./engine').then((module) => module.browserEngine(__ENGINE_EXTENSION_REPOSITORY__));
		return engine;
	}
	function checkOpen(): void {
		if (closed) throw new Error('This read session ended. Refresh the registry before reading again.');
	}
	function keeper(): PageKeeper {
		checkOpen();
		kept ??= pageKeeper(fetchedBytes(__ASSET_BASE_URL__ || base, (url, init) => fetch(url, init)), openEngine, catalog);
		return kept;
	}
	function compactKeeper(): PageKeeper {
		checkOpen();
		compact ??= pageKeeper(compactBytes(compactPrefix, (url, init) => fetch(url, init)), openEngine, catalog);
		return compact;
	}
	const question = questionReader(compactKeeper, openEngine);
	function writeReader() {
		checkOpen();
		return writes ??= compactWriteReader(keeper(), true);
	}
	return {
		question,
		compactWrites: (request) => writeReader().activity(request),
		compactPeriod: (ledger, period, covers, limits) => writeReader().period(ledger, period, covers, limits),
		slice: (ledger, options) => readSlice(keeper(), ledger, options),
		tokenDeviations: (from, to, options) => readSlice(keeper(), 'item-health', {
			columns: TOKEN_HISTORY_COLUMNS, from, to
		}, options),
		ledgerReach: (ledger) => readReach(keeper(), ledger),
		ask: (options) => readAsk(compactKeeper(), options),
		askCost: (ledgers, from, to) => readAskCost(compactKeeper(), ledgers, from, to),
		askColumns: (ledgers, from, to, maxFetchBytes, maxFiles) => readColumns(compactKeeper(), ledgers, from, to, maxFetchBytes, maxFiles),
		startAfresh() {
			closed = true;
			question.close();
			renewReadSession();
			return serial(async () => {
				if (engine !== null) await dropOwnedViews(await engine);
				await kept?.release();
				await compact?.release();
				kept = null;
				compact = null;
				writes = null;
			});
		},
		pageHeldBytes: () => (kept?.heldBytes() ?? 0) + (compact?.heldBytes() ?? 0)
	};
}

let configuredReader: LedgerReader | null = null;
function panelReader(): LedgerReader { return configuredReader ??= createLedgerReader(configuredCatalog); }
export function slice(ledger: LedgerName, options: SliceOptions): Promise<SliceResult> { return panelReader().slice(ledger, options); }
export function compactWrites(request: CompactWriteRequest) { return panelReader().compactWrites(request); }
export function compactPeriod(ledger: LedgerName, period: Period, covers: string, limits: Pick<CompactWriteRequest, 'maxFiles' | 'maxBytes'>) {
	return panelReader().compactPeriod(ledger, period, covers, limits);
}
export function compactLedgerNames(): LedgerName[] {
	return configuredCatalog.entries.filter(({ publish_to_data_explorer }) => publish_to_data_explorer).map(({ name }) => name).sort();
}
export const GARDENER_RECOVERY_COLUMNS = ['date', 'run_id', 'attempt', 'job', 'shard', 'task', 'recovered'] as const;
export function gardenerRecoveries(from: DateStamp, to: DateStamp, runId: string, attempt: number): Promise<SliceResult> {
	if (!isDay(/^\d{4}-\d{2}-\d{2}(?=-\d+$)/.exec(runId)?.[0]) || !Number.isSafeInteger(attempt) || attempt < 1) {
		throw new SliceRequestError('a recovery read needs a valid Gardener run and attempt');
	}
	return slice('gardener', {
		from, to, columns: GARDENER_RECOVERY_COLUMNS,
		where: [{ column: 'run_id', op: '=', value: runId }, { column: 'attempt', op: '=', value: attempt }]
	});
}
export function tokenDeviations(from: DateStamp, to: DateStamp, options: TokenDeviationOptions): Promise<SliceResult> {
	return panelReader().tokenDeviations(from, to, options);
}
export function ledgerReach(ledger: LedgerName): Promise<LedgerReach> { return panelReader().ledgerReach(ledger); }
export function ask(options: AskOptions): Promise<AskResult> { return panelReader().ask(options); }
export function askCost(ledgers: readonly LedgerName[], from: DateStamp, to: DateStamp): Promise<SpanCost> { return panelReader().askCost(ledgers, from, to); }
export function askColumns(ledgers: readonly LedgerName[], from: DateStamp, to: DateStamp, maxFetchBytes: number, maxFiles: number): Promise<Column[]> { return panelReader().askColumns(ledgers, from, to, maxFetchBytes, maxFiles); }
export async function startAfresh(): Promise<void> {
	const current = configuredReader;
	configuredReader = null;
	await current?.startAfresh();
}
export function pageHeldBytes(): number { return configuredReader?.pageHeldBytes() ?? 0; }
