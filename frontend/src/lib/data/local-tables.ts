/** How are page-local Parquet files bounded, inspected and temporarily registered? */

import { columnsOf, quoteIdent } from './ask-reader';
import { listOf, type QueryEngine } from './slice-query';
import type { Column } from './slice-shapes';

export type LocalTable = Readonly<{ alias: string; filename: string; bytes: number; columns: readonly Column[] }>;
export type LocalFile = Pick<File, 'name' | 'size' | 'slice' | 'arrayBuffer'>;
type HeldTable = { table: LocalTable; file: LocalFile };

/** Aliases use an underscore, which the repository ledger vocabulary cannot contain. */
export function localTables() {
	const held = new Map<string, HeldTable>();
	let minted = 0;

	async function register(engine: QueryEngine, file: LocalFile): Promise<string> {
		const bytes = new Uint8Array(await file.arrayBuffer());
		if (bytes.byteLength !== file.size) throw new Error('The local file changed size while being read. Select it again.');
		return engine.register(bytes);
	}

	return {
		list: (): LocalTable[] => [...held.values()].map((one) => one.table),
		has: (alias: string): boolean => held.has(alias.toLowerCase()),
		clear() { held.clear(); },
		remove(alias: string) {
			if (!held.delete(alias)) throw new Error(`Local table ${quoteIdent(alias)} is no longer imported.`);
		},
		async add(engine: QueryEngine, file: LocalFile, maxBytes: number, maxFiles: number): Promise<LocalTable> {
			if (held.size >= maxFiles) throw new Error(`Remove a local table first. The limit is ${maxFiles} files.`);
			const total = [...held.values()].reduce((sum, one) => sum + one.table.bytes, 0) + file.size;
			if (!Number.isSafeInteger(file.size) || file.size <= 0 || total > maxBytes) {
				throw new Error(`Local files must be nonempty and total at most ${maxBytes} bytes. This selection would total ${total} bytes.`);
			}
			// PAR1 is the Parquet format marker, not a tunable threshold.
			const magic = 'PAR1';
			const head = new Uint8Array(await file.slice(0, magic.length).arrayBuffer());
			const tail = new Uint8Array(await file.slice(-magic.length).arrayBuffer());
			const decoder = new TextDecoder();
			if (decoder.decode(head) !== magic || decoder.decode(tail) !== magic) throw new Error('This file is not readable Parquet (PAR1 markers are missing).');
			const name = await register(engine, file);
			try {
				const columns = columnsOf(await engine.rows(`DESCRIBE SELECT * FROM read_parquet(${listOf([name])})`, []));
				minted += 1;
				const table: LocalTable = { alias: `local_${minted}`, filename: file.name, bytes: file.size, columns };
				held.set(table.alias, { table, file });
				return table;
			} finally { await engine.drop([name]); }
		},
		async withViews<T>(engine: QueryEngine, aliases: readonly string[], work: () => Promise<T>): Promise<T> {
			const files: string[] = [];
			const views: string[] = [];
			try {
				for (const alias of aliases) {
					const one = held.get(alias);
					if (one === undefined) throw new Error(`Local table ${quoteIdent(alias)} is missing. Import its Parquet file again.`);
					const name = await register(engine, one.file);
					files.push(name);
					await engine.rows(`CREATE VIEW ${quoteIdent(alias)} AS SELECT * FROM read_parquet(${listOf([name])})`, []);
					views.push(alias);
				}
				return await work();
			} finally {
				try {
					for (const alias of views) await engine.rows(`DROP VIEW IF EXISTS ${quoteIdent(alias)}`, []);
				} finally { if (files.length > 0) await engine.drop(files); }
			}
		}
	};
}

export type LocalTables = ReturnType<typeof localTables>;
