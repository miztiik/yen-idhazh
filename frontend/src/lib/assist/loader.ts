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
import { fetchVerifiedWeights, injectedSource, type WeightsRefusal } from './weights';

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

/** The same three files from the second origin, which does not compress them.
 *
 * 50 MB rather than 43. Our origin serves `model_quantized.onnx` gzipped at
 * 16.22 MB (measured 2026-09-08 on a laptop against CloudFront AMS58-P3, n=3,
 * spread 0) where the hub serves its 22,972,370 bytes as they are, so the same
 * encoder costs about 6.75 MB more when this site could not hand it over.
 *
 * It is a second constant and not a correction to the first because almost
 * nobody pays it: the failover runs only after our own origin has already
 * failed that reader. Printing 50 to everyone would overstate the cost for the
 * whole audience to be accurate for the few. */
export const DOWNLOAD_MB_ELSEWHERE = 50;

/** The token cap the runner truncates at, repeated here because it is not shared yet.
 *
 * One artifact, two runtimes only holds if both runtimes read the same amount
 * of text. The tokenizer config says 512 and the pipeline takes its cap from
 * there, so without this line a long query is read twice as far in the tab as
 * every item it is compared against.
 *
 * This is not a fallback. Nothing merges `config/` over it, so it is the only
 * cap a tab ever uses, and the number it has to equal is `assist.max_tokens`
 * in `config/idhazh.json` - the cap the runner truncated the items at.
 * `backend/tests/test_embed.py` refuses a build where the two differ, so
 * editing that knob means editing this line in the same commit.
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

/** Why the last failover attempt refused, or `null` if it never ran. */
let refusal: WeightsRefusal | null = null;

/** What the second origin did on the last attempt. For a sentence, not a branch. */
export function lastRefusal(): WeightsRefusal | null {
	return refusal;
}

/**
 * Fetch the encoder from the second origin, verify it, and put it where the
 * library is already looking. `true` only when every file verified.
 *
 * The cache keys are the same-origin URLs `localModelPath` resolves to, which
 * is the same store and the same keys transformers.js writes itself and
 * `cachedEncoder()` reads. A reader who takes this path is indistinguishable
 * afterwards from one who never needed it - including on their next visit.
 *
 * **Nothing is written until every digest has matched.** The loop below runs
 * only on a set `fetchVerifiedWeights` has already checked whole, so a set with
 * one bad file leaves no trace: there is no half-seeded cache to recover from
 * and no way for a later load to read a file this build did not vouch for.
 */
async function seedSecondOrigin(
	onProgress?: (progress: EncoderProgress) => void
): Promise<boolean> {
	const source = injectedSource();
	if (!source.baseUrl || typeof caches === 'undefined') {
		refusal = 'off';
		return false;
	}

	const outcome = await fetchVerifiedWeights(source, {
		onBytes: (loaded) => onProgress?.({ loaded, landed: false })
	});
	if (!outcome.ok) {
		refusal = outcome.reason;
		return false;
	}

	try {
		const cache = await caches.open(MODEL_CACHE);
		for (const [path, bytes] of outcome.files) {
			await cache.put(
				`${base}/assist/models/${ENCODER_PATH}/${path}`,
				new Response(bytes, { headers: { 'content-length': String(bytes.byteLength) } })
			);
		}
	} catch {
		// A full or blocked cache. The bytes verified, so nothing unsafe happened -
		// there is just nowhere to put them, and the retry would read our origin
		// again and fail again. Say so rather than loop.
		refusal = 'unreachable';
		return false;
	}

	refusal = null;
	onProgress?.({ loaded: 0, landed: true });
	return true;
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
		//
		// **These three are unchanged by the second origin, and that is the
		// design rather than an omission.** `allowRemoteModels = false` is what
		// makes our own copy primary: the library resolves every file against
		// `localModelPath`, so "local first" is literally what happens with no
		// ordering code to get wrong. Setting it true would also hand the library
		// the fetch, and a file the library fetched is a file nothing hashed - the
		// manifest would then bound nothing at all. The failover below fetches,
		// verifies, and only then puts the bytes where the library was already
		// looking, so every byte is checked before transformers.js sees one.
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

		const start = () =>
			transformers.pipeline('feature-extraction', ENCODER_PATH, {
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

		// Our own origin, then - only if it failed this reader - the second one.
		//
		// The ordering is the library's own resolution rather than code of ours:
		// with `allowRemoteModels = false` the first call can only read our copy,
		// so a reader whose first call works never learns a second origin exists
		// and never pays the extra 6.75 MB. `seedSecondOrigin` verifies every
		// file against the committed manifest and puts the bytes into the cache
		// the library was already looking in, so the retry is an ordinary local
		// load. If seeding refuses for any reason, the ORIGINAL failure is thrown -
		// the reader is told our download did not work, which is what happened.
		let pipe;
		try {
			pipe = await start();
		} catch (ourOrigin) {
			if (!(await seedSecondOrigin(onProgress))) throw ourOrigin;
			pipe = await start();
		}
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
