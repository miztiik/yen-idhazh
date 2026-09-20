/** What machine each job of a run drew, read at build time from `state/`.
 *
 * `state/host-fingerprint/<YYYY>/<MM>/<DD>.csv` has been written since
 * 2026-09-16 and, until this module, nothing read a cell of it. One row a job:
 * the processor's family, model and stepping, the instruction-set flags an
 * inference runtime dispatches on, the cache, the memory bandwidth, and the
 * platform's own name for where it put the machine
 * (`docs/reference/host-metrics.md`).
 *
 * **Bounded, like every other read on this route.** It takes the day files a
 * window reaches and no more, so another published day adds a file this call
 * never opens once the cover is filled (`CLAUDE.md` Guardrail #12).
 *
 * **The row shape and the flag vocabulary are generated, never typed here.**
 * `../../contracts/host-fingerprint-row` is emitted from
 * `backend/idhazh/contracts/host_fingerprint.py` by the same command that
 * writes `schemas/`, and CI regenerates both and fails on any diff. So a column
 * added to the contract lands here as a compile error on the object below
 * rather than as a cell nobody reads, and the twelve chips a card draws cannot
 * fall out of step with the twelve the probe records. A hand-written copy is
 * what the drift gate exists to make impossible, and the page would have
 * carried the eleventh flag for a month before anybody noticed.
 *
 * Nothing here is published. It sits under `$lib/server/` so SvelteKit refuses
 * to bundle it for a browser, the same place and for the same reason as
 * `machine-counters.ts`, and it adds no published telemetry column.
 */

import { join } from 'node:path';
// Relative, not `$lib`, for the reason in `machine-counters.ts`: the browser
// suite loads this module in plain Node, where no Vite alias resolves. The
// generated contracts are reached the same way and for the same reason.
import {
	SERVER_JOB,
	type HostFingerprintRow,
	type ServerJob
} from '../../contracts/host-fingerprint-row';
import { WATCHED_FLAG, type WatchedFlag } from '../../contracts/machine-panels';
import { dayShardFiles, LEDGER_WINDOW_DAYS, readDayShards, STATE_ROOT } from './payload';

/** One job's machine, as the host reported it.
 *
 * The generated row with every key present. The contract marks a column
 * optional because a payload may leave it out; this reader never does - an
 * absent cell arrives as null, which is the reading "nobody took it" rather
 * than a key that is not there. Derived rather than restated, so a column added
 * to the contract arrives here without an edit.
 *
 * The fingerprint is the one cell narrowed past the contract, and that is a
 * fact about this reader rather than about the row: a line carrying no digest
 * is skipped below, so every row that reaches a caller has one.
 */
export type HostFingerprint = Required<HostFingerprintRow> & { fingerprint: string };

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
 * Matched against the generated vocabulary rather than a list typed here. A
 * value outside it is a row this build cannot place, and calling it `work`
 * would put an unknown job into the work shards' own count.
 */
function serverJob(cell: string | undefined): ServerJob | null {
	const named = text(cell);
	return SERVER_JOB.find((job) => job === named) ?? null;
}

/** The newest `days` day files of the machine record, as typed rows.
 *
 * A row with no run id, no fingerprint, or a job this build cannot place is
 * skipped rather than refused: the page degrades to the processor name the
 * counters ledger carries, and a refusal here would take a whole console route
 * down over one stray line (`CLAUDE.md` section 1a).
 */
export function hostFingerprints(
	days: number = LEDGER_WINDOW_DAYS,
	root: string = STATE_ROOT
): HostFingerprint[] {
	const table = readDayShards(join(root, 'host-fingerprint'), days);
	const found: HostFingerprint[] = [];
	for (const row of table.rows) {
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

/** The dates the machine record opened a day file for, whether or not it kept a row.
 *
 * The fact `hostFingerprints` cannot carry. A day with no file is a day the
 * record did not run, and a day whose file holds only its header is a day it
 * ran and what it wrote did not survive - which is the whole difference between
 * an instrument that had not started and a measurement that was destroyed.
 *
 * Bounded by the same cover and the same call the rows are read with, so the
 * two can never answer over different days.
 */
export function machineRecordDays(
	days: number = LEDGER_WINDOW_DAYS,
	root: string = STATE_ROOT
): string[] {
	return dayShardFiles(join(root, 'host-fingerprint'), days).map((shard) => shard.date);
}

/** The flags a card draws a chip for, in the order the probe records them.
 *
 * The generated vocabulary, compiled in rather than parsed back out of a file
 * at run time. The contract restates the probe's tuple and refuses to import on
 * a mismatch, one command writes both the schema and this constant from that
 * contract, and CI regenerates both and fails on a diff - so the probe, the
 * schema and the page cannot drift apart and this module holds no copy at all.
 */
export function watchedFlags(): WatchedFlag[] {
	return [...WATCHED_FLAG];
}
