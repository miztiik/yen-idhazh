import { execFileSync, spawn } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, rmSync, watch } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, relative, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { assertBuild, buildEnvironment, inputFingerprint, REPO, treeFingerprint, writeRecord } from './build-state.ts';
import type { BuildMode, BuildRecord } from './build-state.ts';
import { FRONTEND_GROUPS, groupedSpecs, groupForSpec } from './test-groups.ts';
import { selectionForChange } from './test-scope.ts';
import type { Selection, TestGroup } from './test-scope.ts';
import { playwrightCounts, pytestCounts, requireExecuted } from './test-results.ts';
import type { TestCounts } from './test-results.ts';

type Step = { name: string; exitCode: number; milliseconds: number; tests?: TestCounts };
type RunSelection = { source: string; groups: TestGroup[]; backendFiles: string[] | null; specs: string[]; mode: BuildMode; tooling?: boolean };
export type Result = { id: string; attempt: string; exitCode: number; started: number; finished: number; queueMs: number; steps: Step[]; build?: BuildRecord; selection?: RunSelection };
type RunPolicy = {
	fresh?: boolean;
	requested?: number;
	reusable?: (result: Result) => boolean;
	build?: () => BuildRecord | undefined;
	selection?: RunSelection;
};
type Options = {
	base: string; groups: string[]; specs: string[]; mode: BuildMode;
	list: boolean; fresh: boolean; status: boolean; inside: boolean; python?: string;
};

export function options(args: string[]): Options {
	const { values } = parseArgs({ args, options: {
		base: { type: 'string', default: 'origin/main' },
		group: { type: 'string', multiple: true, default: [] },
		spec: { type: 'string', multiple: true, default: [] },
		mode: { type: 'string', default: 'canary' },
		list: { type: 'boolean', default: false },
		fresh: { type: 'boolean', default: false },
		status: { type: 'boolean', default: false },
		'inside-lock': { type: 'boolean', default: false },
		python: { type: 'string' }
	} });
	if (!['canary', 'real'].includes(values.mode)) throw new Error('--mode must be canary or real.');
	const specs = values.spec.map((name) => name.replace(/^tests\//, ''));
	if (values.group.length && specs.length) throw new Error('Choose --group or --spec, not both.');
	if (specs.includes('whole-day.spec.ts') && (values.mode !== 'real' || specs.length !== 1)) {
		throw new Error('The whole-day spec must run alone with --mode real.');
	}
	if (values.mode === 'real' && (!specs.length || specs.some((name) => !/^(reading-page|layout-overflow|whole-day|item-visual)\.spec\.ts$/.test(name)))) {
		throw new Error('A real-build run requires --spec for reading-page, layout-overflow, whole-day or item-visual.');
	}
	return { base: values.base, groups: values.group, specs, mode: values.mode as BuildMode,
		list: values.list, fresh: values.fresh, status: values.status, inside: values['inside-lock'],
		...(values.python ? { python: values.python } : {}) };
}

export function selection(root: string, opts: Options): Selection {
	const selected = selectionForChange(root, opts.base);
	if (opts.groups.length || opts.specs.length) {
		const asked = opts.groups.flatMap((group) => group === 'all'
			? ['backend', ...FRONTEND_GROUPS] : group === 'browser' ? [...FRONTEND_GROUPS] : [group]);
		for (const name of opts.specs) {
			const group = groupForSpec(name);
			if (!group || !existsSync(join(root, 'frontend/tests', name))) throw new Error(`Unknown spec: ${name}`);
			asked.push(group);
		}
		for (const group of asked) {
			if (!['backend', ...FRONTEND_GROUPS].includes(group)) throw new Error(`Unknown group: ${group}`);
		}
		selected.groups = [...new Set(asked)] as TestGroup[];
		selected.backendFiles = null;
		selected.contracts = opts.groups.includes('all');
		selected.tooling = opts.groups.includes('all');
		selected.reasons = [{ path: 'explicit selection', groups: selected.groups, reason: 'requested groups or specs' }];
	}
	if (selected.backendFiles?.some((file) => !existsSync(join(root, file)))) selected.backendFiles = null;
	return selected;
}

export function pythonModulesFor(selected: Selection): string[] {
	const modules = selected.groups.includes('backend') ? ['pytest', 'xdist', 'ruff', 'mypy'] : [];
	if (selected.tooling && !modules.includes('pytest')) modules.push('pytest');
	if (selected.groups.some((group) => group !== 'logic')) {
		modules.push('pydantic', 'feedparser', 'protego', 'trafilatura', 'onnxruntime', 'tokenizers', 'vl_convert');
	}
	return modules;
}

export function readResult(file: string, id: string): Result | undefined {
	if (!existsSync(file)) return undefined;
	try {
		const result = JSON.parse(readFileSync(file, 'utf8')) as Result;
		for (const step of result.steps ?? []) {
			if (step.exitCode === 0 && ['pytest', 'logic tests', 'browser tests'].includes(step.name)) {
				if (!step.tests) return undefined;
				requireExecuted(step.tests);
			}
		}
		return result.id === id && typeof result.attempt === 'string' && Number.isInteger(result.exitCode)
			&& Array.isArray(result.steps) && result.steps.length > 0
			&& result.steps.every((step) => typeof step.name === 'string' && Number.isInteger(step.exitCode) && Number.isFinite(step.milliseconds))
			&& result.exitCode === (result.steps.find((step) => step.exitCode !== 0)?.exitCode ?? 0)
			&& Number.isFinite(result.started) && Number.isFinite(result.finished)
			&& result.finished >= result.started ? result : undefined;
	} catch {
		return undefined;
	}
}

function alive(pid: number): boolean {
	try { process.kill(pid, 0); return true; } catch { return false; }
}

export function waitForResult(file: string, id: string, pid: number, attempt?: string): Promise<Result> {
	return new Promise((accept, reject) => {
		const started = Date.now();
		const check = () => {
			const result = readResult(file, id);
			if (result && (!attempt || result.attempt === attempt)) { cleanup(); accept(result); }
			else if (!alive(pid) || Date.now() - started > 3_600_000) {
				cleanup(); reject(new Error('The existing run ended without a result, or exceeded the wait limit. Inspect test:changed -- --status.'));
			}
		};
		const watcher = watch(dirname(file), check);
		const timer = setInterval(check, 1000);
		const cleanup = () => { watcher.close(); clearInterval(timer); };
		check();
	});
}

export async function command(name: string, program: string, args: string[], cwd: string, env: NodeJS.ProcessEnv): Promise<Step> {
	console.log(`[checks] ${name}`);
	const started = Date.now();
	const exitCode = await new Promise<number>((accept, reject) => {
		const child = spawn(program, args, { cwd, env, stdio: 'inherit' });
		child.once('error', reject);
		child.once('close', (code) => accept(code ?? 1));
	});
	return { name, exitCode, milliseconds: Date.now() - started };
}

export async function recordRun(directory: string, id: string, work: () => Promise<Step[]>, policy: RunPolicy = {}): Promise<Result> {
	const { fresh = false, requested = 0, reusable = () => true } = policy;
	const file = join(directory, `${id}.json`);
	const cached = readResult(file, id);
	if (cached && reusable(cached) && (!fresh || cached.finished >= requested)) {
		console.log(`[checks] Reusing ${id.slice(0, 12)}: exit ${cached.exitCode}.`);
		return cached;
	}
	const started = Date.now();
	const attempt = randomUUID();
	writeRecord(join(directory, 'active.json'), { id, attempt, pid: process.pid, started });
	let steps: Step[];
	try {
		steps = await work();
		if (!steps.length) throw new Error('No checks executed; an empty result is not a pass.');
	}
	catch (error) {
		console.error(error instanceof Error ? error.message : error);
		steps = [{ name: 'run interrupted', exitCode: 1, milliseconds: Date.now() - started }];
	}
	const build = policy.build?.();
	const result = { id, attempt, exitCode: steps.find((step) => step.exitCode !== 0)?.exitCode ?? 0,
		started, finished: Date.now(), queueMs: requested ? started - requested : 0, steps,
		...(build ? { build } : {}), ...(policy.selection ? { selection: policy.selection } : {}) };
	writeRecord(file, result);
	writeRecord(join(directory, 'latest.json'), result);
	return result;
}

function pythonPath(root: string, asked?: string): string {
	if (asked || process.env.IDHAZH_PYTHON) {
		const explicit = asked ?? process.env.IDHAZH_PYTHON!;
		if (!existsSync(explicit)) throw new Error('The selected Python executable does not exist.');
		return resolve(explicit);
	}
	const candidates = [join(root, '.venv/Scripts/python.exe'), join(root, '.venv/bin/python')];
	const found = candidates.find((candidate) => candidate && existsSync(candidate));
	if (found) return resolve(found);
	return process.platform === 'win32' ? 'python' : 'python3';
}

function npmPath(): string {
	const candidates = [process.env.npm_execpath, join(dirname(process.execPath), 'node_modules/npm/bin/npm-cli.js'), '/usr/share/nodejs/npm/bin/npm-cli.js'];
	const found = candidates.find((candidate) => candidate && existsSync(candidate));
	if (!found) throw new Error('Start this command with npm run test:changed.');
	return found;
}

async function main(args: string[]): Promise<number> {
	const opts = options(args);
	const root = REPO;
	const frontend = join(root, 'frontend');
	const directory = join(root, 'backend/var/checks');
	mkdirSync(directory, { recursive: true });
	if (opts.status) {
		for (const name of ['active.json', 'latest.json']) {
			const file = join(directory, name);
			if (!existsSync(file)) continue;
			const record = JSON.parse(readFileSync(file, 'utf8')) as { id: string; attempt: string; pid?: number };
			const result = readResult(join(directory, `${record.id}.json`), record.id);
			const running = Boolean(record.pid && alive(record.pid) && result?.attempt !== record.attempt);
			console.log(`${name}: ${JSON.stringify({ ...record, ...(name === 'active.json' ? { running } : {}) }, null, 2)}`);
		}
		return 0;
	}
	const selected = selection(root, opts);
	groupedSpecs(join(frontend, 'tests'));
	console.log(`Selected: ${selected.groups.join(', ') || 'whitespace check only'}`);
	for (const item of selected.reasons) console.log(`  ${item.path}: ${item.reason} -> ${item.groups.join(', ') || 'no code suite'}`);
	if (selected.groups.includes('backend')) console.log(`Backend files: ${selected.backendFiles?.join(', ') || 'full suite'}`);
	console.log(`Build: ${selected.groups.some((group) => group !== 'backend' && group !== 'logic') ? opts.mode : 'none'}`);
	console.log(`Test tooling: ${selected.tooling ? 'selected' : 'not selected'}`);
	if (opts.list) return 0;
	if (!selected.groups.length) return (await command('whitespace', 'git', ['diff', '--check'], root, process.env)).exitCode;
	const python = pythonPath(root, opts.python);
	const npm = npmPath();
	const env: NodeJS.ProcessEnv = { ...process.env, PYTHONPATH: join(root, 'backend'), IDHAZH_PYTHON: python,
		SKIP_CONSOLE_SUITE: 'false', IDHAZH_TEST_BUILD: opts.mode };
	for (const name of ['DIGEST_ROOT', 'STATE_ROOT', 'TELEMETRY_ROOT', 'PYTEST_ADDOPTS']) delete env[name];
	const packages: Record<string, string> = {};
	if (selected.groups.some((group) => group !== 'backend')) {
		const manifest = JSON.parse(readFileSync(join(frontend, 'package.json'), 'utf8')) as {
			dependencies?: Record<string, string>; devDependencies?: Record<string, string>
		};
		for (const name of Object.keys({ ...manifest.dependencies, ...manifest.devDependencies }).sort()) {
			const installed = join(frontend, 'node_modules', name, 'package.json');
			if (!existsSync(installed)) throw new Error(`Missing ${name}; run npm ci in frontend before checking.`);
			packages[name] = (JSON.parse(readFileSync(installed, 'utf8')) as { version: string }).version;
		}
		if (selected.groups.some((group) => group !== 'backend' && group !== 'logic')) {
			const require = createRequire(join(frontend, 'package.json'));
			const { chromium } = require('@playwright/test') as { chromium: { executablePath(): string } };
			if (!existsSync(chromium.executablePath())) throw new Error('Chromium is missing; run npx playwright install chromium in frontend before checking.');
		}
	}
	const modules = pythonModulesFor(selected);
	const versions = modules.length ? execFileSync(python, ['-c',
		'import importlib, importlib.metadata, json, sys; names=json.loads(sys.argv[1]); [importlib.import_module(name) for name in names]; print(json.dumps({"python":sys.version,"packages":sorted((package.metadata["Name"], package.version) for package in importlib.metadata.distributions())}))',
		JSON.stringify(modules)], { cwd: root, env, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }) : null;
	const source = inputFingerprint(root);
	const id = createHash('sha256').update(JSON.stringify({ source, versions, packages, node: process.version,
		environment: buildEnvironment(env), groups: selected.groups, files: selected.backendFiles,
		contracts: selected.contracts, tooling: selected.tooling, mode: opts.mode, specs: opts.specs })).digest('hex');
	const resultFile = join(directory, `${id}.json`);
	const requested = Number(process.env.IDHAZH_CHECK_REQUESTED ?? Date.now());
	const needsBuild = selected.groups.some((group) => group !== 'backend' && group !== 'logic');
	const reusable = (result: Result): boolean => {
		if (!needsBuild) return true;
		try {
			const build = assertBuild(root, opts.mode, env);
			return JSON.stringify(result.build) === JSON.stringify(build);
		} catch { return false; }
	};
	if (!opts.inside) {
		const activeFile = join(directory, 'active.json');
		if (existsSync(activeFile)) {
			const active = JSON.parse(readFileSync(activeFile, 'utf8')) as { id: string; attempt: string; pid: number };
			if (active.id === id && alive(active.pid)) {
				console.log(`Joining existing run ${id.slice(0, 12)}; no second test process will start.`);
				const result = await waitForResult(resultFile, id, active.pid, active.attempt);
				if (inputFingerprint(root) !== source || (result.exitCode === 0 && !reusable(result))) {
					throw new Error('The completed run no longer matches this tree or build. Select the checks again.');
				}
				return result.exitCode;
			}
		}
	}
	let cached = readResult(resultFile, id);
	if (cached && !reusable(cached)) cached = undefined;
	if (cached && (!opts.fresh || (opts.inside && cached.finished >= requested))) {
		console.log(`Reusing completed run ${id.slice(0, 12)}: exit ${cached.exitCode}. Use --fresh to rerun unchanged inputs.`);
		return cached.exitCode;
	}
	if (!opts.inside) {
		const lockArgs = selected.groups.every((group) => group === 'logic')
			? ['--lock-file', join(directory, 'logic.lock')] : [];
		return (await command('waiting for the test slot', python,
			[join(root, 'backend/utilities/gate_lock.py'), '--require-lock', ...lockArgs, '--', process.execPath,
				join(frontend, 'scripts/run-checks.ts'), ...args, '--inside-lock'], root,
			{ ...env, IDHAZH_CHECK_EXPECTED: id, IDHAZH_CHECK_REQUESTED: String(Date.now()) })).exitCode;
	}
	if (process.env.IDHAZH_CHECK_EXPECTED !== id) throw new Error('Inputs changed while waiting. Rerun test:changed to select the new inputs.');
	let testedBuild: BuildRecord | undefined;
	const result = await recordRun(directory, id, async () => {
		const steps: Step[] = [];
		const run = async (name: string, program: string, argv: string[], cwd = root, stepEnv = env) => {
			const step = await command(name, program, argv, cwd, stepEnv);
			steps.push(step);
			if (step.exitCode !== 0) throw new Error(`${name} failed with exit ${step.exitCode}; later checks were not run.`);
			return step;
		};
		try {
			await run('whitespace', 'git', ['diff', '--check']);
			if (selected.groups.includes('backend')) {
				await run('ruff', python, ['-m', 'ruff', 'check', '.']);
				await run('mypy', python, ['-m', 'mypy']);
				const report = join(directory, `${id}.xml`);
				rmSync(report, { force: true });
				const step = await run('pytest', python, ['-m', 'pytest', '-o', 'addopts=', '-q', '-n', selected.backendFiles ? '0' : 'auto',
					`--junitxml=${report}`, ...(selected.backendFiles ?? [])]);
				step.tests = pytestCounts(python, report, env);
			}
			if (selected.contracts) {
				const before = treeFingerprint(join(root, 'schemas'));
				await run('schema export', python, ['-m', 'idhazh.contracts.export']);
				if (treeFingerprint(join(root, 'schemas')) !== before) {
					throw new Error('Schema export changed generated files. Review them and rerun the selected checks.');
				}
			}
			if (selected.groups.some((group) => group !== 'backend')) {
				await run('svelte-check', process.execPath, [npm, 'run', 'check'], frontend);
			}
			if (selected.tooling) {
				await run('test tooling', process.execPath, [npm, 'run', 'test:tooling'], frontend);
			}
			const filters = opts.specs.map((name) => `tests/${name}`);
			if (selected.groups.includes('logic')) {
				const report = join(directory, `${id}-logic.json`);
				rmSync(report, { force: true });
				const step = await run('logic tests', process.execPath, [npm, 'run', 'test:logic', '--', '--forbid-only', '--reporter=list,json', ...filters],
					frontend, { ...env, PLAYWRIGHT_JSON_OUTPUT_NAME: report });
				step.tests = playwrightCounts(report);
			}
			const browserGroups = selected.groups.filter((group) => group !== 'backend' && group !== 'logic');
			if (browserGroups.length) {
				try { assertBuild(root, opts.mode, env); }
				catch {
					if (opts.mode === 'canary') await run('canary fixtures', python, ['backend/utilities/build_canary_day.py']);
					await run(`${opts.mode} build`, process.execPath, [npm, 'run', opts.mode === 'canary' ? 'build:canary' : 'build'], frontend);
				}
				testedBuild = assertBuild(root, opts.mode, env);
				const report = join(directory, `${id}-browser.json`);
				rmSync(report, { force: true });
				const wholeDay = opts.specs.includes('whole-day.spec.ts');
				const projects = wholeDay ? [] : browserGroups.map((group) => `--project=${group}`);
				const step = await run('browser tests', process.execPath, [npm, 'run', wholeDay ? 'test:whole-day' : 'test:browser', '--', '--forbid-only', '--max-failures=1', '--reporter=list,json',
					...projects, ...filters], frontend,
					{ ...env, PLAYWRIGHT_JSON_OUTPUT_NAME: report });
				step.tests = playwrightCounts(report);
				if (JSON.stringify(testedBuild) !== JSON.stringify(assertBuild(root, opts.mode, env))) {
					throw new Error('The build changed while browser checks were running.');
				}
			}
			if (inputFingerprint(root) !== source) throw new Error('Inputs changed during the checks; this result cannot certify the new tree.');
		} catch (error) {
			console.error(error instanceof Error ? error.message : error);
			if (!steps.some((step) => step.exitCode !== 0)) steps.push({ name: 'input verification', exitCode: 1, milliseconds: 0 });
		}
		return steps;
	}, { fresh: true, requested, reusable, build: () => testedBuild,
		selection: { source, groups: selected.groups, backendFiles: selected.backendFiles, specs: opts.specs, mode: opts.mode, tooling: selected.tooling } });
	console.log(`Result: exit ${result.exitCode}; queue/startup ${(result.queueMs / 1000).toFixed(1)}s; checks ${((result.finished - result.started) / 1000).toFixed(1)}s.`);
	console.log(`Record: ${relative(root, resultFile).replaceAll('\\', '/')}`);
	return result.exitCode;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
	main(process.argv.slice(2)).then((code) => { process.exitCode = code; }).catch((error: unknown) => {
		console.error(error instanceof Error ? error.message : error);
		process.exitCode = 1;
	});
}
