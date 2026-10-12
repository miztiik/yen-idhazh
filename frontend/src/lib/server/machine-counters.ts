/** Build-time compatibility for callers not moved to the published ledger yet. */
import { daysBetween, type TimeWindow } from '../charts/viewport';
import { machineCounters, type MachineCounters, type MachineLimits } from '../console/machine/counters';
import { inferenceConfig, runConfig } from './config';
import { machineRecord } from './host-fingerprint';
import { itemHealthRows } from './ledger-rows';
import { DIGEST_ROOT, LEDGER_WINDOW_DAYS, loadManifests } from './payload';

export * from '../console/machine/counters';

export async function hostRows(window: TimeWindow): Promise<Record<string, string>[]> {
	return (await machineRecord(window)).rows;
}

export function plannedShards(days = LEDGER_WINDOW_DAYS, root = DIGEST_ROOT): Map<string, number> {
	const found = new Map<string, number>();
	for (const day of loadManifests(root, days)) {
		for (const run of day.records) {
			if (run.shards !== null) found.set(run.runId, run.shards);
		}
	}
	return found;
}

export function machineLimits(): MachineLimits {
	return {
		contextWindow: inferenceConfig().n_ctx,
		jobTimeoutSeconds: runConfig().shard_timeout_minutes * 60
	};
}

export async function loadMachineCounters(window: TimeWindow): Promise<MachineCounters> {
	const hosts = await hostRows(window);
	const health = await itemHealthRows(window);
	return machineCounters(hosts, health.rows, plannedShards(daysBetween(window.start, window.end)), machineLimits());
}
