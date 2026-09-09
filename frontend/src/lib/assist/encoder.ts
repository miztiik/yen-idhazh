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

/** The date `PROVENANCE.md` records these weights were fetched.
 *
 * It is in the URL so that different weights are a different URL. Without it a
 * browser holding the old encoder in its HTTP cache would answer a new day's
 * vectors with it, and the only symptom is worse ranking.
 *
 * Moving it makes every returning searcher pay the whole download again, so it
 * moves when the weights move and at no other time. That is also why it is a
 * DATE and not the upstream commit below: the two say different things, and
 * putting the commit in the path would rename the directory - and re-download
 * 23 MB on every returning reader - the first time a revision was corrected
 * without the bytes changing.
 */
export const ENCODER_DIRECTORY = '2026-08-22';

/** The upstream commit the committed weights are the bytes of.
 *
 * Forty hex characters, and the same value as `assist.model_revision` in
 * `config/idhazh.json` - `backend/tests/test_embed.py` fails when the two
 * differ. It is what the failover leg pins its fetch to, so the second origin
 * is asked for the bytes this manifest describes rather than for whatever was
 * uploaded to a branch last.
 *
 * It does NOT identify one commit: the parent carries the same five files. It
 * is the head of `main` on the fetch date, recorded because a fetch has to name
 * something and a branch name names nothing repeatable.
 */
export const ENCODER_VERSION = '751bff37182d3f1213fa05d7196b954e230abad9';

/** The directory under `assist/models/` that transformers.js loads.
 *
 * Built from the two constants above rather than written out, so the path
 * cannot disagree with the identifier it is named for. transformers.js reads
 * this as a model id, and a slash in one is ordinary - upstream ids are
 * `org/name`.
 */
export const ENCODER_PATH = `${ENCODER_ID}/${ENCODER_DIRECTORY}`;

/** The width the runner writes, so the guard can run before a query exists.
 *
 * `rank` takes the width from the query vector it was handed, which is the
 * stronger check because it measures what actually arrived. This constant is
 * for the one moment there is no query yet: deciding whether to start the
 * download at all.
 */
export const ENCODER_DIMENSIONS = 384;
