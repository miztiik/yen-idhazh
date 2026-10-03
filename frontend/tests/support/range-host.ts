/** How does a browser spec serve the query door's files the way GitHub Pages serves them?
 *
 * One small HTTP server on 127.0.0.1, because `vite preview` compresses a
 * `.parquet` it has no type for and cannot slow only the data files. Under a
 * data root it answers as Pages was measured to answer: a GET naming one byte
 * range gets 206 and that range, a `HEAD` gets 200 and the full length whatever
 * `Range` it carries, every file carries an ETag of its modification time and
 * size in hex and `Cache-Control: max-age`, a `.parquet` goes out as
 * `application/octet-stream`, and a query string is ignored. An `If-Range`
 * naming another ETag gets the whole file, with 200, as Pages was measured to
 * answer it. Nothing is compressed: a browser asks for every byte range
 * uncompressed, and undoes the compression of a whole file before the page
 * reads it, so the compression Pages applies reaches no byte the door reads.
 *
 * Every request under a data root is logged: method, path, query string,
 * `Range`, `Accept-Encoding`, `If-Range`, status, the ETag it answered with and
 * body bytes. A data root may be slowed: each response waits a fixed time before
 * its first byte, then sends its body no faster than a fixed rate. Everything
 * else - the page a spec drives and the engine's add-on - is served plainly,
 * unslowed and unlogged.
 */

import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import type { AddressInfo } from 'node:net';
import os from 'node:os';
import path from 'node:path';

/** How a slowed data root answers: a wait before each response, then a body rate. */
export interface Throttle {
	latencyMs: number;
	bytesPerSecond: number;
}

/** A directory served under `/<name>/state/`, the way Pages serves a data file. */
export interface DataRoot {
	dir: string;
	throttle?: Throttle;
}

/** One request under a data root, as it was answered. */
export interface HostRequest {
	root: string;
	method: string;
	/** The path under the root's `state/`, without its query string. */
	path: string;
	/** The query string as asked, `?` included, or empty. The host ignores it, as Pages does. */
	query: string;
	range: string | null;
	acceptEncoding: string | null;
	ifRange: string | null;
	ifNoneMatch: string | null;
	status: number;
	/** The ETag the answer carried; null for a file that is not there. */
	etag: string | null;
	/** Body bytes written before the response ended or the browser went away. */
	bodyBytes: number;
}

export interface HostOptions {
	/** The directory served at `/`: the page a spec drives. */
	site: string;
	/** Directories served plainly under `/<name>/`, such as the engine's add-on. */
	plain: Record<string, string>;
	data: Record<string, DataRoot>;
	/** The `max-age` a data file carries. Pages sends 600. */
	maxAge: number;
}

export interface RangeHost {
	readonly origin: string;
	/** Every request under a data root, in the order each one finished. */
	readonly log: HostRequest[];
	/** The `max-age` a data file carries from now on. */
	maxAge: number;
	close(): Promise<void>;
}

const TYPES: Record<string, string> = {
	'.html': 'text/html; charset=utf-8',
	'.js': 'text/javascript; charset=utf-8',
	'.json': 'application/json; charset=utf-8',
	'.parquet': 'application/octet-stream',
	'.wasm': 'application/wasm'
};

const typeOf = (file: string): string => TYPES[path.extname(file)] ?? 'application/octet-stream';

/** Where the Node engine keeps downloaded DuckDB add-ons from one repository. */
export function addonCache(repository: string): string {
	const address = new URL(repository);
	const last = `${address.host}${address.pathname}`.split('/').filter((part) => part !== '').at(-1) ?? address.host;
	return path.join(os.homedir(), '.duckdb', 'extensions', last);
}

const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

/** The file `relative` names inside `dir`, or null when it would leave `dir`. */
function inside(dir: string, relative: string): string | null {
	const root = path.resolve(dir);
	const file = path.resolve(root, `.${path.posix.sep}${relative}`);
	return file === root || file.startsWith(`${root}${path.sep}`) ? file : null;
}

/** The one byte range a `Range` header asks for; null for none this host serves; or unsatisfiable. */
function rangeOf(header: string, size: number): { start: number; end: number } | 'unsatisfiable' | null {
	const match = /^bytes=(\d*)-(\d*)$/.exec(header.trim());
	if (match === null || (match[1] === '' && match[2] === '')) return null;
	if (match[1] === '') {
		const suffix = Number(match[2]);
		return suffix === 0 ? 'unsatisfiable' : { start: Math.max(0, size - suffix), end: size - 1 };
	}
	const start = Number(match[1]);
	const end = match[2] === '' ? size - 1 : Math.min(Number(match[2]), size - 1);
	return start >= size || end < start ? 'unsatisfiable' : { start, end };
}

/** Resolves when `response` can take more, or has gone away. */
function drained(response: ServerResponse): Promise<void> {
	return new Promise((resolve) => {
		const done = (): void => {
			response.off('drain', done);
			response.off('close', done);
			resolve();
		};
		response.on('drain', done);
		response.on('close', done);
	});
}

/** Sends bytes `start` to `end` of `file`, no faster than `throttle` allows, counting what it wrote. */
async function sendBody(
	response: ServerResponse,
	file: string,
	start: number,
	end: number,
	throttle: Throttle | undefined,
	counted: { bytes: number }
): Promise<void> {
	const began = performance.now();
	const stream = createReadStream(file, { start, end, highWaterMark: 16 * 1024 });
	try {
		for await (const chunk of stream as AsyncIterable<Buffer>) {
			if (throttle !== undefined) {
				const due = began + ((counted.bytes + chunk.length) / throttle.bytesPerSecond) * 1000;
				const wait = due - performance.now();
				if (wait > 0) await sleep(wait);
			}
			if (response.destroyed) break;
			counted.bytes += chunk.length;
			if (!response.write(chunk)) await drained(response);
		}
	} finally {
		stream.destroy();
	}
	if (!response.destroyed) response.end();
}

async function servePlain(dir: string, relative: string, request: IncomingMessage, response: ServerResponse): Promise<void> {
	const file = inside(dir, relative === '' ? 'index.html' : relative);
	const found = file === null ? null : await stat(file).catch(() => null);
	if (file === null || found === null || !found.isFile()) {
		response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('Not Found');
		return;
	}
	response.writeHead(200, { 'Content-Type': typeOf(file), 'Content-Length': found.size, 'Cache-Control': 'no-store' });
	if (request.method === 'HEAD') response.end();
	else await sendBody(response, file, 0, found.size - 1, undefined, { bytes: 0 });
}

async function serveData(
	root: string,
	data: DataRoot,
	relative: string,
	query: string,
	maxAge: number,
	request: IncomingMessage,
	response: ServerResponse,
	log: HostRequest[]
): Promise<void> {
	const header = (name: string): string | null => {
		const value = request.headers[name];
		return typeof value === 'string' ? value : null;
	};
	const counted = { bytes: 0 };
	// Set when the file is found. A header handed to `writeHead` alone is not one `getHeader` reads back.
	const served: { etag: string | null } = { etag: null };
	response.on('close', () => {
		log.push({
			root,
			method: request.method ?? '',
			path: relative,
			query,
			range: header('range'),
			acceptEncoding: header('accept-encoding'),
			ifRange: header('if-range'),
			ifNoneMatch: header('if-none-match'),
			status: response.statusCode,
			etag: served.etag,
			bodyBytes: counted.bytes
		});
	});
	if (data.throttle !== undefined) await sleep(data.throttle.latencyMs);
	const file = inside(data.dir, relative);
	const found = file === null ? null : await stat(file).catch(() => null);
	if (file === null || found === null || !found.isFile()) {
		response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('Not Found');
		return;
	}
	const seconds = Math.floor(found.mtimeMs / 1000);
	const etag = `"${seconds.toString(16)}-${found.size.toString(16)}"`;
	served.etag = etag;
	const lastModified = new Date(seconds * 1000).toUTCString();
	const common = {
		'Content-Type': typeOf(file),
		'Last-Modified': lastModified,
		ETag: etag,
		'Cache-Control': `max-age=${maxAge}`,
		'Accept-Ranges': 'bytes'
	};
	const noneMatch = header('if-none-match');
	const modifiedSince = header('if-modified-since');
	const unchanged =
		noneMatch !== null
			? noneMatch.split(',').some((tag) => tag.trim() === etag || tag.trim() === '*')
			: modifiedSince !== null && Date.parse(modifiedSince) >= seconds * 1000;
	if (unchanged) {
		response.writeHead(304, common).end();
		return;
	}
	if (request.method === 'HEAD') {
		response.writeHead(200, { ...common, 'Content-Length': found.size }).end();
		return;
	}
	const asked = header('range');
	const ifRange = header('if-range');
	const honoured = asked !== null && (ifRange === null || ifRange === etag || ifRange === lastModified);
	const range = honoured ? rangeOf(asked, found.size) : null;
	if (range === 'unsatisfiable') {
		response.writeHead(416, { ...common, 'Content-Range': `bytes */${found.size}` }).end();
		return;
	}
	if (range === null) {
		response.writeHead(200, { ...common, 'Content-Length': found.size });
		await sendBody(response, file, 0, found.size - 1, data.throttle, counted);
		return;
	}
	response.writeHead(206, {
		...common,
		'Content-Length': range.end - range.start + 1,
		'Content-Range': `bytes ${range.start}-${range.end}/${found.size}`
	});
	await sendBody(response, file, range.start, range.end, data.throttle, counted);
}

/** Starts a host on an ephemeral port of 127.0.0.1. */
export async function startRangeHost(options: HostOptions): Promise<RangeHost> {
	const log: HostRequest[] = [];
	const host = { maxAge: options.maxAge };
	const server = createServer((request, response) => {
		const { pathname, search } = new URL(request.url ?? '/', 'http://host.invalid');
		const [first = '', ...rest] = decodeURIComponent(pathname).split('/').filter((part) => part !== '');
		const answering =
			first in options.data && rest[0] === 'state'
				? serveData(first, options.data[first], rest.slice(1).join('/'), search, host.maxAge, request, response, log)
				: first in options.plain
					? servePlain(options.plain[first], rest.join('/'), request, response)
					: servePlain(options.site, [first, ...rest].filter((part) => part !== '').join('/'), request, response);
		answering.catch((error: unknown) => {
			if (!response.headersSent) response.writeHead(500).end(String(error));
			else response.destroy();
		});
	});
	await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
	const { port } = server.address() as AddressInfo;
	return Object.assign(host, {
		origin: `http://127.0.0.1:${port}`,
		log,
		close: () =>
			new Promise<void>((resolve) => {
				server.closeAllConnections();
				server.close(() => resolve());
			})
	});
}
