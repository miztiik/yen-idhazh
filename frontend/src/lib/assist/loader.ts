/** The only place that loads a model into a reader's tab.
 *
 * Three rules are enforced here rather than requested, because each one is a
 * promise the project made in `CLAUDE.md`:
 *
 * 1. **Nothing loads until a reader asks.** No prefetch, no idle warm-up, no
 *    speculative import. The `import()` below is inside a function that only a
 *    click reaches, which is also what keeps the library out of the first-load
 *    bundle - a static import would put it there no matter what the UI did.
 * 2. **Same origin, always.** `allowRemoteModels = false` makes a fetch to a
 *    third-party hub impossible rather than unlikely. That is Rule #1, and
 *    a runtime fetch to another origin is the half of it that never changed.
 * 3. **Absent, not broken.** Every failure path returns a reason. A reader who
 *    declines, or whose browser cannot run this, sees a page that is missing a
 *    secondary control - never a page that is broken.
 */

import { base } from '$app/paths';
import { ENCODER_PATH } from './encoder';

/** What a reader is told before a single byte moves.
 *
 * Measured 2026-08-22, not rounded up from a guess: 22,972,370 bytes of
 * quantised encoder, 711,661 of tokenizer, and 21,596,019 of ONNX WASM runtime.
 * The browser caches all three, so a second visit is free. If any of those
 * files changes size, this number changes with it - a download figure that
 * drifts from the download is worse than no figure.
 *
 * The runtime is the WebGPU-capable build at 21.6 MB rather than the plain WASM
 * one at 11.1 MB. That was not the intent. transformers.js v3 bundles a
 * onnxruntime-web that requests `ort-wasm-simd-threaded.jsep.mjs` by name, and
 * neither a directory prefix, an explicit `{ mjs, wasm }` mapping, nor
 * `device: 'wasm'` redirects it - all three were tried and all three 404ed on
 * the jsep filename. The choice was 10 MB or no search, so the 10 MB was paid
 * and written down here. Worth revisiting whenever the library offers a
 * WASM-only path again.
 */
export const DOWNLOAD_MB = 43;

/** The token cap the runner truncates at, repeated here because it is not shared yet.
 *
 * One artifact, two runtimes only holds if both runtimes read the same amount
 * of text. The tokenizer config says 512 and the pipeline takes its cap from
 * there, so without this line a long query is read twice as far in the tab as
 * every item it is compared against. The runner's copy is `MAX_TOKENS` in
 * `backend/idhazh/embed.py`; row #8 of the plan moves that one into `config/`
 * and this one follows it there.
 */
export const MAX_TOKENS = 256;

export type AssistState =
	| { status: 'idle' }
	| { status: 'loading' }
	| { status: 'ready' }
	| { status: 'unavailable'; reason: string };

type Extractor = (
	text: string | string[],
	options: { pooling: 'mean'; normalize: boolean }
) => Promise<{ tolist(): number[][] }>;

let extractor: Extractor | null = null;
let inFlight: Promise<Extractor> | null = null;

/** True when this browser can run the encoder at all. */
export function supported(): boolean {
	return typeof WebAssembly === 'object' && typeof Worker === 'function';
}

/** Load the encoder. Idempotent, and safe to call twice from an impatient click. */
export async function load(): Promise<Extractor> {
	if (extractor) return extractor;
	if (inFlight) return inFlight;

	inFlight = (async () => {
		// Dynamic, so the library never reaches the first-load bundle. A static
		// import here would ship transformers.js to every reader of every page.
		const transformers = await import('@huggingface/transformers');

		// Contract, not configuration. There is no knob for these, because a knob
		// is a way for the same-origin promise to be turned off by accident.
		transformers.env.allowRemoteModels = false;
		transformers.env.allowLocalModels = true;
		transformers.env.localModelPath = `${base}/assist/models/`;
		if (transformers.env.backends?.onnx?.wasm) {
			transformers.env.backends.onnx.wasm.wasmPaths = `${base}/assist/wasm/`;
			// Single-threaded. Threads need cross-origin isolation, which needs
			// headers GitHub Pages does not let us set, and the row that rejected
			// service workers closed the other way of getting them.
			transformers.env.backends.onnx.wasm.numThreads = 1;
		}

		const pipe = await transformers.pipeline('feature-extraction', ENCODER_PATH, {
			dtype: 'q8',
			// WASM, not WebGPU. WebGPU is not the baseline.
			//
			// This does not pick the binary. The only runtime committed under
			// `static/assist/wasm/` is `ort-wasm-simd-threaded.jsep.wasm` - the
			// WebGPU-capable build, 21,596,019 bytes measured 2026-08-26 - and the
			// header comment above says why the lighter one is not there. This line
			// used to claim it stopped that 10 MB reaching a reader. It never did.
			device: 'wasm'
		});
		// The feature-extraction pipeline hardcodes `truncation: true` and passes
		// no length, so the cap comes from the tokenizer config. Setting it here
		// is the only place the browser's cap can be named.
		pipe.tokenizer.model_max_length = MAX_TOKENS;
		extractor = pipe as unknown as Extractor;
		return extractor;
	})();

	try {
		return await inFlight;
	} finally {
		inFlight = null;
	}
}

/** Embed one query. The browser never embeds an item - those vectors are committed. */
export async function embedQuery(text: string): Promise<number[]> {
	const pipe = await load();
	const output = await pipe(text, { pooling: 'mean', normalize: true });
	return output.tolist()[0];
}
