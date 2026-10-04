/**
 * How does the query engine start, in a browser and in Node, and how does it take a file and run one statement?
 *
 * **The only module in `frontend/` that imports `@duckdb/duckdb-wasm`**, so the
 * engine stays replaceable: a second importer is a second place to change when
 * it moves. Everything else reaches it through `QueryEngine` in `slice-query.ts`,
 * and the query door reaches this module only through a dynamic `import()`.
 *
 * **Every file it takes gets a name it mints**, whole or at an address:
 * `door/<n>.parquet` from a counter, never from an index, a `covers` value or a
 * caller, so no fetched text can name a file. Every file the door registers sits
 * under that one directory, which is what an engine that admits one directory
 * alone can still read.
 *
 * **In a browser the engine takes the buffer it is handed**: registering moves it
 * to the engine's worker and leaves the caller's copy empty. In Node the engine
 * copies it. So a caller hands a buffer over once, and keeps the name instead.
 *
 * **In a browser it can also read a file at an address by byte range**, asking the
 * host only for the parts a query needs, and it opens the file as it registers it
 * so the caller learns the length the host gave. The engine's own default reads a
 * registered address whole, in one request with no `Range`, so the database is
 * opened with `forceFullHTTPReads` off. `allowFullHTTPReads` stays on: with it off
 * the engine opens a file only when its opening `HEAD` is answered 206, and Pages
 * answers 200. The address is made absolute, because a `blob:` worker resolves no
 * relative one. The Node half has no reader for a host, so every file it reads is
 * handed to it.
 *
 * **In a browser** it loads the single-threaded build that needs WebAssembly
 * exception handling, and nothing else: the threaded build needs response
 * headers a static host cannot send. The package, its wasm and its worker are
 * all reached by dynamic `import()`, so none of them is part of a page's first
 * load, and a browser without the feature gets an error the door draws as
 * `unreachable`. The worker starts from a `blob:` bootstrap that imports the
 * same-origin worker file by absolute URL: a worker started from a same-origin
 * URL takes its policy from its own response headers, and Pages sends none,
 * while a `blob:` worker inherits the page's `connect-src`. A relative URL
 * does not resolve inside a `blob:` worker, so both addresses are made absolute.
 *
 * **In Node** it loads the package's blocking build and reads the wasm from the
 * installed package, through `locate`, which the Node-only caller supplies so
 * that this module names no Node built-in. The build's name is held in a
 * variable the browser bundler cannot follow, so no browser chunk carries the
 * Node half.
 *
 * **The parquet reader is an add-on the engine downloads.** This build links
 * only DuckDB's core functions, so the first query over parquet makes the engine
 * fetch the parquet add-on from `ledger.engine_extension_repository` - DuckDB's
 * own host by default - and check its signature before loading it, which is
 * what DuckDB-Wasm does on any site. In a browser the page's `connect-src`
 * admits that one origin; in Node the engine keeps the file in a cache under the
 * user's home directory, so only a machine's first query downloads it.
 */

import type { Bound, QueryEngine } from './slice-query';

/** The engine package, spelled once. */
const PACKAGE = '@duckdb/duckdb-wasm';

/** The Node half's build, in a variable so the browser bundler never follows it. */
const NODE_BUILD = `${PACKAGE}/blocking`;

/** Where the engine fetches an add-on from. Empty leaves the engine's built-in address. */
function repositorySetting(repository: string): string[] {
	return repository ? [`SET custom_extension_repository = '${repository.replaceAll("'", "''")}'`] : [];
}

/** An engine result, as far as this module reads one. */
interface ResultTable {
	toArray(): { toJSON(): Record<string, unknown> }[];
}

let minted = 0;

/** The name one registered file is read under, never taken from an index or a caller. */
function mintName(): string {
	minted += 1;
	return `door/${minted}.parquet`;
}

function plainRows(table: ResultTable): Record<string, unknown>[] {
	return table.toArray().map((row) => row.toJSON());
}

let browser: Promise<QueryEngine> | null = null;
let node: Promise<QueryEngine> | null = null;

/** Starts once; a start that failed is tried again by the next caller. */
function once(slot: 'browser' | 'node', start: () => Promise<QueryEngine>): Promise<QueryEngine> {
	const held = slot === 'browser' ? browser : node;
	if (held !== null) return held;
	const started = start().catch((error: unknown) => {
		if (slot === 'browser') browser = null;
		else node = null;
		throw error;
	});
	if (slot === 'browser') browser = started;
	else node = started;
	return started;
}

/** The engine in this browser tab, fetching its add-ons from `repository`. */
export function browserEngine(repository: string): Promise<QueryEngine> {
	return once('browser', () => startInBrowser(repository));
}

async function startInBrowser(repository: string): Promise<QueryEngine> {
	const [duckdb, wasm, worker] = await Promise.all([
		import('@duckdb/duckdb-wasm'),
		import('@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url'),
		import('@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url')
	]);
	if (!(await duckdb.getPlatformFeatures()).wasmExceptions) {
		throw new Error('this browser has no WebAssembly exception handling, and the one engine build needs it');
	}
	const workerUrl = new URL(worker.default, location.href).href;
	const bootstrap = URL.createObjectURL(
		new Blob([`importScripts(${JSON.stringify(workerUrl)});`], { type: 'text/javascript' })
	);
	try {
		const workerInstance = new Worker(bootstrap);
		const workerStarted = new Promise<never>((_, reject) => {
			workerInstance.addEventListener('error', () => reject(new Error('the query engine worker did not start')), { once: true });
		});
		const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), workerInstance);
		await Promise.race([db.instantiate(new URL(wasm.default, location.href).href), workerStarted]);
		await db.open({ filesystem: { forceFullHTTPReads: false } });
		const connection = await db.connect();
		for (const statement of repositorySetting(repository)) await connection.query(statement);
		return {
			async register(bytes) {
				const name = mintName();
				await db.registerFileBuffer(name, bytes);
				return name;
			},
			async registerAddress(url) {
				const name = mintName();
				await db.registerFileURL(name, new URL(url, location.href).href, duckdb.DuckDBDataProtocol.HTTP, false);
				try {
					// The engine learns a file's length when a statement first opens it.
					await connection.query(`SELECT size FROM read_blob('${name.replaceAll("'", "''")}')`);
				} catch (error) {
					await db.dropFile(name);
					throw error;
				}
				const [opened] = await db.globFiles(name);
				return { name, bytes: opened?.fileSize ?? Number.NaN };
			},
			async drop(names) {
				await db.dropFiles([...names]);
			},
			async rows(sql: string, params: readonly Bound[]) {
				const prepared = await connection.prepare(sql);
				try {
					return plainRows(await prepared.query(...params));
				} finally {
					await prepared.close();
				}
			}
		};
	} finally {
		URL.revokeObjectURL(bootstrap);
	}
}

/** The engine in this Node process. `locate` turns a path inside the package into a file path;
 *  `repository` is where the engine fetches its add-ons. */
export function nodeEngine(locate: (specifier: string) => string, repository: string): Promise<QueryEngine> {
	return once('node', () => startInNode(locate, repository));
}

async function startInNode(locate: (specifier: string) => string, repository: string): Promise<QueryEngine> {
	const duckdb = (await import(/* @vite-ignore */ NODE_BUILD)) as typeof import('@duckdb/duckdb-wasm/blocking');
	const file = (name: string) => locate(`${PACKAGE}/dist/${name}`);
	const db = await duckdb.createDuckDB(
		{
			mvp: { mainModule: file('duckdb-mvp.wasm'), mainWorker: file('duckdb-node-mvp.worker.cjs') },
			eh: { mainModule: file('duckdb-eh.wasm'), mainWorker: file('duckdb-node-eh.worker.cjs') }
		},
		new duckdb.VoidLogger(),
		duckdb.NODE_RUNTIME
	);
	await db.instantiate(() => {});
	const connection = db.connect();
	for (const statement of repositorySetting(repository)) connection.query(statement);
	return {
		async register(bytes) {
			const name = mintName();
			db.registerFileBuffer(name, bytes);
			return name;
		},
		async drop(names) {
			db.dropFiles([...names]);
		},
		async rows(sql: string, params: readonly Bound[]) {
			const prepared = connection.prepare(sql);
			try {
				return plainRows(prepared.query(...params));
			} finally {
				prepared.close();
			}
		}
	};
}
