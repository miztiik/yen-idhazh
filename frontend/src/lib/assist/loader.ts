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
 * 4. **The download is described from measurement, never from a guess.** What
 *    has already arrived is read out of the browser's own cache storage, and
 *    what is arriving now is the library's own byte count. Reading this
 *    device's disk is not telemetry: nothing is sent anywhere (Rule #1).
 */

import { base } from '$app/paths';
import { ENCODER_ID, ENCODER_PATH } from './encoder';

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

/** How much of the download has arrived, from the library's own numbers.
 *
 * `loaded` counts the encoder's own files and nothing else: the ONNX runtime is
 * fetched by onnxruntime-web, which reports no progress to anybody. That is why
 * the sentence reading this stops printing bytes once the weights land and
 * prints a word instead - the counter can no longer see what is happening, and
 * a bar that keeps moving on no measurement is a bar that is making it up.
 */
export interface EncoderProgress {
	/** Bytes of the encoder's own files that have arrived. */
	loaded: number;
	/** True once the weights are in hand and only the start-up is left. */
	landed: boolean;
}

/** What this device's cache storage says about the encoder, before a byte moves.
 *
 * `stale` is the state a reader cannot guess at: the weights moved, so the path
 * moved with them, and a returning searcher pays the whole download again. It
 * is worth its own sentence for exactly that reason.
 */
export type CachedEncoder = 'present' | 'stale' | 'absent' | 'unknown';

/** transformers.js writes model files here. Its constant, not ours. */
const MODEL_CACHE = 'transformers-cache';

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

/** Ask this device whether the download has already been paid for.
 *
 * The library caches every model file it fetches under a same-origin key, so
 * the answer is a lookup on local disk. Nothing is sent, and nothing is
 * fetched - a reader who never searches never learns this was asked.
 *
 * `unknown` is returned rather than guessed whenever the cache cannot be read.
 * The sentence that reads it then prints the whole download, because
 * overstating a cost is honest and understating one is not.
 */
export async function cachedEncoder(): Promise<CachedEncoder> {
	if (typeof caches === 'undefined') return 'unknown';
	try {
		if (!(await caches.has(MODEL_CACHE))) return 'absent';
		const cache = await caches.open(MODEL_CACHE);
		const models = `${base}/assist/models/`;
		if (await cache.match(`${models}${ENCODER_PATH}/onnx/model_quantized.onnx`)) return 'present';
		// Some version of this encoder is here, and it is not the one this build
		// reads. The path carries the date the weights were fetched, so an older
		// one is a different URL and a whole second download.
		const keys = await cache.keys();
		const older = keys.some((request) => request.url.includes(`${models}${ENCODER_ID}/`));
		return older ? 'stale' : 'absent';
	} catch {
		return 'unknown';
	}
}

/** Turn the library's per-file events into one running byte count. */
function watch(report: (progress: EncoderProgress) => void) {
	const byFile = new Map<string, number>();
	let landed = false;
	return (event: { status: string; file?: string; loaded?: number }) => {
		// The weights are the last and by far the largest file, so the moment they
		// finish is the moment a byte count stops being able to say anything.
		if (event.status === 'done' && event.file?.endsWith('.onnx')) landed = true;
		if (event.status === 'progress' && event.file && typeof event.loaded === 'number') {
			byFile.set(event.file, event.loaded);
		}
		let loaded = 0;
		for (const bytes of byFile.values()) loaded += bytes;
		report({ loaded, landed });
	};
}

/** Load the encoder. Idempotent, and safe to call twice from an impatient click. */
export async function load(onProgress?: (progress: EncoderProgress) => void): Promise<Extractor> {
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
			progress_callback: onProgress ? watch(onProgress) : undefined,
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
export async function embedQuery(
	text: string,
	onProgress?: (progress: EncoderProgress) => void
): Promise<number[]> {
	const pipe = await load(onProgress);
	const output = await pipe(text, { pooling: 'mean', normalize: true });
	return output.tolist()[0];
}
