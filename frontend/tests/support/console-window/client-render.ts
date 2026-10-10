/** The existing real client compiler, over a caller-supplied named component list. */
import { type Page } from '../browser';

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { build } from 'esbuild';
import { compile, preprocess } from 'svelte/compiler';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import svelteConfig from '../../../svelte.config.js';

declare global {
	interface Window {
		oneDayWords: { draw: (name: string, props: Record<string, unknown>) => void };
	}
}
export async function clientCode(components: readonly (readonly [string,string])[]): Promise<string> {
const kit: {
	paths: { base: string; assets?: string; relative?: boolean };
	appDir?: string;
} = svelteConfig.kit;
const result = await build({
	stdin: {
		contents: `import { mount } from 'svelte';\n${components.map(([name,file]) => `import ${name} from '${file}';`).join('\n')}\nconst components = { ${components.map(([name])=>name).join(', ')} };\nexport function draw(name, props) { mount(components[name], { target: document.querySelector('main'), props }); }`,
		resolveDir: process.cwd()
	},
	bundle: true,
	write: false,
	format: 'iife',
	globalName: 'oneDayWords',
	conditions: ['browser'],
	define: {
		__SVELTEKIT_PATHS_BASE__: JSON.stringify(kit.paths?.base ?? ''),
		__SVELTEKIT_PATHS_ASSETS__: JSON.stringify(kit.paths?.assets ?? ''),
		__SVELTEKIT_APP_DIR__: JSON.stringify(kit.appDir ?? '_app'),
		__SVELTEKIT_PATHS_RELATIVE__: JSON.stringify(kit.paths?.relative ?? true)
	},
	alias: {
		$lib: resolve('src/lib'),
		'$app/paths': resolve('node_modules/@sveltejs/kit/src/runtime/app/paths/internal/server.js')
	},
	plugins: [{
		name: 'real-svelte-components',
		setup(bundler) {
			bundler.onLoad({ filter: /\.svelte$/ }, async ({ path }) => {
				const pre = await preprocess(readFileSync(path, 'utf8'), vitePreprocess(), { filename: path });
				return {
					contents: compile(pre.code, { filename: path, generate: 'client', css: 'injected' }).js.code,
					resolveDir: resolve(path, '..')
				};
			});
		}
	}]
});
return result.outputFiles[0].text;
}
export async function drawClient(page: Page, browserCode: string, name: string, props: Record<string, unknown>) {
	await page.route('**/l34-generated-records', (route) => route.fulfill({
		contentType: 'text/html',
		body: '<!doctype html><html><body><main></main></body></html>'
	}));
	await page.goto('/l34-generated-records');
	await page.addScriptTag({ content: browserCode });
	await page.evaluate(({ name, props }) => window.oneDayWords.draw(name, props), { name, props });
}
