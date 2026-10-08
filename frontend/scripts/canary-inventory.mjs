/** Name the files produced by one generated canary run, never a committed tree. */
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

/** @param {string} root @param {string} [relative] @returns {string[]} */
function runFiles(root, relative = '') {
	return readdirSync(join(root, relative), { withFileTypes: true }).flatMap((entry) => {
		const name = relative ? `${relative}/${entry.name}` : entry.name;
		return entry.isDirectory() ? runFiles(root, name) : [name];
	});
}

/** @param {string} publicRoot @param {string} stateRoot */
export function canaryFiles(publicRoot, stateRoot) {
	const held = runFiles(publicRoot).filter((name) => !name.startsWith('state/') &&
		!name.startsWith('fixture-rows/') && name !== 'publication.json');
	const publicFiles = new Set(held.filter((name) => !name.startsWith('digest/') ||
		/\/(?:digest|run)\.json$/.test(name)));
	for (const name of [...publicFiles].filter((name) => /^digest\/.+\/digest\.json$/.test(name))) {
		const day = JSON.parse(readFileSync(join(publicRoot, ...name.split('/')), 'utf8'));
		for (const item of day.items) {
			if (item.visual?.state === 'rendered' && typeof item.visual.data_path === 'string') {
				publicFiles.add(item.visual.data_path);
			}
		}
	}
	const stateFiles = runFiles(stateRoot).filter((name) =>
		/^(?:raw|compact)\/feed-health\//.test(name) ||
		/^(?:raw|compact)\/content-similarity-judge\/merge-line-holdout-scores\//.test(name));
	return { publicFiles: [...publicFiles].sort(), stateFiles: stateFiles.sort() };
}
