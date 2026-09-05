import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { assertBuild, beginBuild, buildMode, completeBuild, inputFingerprint, recordBuild } from '../build-state.ts';

function fixture() {
	const root = mkdtempSync(join(tmpdir(), 'idhazh-build-state-'));
	execFileSync('git', ['init', '--quiet', root]);
	for (const directory of ['frontend/src', 'frontend/tests', 'frontend/build', 'frontend/.svelte-kit/output/client', 'docs', 'backend/var/canary/state']) {
		mkdirSync(join(root, directory), { recursive: true });
	}
	writeFileSync(join(root, 'frontend/src/page.ts'), 'export const value = 1;\n');
	writeFileSync(join(root, 'frontend/build/index.html'), '<h1>A fixture page</h1>\n');
	writeFileSync(join(root, 'frontend/.svelte-kit/output/client/start.js'), 'const value = 1;\n');
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

test('test and documentation edits do not require a site rebuild', () => {
	const root = fixture();
	try {
		recordBuild(root, 'real');
		const before = inputFingerprint(root);
		writeFileSync(join(root, 'frontend/tests/example.spec.ts'), 'test changes\n');
		writeFileSync(join(root, 'frontend/playwright.config.ts'), 'test configuration changes\n');
		writeFileSync(join(root, 'docs/example.md'), '# New documentation\n');
		assert.doesNotThrow(() => assertBuild(root, 'real'));
		assert.notEqual(inputFingerprint(root), before);
		const after = inputFingerprint(root);
		writeFileSync(join(root, 'docs/example.md'), '# More documentation\n');
		assert.equal(inputFingerprint(root), after);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('canary changes invalidate the canary build independently of source changes', () => {
	const root = fixture();
	try {
		const ledger = join(root, 'backend/var/canary/state/runtime-counters.csv');
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

test('Markdown fixture data invalidates checks even though documentation does not', () => {
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

test('a failed or still-running build cannot reuse the previous build record', () => {
	const root = fixture();
	try {
		recordBuild(root, 'real');
		beginBuild(root, 'real');
		assert.throws(() => assertBuild(root, 'real'), /No verified real build/);
		completeBuild(root, 'real');
		assert.doesNotThrow(() => assertBuild(root, 'real'));
		assert.throws(() => completeBuild(root, 'real'), /no start record/);
	} finally { rmSync(root, { recursive: true, force: true }); }
});

test('source changes during compilation do not certify old output as current', () => {
	const root = fixture();
	try {
		beginBuild(root, 'real');
		writeFileSync(join(root, 'frontend/src/page.ts'), 'export const value = 2;\n');
		assert.throws(() => completeBuild(root, 'real'), /changed during compilation/);
		assert.throws(() => assertBuild(root, 'real'), /No verified real build/);
	} finally { rmSync(root, { recursive: true, force: true }); }
});
