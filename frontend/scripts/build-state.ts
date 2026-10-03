import { execFileSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, readdirSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const REPO = fileURLToPath(new URL('../../', import.meta.url));
export type BuildMode = 'canary' | 'real';
export type BuildRecord = { mode: BuildMode | 'custom'; inputs: string; output: string };

export function buildEnvironment(env: NodeJS.ProcessEnv): Record<string, string> {
	return {
		BASE_PATH: env.BASE_PATH ?? '', BUILD_VERSION: env.BUILD_VERSION ?? '',
		CANARY_BUILD: env.CANARY_BUILD ?? ''
	};
}

export function writeRecord(file: string, record: unknown): void {
	mkdirSync(dirname(file), { recursive: true });
	const temporary = `${file}.${randomUUID()}.tmp`;
	writeFileSync(temporary, `${JSON.stringify(record, null, 2)}\n`, 'utf8');
	renameSync(temporary, file);
}

/** Enumerate one generated build or canary run directory, never a committed tree. */
function filesUnder(root: string): string[] {
	if (!existsSync(root)) return [];
	return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
		const path = join(root, entry.name);
		return entry.isDirectory() ? filesUnder(path) : [path];
	}).sort();
}

/** The bytes of a file, or null when it is not there. One open, never two. */
function contentOf(path: string): Buffer | null {
	try {
		return readFileSync(path);
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code === 'ENOENT') return null;
		throw error;
	}
}

function hashFiles(root: string, paths: string[]): string {
	const hash = createHash('sha256');
	for (const path of paths.sort()) {
		hash.update(relative(root, path).replaceAll('\\', '/'));
		hash.update('\0');
		const content = contentOf(path);
		hash.update(content ? 'present\0' : 'missing\0');
		if (content) hash.update(content);
		hash.update('\0');
	}
	return hash.digest('hex');
}

function gitPaths(root: string, args: string[]): string[] {
	const listed = execFileSync('git', ['-C', root, ...args, '-z'], {
		encoding: 'utf8', maxBuffer: 64 * 1024 * 1024
	});
	return listed.split('\0').filter(Boolean);
}

/** Hash Git's named committed tree, working diff and non-ignored untracked files.
 * Git supplies object identity; this code never lists the committed repository.
 * Build and check records use the same complete set of inputs. */
export function inputFingerprint(root: string, _purpose: 'build' | 'checks' = 'checks'): string {
	const options = { encoding: 'utf8' as const, maxBuffer: 64 * 1024 * 1024 };
	const tree = execFileSync('git', ['-C', root, 'rev-parse', 'HEAD^{tree}'], options).trim();
	const diff = execFileSync('git', ['-C', root, 'diff', 'HEAD', '--binary', '--no-ext-diff'], options);
	const hash = createHash('sha256').update(tree).update('\0').update(diff).update('\0');
	for (const path of gitPaths(root, ['ls-files', '--others', '--exclude-standard']).sort()) {
		hash.update(path);
		hash.update('\0');
		const content = contentOf(join(root, path));
		hash.update(content ? 'present\0' : 'missing\0');
		if (content) hash.update(content);
		hash.update('\0');
	}
	return hash.digest('hex');
}

/** The fingerprinted paths git reports as changed, as a sentence or as nothing.
 *
 * This runs only after certification fails and names Git's current changes.
 *
 * A tree already dirty at capture is listed too. A failed diagnostic must not
 * replace the build failure, so an unavailable Git omits this optional note.
 */
export function changedInputNote(root: string, _purpose: 'build' | 'checks' = 'checks'): string {
	let reported = '';
	try {
		reported = execFileSync('git', ['-C', root, 'status', '--porcelain=v1', '-z', '--untracked-files=all'], {
			encoding: 'utf8', maxBuffer: 16 * 1024 * 1024
		});
	} catch {
		return '';
	}
	const entries = reported.split('\0');
	const changed: string[] = [];
	for (let index = 0; index < entries.length; index += 1) {
		const entry = entries[index];
		if (!entry) continue;
		changed.push(entry.slice(3));
		// A rename or a copy spends a second field on the name it came from.
		if (/^[RC]/.test(entry)) index += 1;
	}
	const named = [...new Set(changed)].sort();
	if (named.length === 0) return '';
	const shown = named.slice(0, 10).join(', ');
	const rest = named.length > 10 ? `, and ${named.length - 10} more` : '';
	return `Changed in the working tree: ${shown}${rest}. `;
}

function buildInputs(root: string, mode: BuildRecord['mode'], env: NodeJS.ProcessEnv): string {
	const buildEnv = mode === 'canary' ? { ...env, CANARY_BUILD: '1' } : env;
	const hash = createHash('sha256').update(inputFingerprint(root, 'build')).update(process.version)
		.update(JSON.stringify(buildEnvironment(buildEnv)));
	if (mode === 'canary') {
		const canary = join(root, 'backend/var/canary');
		hash.update(hashFiles(canary, filesUnder(canary)));
	}
	return hash.digest('hex');
}

function outputFingerprint(root: string): string {
	const build = join(root, 'frontend/build');
	const served = join(root, 'frontend/.svelte-kit/output');
	if (!existsSync(join(build, 'index.html')) || !existsSync(served)) {
		throw new Error('The build or the SvelteKit preview output is missing.');
	}
	return hashFiles(root, [...filesUnder(build), ...filesUnder(served)]);
}

export function buildMode(root: string, env: NodeJS.ProcessEnv): BuildRecord['mode'] {
	const overrides = ['DIGEST_ROOT', 'STATE_ROOT', 'TELEMETRY_ROOT'] as const;
	if (overrides.every((name) => !env[name])) return 'real';
	const canary = resolve(root, 'backend/var/canary');
	const expected = [join(canary, 'digest'), join(canary, 'state'), join(canary, 'state/telemetry')];
	return overrides.every((name, index) => env[name] && relative(expected[index]!, resolve(env[name]!)) === '')
		? 'canary' : 'custom';
}

export function recordBuild(root: string, mode: BuildRecord['mode'], env: NodeJS.ProcessEnv = process.env): BuildRecord {
	const record = { mode, inputs: buildInputs(root, mode, env), output: outputFingerprint(root) };
	writeRecord(join(root, 'backend/var/checks/build.json'), record);
	return record;
}

export function beginBuild(root: string, mode: BuildRecord['mode'], env: NodeJS.ProcessEnv = process.env): void {
	rmSync(join(root, 'backend/var/checks/build.json'), { force: true });
	writeRecord(join(root, 'backend/var/checks/build-start.json'), { mode, inputs: buildInputs(root, mode, env) });
}

export function completeBuild(root: string, mode: BuildRecord['mode'], env: NodeJS.ProcessEnv = process.env): BuildRecord {
	const started = join(root, 'backend/var/checks/build-start.json');
	if (!existsSync(started)) throw new Error('The build has no start record. Run npm run build.');
	const previous = JSON.parse(readFileSync(started, 'utf8')) as Pick<BuildRecord, 'mode' | 'inputs'>;
	const output = outputFingerprint(root);
	const inputs = buildInputs(root, mode, env);
	if (previous.mode !== mode || previous.inputs !== inputs) {
		throw new Error('Build inputs changed during compilation; the output was not certified. Build again.');
	}
	const record = { mode, inputs, output };
	writeRecord(join(root, 'backend/var/checks/build.json'), record);
	rmSync(started);
	return record;
}

export function assertBuild(root: string, mode: BuildMode, env: NodeJS.ProcessEnv = process.env): BuildRecord {
	const file = join(root, 'backend/var/checks/build.json');
	const help = 'Use npm run test:changed to prepare the selected tests, or rebuild in the required mode.';
	if (!existsSync(file)) throw new Error(`No verified ${mode} build. ${help}`);
	const record = JSON.parse(readFileSync(file, 'utf8')) as BuildRecord;
	if (record.mode !== mode) throw new Error(`Expected a ${mode} build; found ${record.mode}. ${help}`);
	if (record.inputs !== buildInputs(root, mode, env)) {
		throw new Error(`The ${mode} build has stale inputs. ${changedInputNote(root, 'build')}${help}`);
	}
	if (record.output !== outputFingerprint(root)) throw new Error(`The ${mode} build output changed. ${help}`);
	return record;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
	const mode = buildMode(REPO, process.env);
	if (process.argv[2] === '--begin') {
		beginBuild(REPO, mode);
		console.log(`Captured ${mode} build inputs before compilation.`);
	} else if (process.argv[2] === '--complete') {
		completeBuild(REPO, mode);
		console.log(`Verified ${mode} build inputs and output after compilation.`);
	} else {
		throw new Error('Choose --begin or --complete; use npm run build for both.');
	}
}
