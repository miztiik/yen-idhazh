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
 * The keys are also used by the specs, so the selector and tests cannot name
 * different pages.
 */
const DOC_TEST_INPUTS: Record<string, TestGroup[]> = {
	[CONSOLE_MODEL_LABELS_PAGE]: ['logic'],
	[CHART_VOCABULARY_PAGE]: ['logic']
};

export type CiAnswer = {
	code: boolean;
	bun: boolean;
	logic: boolean;
	tooling: boolean;
};

// Native packages share configuration, contracts, and recorded inputs.
const BUN_TEST_INPUTS = [
	/^(?:packages|config|tests\/fixtures|backend\/idhazh\/contracts)\//,
	/^services\/(?:feed-ingest-plan|host-fingerprints|host-probes|serve-pipeline-apis|summary-generator)\//,
	/^tools\/summary-generator-caller\//,
	/^\.github\/(?:actions\/publication-runtime\/|scripts\/|workflows\/(?:ci|ai-pipeline-tests|feed-ingest-plan-test|yen-ai-pipeline)\.yml$)/,
	/^(?:full-ci-run|unresolved-change-base)$/
];

export function ciAnswer(paths: readonly string[]): CiAnswer {
	const { groups, contracts, tooling, reasons } = selectPaths(paths);
	return {
		code: groups.length > 0 || contracts || tooling,
		bun: reasons.some(({ path }) => BUN_TEST_INPUTS.some((input) => input.test(path))),
		logic: groups.includes('logic'),
		tooling
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
		} else if (/^services\/(?:serve-pipeline-apis|feed-ingest-plan|host-fingerprints|host-probes)\//.test(path)
			|| path === 'config/hono-server.json'
			|| path === '.github/workflows/feed-ingest-plan-test.yml') {
			selected = ['backend'];
			fullBackend = true;
			reason = 'pipeline APIs; CI checks composition, planner, fingerprints and probes';
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
	let paths: string[] = ['full-ci-run'];
	if (base !== '' && head !== '') {
		try {
			paths = changedPaths(process.cwd(), base, head, false);
		} catch {
			paths = ['unresolved-change-base'];
		}
	}
	if (process.argv.includes('--ci')) {
		for (const [suite, selected] of Object.entries(ciAnswer(paths))) {
			console.log(`${suite}=${selected}`);
		}
	} else {
		console.log(JSON.stringify(selectPaths(paths), null, 2));
	}
}
