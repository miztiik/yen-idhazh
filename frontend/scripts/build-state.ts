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

export function treeFingerprint(root: string): string {
	return hashFiles(root, filesUnder(root));
}

/** Whether a path's content can change what a run is certifying.
 *
 * **The rule, written down so the next file of this kind needs no second
 * visit.** An input is any tracked or untracked file that a program in this
 * repository reads. Exactly two kinds are not, and the list below holds nothing
 * else. One is a tree this tooling itself writes: `backend/var/`, and the
 * installed, built, reported and compiled trees under `frontend/`. The other is
 * prose no program reads: `docs/`, `TODO/`, the authored agent material, and the
 * three markdown files at the root. A `build` run drops a third kind - the tests
 * and the harness that selects and runs them, neither of which can change the
 * built site, so a test edit must not cost a rebuild.
 *
 * **A ledger under `state/` is an input under this rule and stays one**, because
 * the console pages are prerendered from `state/`. So a run that finds one
 * changed underneath it is not being told a lie by this list; it has a producer
 * writing where it should not, and the answer belongs at that producer. That was
 * defect 20, and the producer was `idhazh validate-days` filing receipts about a
 * scratch tree into `state/day-validations.csv`. `changedInputNote` names the
 * file so the next one costs a line rather than an afternoon.
 */
function isInput(path: string, purpose: 'build' | 'checks'): boolean {
	if (/^(backend\/var\/|frontend\/(node_modules|build|test-results|\.svelte-kit)\/)/.test(path)) return false;
	if (/^(docs\/|TODO\/|\.claude\/|\.github\/(agents|prompts|instructions|skills)\/)/.test(path)) return false;
	if (purpose === 'build' && /^(frontend\/tests\/|frontend\/scripts\/tests\/|backend\/tests\/)/.test(path)) return false;
	if (purpose === 'build' && /^frontend\/(playwright(?:\.logic)?\.config\.ts|scripts\/(test-(groups|scope|results)|run-checks|verified-preview)\.ts)$/.test(path)) return false;
	return !/^(README|AGENTS|CLAUDE)\.md$/.test(path);
}

function gitPaths(root: string, args: string[]): string[] {
	const listed = execFileSync('git', ['-C', root, ...args, '-z'], {
		encoding: 'utf8', maxBuffer: 64 * 1024 * 1024
	});
	return listed.split('\0').filter(Boolean);
}

/** Every tracked path against the hash git already holds for its content.
 *
 * Git hashed each of these when it staged them, so asking the index is the same
 * answer as reading the file - `core.autocrlf` is false and `.gitattributes`
 * pins these paths to LF, so the bytes on disk are the bytes git hashed.
 */
function indexDigests(root: string): Map<string, string> {
	const found = new Map<string, string>();
	for (const entry of gitPaths(root, ['ls-files', '--stage'])) {
		const tab = entry.indexOf('\t');
		const blob = entry.slice(0, tab).split(' ')[1];
		if (tab > 0 && blob) found.set(entry.slice(tab + 1), blob);
	}
	return found;
}

/** What the build was made from, as one hash.
 *
 * The cost follows the working tree's diff, not the repository's size. A tracked
 * file git reports unchanged contributes the hash from the index and is never
 * opened; only what is modified, deleted or untracked is read. That matters
 * because `frontend/public/digest/` is tracked and gains a payload and its
 * pictures on every run, so reading every named path charged this check for the
 * whole archive on a change that touched one file.
 *
 * A file modified and then reverted reads as changed until git refreshes its
 * stat cache, which costs one rebuild and never a wrong certification.
 */
export function inputFingerprint(root: string, purpose: 'build' | 'checks' = 'checks'): string {
	const index = indexDigests(root);
	const unread = new Set(gitPaths(root, ['ls-files', '--modified', '--deleted', '--others', '--exclude-standard']));
	const paths = [...new Set([...index.keys(), ...unread])].filter((path) => isInput(path, purpose));
	const hash = createHash('sha256');
	for (const path of paths.sort()) {
		hash.update(path);
		hash.update('\0');
		const staged = unread.has(path) ? undefined : index.get(path);
		if (staged !== undefined) {
			hash.update('staged\0');
			hash.update(staged);
		} else {
			const content = contentOf(join(root, path));
			hash.update(content ? 'present\0' : 'missing\0');
			if (content) hash.update(content);
		}
		hash.update('\0');
	}
	return hash.digest('hex');
}

/** The fingerprinted paths git reports as changed, as a sentence or as nothing.
 *
 * A stale fingerprint is a fact about every input at once, which is the least
 * useful shape a true statement can have: the reader is told the tree moved and
 * left to find out where. This names the files. It runs only on the failure
 * path, so it costs one `git status` in a run that has already failed.
 *
 * It reports the working tree as it stands rather than a diff against the moment
 * the fingerprint was taken, which is why the sentence says `changed in the
 * working tree` - a tree that was already dirty is listed too. And a diagnostic
 * may never turn a clear failure into an obscure one, so a git that will not
 * answer says nothing at all.
 */
export function changedInputNote(root: string, purpose: 'build' | 'checks' = 'checks'): string {
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
	const named = [...new Set(changed)].filter((path) => isInput(path, purpose)).sort();
	if (named.length === 0) return '';
	const shown = named.slice(0, 10).join(', ');
	const rest = named.length > 10 ? `, and ${named.length - 10} more` : '';
	return `Changed in the working tree: ${shown}${rest}. `;
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
