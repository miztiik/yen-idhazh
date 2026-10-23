/** Which consented repository tables and page-local files does this SQL actually read? */

import { dropOwnedViews, preflight, readAskCost, readPreparedAsk, serial } from './ask-reader';
import { localTables, type LocalFile } from './local-tables';
import type { EngineOpener, PageKeeper } from './page-keeper';
import type { QueryEngine } from './slice-query';
import type { AskOptions, AskResult, SpanCost } from './slice-shapes';
import { checkStatement } from './statement';
import { checkTableSchemas } from './sql-tables';

export function questionReader(keeper: () => PageKeeper, openEngine: EngineOpener) {
	const imports = localTables();
	let closed = false;
	let lastScope: { ledgers: string[]; locals: string[] } = { ledgers: [], locals: [] };
	function checkOpen() {
		if (closed) throw new Error('This question session ended. Import the local files again.');
	}
	async function dependencies(engine: QueryEngine, sql: string): Promise<{ ledgers: string[]; locals: string[] }> {
		checkOpen();
		await dropOwnedViews(engine);
		const names = [...new Set((await engine.tableNames(sql)).map((name) => name.toLowerCase()))];
		await checkTableSchemas(sql, (statement) => engine.rows(statement, []));
		const ledgers: string[] = [];
		const locals: string[] = [];
		for (const name of names) {
			if (imports.has(name)) { locals.push(name); continue; }
			const ledger = keeper().catalog.get(name);
			if (ledger === undefined) throw new Error(`Table "${name}" is not available. Check the ledger name or import its local Parquet file again.`);
			if (!ledger.publish_to_data_explorer) throw new Error(`Ledger "${name}" is not enabled for the Data explorer.`);
			ledgers.push(ledger.name);
		}
		return { ledgers, locals };
	}
	async function costFor(ledgers: string[], locals: string[], opts: AskOptions): Promise<SpanCost> {
		const cost = await readAskCost(keeper(), ledgers, opts.from, opts.to);
		const tables = imports.list().filter((table) => locals.includes(table.alias));
		return { ...cost, ledgers, locals, files: cost.files + tables.length, bytes: cost.bytes + tables.reduce((sum, table) => sum + table.bytes, 0) };
	}
	function failure(error: unknown): AskResult {
		const message = error instanceof Error ? error.message : String(error);
		console.warn(`Data explorer: ${message}`);
		return { state: 'refused', because: { kind: 'engine-error', message } };
	}
	return {
		localTables: imports.list,
		lastScope: () => lastScope,
		async importFile(file: LocalFile, maxBytes: number, maxFiles: number) {
			return serial(async () => {
				checkOpen();
				const table = await imports.add(await openEngine(), file, maxBytes, maxFiles);
				if (closed) { imports.clear(); checkOpen(); }
				return table;
			});
		},
		async removeFile(alias: string) { return serial(async () => { checkOpen(); imports.remove(alias); }); },
		async cost(opts: AskOptions): Promise<SpanCost> {
			const checked = checkStatement(opts.sql, opts.maxChars);
			if (checked.refusal !== null) return { files: 0, bytes: 0, readFrom: null, readTo: null, cut: [], through: {}, failure: { state: 'refused', because: checked.refusal } };
			return serial(async () => {
				try {
					const refs = await dependencies(await openEngine(), checked.sql);
					return await costFor(refs.ledgers, refs.locals, opts);
				} catch (error) {
					return { files: 0, bytes: 0, readFrom: null, readTo: null, cut: [], through: {}, failure: failure(error) };
				}
			});
		},
		async ask(opts: AskOptions): Promise<AskResult> {
			const checked = checkStatement(opts.sql, opts.maxChars);
			if (checked.refusal !== null) return { state: 'refused', because: checked.refusal };
			return serial(async () => {
				let engine: QueryEngine | null = null;
				try {
					engine = await openEngine();
					const refs = await dependencies(engine, checked.sql);
					lastScope = refs;
					const cost = await costFor(refs.ledgers, refs.locals, opts);
					if (cost.failure !== undefined) return cost.failure;
					const refusal = preflight(cost, opts.maxFiles, opts.maxFetchBytes);
					if (refusal !== null) return { state: 'refused', because: refusal };
					return await imports.withViews(engine, refs.locals, () => readPreparedAsk(keeper(), { ...opts, sql: checked.sql, ledgers: refs.ledgers }, refs.locals.length > 0 || refs.ledgers.length === 0));
				} catch (error) {
					if (engine === null) {
						console.warn('Data explorer engine:', error);
						return { state: 'unreachable', ledger: null, at: null, fault: 'engine' };
					}
					return failure(error);
				}
				finally { if (engine !== null) await dropOwnedViews(engine); }
			});
		},
		close() { closed = true; imports.clear(); }
	};
}
