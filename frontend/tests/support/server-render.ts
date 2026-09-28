/** How a spec renders a real Svelte component with no build.
 *
 * Each component is compiled for the server into one module, written beside
 * its siblings, and a child's import is pointed at the child's compiled copy.
 * So a parent renders with its real children rather than with stubs, and a
 * check made against the markup is a check against what a page would draw.
 *
 * The modules are written under `frontend/test-results/`, because Node cannot
 * import a `.svelte` file and a compiled copy has to live somewhere a spec can
 * import it from. A `$lib/...` import inside a compiled module still resolves
 * there; a relative `../x` import does not, so a component compiled this way
 * names its imports through `$lib`.
 */

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { compile, preprocess } from 'svelte/compiler';

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

/** One import a compiled module names, and the compiled copy it names instead. */
export type Rewrite = readonly [from: string, to: string];

/** Compile one component and return the path of the module it was written to. */
export interface ServerCompile {
	(file: string, name: string, rewrite: readonly Rewrite[]): Promise<string>;
	/** The CSS each compiled component emitted, by name. Markup rendered
	 * without it has none of the component's own styles, so a check that
	 * measures a box has to mount the two together. */
	readonly css: ReadonlyMap<string, string>;
}

/** A compiler that writes every component it is handed into `directory`.
 *
 * `file` is relative to `frontend/`. The module is written as
 * `<name>.server.mjs`, so a sibling's rewrite can name it before it exists.
 */
export function serverCompiler(directory: string): ServerCompile {
	const css = new Map<string, string>();
	const compiled = async (file: string, name: string, rewrite: readonly Rewrite[]): Promise<string> => {
		const filename = path.join(frontend, file);
		const pre = await preprocess(readFileSync(filename, 'utf8'), vitePreprocess(), { filename });
		const result = compile(pre.code, { generate: 'server', filename, name });
		mkdirSync(directory, { recursive: true });
		const module = path.join(directory, `${name}.server.mjs`);
		let code = result.js.code;
		for (const [from, to] of rewrite) code = code.split(`'${from}'`).join(`'${to}'`);
		writeFileSync(module, code, 'utf8');
		css.set(name, result.css?.code ?? '');
		return module;
	};
	return Object.assign(compiled, { css });
}
