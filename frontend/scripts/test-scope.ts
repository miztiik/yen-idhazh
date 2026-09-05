import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { FRONTEND_GROUPS, groupForSpec } from './test-groups.ts';
import type { FrontendGroup } from './test-groups.ts';

export type TestGroup = FrontendGroup | 'backend';
export type Selection = {
	groups: TestGroup[];
	backendFiles: string[] | null;
	contracts: boolean;
	tooling: boolean;
	reasons: { path: string; groups: TestGroup[]; reason: string }[];
};

const ALL: TestGroup[] = ['backend', ...FRONTEND_GROUPS];
const READER: TestGroup[] = ['logic', 'reader', 'publishing'];
const CONSOLE: TestGroup[] = ['logic', 'console', 'publishing'];

/** The operator console's own files.
 *
 * The console's specs are 584 of the browser suite's 997 tests, measured
 * 2026-09-05, and the console is a page one operator opens rather than anything
 * a reader is served. So a pull request buys them only when the change is the
 * console's own; every other change reaches them in `nightly.yml`, within the
 * day. What that costs is stated rather than implied: a shared component or a
 * token edit that breaks the console is found the next morning, not at the
 * pull request.
 */
const CONSOLE_OWNED =
	/^frontend\/(tests\/console[-.]|src\/(routes|lib)\/console\/|src\/lib\/components\/Console[A-Z]|src\/lib\/server\/console-shell\.ts$)/;

function consoleIsTheSubject(paths: readonly string[]): boolean {
	return paths.some((path) => CONSOLE_OWNED.test(path.replaceAll('\\', '/')));
}

export type CiAnswer = { browser: boolean; console: boolean };

/** The two lines the `scope` job writes to `$GITHUB_OUTPUT`.
 *
 * A pure function of the changed paths, so the truth table is checked here at
 * microseconds a case rather than through a temporary git repository and a
 * shell. `backend/tests/test_workflows.py` still drives the real script end to
 * end, on a handful of cases, because the plumbing can break on its own.
 */
export function ciAnswer(paths: readonly string[], isPr: boolean): CiAnswer {
	const selection = selectPaths(paths);
	// A harness change still proves itself on everything: `tooling` covers the
	// selector, the Playwright config and the workflow that reads them.
	const deferred = isPr && !selection.tooling && !consoleIsTheSubject(paths);
	return {
		browser: selection.groups.some((group) => group !== 'backend' && group !== 'logic'),
		console: selection.groups.includes('console') && !deferred
	};
}
const MODULE_TESTS: Record<string, string[]> = {
	discover: ['test_discover', 'test_pipeline'],
	rank: ['test_discover', 'test_pipeline'],
	extract: ['test_extract', 'test_canaries', 'test_evals', 'test_pipeline'],
	sanitize: ['test_extract', 'test_canaries'],
	ledger: ['test_ledger', 'test_pipeline', 'test_telemetry', 'test_publish_telemetry', 'test_publish_source_health'],
	telemetry: ['test_telemetry', 'test_publish_telemetry'],
	publish_telemetry: ['test_publish_telemetry', 'test_telemetry']
};

export function selectPaths(paths: readonly string[]): Selection {
	const groups = new Set<TestGroup>();
	const backendFiles = new Set<string>();
	let fullBackend = false;
	let contracts = false;
	let tooling = false;
	const reasons: Selection['reasons'] = [];
	for (const original of [...new Set(paths)].sort()) {
		const path = original.replaceAll('\\', '/');
		let selected: TestGroup[] = [];
		let reason = 'documentation only';
		if (/^(docs\/|TODO\/|(?:README|AGENTS|CLAUDE)\.md$|\.claude\/|\.github\/(agents|instructions|prompts|skills)\/)/.test(path)) {
			selected = [];
		} else if (/^backend\/tests\/test_[^/]+\.py$/.test(path)) {
			selected = ['backend'];
			backendFiles.add(path);
			reason = 'changed backend test module';
		} else if (/^frontend\/tests\/[^/]+\.spec\.ts$/.test(path)) {
			const group = groupForSpec(path);
			selected = group ? [group] : [...FRONTEND_GROUPS];
			reason = group ? 'changed frontend spec' : 'unmapped spec; all frontend groups';
		} else if (/^frontend\/src\/routes\/(?:console)(?:\/|$)/.test(path)) {
			selected = CONSOLE;
			reason = 'console route and publishing checks';
		} else if (/^frontend\/src\/routes\/archive\//.test(path)) {
			selected = ['logic', 'archive', 'model-search', 'publishing'];
			reason = 'archive route and search consumer';
		} else if (/^frontend\/src\/routes\/(?:\[date\]\/|\+page\.)/.test(path)) {
			selected = READER;
			reason = 'reading route and publishing checks';
		} else if (/^frontend\/src\/lib\/assist\//.test(path)) {
			selected = [...READER, 'archive', 'model-search'];
			reason = 'shared day loading and on-device search';
		} else if (/^frontend\//.test(path)) {
			selected = [...FRONTEND_GROUPS];
			reason = 'shared or unmapped frontend input';
		} else if (/^backend\/idhazh\/[^/]+\.py$/.test(path)) {
			const module = path.split('/').at(-1)!.replace(/\.py$/, '');
			const tests = MODULE_TESTS[module];
			if (tests) {
				for (const name of tests) backendFiles.add(`backend/tests/${name}.py`);
				selected = ['backend'];
				if (['extract', 'sanitize'].includes(module)) selected.push('logic', 'publishing');
				if (['ledger', 'telemetry', 'publish_telemetry'].includes(module)) selected.push(...FRONTEND_GROUPS);
				reason = 'module tests and declared consumers';
			} else {
				selected = ALL;
				fullBackend = true;
				reason = 'unmapped backend dependency; full coverage';
			}
		} else {
			selected = ALL;
			fullBackend = true;
			reason = 'shared or unknown input; full coverage';
		}
		if (/^(config\/|schemas\/|backend\/idhazh\/contracts\/|pyproject\.toml$)/.test(path)) {
			contracts = true;
		}
		if (/^(frontend\/(scripts\/|playwright(?:\.logic)?\.config\.ts$|package(?:-lock)?\.json$)|\.github\/(scripts\/browser-suite-needed\.sh|workflows\/ci\.yml)$|backend\/utilities\/gate_lock\.py$|pyproject\.toml$|unresolved-change-base$|full-ci-run$)/.test(path)) {
			tooling = true;
		}
		for (const group of selected) groups.add(group);
		reasons.push({ path, groups: [...new Set(selected)], reason });
	}
	return {
		groups: ALL.filter((group) => groups.has(group)),
		backendFiles: fullBackend ? null : [...backendFiles].sort(),
		contracts,
		tooling,
		reasons
	};
}

function git(root: string, args: string[]): string {
	return execFileSync('git', ['-C', root, ...args], {
		encoding: 'utf8', maxBuffer: 16 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe']
	});
}

export function changedPaths(root: string, base: string, head = 'HEAD', dirty = true): string[] {
	const ancestor = git(root, ['merge-base', base, head]).trim();
	const lists = [git(root, ['diff', '--name-only', '--no-renames', '-z', `${ancestor}...${head}`])];
	if (dirty) {
		lists.push(git(root, ['diff', '--name-only', '--no-renames', '-z', 'HEAD']));
		lists.push(git(root, ['ls-files', '--others', '--exclude-standard', '-z']));
	}
	return [...new Set(lists.flatMap((list) => list.split('\0').filter(Boolean)))].sort();
}

export function selectionForChange(root: string, base = 'origin/main', head = 'HEAD', dirty = true): Selection {
	try {
		return selectPaths(changedPaths(root, base, head, dirty));
	} catch {
		return selectPaths(['unresolved-change-base']);
	}
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
	const base = process.env.BASE ?? '';
	const head = process.env.HEAD ?? '';
	const isPr = process.env.EVENT === 'pull_request' && base !== '' && head !== '';
	let paths: string[] = ['full-ci-run'];
	if (isPr) {
		try {
			paths = changedPaths(process.cwd(), base, head, false);
		} catch {
			paths = ['unresolved-change-base'];
		}
	}
	if (process.argv.includes('--ci')) {
		const answer = ciAnswer(paths, isPr);
		console.log(`browser=${answer.browser}`);
		console.log(`console=${answer.console}`);
	} else {
		console.log(JSON.stringify(selectPaths(paths), null, 2));
	}
}
