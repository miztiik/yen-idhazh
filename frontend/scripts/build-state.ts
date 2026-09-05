import { execFileSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, readdirSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const REPO = fileURLToPath(new URL('../../', import.meta.url));
export type BuildMode = 'canary' | 'real';
export type BuildRecord = { mode: BuildMode | 'custom'; inputs: string; output: string };

export function buildEnvironment(env: NodeJS.ProcessEnv): Record<string, string> {
	return { BASE_PATH: env.BASE_PATH ?? '', BUILD_VERSION: env.BUILD_VERSION ?? '' };
}

export function writeRecord(file: string, record: unknown): void {
	mkdirSync(dirname(file), { recursive: true });
	const temporary = `${file}.${randomUUID()}.tmp`;
	writeFileSync(temporary, `${JSON.stringify(record, null, 2)}\n`, 'utf8');
	renameSync(temporary, file);
}

export function filesUnder(root: string): string[] {
	if (!existsSync(root)) return [];
	return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
		const path = join(root, entry.name);
		return entry.isDirectory() ? filesUnder(path) : [path];
	}).sort();
}

function hashFiles(root: string, paths: string[]): string {
	const hash = createHash('sha256');
	for (const path of paths.sort()) {
		hash.update(relative(root, path).replaceAll('\\', '/'));
		hash.update('\0');
		const present = existsSync(path);
		hash.update(present ? 'present\0' : 'missing\0');
		if (present) hash.update(readFileSync(path));
		hash.update('\0');
	}
	return hash.digest('hex');
}

export function treeFingerprint(root: string): string {
	return hashFiles(root, filesUnder(root));
}

export function inputFingerprint(root: string, purpose: 'build' | 'checks' = 'checks'): string {
	const listed = execFileSync('git', ['-C', root, 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], {
		encoding: 'utf8', maxBuffer: 16 * 1024 * 1024
	});
	const paths = [...new Set(listed.split('\0').filter(Boolean))].filter((path) => {
		if (/^(backend\/var\/|frontend\/(node_modules|build|test-results|\.svelte-kit)\/)/.test(path)) return false;
		if (/^(docs\/|TODO\/|\.claude\/|\.github\/(agents|prompts|instructions|skills)\/)/.test(path)) return false;
		if (purpose === 'build' && /^(frontend\/tests\/|frontend\/scripts\/tests\/|backend\/tests\/)/.test(path)) return false;
		if (purpose === 'build' && /^frontend\/(playwright(?:\.logic)?\.config\.ts|scripts\/(test-(groups|scope|results)|run-checks|verified-preview)\.ts)$/.test(path)) return false;
		return !/^(README|AGENTS|CLAUDE)\.md$/.test(path);
	});
	return hashFiles(root, paths.map((path) => join(root, path)));
}

function buildInputs(root: string, mode: BuildRecord['mode'], env: NodeJS.ProcessEnv): string {
	const hash = createHash('sha256').update(inputFingerprint(root, 'build')).update(process.version)
		.update(JSON.stringify(buildEnvironment(env)));
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
	if (record.inputs !== buildInputs(root, mode, env)) throw new Error(`The ${mode} build has stale inputs. ${help}`);
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
