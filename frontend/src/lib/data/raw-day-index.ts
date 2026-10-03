/** Can this build read a raw day listing staged for the query door? */

import type { DateStamp, LedgerName } from './slice-shapes';

export const RAW_DAY_INDEX_STAMP = '2026-10-03';

export interface RawDayIndex {
	version?: string;
	ledger: LedgerName;
	date: DateStamp;
	files: string[];
	bytes: number[];
	content_sha256: string;
	listed_at: string;
}

const FILE_ID_NAME = /^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.(parquet|json)$/;
const STAMP = /^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?)?$/;
const INSTANT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const SHA256 = /^[0-9a-f]{64}$/;

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isCount(value: unknown): value is number {
	return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}

export type RawDayReading = { index: RawDayIndex } | { refused: string };

export function readRawDayIndex(value: unknown, ledger: LedgerName, day: DateStamp): RawDayReading {
	const refused = (why: string): RawDayReading => ({ refused: why });
	if (!isRecord(value)) return refused('it is not a JSON object');
	const stamp = value.version ?? RAW_DAY_INDEX_STAMP;
	if (typeof stamp !== 'string' || !STAMP.test(stamp)) return refused(`its version ${JSON.stringify(stamp)} is not a stamp`);
	if (stamp > RAW_DAY_INDEX_STAMP) return refused(`it is stamped ${stamp} and this build reads ${RAW_DAY_INDEX_STAMP} or older`);
	if (value.ledger !== ledger) return refused(`it names the ledger ${JSON.stringify(value.ledger)}`);
	if (value.date !== day) return refused(`it names the day ${JSON.stringify(value.date)}`);
	if (!Array.isArray(value.files)) return refused('it has no list of files');
	if (!Array.isArray(value.bytes)) return refused('it has no list of bytes');
	if (value.files.length !== value.bytes.length) return refused(`it lists ${value.files.length} files and ${value.bytes.length} sizes`);
	let previous = '';
	const files: string[] = [];
	for (const [at, file] of value.files.entries()) {
		if (typeof file !== 'string' || !FILE_ID_NAME.test(file)) return refused(`file ${at} is ${JSON.stringify(file)}`);
		if (file <= previous) return refused(`file ${file} does not come after ${previous}`);
		previous = file;
		files.push(file);
	}
	const bytes: number[] = [];
	for (const [at, one] of value.bytes.entries()) {
		if (!isCount(one)) return refused(`byte ${at} is ${JSON.stringify(one)}`);
		bytes.push(one);
	}
	if (typeof value.content_sha256 !== 'string' || !SHA256.test(value.content_sha256)) return refused('its digest is not a SHA-256');
	if (typeof value.listed_at !== 'string' || !INSTANT.test(value.listed_at)) return refused('listed_at is not a whole-second UTC instant');
	return { index: { version: stamp, ledger, date: day, files, bytes, content_sha256: value.content_sha256, listed_at: value.listed_at } };
}
