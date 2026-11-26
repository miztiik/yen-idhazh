/** Which runs the Hardware route counts, and which it refuses.
 *
 * Two ledgers meet here and neither is derived from the other. The machine
 * record carries one row per job. The article record carries one row per item
 * and says which machine shard took it. Serving evidence does not count jobs.
 * A run is the rows of both ledgers that share a run id. Both are read from
 * their packed files through the query door.
 *
 * **A run whose rows contradict each other is refused, never dropped and never
 * half counted.** The page prints the run count and, beside it, each refused
 * run with the reason, so a count that quietly left one out could not be
 * checked.
 *
 * **The planned shard count is never counted off the rows that reported.** A
 * denominator taken from the same rows as its numerator is always equal to it,
 * so a run that filed more shards than its plan split it into, or a shard
 * numbered past the plan, could never be seen. The count comes from the narrow
 * manifest-derived run-shards record and from nowhere else. A run whose
 * manifest predates the cell carries `null`, which is unknown and refuses
 * nothing.
 *
 * This module reads no files and adds no persisted cells.
 *
 * Imports nothing that needs a Vite alias: the browser suite loads this module
 * in plain Node, where no alias resolves.
 */

// Relative, not `$lib`, for the reason in the module docstring.
import { normalizeHostRow } from '../../data/host-fingerprint';
import { DIGEST_PIPELINE } from './serving-speed';

/** One counted run, on the day the page counts it under. */
export interface MachineRun {
	date: string;
}

/** A run whose rows cannot be made into one run, and what stopped it.
 *
 * Never dropped silently. The machine record writes its row in two halves at
 * one key, so a half that disagrees with its partner about a cell is two
 * servers answering for one shard - which cannot be added and cannot be picked
 * between.
 */
export interface RefusedRun {
	runId: string;
	date: string;
	/** Rows the two ledgers hold for the run. */
	rows: number;
	/** Plain words: what could not be reconciled. */
	why: string;
}

/** Every run the two ledgers describe, and every run they could not. */
export interface MachineCounters {
	/** Newest first, by run id. */
	runs: MachineRun[];
	/** Newest first. A page that prints a run count prints this one beside it. */
	refused: RefusedRun[];
}

/** An empty cell is an absent value, never a zero. */
function measured(value: string | undefined): number | null {
	if (value === undefined || value.trim() === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

/** Hardware cells that must agree between a shard's historical halves. */
const HOST_CELLS = [
	'fingerprint',
	'fingerprint_version',
	'cpu_model',
	'cpu_logical_processors'
] as const;

/** Whether the machine record's halves for one shard fill a cell differently. */
function hostHalvesConflict(rows: Record<string, string>[]): boolean {
	const held = new Map<string, string>();
	for (const row of rows) {
		for (const cell of HOST_CELLS) {
			const value = (row[cell] ?? '').trim();
			if (value === '') continue;
			const carried = held.get(cell);
			if (carried !== undefined && carried !== value) return true;
			held.set(cell, value);
		}
	}
	return false;
}

/** The two ledgers' rows for one run, as one run - or the reason they are not.
 *
 * `health` and `hosts` are this run's own rows, already picked out by the
 * caller. `planned` is what its manifest said, which may be nothing.
 */
function oneRun(
	runId: string,
	hosts: Record<string, string>[],
	health: Record<string, string>[],
	planned: number | null
): MachineRun | RefusedRun {
	const rows = hosts.length + health.length;
	const date = hosts[0]?.date ?? health[0]?.date ?? '';
	const refuse = (why: string): RefusedRun => ({ runId, date, rows, why });

	const days = new Set([...hosts, ...health].map((row) => row.date ?? ''));
	if (days.size > 1) {
		return refuse('its rows disagree about which day the run belongs to');
	}

	const hostsByShard = new Map<number, Record<string, string>[]>();
	for (const row of hosts) {
		const shard = measured(row.shard ?? '');
		// A row that does not say which shard it is cannot be merged against any
		// other row, and reading it as shard zero would fold it into a real
		// shard's record.
		if (shard === null) return refuse('a machine record does not say which shard it came from');
		if (!Number.isSafeInteger(shard) || shard < 0) return refuse('a machine record names an invalid shard');
		const normalized = normalizeHostRow(row);
		if (normalized === null) return refuse('a machine record has an unreadable host version or fingerprint algorithm');
		const held = hostsByShard.get(shard);
		if (held === undefined) hostsByShard.set(shard, [normalized]);
		else held.push(normalized);
	}

	const reported = new Set(hostsByShard.keys());
	for (const row of health) {
		// The machine the item's readings were taken on. The row's own writer cells
		// are never read: they name the job that filed the row, not the one it ran on.
		const shard = measured(row.machine_shard ?? '');
		if (shard === null) continue;
		if (!Number.isSafeInteger(shard) || shard < 0) return refuse('an article record names an invalid machine shard');
		reported.add(shard);
	}

	const shards = [...reported].sort((a, b) => a - b);
	for (const shard of shards) {
		if (hostHalvesConflict(hostsByShard.get(shard) ?? [])) {
			return refuse(
				`shard ${shard} filed two machine records that disagree, so two servers ` +
					'answered for one shard and neither can be read over the other'
			);
		}
	}
	if (shards.length === 0) return refuse('neither ledger holds a shard for this run');

	// The plan's own count. Never the count of who answered: those are the same
	// rows the numerator comes from, so the difference this denominator exists to
	// show could never appear.
	if (planned !== null && shards.length > planned) {
		return refuse(
			`${shards.length} shards filed a row for a run the plan split into ${planned}`
		);
	}
	if (planned !== null && shards.some((shard) => shard >= planned)) {
		return refuse(`a shard index sits at or above the run's planned shard count of ${planned}`);
	}

	return { date };
}

/** Only the work job files the rows this route reads.
 *
 * Every job records the machine it drew, and they are not this slice: the plan
 * and assemble jobs run one shard each and serve different weights, so pooling
 * them would answer about a matrix nobody dispatched. A row
 * whose cell is empty is the work job, which is what the contract defaults it
 * to. The same rule `machine.PUBLISHED_JOB` states for the published series.
 */
export const READ_JOB = 'work';

/** Every run the two ledgers describe, newest first.
 *
 * Pure: it takes rows and the planned shard counts, so a test drives a fixture
 * without touching the disk and `countersFrom` is the only thing that knows where
 * the rows come from.
 *
 * Both ledgers are grouped by run in one pass each, and each run is then handed
 * its own rows - one check a row whatever the run count is (Guardrail #12).
 */
export function machineCounters(
	hosts: Record<string, string>[],
	health: Record<string, string>[],
	planned: ReadonlyMap<string, number>
): MachineCounters {
	const byRun = new Map<string, Record<string, string>[]>();
	for (const row of hosts) {
		const runId = row.run_id ?? '';
		if (!runId) continue;
		if (row.pipeline_name
			? row.pipeline_name !== DIGEST_PIPELINE || row.task_name !== READ_JOB
			: !!row.job && row.job !== READ_JOB) continue;
		const held = byRun.get(runId);
		if (held === undefined) byRun.set(runId, [row]);
		else held.push(row);
	}
	const itemsByRun = new Map<string, Record<string, string>[]>();
	for (const row of health) {
		const runId = row.run_id ?? '';
		if (!runId) continue;
		// The same rule the machine rows take above, on the job whose machine took
		// the item's readings. Empty is a row written before that cell was, or the
		// day's census, which names no machine and is skipped by its shard below.
		if ((row.machine_job ?? '') !== '' && row.machine_job !== READ_JOB) continue;
		const held = itemsByRun.get(runId);
		if (held === undefined) itemsByRun.set(runId, [row]);
		else held.push(row);
	}
	const runs: MachineRun[] = [];
	const refused: RefusedRun[] = [];
	// Run ids are `<date>-<n>`, so a plain string sort orders a day's runs
	// correctly and orders the days too - up to run ten of one day, which this
	// pipeline has never reached and which `run.max_parallel` of 4 bounds.
	const ids = [...new Set([...byRun.keys(), ...itemsByRun.keys()])].sort().reverse();
	for (const runId of ids) {
		const result = oneRun(
			runId,
			byRun.get(runId) ?? [],
			itemsByRun.get(runId) ?? [],
			planned.get(runId) ?? null
		);
		if ('why' in result) refused.push(result);
		else runs.push(result);
	}
	return { runs, refused };
}
