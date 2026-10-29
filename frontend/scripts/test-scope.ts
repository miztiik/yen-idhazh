import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { CHART_VOCABULARY_PAGE, CONSOLE_MODEL_LABELS_PAGE } from './doc-test-inputs.ts';
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

/** A document a test reads is that test's input, not documentation.
 *
 * `chart-vocabulary.spec.ts` reads the chart-type list from this page, so an edit
 * buys the logic group and no browser. The key is the constant the spec reads
 * its page from, so the selector and test cannot name different pages.
 */
const DOC_TEST_INPUTS: Record<string, TestGroup[]> = {
	[CONSOLE_MODEL_LABELS_PAGE]: ['logic'],
	[CHART_VOCABULARY_PAGE]: ['logic']
};

export type CiAnswer = {
	browser: boolean;
	code: boolean;
	modelAbsent: boolean;
	console: boolean;
	robots: boolean;
	validateAll: boolean;
};

/** The module the `robots` job runs on a second interpreter. A change that does
 * not select it cannot move how two interpreters read a `robots.txt`. */
const ROBOTS_TESTS = 'backend/tests/test_extract.py';

/** Anything under here IS the archive, so a change to it has to be re-read. */
const ARCHIVE_TOUCHED = /^frontend\/public\/(digest|telemetry|assist)\//;

/** The check decisions the `scope` job writes to `$GITHUB_OUTPUT`.
 *
 * A pure function of the changed paths, so the truth table is checked here at
 * microseconds a case rather than through a temporary git repository and a
 * shell. `backend/tests/workflows/` still drives the real script end to
 * end, on a handful of cases, because the plumbing can break on its own.
 */
export function ciAnswer(paths: readonly string[], isPr: boolean): CiAnswer {
	const selection = selectPaths(paths);
	// Whether anything but documentation changed. Skipping on this is safe
	// because the documentation branch in `selectPaths` is a closed list of
	// prefixes: a path nobody classified falls to full coverage instead.
	const code = selection.groups.length > 0 || selection.contracts || selection.tooling;
	// The required PR run covers every check that previously ran only after merge.
	const fullPr = code && isPr;
	return {
		browser: fullPr || selection.groups.some((group) => group !== 'backend' && group !== 'logic'),
		code,
		modelAbsent: fullPr || (code && (selection.tooling || selection.contracts || selection.reasons.some(({ path, groups }) => {
			const clean = path.replaceAll('\\', '/');
			if (/^(docs\/|TODO\/|(?:README|AGENTS|CLAUDE)\.md$|frontend\/tests\/)/.test(clean)) return false;
			if (/^frontend\/src\/(routes\/console\/|lib\/(console|charts|data)\/|styles\/)/.test(clean)) return false;
			// A backend-only selection cannot change model asset staging. Unknown
			// inputs still select frontend groups and therefore buy the second build.
			return groups.some((group) => group !== 'backend');
		}))),
		console: fullPr || selection.groups.includes('console'),
		// A full backend selection (null) is an unknown change, so it buys the job.
		robots: fullPr || (selection.backendFiles?.includes(ROBOTS_TESTS) ?? true),
		// The required PR run validates every committed day before merge.
		validateAll: fullPr || (code && (
			selection.contracts ||
			selection.tooling ||
			paths.some((path) => ARCHIVE_TOUCHED.test(path.replaceAll('\\', '/')))
		))
	};
}
// A value is a pytest target, so a package directory stands for every module
// in it - which is what a split left behind where one module used to be.
const MODULE_TESTS: Record<string, string[]> = {
	discover: ['backend/tests/test_discover.py', 'backend/tests/pipeline/'],
	rank: ['backend/tests/test_discover.py', 'backend/tests/pipeline/'],
	extract: [
		'backend/tests/test_extract.py',
		'backend/tests/test_canaries.py',
		'backend/tests/test_evals.py',
		'backend/tests/pipeline/'
	],
	sanitize: ['backend/tests/test_extract.py', 'backend/tests/test_canaries.py'],
	ledger: [
		'backend/tests/test_ledger.py',
		'backend/tests/pipeline/',
		'backend/tests/test_telemetry.py',
		'backend/tests/test_publish_telemetry.py',
		'backend/tests/test_publish_source_health.py'
	],
	telemetry: ['backend/tests/test_telemetry.py', 'backend/tests/test_publish_telemetry.py']
};

// A utility that no stage, build or workflow imports or runs, so a change to it
// can break only its own test module. One that something else reaches stays off
// this list and falls to full coverage.
const UTILITY_TESTS: Record<string, string> = {
	'backend/utilities/doc_load.py': 'backend/tests/test_doc_load.py'
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
		if (DOC_TEST_INPUTS[path]) {
			selected = DOC_TEST_INPUTS[path];
			reason = 'documentation a test reads';
		} else if (/^(docs\/|TODO\/|(?:README|AGENTS|CLAUDE)\.md$|\.claude\/|\.github\/(agents|instructions|prompts|skills)\/)/.test(path)) {
			selected = [];
		} else if (/^backend\/tests\/(?:[^/]+\/)?test_[^/]+\.py$/.test(path)) {
			selected = ['backend'];
			backendFiles.add(path);
			reason = 'changed backend test module';
		} else if (/^frontend\/tests\/[^/]+\.spec\.ts$/.test(path)) {
			const group = groupForSpec(path);
			selected = group ? [group] : [...FRONTEND_GROUPS];
			reason = group ? 'changed frontend spec' : 'unmapped spec; all frontend groups';
		} else if (/^frontend\/tests\/fixtures\/panels\//.test(path)) {
			selected = ['logic'];
			reason = 'deterministic panel fixture';
		} else if (/^config\/console\//.test(path)) {
			selected = CONSOLE;
			reason = 'route-owned console config and panel checks';
		} else if (/^frontend\/src\/lib\/console\/model\//.test(path) ||
			path === 'frontend/tests/support/model-route.ts') {
			selected = CONSOLE;
			reason = 'Summaries declarations, private builder and state consumers';
		} else if (/^frontend\/tests\/support\/console-expect\//.test(path)) {
			selected = CONSOLE;
			reason = 'route-owned console expectations';
		} else if (/^frontend\/tests\/support\/console-window\//.test(path)) {
			selected = CONSOLE;
			reason = 'shared window controls and focused route window consumers';
		} else if (/^frontend\/src\/routes\/(?:console)(?:\/|$)/.test(path)) {
			selected = CONSOLE;
			reason = 'console route and publishing checks';
		} else if (/^frontend\/src\/lib\/console\/(?:voices|pipelines)\//.test(path) ||
			/^frontend\/tests\/support\/(?:pipelines-ledgers|pipelines-span|retained-telemetry)\.ts$/.test(path) ||
			path === 'frontend/tests/support/panel-drivers/pipelines.ts') {
			selected = CONSOLE;
			reason = 'route-owned Voices panels and publishing checks';
		} else if (/^frontend\/src\/lib\/console\/machine\//.test(path)) {
			selected = CONSOLE;
			reason = 'route-owned Hardware panels and native publication checks';
		} else if (/^frontend\/src\/routes\/archive\//.test(path)) {
			selected = ['logic', 'archive', 'model-search', 'publishing'];
			reason = 'archive route and search consumer';
		} else if (/^frontend\/src\/routes\/(?:\[date\]\/|\+page\.)/.test(path)) {
			selected = READER;
			reason = 'reading route and publishing checks';
		} else if (/^frontend\/src\/lib\/assist\//.test(path)) {
			selected = [...READER, 'archive', 'model-search'];
			reason = 'shared day loading and on-device search';
		} else if (/^frontend\/src\/lib\/data\//.test(path)) {
			selected = CONSOLE;
			reason = 'ledger queries and console consumers';
		} else if (/^frontend\//.test(path)) {
			selected = [...FRONTEND_GROUPS];
			reason = 'shared or unmapped frontend input';
		} else if (Object.hasOwn(MODULE_TESTS, path.match(/^backend\/idhazh\/([^/]+)\.py$/)?.[1] ?? '')) {
			const module = path.split('/').at(-1)!.replace(/\.py$/, '');
			for (const name of MODULE_TESTS[module]) backendFiles.add(name);
			selected = ['backend'];
			if (['extract', 'sanitize'].includes(module)) selected.push('logic', 'publishing');
			if (['ledger', 'telemetry'].includes(module)) selected.push(...FRONTEND_GROUPS);
			reason = 'module tests and declared consumers';
		} else if (Object.hasOwn(UTILITY_TESTS, path)) {
			selected = ['backend'];
			backendFiles.add(UTILITY_TESTS[path]);
			reason = 'utility nothing else runs; its own tests';
		} else if (/^backend\/idhazh\/(?!contracts\/).+\.py$/.test(path)) {
			// Backend changes can alter the canary build, so every code pull
			// request adds browser coverage to the complete backend suite.
			selected = ['backend'];
			fullBackend = true;
			reason = 'backend module; full backend suite';
		} else {
			selected = ALL;
			fullBackend = true;
			reason = 'shared or unknown input; full coverage';
		}
		if (/^(config\/|backend\/idhazh\/contracts\/|pyproject\.toml$)/.test(path)) {
			contracts = true;
		}
		if (/^(frontend\/(scripts\/|playwright(?:\.logic)?\.config\.ts$|package(?:-lock)?\.json$)|\.github\/workflows\/ci\.yml$|backend\/utilities\/gate_lock\.py$|pyproject\.toml$|unresolved-change-base$|full-ci-run$)/.test(path)) {
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
	// Without a range - a dispatch, or a first push - the sentinel buys
	// everything, which is what an unknown change is worth.
	let paths: string[] = ['full-ci-run'];
	if (base !== '' && head !== '') {
		try {
			const changed = changedPaths(process.cwd(), base, head, false);
			// A code pull request buys full coverage. Pushes keep their own changed
			// paths for the publication decision; regression jobs do not run there.
			paths = changed;
		} catch {
			paths = ['unresolved-change-base'];
		}
	}
	if (process.argv.includes('--ci')) {
		const answer = ciAnswer(paths, isPr);
		console.log(`browser=${answer.browser}`);
		console.log(`code=${answer.code}`);
		console.log(`model_absent=${answer.modelAbsent}`);
		console.log(`console=${answer.console}`);
		console.log(`robots=${answer.robots}`);
		console.log(`validate_all=${answer.validateAll}`);
	} else {
		console.log(JSON.stringify(selectPaths(paths), null, 2));
	}
}
