/** What can a published Parquet footer establish about a Gardener write? */
import type { Period } from './compact-index';
import type { QueryEngine } from './slice-query';
import { isDay, type LedgerName } from './slice-shapes';

export interface CompactWrite {
	ledger: LedgerName;
	period: Period;
	covers: string;
	writtenAt: number;
	runId: string;
	attempt: number;
	shard: number;
	inputs: number | null;
	rows: number;
	bytes: number;
}

export const COMPACT_WRITE_FOOTER_KEYS = [
	'envelope_version', 'tier', 'ledger', 'period', 'covers', 'written_at_ms', 'run_id', 'attempt', 'job', 'shard', 'producer',
	'built_from'
] as const;

const PLACEHOLDERS = COMPACT_WRITE_FOOTER_KEYS.map(() => '?').join(', ');

export async function compactWriteFooter(
	engine: QueryEngine, file: string, member: Pick<CompactWrite, 'ledger' | 'period' | 'covers' | 'rows' | 'bytes'>
): Promise<CompactWrite | null> {
	const cells = await engine.rows(
		`SELECT decode(key) AS key, decode(value) AS value FROM parquet_kv_metadata(?) WHERE decode(key) IN (${PLACEHOLDERS})`,
		[file, ...COMPACT_WRITE_FOOTER_KEYS]
	);
	const footer = new Map<string, string>();
	for (const { key, value } of cells) {
		if (typeof key !== 'string' || typeof value !== 'string' || footer.has(key)) return null;
		footer.set(key, value);
	}
	const decimal = (key: string) => {
		const text = footer.get(key);
		const value = text === undefined || !/^\d+$/.test(text) ? NaN : Number(text);
		return Number.isSafeInteger(value) ? value : null;
	};
	const writtenAt = decimal('written_at_ms');
	const attempt = decimal('attempt');
	const shard = decimal('shard');
	const runId = footer.get('run_id');
	const runDay = runId === undefined ? undefined : /^(\d{4}-\d{2}-\d{2})-\d+$/.exec(runId)?.[1];
	const version = footer.get('envelope_version');
	const stamp = writtenAt === null ? null : new Date(writtenAt);
	if (version === undefined || !isDay(version.split('T')[0]) ||
		footer.get('tier') !== 'compact' || footer.get('ledger') !== member.ledger ||
		footer.get('period') !== member.period || footer.get('covers') !== member.covers ||
		footer.get('job') !== 'run-tasks' || footer.get('producer') !== 'gardener.tasks.compaction' ||
		runId === undefined || !isDay(runDay) || attempt === null || attempt < 1 || shard === null ||
		writtenAt === null || stamp === null || !Number.isFinite(stamp.getTime()) || !isDay(stamp.toISOString().slice(0, 10))) return null;
	return { ...member, writtenAt, runId, attempt, shard, inputs: decimal('built_from') };
}
