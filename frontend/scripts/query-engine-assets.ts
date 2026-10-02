/** Which content-named outputs does the browser query engine load? */
import { createHash } from 'node:crypto';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import type { Manifest, Plugin } from 'vite';

const ENGINE_ENTRY = 'src/lib/data/engine.ts';

export function queryEngineAssets(manifest: Manifest): { files: string[]; version: string } {
	const visited = new Set<string>();
	const files = new Set<string>();
	function visit(key: string): void {
		if (visited.has(key)) return;
		visited.add(key);
		const entry = manifest[key];
		if (!entry) throw new Error(`The browser build manifest does not name ${key}`);
		files.add(entry.file);
		for (const asset of [...(entry.assets ?? []), ...(entry.css ?? [])]) files.add(asset);
		for (const dependency of [...(entry.imports ?? []), ...(entry.dynamicImports ?? [])]) visit(dependency);
	}
	visit(ENGINE_ENTRY);
	const ordered = [...files].sort();
	return { files: ordered, version: createHash('sha256').update(JSON.stringify(ordered)).digest('hex') };
}

export function queryEngineAssetModule(): Plugin {
	let client = false;
	let generated = '';
	function writeAssets(assets: ReturnType<typeof queryEngineAssets>): void {
		mkdirSync(dirname(generated), { recursive: true });
		writeFileSync(generated, `export default ${JSON.stringify(assets)};\n`, 'utf8');
	}
	return {
		name: 'query-engine-assets',
		configResolved(config) {
			client = !config.build.ssr;
			generated = join(config.root, '.svelte-kit', 'query-engine-assets.generated.js');
			if (config.command === 'serve') writeAssets({ files: [], version: 'dev' });
		},
		writeBundle(_options, bundle) {
			if (!client) return;
			const manifest = bundle['.vite/manifest.json'];
			if (manifest?.type !== 'asset') throw new Error('The browser build did not emit its Vite manifest');
			const text = typeof manifest.source === 'string' ? manifest.source : Buffer.from(manifest.source).toString('utf8');
			writeAssets(queryEngineAssets(JSON.parse(text) as Manifest));
		}
	};
}