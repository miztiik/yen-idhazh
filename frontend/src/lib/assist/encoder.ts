/** What the browser and the runner must agree about, in one place.
 *
 * `backend/idhazh/embed.py` stamps the identifier into every day payload and
 * loads the weights from the directory these constants name. The browser reads
 * that payload and fetches that directory. A disagreement between the two files
 * is neither a type error nor a 404 - it is a search that returns confident
 * nonsense - so `backend/tests/test_embed.py` reads this file and fails when
 * the two drift.
 *
 * Contract, not configuration, on the grounds `embed.py` gives for its own
 * copy: a knob here is a way to turn the guard off by accident.
 *
 * Nothing framework-specific is imported, on purpose. `search.ts` depends on
 * this module, and the browser suite imports `search.ts` directly in Node,
 * where `$lib` and `$app` do not resolve.
 */

/** The identifier the runner stamps into `embeddings.model_id`.
 *
 * Lower case because the payload contract types that field as a slug -
 * `^[a-z0-9]+(?:-[a-z0-9]+)*$` - so the upstream repository's mixed-case name
 * could never be written into a day. The browser used to hold that mixed-case
 * name instead, which is why the guard in `search.ts` could not be written.
 */
export const ENCODER_ID = 'all-minilm-l6-v2-quantized';

/** The directory under `assist/models/` that transformers.js loads.
 *
 * Separate from the identifier because one constant was doing both jobs, and a
 * path pinned to an identifier is a path nobody can version.
 */
export const ENCODER_PATH = 'all-MiniLM-L6-v2';
