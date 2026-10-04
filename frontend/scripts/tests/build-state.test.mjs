import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { assertBuild, beginBuild, buildMode, changedInputNote, completeBuild, inputFingerprint, recordBuild } from '../build-state.ts';

function fixture() {
	const root = mkdtempSync(join(tmpdir(), 'idhazh-build-state-'));
	execFileSync('git', ['init', '--quiet', root]);
	for (const directory of ['frontend/src', 'frontend/tests', 'frontend/build', 'frontend/.svelte-kit/output/client', 'docs', 'backend/var/canary/state']) {
		mkdirSync(join(root, directory), { recursive: true });
	}
	writeFileSync(join(root, 'frontend/src/page.ts'), 'export const value = 1;\n');
	writeFileSync(join(root, 'frontend/build/index.html'), '<h1>A fixture page</h1>\n');
	writeFileSync(join(root, 'frontend/.svelte-kit/output/client/start.js'), 'const value = 1;\n');
	writeFileSync(join(root, '.gitignore'), 'frontend/build/\nfrontend/.svelte-kit/\nbackend/var/\n');
	commit(root, '.gitignore', 'frontend/src/page.ts');
	return root;
}

test('a build record rejects missing, wrong-mode, stale-source and changed-output builds', () => {
	const root = fixture();
	try {
		assert.throws(() => assertBuild(root, 'canary'), /No verified canary build/);
		recordBuild(root, 'real');
		assert.doesNotThrow(() => assertBuild(root, 'real'));
		assert.throws(() => assertBuild(root, 'canary'), /Expected a canary build/);
		writeFileSync(join(root, 'frontend/src/page.ts'), 'export const value = 2;\n');
		assert.throws(() => assertBuild(root, 'real'), /stale inputs/);
		recordBuild(root, 'real');
		writeFileSync(join(root, 'frontend/build/index.html'), '<h1>Another build</h1>\n');
		assert.throws(() => assertBuild(root, 'real'), /output changed/);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('test and documentation edits invalidate a site build and its checks', () => {
	const root = fixture();
	try {
		recordBuild(root, 'real');
		const before = inputFingerprint(root);
		writeFileSync(join(root, 'frontend/tests/example.spec.ts'), 'test changes\n');
		writeFileSync(join(root, 'frontend/playwright.config.ts'), 'test configuration changes\n');
		writeFileSync(join(root, 'docs/example.md'), '# New documentation\n');
		assert.throws(() => assertBuild(root, 'real'), /stale inputs/);
		assert.notEqual(inputFingerprint(root), before);
		const after = inputFingerprint(root);
		writeFileSync(join(root, 'docs/example.md'), '# More documentation\n');
		assert.notEqual(inputFingerprint(root), after);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('a stale build names the inputs that moved, and nothing that is not one', () => {
	const root = fixture();
	try {
		recordBuild(root, 'real');
		assert.equal(changedInputNote(root, 'build'), '', 'a clean tree has nothing to name');
		writeFileSync(join(root, 'docs/example.md'), '# New documentation\n');
		assert.match(changedInputNote(root, 'build'), /docs\/example\.md/);
		writeFileSync(join(root, 'frontend/src/page.ts'), 'export const value = 2;\n');
		assert.throws(
			() => assertBuild(root, 'real'),
			(error) => /stale inputs/.test(error.message)
				&& /frontend\/src\/page\.ts/.test(error.message),
			'a stale build says which file moved, or the reader has to find it'
		);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('canary changes invalidate the canary build independently of source changes', () => {
	const root = fixture();
	try {
		const ledger = join(root, 'backend/var/canary/state/host-fingerprint/2026/09/05.csv');
		mkdirSync(join(root, 'backend/var/canary/state/host-fingerprint/2026/09'), { recursive: true });
		writeFileSync(ledger, 'date,value\n2026-09-05,1\n');
		recordBuild(root, 'canary');
		assert.doesNotThrow(() => assertBuild(root, 'canary'));
		writeFileSync(ledger, 'date,value\n2026-09-05,2\n');
		assert.throws(() => assertBuild(root, 'canary'), /stale inputs/);
		assert.equal(buildMode(root, {}), 'real');
		assert.equal(buildMode(root, { STATE_ROOT: root }), 'custom');
		assert.equal(buildMode(root, {
			DIGEST_ROOT: join(root, 'backend/var/canary/digest'),
			STATE_ROOT: join(root, 'backend/var/canary/state'),
			TELEMETRY_ROOT: join(root, 'backend/var/canary/state/telemetry')
		}), 'canary');
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('preview assets outside the static build are part of its identity', () => {
	const root = fixture();
	try {
		recordBuild(root, 'real');
		writeFileSync(join(root, 'frontend/.svelte-kit/output/client/start.js'), 'const value = 2;\n');
		assert.throws(() => assertBuild(root, 'real'), /output changed/);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('base path and build version changes invalidate a recorded build', () => {
	const root = fixture();
	try {
		recordBuild(root, 'real', {});
		assert.throws(() => assertBuild(root, 'real', { BASE_PATH: '/different' }), /stale inputs/);
		assert.throws(() => assertBuild(root, 'real', { BUILD_VERSION: 'different' }), /stale inputs/);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('Markdown fixture data invalidates checks', () => {
	const root = fixture();
	try {
		mkdirSync(join(root, 'tests/fixtures'), { recursive: true });
		const fixtureFile = join(root, 'tests/fixtures/article.md');
		writeFileSync(fixtureFile, '# Original article\n');
		const before = inputFingerprint(root);
		writeFileSync(fixtureFile, '# Different article\n');
		assert.notEqual(inputFingerprint(root), before);
	} finally { rmSync(root, { recursive: true, force: true }); }
});

function commit(root, ...paths) {
	execFileSync('git', ['-C', root, 'add', '--', ...paths]);
	execFileSync('git', ['-C', root, '-c', 'user.email=t@example.com', '-c', 'user.name=Test',
		'-c', 'commit.gpgsign=false', 'commit', '--quiet', '-m', 'a fixture']);
}

test('committed changes, working changes and non-ignored untracked files each change the fingerprint', () => {
	const root = fixture();
	try {
		const first = inputFingerprint(root);
		writeFileSync(join(root, 'frontend/src/page.ts'), 'export const value = 2;\n');
		const working = inputFingerprint(root);
		assert.notEqual(working, first);
		commit(root, 'frontend/src/page.ts');
		const committed = inputFingerprint(root);
		assert.notEqual(committed, first);
		assert.notEqual(committed, working);
		writeFileSync(join(root, 'frontend/src/new.ts'), 'export const added = true;\n');
		const untracked = inputFingerprint(root);
		assert.notEqual(untracked, committed);
		writeFileSync(join(root, 'frontend/src/new.ts'), 'export const added = false;\n');
		assert.notEqual(inputFingerprint(root), untracked);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('an unchanged committed file is represented by its tree object', () => {
	const root = fixture();
	try {
		const source = join(root, 'frontend/src/page.ts');
		const before = inputFingerprint(root);
		// git is told to stop reporting this path, so a fingerprint that moved
		// could only have come from reading the file off disk.
		execFileSync('git', ['-C', root, 'update-index', '--assume-unchanged', 'frontend/src/page.ts']);
		writeFileSync(source, 'export const value = 999;\n');
		assert.equal(inputFingerprint(root), before, 'the unchanged tracked file was read from disk');
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('a tracked file modification or deletion changes the Git diff fingerprint', () => {
	const root = fixture();
	try {
		const source = join(root, 'frontend/src/page.ts');
		const committed = inputFingerprint(root);
		writeFileSync(source, 'export const value = 2;\n');
		const modified = inputFingerprint(root);
		assert.notEqual(modified, committed, 'a modified tracked file kept the hash the index holds');
		rmSync(source);
		assert.notEqual(inputFingerprint(root), modified, 'a deleted tracked file kept the bytes it no longer has');
		assert.notEqual(inputFingerprint(root), committed, 'a deleted tracked file reads as its committed self');
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('a failed or still-running build cannot reuse the previous build record', () => {
	const root = fixture();
	try {
		recordBuild(root, 'real');
		writeFileSync(join(root, 'frontend/build.publication.json'), '{}\n');
		writeFileSync(join(root, 'frontend/build/stale.html'), 'stale\n');
		beginBuild(root, 'real');
		assert.throws(() => assertBuild(root, 'real'), /No verified real build/);
		assert.equal(existsSync(join(root, 'frontend/build.publication.json')), false);
		assert.equal(existsSync(join(root, 'frontend/build/stale.html')), false);
		assert.throws(() => completeBuild(root, 'real'), /output is missing/);
		mkdirSync(join(root, 'frontend/build'));
		writeFileSync(join(root, 'frontend/build/index.html'), '<h1>A fresh build</h1>\n');
		completeBuild(root, 'real');
		assert.doesNotThrow(() => assertBuild(root, 'real'));
		assert.throws(() => completeBuild(root, 'real'), /no start record/);
	} finally { rmSync(root, { recursive: true, force: true }); }
});

test('source changes during compilation do not certify old output as current', () => {
	const root = fixture();
	try {
		beginBuild(root, 'real');
		mkdirSync(join(root, 'frontend/build'));
		writeFileSync(join(root, 'frontend/build/index.html'), '<h1>A fresh build</h1>\n');
		writeFileSync(join(root, 'frontend/src/page.ts'), 'export const value = 2;\n');
		assert.throws(() => completeBuild(root, 'real'), /changed during compilation/);
		assert.throws(() => assertBuild(root, 'real'), /No verified real build/);
	} finally { rmSync(root, { recursive: true, force: true }); }
});

test('a site build completes on a machine with no Python', () => {
	const root = fixture();
	try {
		const script = join(root, 'frontend/scripts/build-state.ts');
		mkdirSync(join(root, 'frontend/scripts'), { recursive: true });
		writeFileSync(join(root, 'frontend/package.json'), '{ "type": "module" }\n');
		copyFileSync(fileURLToPath(new URL('../build-state.ts', import.meta.url)), script);
		const env = { ...process.env, IDHAZH_PYTHON: join(root, 'no-python-here') };
		for (const name of ['DIGEST_ROOT', 'STATE_ROOT', 'TELEMETRY_ROOT']) delete env[name];
		execFileSync(process.execPath, [script, '--begin'], { env, stdio: 'pipe' });
		mkdirSync(join(root, 'frontend/build'));
		writeFileSync(join(root, 'frontend/build/index.html'), '<h1>A fresh build</h1>\n');
		execFileSync(process.execPath, [script, '--complete'], { env, stdio: 'pipe' });
		assert.doesNotThrow(() => assertBuild(root, 'real', env));
	} finally { rmSync(root, { recursive: true, force: true }); }
});
