/** Refuse old planner publication bytes and expose their unavailable covered days. */
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const script = fileURLToPath(new URL('../../packages/ledger-file-writer/src/planner-publication-cli.ts', import.meta.url));
export function projectPlannerPublication(copy, stateRoot) {
	const prefix = 'compact/feed-ingest-plan/';
	const files = copy.files.filter((path) => path.startsWith(prefix) && path.endsWith('.parquet'));
	if (files.length === 0) return copy;
	const indexes = Object.fromEntries(Object.entries(copy.indexes)
		.filter(([path]) => path.startsWith(prefix))
		.map(([path, text]) => [path, JSON.parse(text)]));
	const result = spawnSync('bun', ['run', script], {
		cwd: stateRoot, encoding: 'utf8',
		input: JSON.stringify({ files: files.map((path) => ({ path, ledger: path.split('/')[2] })), indexes }),
	});
	if (result.error || result.status !== 0) {
		throw new Error(`Current planner publication validation failed: ${result.error?.message ?? result.stderr.trim()}`);
	}
	const response = JSON.parse(result.stdout);
	if (!Array.isArray(response.files) || !Array.isArray(response.refused)
		|| typeof response.indexes !== 'object' || response.indexes === null
		|| Object.keys(response.indexes).sort().join('\n') !== Object.keys(indexes).sort().join('\n')
		|| response.files.some((path) => !files.includes(path))
		|| response.refused.some((file) => !files.includes(file.path))
		|| new Set([...response.files, ...response.refused.map((file) => file.path)]).size !== files.length) {
		throw new Error('Planner publication returned a different named file set');
	}
	const refused = new Set(response.refused.map((file) => file.path));
	return {
		...copy, files: copy.files.filter((path) => !refused.has(path)),
		indexes: { ...copy.indexes, ...Object.fromEntries(Object.entries(response.indexes)
			.map(([path, index]) => [path, `${JSON.stringify(index, null, 2)}\n`])) },
		logs: [...copy.logs, ...response.refused.map((file) =>
			`::warning title=Planner publication format refused::${file.path} uses envelope ${file.envelope_version} and row ${file.row_schema_version}; current data was not published, and its covered days are unavailable. Historical files remain unchanged.`)],
	};
}
