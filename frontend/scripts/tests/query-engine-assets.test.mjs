import assert from 'node:assert/strict';
import { test } from 'node:test';
import { queryEngineAssets } from '../query-engine-assets.ts';

function manifest() {
	return {
		'src/lib/data/engine.ts': {
			file: '_app/immutable/chunks/BDAd77cq.js',
			dynamicImports: ['duckdb-browser', 'duckdb-wasm', 'duckdb-worker']
		},
		'duckdb-browser': { file: '_app/immutable/chunks/mUOgBBDp.js' },
		'duckdb-wasm': {
			file: '_app/immutable/chunks/DMr4j5kM.js',
			assets: ['_app/immutable/assets/duckdb-eh.CfdE9-rk.wasm']
		},
		'duckdb-worker': {
			file: '_app/immutable/chunks/CH5b4hkc.js',
			assets: ['_app/immutable/assets/duckdb-browser-eh.worker.CwdVMcbT.js']
		}
	};
}

test('the engine cache includes anonymous chunks and binary assets, not unrelated pages', () => {
	const graph = { ...manifest(), unrelated: { file: '_app/immutable/chunks/other.js' } };
	const assets = queryEngineAssets(graph);
	assert.equal(assets.files.length, 6);
	assert.ok(assets.files.includes('_app/immutable/chunks/mUOgBBDp.js'));
	assert.ok(assets.files.includes('_app/immutable/assets/duckdb-eh.CfdE9-rk.wasm'));
	assert.ok(assets.files.includes('_app/immutable/assets/duckdb-browser-eh.worker.CwdVMcbT.js'));
	assert.ok(!assets.files.includes(graph.unrelated.file));
	graph.unrelated.file = '_app/immutable/chunks/next-deploy.js';
	assert.equal(queryEngineAssets(graph).version, assets.version);
	graph['duckdb-wasm'].assets[0] = '_app/immutable/assets/duckdb-eh.changed.wasm';
	assert.notEqual(queryEngineAssets(graph).version, assets.version);
});

test('shared imports are deduplicated, cycles terminate and a missing dependency fails by name', () => {
	const graph = manifest();
	graph['duckdb-browser'].imports = ['duckdb-worker'];
	graph['duckdb-worker'].imports = ['duckdb-browser'];
	assert.equal(queryEngineAssets(graph).files.length, 6);
	delete graph['duckdb-worker'];
	assert.throws(() => queryEngineAssets(graph), /does not name duckdb-worker/);
});