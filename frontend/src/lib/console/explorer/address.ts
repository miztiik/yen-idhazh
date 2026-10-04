import type { LedgerName } from '../../data/slice-shapes';

export const UNKNOWN_LEDGER_NOTICE = (name: string): string => `The link named "${name}", which this site does not have, so it was left out.`;
export const DAYS_NOTICE = (value: string, fallback: number): string => `The link asked for ${value} days, which this page does not offer, so it reads ${fallback} days.`;
export const DATE_SPAN_NOTICE = (from: string, end: string): string => `The link asked for ${from} to ${end}, which is not a span this page can read, so it ends today.`;
export const UNREADABLE_QUESTION_NOTICE = 'The question in this link could not be read, so the editor is empty.';
export const LINK_TOO_LONG_NOTICE = 'This question is too long for a link, so the link carries the ledgers and the days only.';

export type ExplorerAddressInput = {
	basePath: string;
	ledgers: readonly LedgerName[];
	days: number;
	from?: string;
	end?: string;
	statement: string;
	maxBytes?: number;
};

export type ExplorerAddress = {
	href: string;
	query: string;
	linkedStatement: boolean;
	notices: readonly string[];
};

export type ParsedExplorerAddress = {
	ledgers: readonly LedgerName[];
	days: number;
	from: string | null;
	end: string | null;
	statement: string;
	notices: readonly string[];
};

export type ParseExplorerAddressOptions = {
	ledgerNames: readonly LedgerName[];
	windowPresets: readonly number[];
	defaultDays: number;
	today?: string;
	reachDays?: number;
};

function bytesOf(value: string): number {
	return new TextEncoder().encode(value).length;
}

function bytesToBinary(bytes: Uint8Array): string {
	let output = '';
	const chunk = 0x8000;
	for (let index = 0; index < bytes.length; index += chunk) {
		output += String.fromCharCode(...bytes.slice(index, index + chunk));
	}
	return output;
}

function binaryToBytes(value: string): Uint8Array {
	return Uint8Array.from(value, (char) => char.charCodeAt(0));
}

function blobPart(bytes: Uint8Array): ArrayBuffer {
	return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}

async function readStream(stream: ReadableStream<Uint8Array>): Promise<Uint8Array> {
	const reader = stream.getReader();
	const chunks: Uint8Array[] = [];
	let length = 0;
	while (true) {
		const { value, done } = await reader.read();
		if (done) break;
		chunks.push(value);
		length += value.length;
	}
	const out = new Uint8Array(length);
	let offset = 0;
	for (const chunk of chunks) {
		out.set(chunk, offset);
		offset += chunk.length;
	}
	return out;
}

function base64Url(bytes: Uint8Array): string {
	return btoa(bytesToBinary(bytes)).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '');
}

function fromBase64Url(value: string): Uint8Array {
	if (!/^[A-Za-z0-9_-]*$/.test(value)) throw new Error('not base64url');
	const padded = value.replaceAll('-', '+').replaceAll('_', '/') + '='.repeat((4 - (value.length % 4)) % 4);
	return binaryToBytes(atob(padded));
}

export async function encodeQuestion(statement: string): Promise<string> {
	const stream = new Blob([blobPart(new TextEncoder().encode(statement))]).stream().pipeThrough(new CompressionStream('deflate-raw'));
	return base64Url(await readStream(stream));
}

export async function decodeQuestion(q: string): Promise<string> {
	const stream = new Blob([blobPart(fromBase64Url(q))]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
	return new TextDecoder().decode(await readStream(stream));
}

function queryFor(ledgers: readonly LedgerName[], days: number, from: string | null, end: string | null, encodedQuestion: string | null): string {
	const params = new URLSearchParams();
	if (ledgers.length > 0) params.set('ledgers', ledgers.join(','));
	if (from !== null && end !== null) {
		params.set('from', from);
		params.set('end', end);
	} else {
		params.set('days', String(days));
	}
	if (encodedQuestion !== null) params.set('q', encodedQuestion);
	return params.toString();
}

export async function explorerAddress(input: ExplorerAddressInput): Promise<ExplorerAddress> {
	const q = await encodeQuestion(input.statement);
	const custom = input.from !== undefined && input.end !== undefined;
	let query = queryFor(input.ledgers, input.days, custom ? input.from ?? null : null, custom ? input.end ?? null : null, q);
	let href = `${input.basePath}?${query}`;
	if (input.maxBytes !== undefined && bytesOf(href) > input.maxBytes) {
		query = queryFor(input.ledgers, input.days, custom ? input.from ?? null : null, custom ? input.end ?? null : null, null);
		href = `${input.basePath}?${query}`;
		return { href, query, linkedStatement: false, notices: [LINK_TOO_LONG_NOTICE] };
	}
	return { href, query, linkedStatement: true, notices: [] };
}

function isDay(value: string): boolean {
	if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
	return new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
}

function addDays(day: string, delta: number): string {
	const date = new Date(`${day}T00:00:00Z`);
	date.setUTCDate(date.getUTCDate() + delta);
	return date.toISOString().slice(0, 10);
}

export async function parseExplorerAddress(search: string, options: ParseExplorerAddressOptions): Promise<ParsedExplorerAddress> {
	const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
	const ledgerSet = new Set<string>(options.ledgerNames);
	const notices: string[] = [];
	const ledgers: LedgerName[] = [];
	for (const name of (params.get('ledgers') ?? '').split(',').filter(Boolean)) {
		if (ledgerSet.has(name)) ledgers.push(name as LedgerName);
		else notices.push(UNKNOWN_LEDGER_NOTICE(name));
	}

	let days = options.defaultDays;
	let from: string | null = null;
	let end: string | null = null;
	const today = options.today ?? new Date(Date.now()).toISOString().slice(0, 10);
	const reachDays = options.reachDays ?? 365;
	const rawFrom = params.get('from');
	const rawEnd = params.get('end');
	const min = addDays(today, 1 - reachDays);
	if (rawFrom !== null || rawEnd !== null) {
		if (rawFrom !== null && rawEnd !== null && isDay(rawFrom) && isDay(rawEnd) && rawFrom >= min && rawEnd <= today && rawFrom <= rawEnd) {
			from = rawFrom;
			end = rawEnd;
			const parsedDays = Math.round((Date.parse(`${end}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000) + 1;
			days = parsedDays;
		} else {
			notices.push(DATE_SPAN_NOTICE(rawFrom ?? '', rawEnd ?? ''));
		}
	}
	const rawDays = params.get('days');
	if (rawDays !== null && from === null) {
		const parsed = Number(rawDays);
		if (Number.isInteger(parsed) && options.windowPresets.includes(parsed)) days = parsed;
		else notices.push(DAYS_NOTICE(rawDays, options.defaultDays));
	}

	let statement = '';
	const q = params.get('q');
	if (q !== null && q !== '') {
		try {
			statement = await decodeQuestion(q);
		} catch {
			notices.push(UNREADABLE_QUESTION_NOTICE);
		}
	}
	return { ledgers, days, from, end, statement, notices };
}

export function requestTargetBytes(pathAndQuery: string): number {
	return bytesOf(pathAndQuery);
}
