/** How many recorded jobs used each reported L3 capacity on each UTC day? */
import type { FleetJob, FleetOptions, FleetRow, FleetView } from './fleet';
import { fleetIdentities } from './fleet-identity';
import { machineKeys, UNRECORDED_KEY } from './machine-colour';
import { RESERVED_GREY_INK } from './d3/ordered-colour';
import { formatNumber } from '../number-format';

/** Binary cache capacities are stored in bytes and displayed in MiB. */
const BYTES_PER_MIB = 2 ** 20;
const UNKNOWN_CACHE = 'l3:unmeasured';

export function fleetCacheView(jobs: readonly FleetJob[], options: FleetOptions): FleetView {
	const placed = jobs.filter((job) => job.date >= options.start && job.date <= options.end);
	const days = [...new Set(placed.map((job) => job.date))].sort();
	const dayOf = new Map(days.map((day, index) => [day, index]));
	const capacities = [...new Set(jobs.flatMap((job) =>
		job.l3CacheBytes === null ? [] : [job.l3CacheBytes]))].sort((a, b) => b - a);
	const identities = fleetIdentities(options.ramp.rows, options.appearance);
	const resolve = machineKeys(jobs);
	const cacheKey = (job: FleetJob) => job.l3CacheBytes === null ? UNKNOWN_CACHE : `l3:${job.l3CacheBytes}`;
	const present = new Set(placed.map(cacheKey));
	const groups: (number | null)[] = capacities.filter((bytes) => present.has(`l3:${bytes}`));
	if (present.has(UNKNOWN_CACHE)) groups.push(null);
	const rows: FleetRow[] = groups.map((bytes) => {
		const key = bytes === null ? UNKNOWN_CACHE : `l3:${bytes}`;
		const label = bytes === null ? 'L3 not measured'
			: `${formatNumber(bytes / BYTES_PER_MIB, options.numberFormat, { si: false, exact: true })} MiB L3`;
		const rank = bytes === null ? 0 : capacities.indexOf(bytes);
		const share = capacities.length < 2 ? 1
			: 1 - (1 - options.appearance.floor) * rank / (capacities.length - 1);
		const colour = bytes === null ? RESERVED_GREY_INK
			: `color-mix(in oklab, var(--chart-1) ${share * 100}%, var(--chart-identity-highlight))`;
		const top = `color-mix(in oklab, ${colour} ${(1 - options.appearance.floor) * 100}%, var(--chart-identity-highlight))`;
		const gradient = bytes !== null && options.appearance.gradients ? { top, bottom: colour } : null;
		const counts = days.map(() => 0);
		for (const job of placed) {
			if (cacheKey(job) === key) counts[dayOf.get(job.date)!]++;
		}
		return {
			key, label, note: null, colour, drawing: bytes === null ? 'unrecorded' : 'step',
			step: null, rate: null, counts, placements: counts.reduce((sum, count) => sum + count, 0),
			members: [],
			parts: [{
				key, label, colour, gradient, token: bytes === null ? '--chart-8' : '--chart-1',
				swatch: gradient === null ? colour : `${colour} linear-gradient(180deg, ${top}, ${colour})`,
				counts, note: null
			}]
		};
	});
	const rowOf = new Map(rows.map((row) => [row.key, row]));
	const lines: FleetView['lines'] = days.map(() => []);
	for (const job of placed) {
		const identity = identities.get(resolve(job).key);
		if (identity === undefined) throw new Error('The widest host query omitted a recorded machine identity.');
		const row = rowOf.get(cacheKey(job))!;
		lines[dayOf.get(job.date)!].push({
			runId: job.runId, job: job.job, pipelineName: job.pipelineName, taskName: job.taskName,
			shard: job.shard, machine: identity.label, swatch: row.parts[0].swatch,
			l3Cache: row.label, seconds: job.seconds, rate: job.rate, row: row.key
		});
	}
	for (const day of lines) day.sort((a, b) =>
		a.runId.localeCompare(b.runId) ||
		(a.pipelineName ?? a.job ?? '').localeCompare(b.pipelineName ?? b.job ?? '') ||
		(a.taskName ?? '').localeCompare(b.taskName ?? '') || (a.shard ?? -1) - (b.shard ?? -1));
	const lost = (options.lost ?? []).some((day) => day.date >= options.start && day.date <= options.end);
	return {
		days, rows, lines, placements: placed.length, windowDays: options.windowDays,
		daysWithout: Math.max(0, options.windowDays - days.length),
		shape: placed.length >= options.minRows ? 'bars' : 'dots',
		minRows: options.minRows, topKinds: options.topKinds, numberFormat: options.numberFormat,
		mostPlaced: [...rows].sort((a, b) => b.placements - a.placements)[0] ?? null,
		nothing: !options.recording ? 'recording-off'
			: placed.length === 0 ? lost ? 'record-lost' : 'none'
			: lost && placed.every((job) => job.l3CacheBytes === null && resolve(job).key === UNRECORDED_KEY) ? 'record-lost' : null
	};
}
