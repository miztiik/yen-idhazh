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
	rust: boolean;
	reasons: { path: string; groups: TestGroup[]; reason: string }[];
};

const ALL: TestGroup[] = ['backend', ...FRONTEND_GROUPS];
const READER: TestGroup[] = ['logic', 'reader', 'publishing'];
const CONSOLE: TestGroup[] = ['logic', 'console', 'panels', 'publishing'];

/** The operator console's own files.
 *
 * The console's specs are 584 of the browser suite's 997 tests, measured
 * 2026-09-05, and the console is a page one operator opens rather than anything
 * a reader is served. So a pull request buys them only when the change is the
 * console's own; every other change reaches them on the merge push to `main`,
 * which runs every group. What that costs is stated rather than implied: a
 * shared component or a token edit that breaks the console is found on that
 * push, not at the pull request. The shared panel frame is an exception: every
 * console route renders it, so its edits buy the console on the pull request.
 */
const CONSOLE_OWNED =
	/^(frontend\/(tests\/(?:console[-.]|support\/(?:console-expect|console-window|panel-drivers)\/)|src\/(routes|lib)\/console\/|src\/lib\/components\/(?:Console[A-Z]|Panel\.svelte$)|src\/lib\/server\/console-shell\.ts$)|config\/console\/)/;

/** What a console panel's picture is drawn from, beyond the console's own files.
 *
 * The `panels` group is two spec files against the console's hundreds of
 * tests, so it is bought by a wider set: the panel frame and the readout strip
 * every panel shares, the chart modules, the stylesheets and tokens, the
 * appearance config the panels read, and the captures' own specs, fixture and
 * helpers. These are the edits that move every panel image at once, and
 * deferring them to the merge push would mean their first pictures arrive
 * after the change is already on `main`.
 */
const PANELS_DRAWN =
	/^(frontend\/(tests\/(panel-|fixtures\/panels\/|support\/)|src\/(styles|lib\/charts)\/|src\/lib\/components\/(Panel|PanelGroup|ChartReadout|Reserved)\.svelte$)|config\/(?:appearance\.json$|console\/))/;

/** A document a test reads is that test's input, not documentation.
 *
 * `frontend/tests/console-model.spec.ts` asserts the console's label set
 * against this page, so an edit to it can redden a suite the documentation
 * branch below would otherwise have answered for. The key is the constant the
 * spec reads its page from, so the two cannot name different pages.
 * `chart-vocabulary.spec.ts` reads the chart-type list the same way, and it is a
 * logic spec, so an edit to that page buys the logic group and no browser.
 */
const DOC_TEST_INPUTS: Record<string, TestGroup[]> = {
	[CONSOLE_MODEL_LABELS_PAGE]: ['console'],
	[CHART_VOCABULARY_PAGE]: ['logic']
};

function consoleIsTheSubject(paths: readonly string[]): boolean {
	return paths.some((path) => {
		const clean = path.replaceAll('\\', '/');
		return CONSOLE_OWNED.test(clean) || (DOC_TEST_INPUTS[clean]?.includes('console') ?? false);
	});
}

function panelsAreTheSubject(paths: readonly string[]): boolean {
	return paths.some((path) => PANELS_DRAWN.test(path.replaceAll('\\', '/')));
}

export type CiAnswer = {
	browser: boolean;
	code: boolean;
	modelAbsent: boolean;
	console: boolean;
	panels: boolean;
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
	// A harness change still proves itself on everything: `tooling` covers the
	// selector, the Playwright config and the workflow that reads them.
	const deferred = isPr && !selection.tooling && !consoleIsTheSubject(paths);
	// Whether anything but documentation changed. Skipping on this is safe
	// because the documentation branch in `selectPaths` is a closed list of
	// prefixes: a path nobody classified falls to full coverage instead.
	const code = selection.groups.length > 0 || selection.contracts || selection.tooling;
	return {
		browser: selection.groups.some((group) => group !== 'backend' && group !== 'logic'),
		code,
		modelAbsent: code && (!isPr || selection.tooling || selection.contracts || selection.reasons.some(({ path, groups }) => {
			const clean = path.replaceAll('\\', '/');
			if (/^(docs\/|TODO\/|(?:README|AGENTS|CLAUDE)\.md$|frontend\/tests\/)/.test(clean)) return false;
			if (/^frontend\/src\/(routes\/console\/|lib\/(console|charts|data)\/|styles\/)/.test(clean)) return false;
			// A backend-only selection cannot change model asset staging. Unknown
			// inputs still select frontend groups and therefore buy the second build.
			return groups.some((group) => group !== 'backend');
		})),
		console: selection.groups.includes('console') && !deferred,
		// Whatever buys the console buys panel assertions, as do shared drawing inputs.
		panels: selection.groups.includes('panels') && (!deferred || panelsAreTheSubject(paths)),
		// A full backend selection (null) is an unknown change, so it buys the job.
		robots: selection.backendFiles?.includes(ROBOTS_TESTS) ?? true,
		// A published day is frozen, so the only thing that can invalidate one is a
		// change to the shape it is read through - or an edit to the day itself.
		// Everything else leaves an answer that was settled when the day was
		// written, and re-deriving it costs about 0.27 s a day (`CLAUDE.md` Guardrail
		// #12). Outside a pull request a code change always re-reads: that is the
		// merge to `main`. Documentation carries no shape, so it never does.
		validateAll:
			code &&
			(!isPr ||
				selection.contracts ||
				selection.tooling ||
				paths.some((path) => ARCHIVE_TOUCHED.test(path.replaceAll('\\', '/'))))
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
export const RUST_PARITY_TEST = 'backend/tests/contracts/test_rust_host_file_parity.py';
export const RUST_STORE_TEST = 'backend/tests/test_rust_host_store_parity.py';
export const RUST_TESTS = [RUST_PARITY_TEST, RUST_STORE_TEST];
const HOST_TESTS: Record<string, string[]> = {
	'backend/idhazh/contracts/host_events.py': ['backend/tests/contracts/test_host_events.py', 'backend/tests/test_host_event_files.py', RUST_PARITY_TEST],
	'backend/idhazh/contracts/host_output.py': ['backend/tests/contracts/test_host_output.py', 'backend/tests/contracts/test_host_events.py', 'backend/tests/test_host_output_verify.py', RUST_PARITY_TEST],
	'backend/idhazh/telemetry/host_event_files.py': ['backend/tests/test_host_event_files.py'],
	'backend/idhazh/telemetry/host_output_verify.py': ['backend/tests/test_host_output_verify.py', RUST_PARITY_TEST],
	'backend/idhazh/telemetry/host_parquet_admission.py': ['backend/tests/test_host_parquet_admission.py', 'backend/tests/test_host_output_verify.py', RUST_PARITY_TEST],
	'backend/utilities/verify_host_output.py': ['backend/tests/test_host_output_verify.py'],
	'config/host-telemetry-experiment.json': ['backend/tests/contracts/test_host_events.py', 'backend/tests/test_host_event_files.py', RUST_PARITY_TEST],
	'tests/fixtures/host-events/file-parity.json': [RUST_PARITY_TEST],
	'tests/fixtures/host-events/storage-parity.json': [RUST_STORE_TEST],
	'tests/fixtures/host-events/manifest.json': ['backend/tests/contracts/test_host_events.py', 'backend/tests/test_host_event_files.py', RUST_PARITY_TEST],
	'tests/fixtures/host-events/cpu-snapshots.json': ['backend/tests/contracts/test_host_output.py'],
	'tests/fixtures/host-events/fingerprint-versions.json': ['backend/tests/contracts/test_host_output.py']
};

export function selectPaths(paths: readonly string[]): Selection {
	const groups = new Set<TestGroup>();
	const backendFiles = new Set<string>();
	let fullBackend = false;
	let contracts = false;
	let tooling = false;
	let rust = false;
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
		} else if (path.startsWith('backend/rust/host-telemetry/') || RUST_TESTS.includes(path)) {
			selected = ['backend'];
			for (const file of RUST_TESTS) backendFiles.add(file);
			rust = true;
			reason = 'native Rust module checks and actual cross-language codec fixtures';
		} else if (Object.hasOwn(HOST_TESTS, path)) {
			selected = ['backend'];
			for (const file of HOST_TESTS[path]) backendFiles.add(file);
			rust ||= HOST_TESTS[path].some((file) => RUST_TESTS.includes(file));
			reason = 'isolated host exchange/verifier tests and declared native consumers';
		} else if (/^backend\/tests\/(?:[^/]+\/)?test_[^/]+\.py$/.test(path)) {
			selected = ['backend'];
			backendFiles.add(path);
			reason = 'changed backend test module';
		} else if (/^frontend\/tests\/[^/]+\.spec\.ts$/.test(path)) {
			const group = groupForSpec(path);
			selected = group ? [group] : [...FRONTEND_GROUPS];
			reason = group ? 'changed frontend spec' : 'unmapped spec; all frontend groups';
		} else if (/^frontend\/tests\/fixtures\/panels\//.test(path)) {
			selected = ['panels'];
			reason = 'the panel the sufficiency gates are proven against';
		} else if (/^config\/console\//.test(path)) {
			selected = CONSOLE;
			reason = 'route-owned console config and panel checks';
		} else if (/^frontend\/tests\/support\/(?:console-expect|panel-drivers)\//.test(path)) {
			selected = CONSOLE;
			reason = 'route-owned console expectations and drivers';
		} else if (/^frontend\/tests\/support\/console-window\//.test(path)) {
			selected = CONSOLE;
			reason = 'shared window controls and focused route window consumers';
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
			// The browser reaches backend code only through the canary build, so a
			// pull request answers with the whole backend suite, and the merge push
			// to `main`, which runs every group, settles the browser.
			selected = ['backend'];
			fullBackend = true;
			reason = 'backend module; full backend suite';
		} else {
			selected = ALL;
			fullBackend = true;
			reason = 'shared or unknown input; full coverage';
		}
		if (!Object.hasOwn(HOST_TESTS, path) && /^(config\/|backend\/idhazh\/contracts\/|pyproject\.toml$)/.test(path)) {
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
		rust: rust || fullBackend,
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
			// A pull request is answered from its own paths. A push is answered from
			// the sentinel, because the group each path selects is a wager that
			// nobody forgot a path and the merge is where that wager is settled. The
			// one thing a push does read the paths for is whether any code changed
			// at all: that branch is a closed list of prefixes rather than a wager.
			paths = isPr || !ciAnswer(changed, false).code ? changed : ['full-ci-run'];
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
		console.log(`panels=${answer.panels}`);
		console.log(`robots=${answer.robots}`);
		console.log(`validate_all=${answer.validateAll}`);
	} else {
		console.log(JSON.stringify(selectPaths(paths), null, 2));
	}
}
