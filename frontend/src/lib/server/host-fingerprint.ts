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
 * **The flag vocabulary comes from the generated schema, never from a list
 * typed here.** `schemas/machine-panels.schema.json` is generated from
 * `backend/idhazh/contracts/machine_panels.py`, which restates the probe's own
 * `WATCHED_FLAGS`, so the twelve chips a card draws cannot fall out of step with
 * the twelve the probe records. A hand-written copy is what the drift gate
 * exists to make impossible, and the page would have carried the eleventh flag
 * for a month before anybody noticed.
 *
 * Nothing here is published. It sits under `$lib/server/` so SvelteKit refuses
 * to bundle it for a browser, the same place and for the same reason as
 * `runtime-counters.ts`, and it adds no published telemetry column.
 */

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
// Relative, not `$lib`, for the reason in `runtime-counters.ts`: the browser
// suite loads this module in plain Node, where no Vite alias resolves.
import { dayShardFiles, LEDGER_WINDOW_DAYS, readDayShards, REPO_ROOT, STATE_ROOT } from './payload';

/** One job's machine, as the host reported it. Absence is null, never zero. */
export interface HostFingerprint {
	date: string;
	runId: string;
	/** The workflow job: `plan`, `work`, `assemble`, `visuals`, `runtime`. */
	job: string;
	/** The shard inside that job. A single-shard job records 0. */
	shard: number;
	/** Sixteen hex characters over the cells that cannot change inside a job. */
	fingerprint: string;
	cpuModel: string | null;
	cpuFamily: number | null;
	cpuModelNumber: number | null;
	cpuStepping: number | null;
	microcode: string | null;
	l3CacheBytes: number | null;
	/** The watched flags this host reported. Empty is a reading, not a gap. */
	flags: string[];
	memcpyGibPerSecond: number | null;
	/** The buffer each side of the copy used. Zero means the probe was off. */
	memcpyProbeMib: number | null;
	vmSize: string | null;
	vmLocation: string | null;
	vmZone: string | null;
	vmFaultDomain: string | null;
}

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

/** The newest `days` day files of the machine record, as typed rows.
 *
 * A row with no run id or no fingerprint is skipped rather than refused: the
 * page degrades to the processor name the counters ledger carries, and a
 * refusal here would take a whole console route down over one stray line
 * (`CLAUDE.md` section 1a).
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
		if (runId === null || fingerprint === null) continue;
		found.push({
			date: row.date ?? '',
			runId,
			job: text(row.job) ?? 'work',
			shard: figure(row.shard) ?? 0,
			fingerprint,
			cpuModel: text(row.cpu_model),
			cpuFamily: figure(row.cpu_family),
			cpuModelNumber: figure(row.cpu_model_number),
			cpuStepping: figure(row.cpu_stepping),
			microcode: text(row.microcode),
			l3CacheBytes: figure(row.l3_cache_bytes),
			flags: (text(row.flags) ?? '').split(/\s+/).filter((flag) => flag !== ''),
			memcpyGibPerSecond: figure(row.memcpy_gib_s),
			memcpyProbeMib: figure(row.memcpy_probe_mib),
			vmSize: text(row.vm_size),
			vmLocation: text(row.vm_location),
			vmZone: text(row.vm_zone),
			vmFaultDomain: text(row.vm_fault_domain)
		});
	}
	return found;
}

/** Where the generated schema for the machine panels sits. */
export const MACHINE_PANELS_SCHEMA = join(REPO_ROOT, 'schemas', 'machine-panels.schema.json');

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
 * Read out of the generated schema rather than declared here. The schema is
 * generated from the contract, the contract restates the probe's tuple and
 * refuses to import on a mismatch, and CI regenerates the schema and fails on a
 * diff - so the three cannot drift apart and this module holds no copy at all.
 *
 * **An absent or unreadable schema hands back nothing**, and the panel then says
 * the instruction set was not read rather than drawing zero chips as if the
 * machine had no flags (section 1a). The build would have failed long before
 * this on any checkout where the file is really missing.
 */
export function watchedFlags(path: string = MACHINE_PANELS_SCHEMA): string[] {
	if (!existsSync(path)) return [];
	const schema = JSON.parse(readFileSync(path, 'utf8')) as {
		$defs?: { WatchedFlag?: { enum?: unknown } };
	};
	const named = schema.$defs?.WatchedFlag?.enum;
	if (!Array.isArray(named)) return [];
	return named.filter((flag): flag is string => typeof flag === 'string');
}
