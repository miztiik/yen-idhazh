import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';

/**
 * A published site a test builds, laid out the way `frontend/public/` holds one: a digest
 * file for each published day, a telemetry shard for each month it is handed, and the
 * publication list that names exactly those files. Every reader on the site goes through
 * that list rather than a listing of the folder, so a file it does not name is not there.
 */

/** Projection rows by the month shard they are filed in, `YYYY-MM`. A shard may hold a row
 *  dated in another month, as a misfiled one would. Every row of a shard has the same cells. */
export type TelemetryShards = Readonly<Record<string, readonly Readonly<Record<string, string>>[]>>;

export interface BuiltSite {
	site: string;
	/** The digest root, the folder `windowDay()` and `latestDate()` read. */
	digest: string;
	/** The telemetry root, the folder `telemetryRows()` reads. */
	telemetry: string;
}

export function publishedSite(
	site: string,
	{ published = [], telemetry = {} }: { published?: readonly string[]; telemetry?: TelemetryShards }
): BuiltSite {
	mkdirSync(site, { recursive: true });
	const days = published.map((day) => {
		const [year, month, date] = day.split('-');
		const file = path.join(site, 'digest', year!, month!, date!, 'digest.json');
		mkdirSync(path.dirname(file), { recursive: true });
		writeFileSync(file, JSON.stringify({ date: day, items: [] }));
		return { root: 'public', path: `digest/${year}/${month}/${date}/digest.json`, bytes: 0, items: 0 };
	});
	const shards = Object.entries(telemetry).map(([month, rows]) => {
		const columns = Object.keys(rows[0] ?? {});
		const lines = [columns.join(','), ...rows.map((row) => columns.map((column) => row[column] ?? '').join(','))];
		const file = path.join(site, 'telemetry', `${month}.csv`);
		mkdirSync(path.dirname(file), { recursive: true });
		writeFileSync(file, `${lines.join('\n')}\n`);
		return { root: 'public', path: `telemetry/${month}.csv`, bytes: 0, items: rows.length };
	});
	writeFileSync(
		path.join(site, 'publication.json'),
		JSON.stringify({
			version: '2026-10-01',
			changelog: [],
			dates: [...published],
			entries: [...days, ...shards],
			total_bytes: 0,
			total_items: 0
		})
	);
	return { site, digest: path.join(site, 'digest'), telemetry: path.join(site, 'telemetry') };
}
