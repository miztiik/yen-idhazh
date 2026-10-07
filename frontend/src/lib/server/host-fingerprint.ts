/** What machine each job of a run drew, read at build time from `state/`.
 *
 * `state/host-fingerprint/` has been written since 2026-09-16 and, until this
 * module, nothing read a cell of it. One row a job: the processor's family,
 * model and stepping, the instruction-set flags an inference runtime dispatches
 * on, the cache, the memory bandwidth, and the platform's own name for where it
 * put the machine (`docs/reference/host-metrics.md`).
 *
 * **Read from its packed files, through the query door**, like the article and
 * score records (`ledger-rows.ts`): the newest days a window reaches and no more,
 * so another published day adds a file this call never opens once the cover is
 * filled (`CLAUDE.md` Guardrail #12). A job's two halves - the machine before
 * its heaviest step, its clock after the last item - are one row once packed,
 * because the clock step files the whole row.
 *
 * **The row shape and the flag vocabulary are copied by hand, and two tests
 * hold the copy in step.** `backend/tests/contracts/test_frontend_field_set.py`
 * fails when this file's `HostFingerprintRow` names a different set of columns,
 * or a different type for one, than `backend/idhazh/contracts/host_fingerprint.py`
 * declares. `backend/tests/contracts/test_frontend_vocabularies.py` fails when
 * either closed set below holds a different member list from its Python enum.
 * So a column added to the contract lands here as a red test rather than as a
 * cell nobody reads, and the twelve chips a card draws cannot fall out of step
 * with the twelve the probe records. The columns' own descriptions stay on the
 * Pydantic model, which is the one place they are written.
 *
 * Nothing here is published. It sits under `$lib/server/` so SvelteKit refuses
 * to bundle it for a browser, the same place and for the same reason as
 * `machine-counters.ts`, and it adds no published telemetry column.
 */

// Relative, not `$lib`: the browser suite loads this module in plain Node.
import type { TimeWindow } from '../charts/viewport';
import { sliceFromDisk } from './ledger-disk';
import { datedFirst, windowRows, type LedgerTable } from './ledger-rows';
import { STATE_ROOT } from './payload';

/** Which workflow job produced a row. `ServerJob` in `contracts/base.py`. */
export const SERVER_JOB = [
	'plan',
	'work',
	'assemble',
	'visuals',
	'runtime',
	'decide',
	'migrate',
	'run-tasks',
	'history',
	'save_council_results'
] as const;

export type ServerJob = (typeof SERVER_JOB)[number];

/** The instruction-set flags a card draws a chip for. `WatchedFlag` in
 * `contracts/machine_panels.py`, which restates the probe's own `WATCHED_FLAGS`
 * tuple and refuses to import on a mismatch. */
export const WATCHED_FLAG = [
	'amx_bf16',
	'amx_int8',
	'amx_tile',
	'avx2',
	'avx512_bf16',
	'avx512_fp16',
	'avx512_vnni',
	'avx512f',
	'avx_vnni',
	'f16c',
	'fma',
	'sse4_2'
] as const;

export type WatchedFlag = (typeof WATCHED_FLAG)[number];

/** One job, one machine, one row: what the host said it was.
 *
 * `HostFingerprintRow` in `contracts/host_fingerprint.py`, in its field order.
 * What each column means is written there and nowhere else.
 */
export interface HostFingerprintRow {
	version?: string;
	date: string;
	run_id: string;
	job?: ServerJob;
	shard: number;
	fingerprint?: string | null;
	cpu_model?: string | null;
	cpu_vendor?: string | null;
	cpu_family?: number | null;
	cpu_model_number?: number | null;
	cpu_stepping?: number | null;
	microcode?: string | null;
	cores?: number | null;
	threads?: number | null;
	l3_cache_bytes?: number | null;
	mhz_max?: number | null;
	mhz_at_probe?: number | null;
	flags?: string;
	boot_seconds?: number | null;
	memcpy_gib_s?: number | null;
	memcpy_probe_mib?: number | null;
	vm_size?: string | null;
	vm_location?: string | null;
	vm_zone?: string | null;
	vm_fault_domain?: string | null;
	runner_name?: string | null;
	measured_at?: string | null;
	model_load_ms?: number | null;
	job_seconds?: number | null;
	server_prompt_tokens?: number | null;
	server_prompt_seconds?: number | null;
}

/** One job's machine, as the host reported it.
 *
 * The row above with every key present. The contract marks a column optional
 * because a payload may leave it out; this reader never does - an absent cell
 * arrives as null, which is the reading "nobody took it" rather than a key that
 * is not there. Derived rather than restated, so a column added to the row
 * arrives here without an edit.
 *
 * The fingerprint is the one cell narrowed past the contract, and that is a
 * fact about this reader rather than about the row: a line carrying no digest
 * is skipped below, so every row that reaches a caller has one.
 */
export type HostFingerprint = Required<HostFingerprintRow> & { fingerprint: string };

/** Every column of the row above, in its order: what a read asks the door for.
 *
 * Written as a set keyed by the interface, so the compiler refuses a column the
 * interface names and this set does not, and a name the interface does not
 * know - and the interface is the copy the field-set test already holds to the
 * contract. A second list that could drift is the one thing this is not.
 */
export const HOST_FINGERPRINT_COLUMNS = Object.keys({
	version: true,
	date: true,
	run_id: true,
	job: true,
	shard: true,
	fingerprint: true,
	cpu_model: true,
	cpu_vendor: true,
	cpu_family: true,
	cpu_model_number: true,
	cpu_stepping: true,
	microcode: true,
	cores: true,
	threads: true,
	l3_cache_bytes: true,
	mhz_max: true,
	mhz_at_probe: true,
	flags: true,
	boot_seconds: true,
	memcpy_gib_s: true,
	memcpy_probe_mib: true,
	vm_size: true,
	vm_location: true,
	vm_zone: true,
	vm_fault_domain: true,
	runner_name: true,
	measured_at: true,
	model_load_ms: true,
	job_seconds: true,
	server_prompt_tokens: true,
	server_prompt_seconds: true
} satisfies Record<keyof HostFingerprintRow, true>) as (keyof HostFingerprintRow)[];

function text(cell: string | undefined): string | null {
	const trimmed = (cell ?? '').trim();
	return trimmed === '' ? null : trimmed;
}

function figure(cell: string | undefined): number | null {
	const raw = text(cell);
	if (raw === null) return null;
	const parsed = Number(raw);
	return Number.isFinite(parsed) ? parsed : null;
}

/** The job a cell names, or null where it names nothing this build knows.
 *
 * Matched against the one vocabulary above rather than a second list typed at
 * the call site. A value outside it is a row this build cannot place, and
 * calling it `work` would put an unknown job into the work shards' own count.
 */
function serverJob(cell: string | undefined): ServerJob | null {
	const named = text(cell);
	return SERVER_JOB.find((job) => job === named) ?? null;
}

/** The machine record's rows in `window`, as the text cells the counters read, and
 * how the read went.
 *
 * One row a job a run, as packed. The route reads it once and hands the rows to
 * `fingerprintsOf`, `machineRecordDays` and the counters, so the three cannot
 * answer over different days.
 */
export async function machineRecord(window: TimeWindow, root: string = STATE_ROOT): Promise<LedgerTable> {
	return windowRows(root, 'host-fingerprint', window, HOST_FINGERPRINT_COLUMNS, (start, end) =>
		sliceFromDisk(root, 'host-fingerprint', {
			columns: [...datedFirst(HOST_FINGERPRINT_COLUMNS)],
			from: start,
			to: end
		})
	);
}

/** The machine record's rows as typed rows, one a job.
 *
 * A row with no run id, no fingerprint, or a job this build cannot place is
 * skipped rather than refused: the page degrades to the processor name the
 * counters ledger carries, and a refusal here would take a whole console route
 * down over one stray line (`CLAUDE.md` section 1a).
 */
export function fingerprintsOf(rows: readonly Record<string, string>[]): HostFingerprint[] {
	const found: HostFingerprint[] = [];
	for (const row of rows) {
		const runId = text(row.run_id);
		const fingerprint = text(row.fingerprint);
		const job = serverJob(row.job);
		if (runId === null || fingerprint === null || job === null) continue;
		found.push({
			version: text(row.version) ?? '',
			date: row.date ?? '',
			run_id: runId,
			job,
			shard: figure(row.shard) ?? 0,
			fingerprint,
			cpu_model: text(row.cpu_model),
			cpu_vendor: text(row.cpu_vendor),
			cpu_family: figure(row.cpu_family),
			cpu_model_number: figure(row.cpu_model_number),
			cpu_stepping: figure(row.cpu_stepping),
			microcode: text(row.microcode),
			cores: figure(row.cores),
			threads: figure(row.threads),
			l3_cache_bytes: figure(row.l3_cache_bytes),
			mhz_max: figure(row.mhz_max),
			mhz_at_probe: figure(row.mhz_at_probe),
			// The contract's own shape: the watched flags this host reported, space
			// joined. Empty is a reading and not a gap, so a consumer that wants the
			// set splits it rather than this reader guessing at one.
			flags: text(row.flags) ?? '',
			boot_seconds: figure(row.boot_seconds),
			memcpy_gib_s: figure(row.memcpy_gib_s),
			memcpy_probe_mib: figure(row.memcpy_probe_mib),
			vm_size: text(row.vm_size),
			vm_location: text(row.vm_location),
			vm_zone: text(row.vm_zone),
			vm_fault_domain: text(row.vm_fault_domain),
			runner_name: text(row.runner_name),
			measured_at: text(row.measured_at),
			model_load_ms: figure(row.model_load_ms),
			job_seconds: figure(row.job_seconds),
			server_prompt_tokens: figure(row.server_prompt_tokens),
			server_prompt_seconds: figure(row.server_prompt_seconds)
		});
	}
	return found;
}

/** The dates the machine record holds any row for, whether or not a row names its machine.
 *
 * The fact `fingerprintsOf` cannot carry. A day whose rows all lack a
 * fingerprint is a day the record ran and what it measured about the machine
 * did not survive - the clock's half landed and the probe's did not - which is
 * the whole difference between an instrument that had not started and a
 * measurement that was destroyed. A day with no row at all is a day the record
 * did not run: packing writes an empty file for every quiet day, so an empty
 * file says nothing more than that.
 *
 * Over the same rows the fingerprints are taken from, so the two can never
 * answer over different days.
 */
export function machineRecordDays(rows: readonly Record<string, string>[]): string[] {
	return [...new Set(rows.map((row) => row.date ?? '').filter((date) => date !== ''))];
}

/** The flags a card draws a chip for, in the order the probe records them.
 *
 * Compiled in rather than parsed back out of a file at run time. The contract
 * restates the probe's tuple and refuses to import on a mismatch, and the
 * vocabulary test holds the copy above in step with that contract - so the
 * probe and the page cannot drift apart.
 */
export function watchedFlags(): WatchedFlag[] {
	return [...WATCHED_FLAG];
}
