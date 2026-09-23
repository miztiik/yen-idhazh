# The on-device encoder, and what its vectors promise

**Last Updated**: 2026-09-23

On-device search only means anything if the runner and the reader's tab compute
the same numbers from the same words. Four things hold that: the day names the
encoder that wrote its vectors, the browser refuses vectors from any other, the
encoder itself has a second origin that is safe only because of a manifest, and
the arithmetic is pinned so one sentence embeds the same way in a batch and
alone. This page holds all four, and the repair that had to run when one of them
arrived late. The control that downloads the encoder is
[how-a-reader-finds-a-story.md](how-a-reader-finds-a-story.md).

## The archive names its encoder, and refuses vectors from any other

On-device search on `/archive/` embeds a query in the tab and dot-products it against vectors the runner committed. That only means anything if both sides used the same encoder, so the payload has always carried `embeddings.model_id`. Until 2026-08-26 nothing read it: the browser checked the width and the dtype and nothing else, so a day written by a different 384-wide int8 encoder passed and was ranked. The scores looked like scores.

Three rules hold it together now.

- **One identifier, and it is the runner's.** `embeddings.model_id` is a `Slug` in the payload contract - `^[a-z0-9]+(?:-[a-z0-9]+)*$` - so `all-minilm-l6-v2-quantized` is the only one of the two strings that can be written into a day at all. The browser used to hold the upstream repository's mixed-case `all-MiniLM-L6-v2` instead. That name could never have reached a payload, so reconciling to it would have meant widening a persisted contract to accommodate a spelling.
- **The identifier and the path are different constants.** One constant used to be both, which is why the path could not be versioned without changing what the guard compares. `frontend/src/lib/assist/encoder.ts` now holds the identifier, the version and the width; `backend/tests/test_embed.py` reads that file and fails when it disagrees with `backend/idhazh/embed.py`. There is no config knob, on the grounds `embed.py` already gives for its own copy: a knob here is a way to turn the guard off by accident.
- **The path carries the version, so different weights are a different URL.** `assist/models/<identifier>/<the date the weights were fetched>/`. A browser caches 43 MB on first search; without the date, a returning reader would answer new vectors with an old encoder and the only symptom would be worse ranking.

The cost is paid on the day the date moves: every returning searcher downloads the encoder again, in full. That is why it moves when the weights move and at no other time.

A reader whose days were written by another encoder gets one line where the offer was, and gets it **before** the download rather than after - there is nothing they can do about it, so there is nothing to prompt them about, and no reason to spend 43 MB of their connection first.

**From 2026-09-10 that guard compares two things that can really differ**, and until then it could not. The browser's encoder was the one this site published, so `model_id` could only ever match; it was a check written against a failure that had no way to happen. The second origin below is what gives it a job.

## The encoder has a second origin, and a manifest is what makes that safe

Our own origin is primary and the committed weights stay. A reader whose fetch of them fails - a dead cache, a partial deploy, a network that answers this site but not that file - used to get an archive with no search in it and one sentence saying the download did not finish. Since 2026-09-10 the browser tries again at Hugging Face.

**The ordering is the library's own resolution, not code of ours.** `transformers.env.allowRemoteModels` stays `false` and `allowLocalModels` stays `true`, so the first `pipeline` call can only read our copy. Nobody pays the second origin's extra 6.75 MB unless this site has already failed them, and there is no ordering code to get wrong. Only when that call throws does [frontend/src/lib/assist/weights.ts](../../../frontend/src/lib/assist/weights.ts) run.

**The URL is the convenience; the manifest is the point.** `assist.model_digests` in `config/idhazh.json` holds the SHA-256 of all five encoder files. The browser hashes every arriving file and compares before a single byte reaches transformers.js. On any miss - a non-200, a truncation, a timeout or a wrong digest - the **whole set is discarded**, and the reader is told the download did not finish. Provenance is never mixed across files: five verified files or none, never four of ours and one of theirs. Without that, naming a second origin would be a permission for another party to put bytes into a reader's tab.

Four things make it check rather than look like it checks.

- **The manifest is baked into the bundle, not fetched.** `vite.config.ts` reads it from `config/` at build time into `__ENCODER_SOURCE__`. A manifest a page fetched could be answered by whoever answered the fetch, which is the thing it exists to guard against. It rides in the `/archive/` route's JavaScript rather than the prerendered document, so roughly 600 bytes of hex stay out of a page measured against a 6,400-byte ceiling.
- **The fetch is pinned to a 40-hex commit.** `assist.model_revision` is refused by the contract unless it is one, because a branch hands back whatever was uploaded last and would make every digest a coin flip. `ENCODER_VERSION` in `encoder.ts` is the browser's copy of it and `backend/tests/test_embed.py` fails when the two differ.
- **The manifest is checked against the committed weights on every build**, not on a reader's device. A manifest that drifted from the bytes would discard every set a browser fetched and leave no trace except readers with no search. The same test hashes the five files.
- **An incomplete block turns the leg off rather than half on.** `encoderSource` in [frontend/asset-base.js](../../../frontend/asset-base.js) answers the empty block unless a URL, a revision, a non-empty manifest and a deadline are all present, so a config edit cannot widen `connect-src` without also committing what the bytes must hash to.

**`connect-src` ships as `'self' https://huggingface.co https://us.aws.cdn.hf.co`.** Three sources, every one derived from `config/idhazh.json` by the same module the fetch reads, so the CSP half and the fetch half cannot disagree. The CDN is listed because a browser checks a redirect target: measured 2026-09-09 from the live Pages origin, 15 reads of 15, the four small files answer on the base host and the 23 MB of weights answers 302 to that CDN. Listing the base host alone would pass the small files and block the model, which is the worst of both.

**A GitHub Release asset cannot serve this**, which is why the second origin is the hub rather than a copy we publish. Measured the same day: no `Access-Control-Allow-Origin` on any hop, 15 refusals in 15 attempts.

**The release that was built for that leg is deleted, and the decision is taken.** Tag `encoder-2026-08-22` at commit `5f1eaf60`, and the release under it carrying the five weight files as flat assets, were made on 2026-09-09 for the failover the measurement above killed. Nothing referenced them: not `config/`, not `asset-base.js`, not a test - only `backend/utilities/encoder_origin_probe.mjs`, which is a hand-run operator tool that joins no suite. **What they cost was not disk.** A tag pins that commit's whole tree - `corpus/` and its article text included - reachable for ever, and `.github/workflows/prune.yml` pushes no tags, so for that one commit it would have quietly undone the thing CLAUDE.md section 8 grants the prune its force-push exception to achieve. That cost had not arrived yet: measured 2026-09-10, `git rev-list 5f1eaf60 --not origin/main` was empty, so the tag held nothing `main` did not already hold. It would have arrived on the day the next prune reached that range, which is exactly when nobody would be looking. **What the deletion cost is stated rather than implied:** the five assets a browser trace verified have no published copy now, and any later argument about that leg starts from a fresh measurement. The measurement itself survives in [../../reference/site-weight.md](../../reference/site-weight.md), which is what an argument would cite anyway. Owner decision, 2026-09-10, taken over the alternative of keeping the tag and recording a deliberate hole in the section 8 exception. The probe now reads the weights at `main` rather than at a tag, and its two release target families are gone with the release.

**What it costs a reader, said before they press the button.** The search panel's sentence names this site as the source, and adds one conditional clause: if this site cannot serve the files, the browser asks Hugging Face instead - about 50 MB rather than 43, because the hub does not compress the weights - and they would see the request. The unconditional half stays first and stays true either way: nothing a reader types leaves their browser. Almost nobody pays the conditional half, so it does not open the sentence; a reader deciding whether to start is still told before they start.

The service worker never touches any of it. It refuses an off-origin request before it looks at anything else, so the only copy of a fetched-elsewhere encoder is the one the loader put in the library's own store **after** hashing it. A worker that cached it would be a second copy nobody verified, keyed by a URL nobody checked.

## A vector is a function of its own text, and of nothing it travelled with

Naming the encoder is only half the promise. The other half is that the runner and the tab compute the same thing from the same words, and until 2026-08-26 they did not.

The committed encoder is **dynamically quantised** - 24 `DynamicQuantizeLinear` nodes feeding 36 `MatMulInteger`. A dynamic quantiser reads its activation scale off whatever tensor it is handed, so every sentence in a batch helps set the range the other fifteen are measured against, and so does every pad token. The runner used to embed sixteen items at a time padded to the longest of them; the browser embeds one query with no padding. Measured 2026-08-25 over 48 committed items, the two paths agreed byte for byte on **0 of 48**, and the cosine between them bottomed out at 0.9926. Two batches of sixteen that shared one sentence disagreed about that sentence by up to 1.46e-2 per component - far above anything int8 quantisation hides.

So the rule the encoder path holds to now:

- **One sequence per forward pass, no padding, truncated at `assist.max_tokens`.** That is exactly what a tab does with a lone query, which is the only way the two sides can be compared at all.
- **One intra-op thread, one inter-op thread, sequential execution, the CPU provider named.** The session used to be built with no options, so the thread count came from the host's core count and float addition is not associative.
- **`onnxruntime` is pinned exactly, not floored.** A kernel rewrite in a patch release moves the bytes without moving any API a test watches.

The cost is about 14 percent of the encode stage - 121 ms an item before, 138 ms after, over 48 real items on a loaded developer machine - which is under a minute for every item ever published.

A vector that predates this rule cannot be told apart from one that follows it, because `DigestEmbeddings` records the model, the width and the dtype and not the arithmetic. That is why the repair below re-encodes a short day whole.

## The committed days were part empty, and part written by a retired arithmetic

`build_day` used to replace a day's embeddings block instead of merging it, so a day that ran five times kept the last run's vectors alone. It merges now. Nothing revisits a closed day, though - a scheduled run only ever appends to the current one - so the days already committed stayed wrong until something went back for them. On 2026-08-26 the five closed days held 439 vectors for the 1,614 items that had earned one. `python -m idhazh backfill-vectors` is that something, and [`../../reference/github-actions.md`](../../reference/github-actions.md#vector-backfill) owns how it is run.

**The repair re-encodes a wrong day whole rather than topping it up**, and the reason came out of the measurement rather than the design. Re-encoding the 439 vectors those days already carried reproduced them at a median cosine of 0.9936 - not 1.0 - and moved the top-10 neighbour list of 413 of them. The same test against the day CI had written hours earlier returned a median cosine of exactly 1.000000 with 54 of 80 vectors byte-identical. So the gap was the code, not the machine: every closed day predates the commit that stopped `encode` padding its input and batching it, and its vectors carry an arithmetic the browser's query encoder no longer uses. Filling only the gaps would have left one block holding two arithmetics, and a reader's query cannot rank two populations it cannot compare fairly. One block, one encoder - the same rule `assemble.merge_embeddings` already applies across model ids.

After the repair, a re-encode of a repaired day reproduces it byte for byte: cosine 1.000000 over 180 sampled vectors, zero rank movement, maximum byte delta 0.

**An item that earns no vector gets none, and loses the one it had.** The count to hold a day against is the items above `assist.min_readable_letter_share`, not `len(items)`: a headline in a script the encoder's vocabulary does not carry gets a well-formed vector about its characters rather than its story, which no query a reader types will ever retrieve. Two items on the closed days are in that state, and neither had a vector to lose.

**The current UTC day is excluded and always will be.** A day payload is one JSON file with no union merge, and the scheduled pipeline appends to the live day several times an hour. Two producers writing it do not interleave - one wins whole and the other one's run is gone.

**Two days are still short of that promise, and nothing can see it.** 2026-08-21 and 2026-08-22 already carried a vector for every item they earned, so the repair skipped them - which is what makes the command safe to dispatch twice. Their 14 vectors are still the retired arithmetic. `DigestEmbeddings` records the model, the width and the dtype, and nothing records which encoder path wrote a vector, so no detector can tell a stale block from a current one when the counts agree. Fixing that means a field on a persisted contract, which is a `CLAUDE.md` section 6 Level 5 change and belongs to whoever signs it.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Reconciling the encoder identifier to the upstream `all-MiniLM-L6-v2` | `embeddings.model_id` is a slug, so that spelling can never be written into a payload. Adopting it means widening a persisted contract to fit a capital letter, and re-stamping five committed days to buy nothing. | Fowler, Andre |
| A config knob for the encoder identifier or its version | The guard compares a payload against this string. A knob is a way to turn the guard off by accident, which is the same reason `embed.py` refuses one for its own copy. | Andre |
| Telling the reader their vectors are stale and offering to update | There is no update for them to take - the encoder is whatever this build committed. A prompt with no action behind it is a notification asking for thanks. | Jony, Reader |
| Padding every sequence to the token cap so batch composition stops mattering | It was the first proposal and the measurement refused it. Fixed padding removes the *shape* a batch imposes, not the *scale* it sets: pad-to-cap against no padding still moved a component by 1.56e-2, and padding also moves the runner further from a browser that pads nothing. | Carmack, Guardrail #10 |
| Accepting host variation and gating a re-encode on cosine alone | A cosine tolerance is the right check for a backfill, but leaving the arithmetic unpinned makes every future re-encode a fresh argument about which machine was right. | Carmack |
| Serving the second copy of the weights from a GitHub Release asset | No `Access-Control-Allow-Origin` on any hop, 15 refusals in 15 attempts, measured 2026-09-09. A browser cannot read it at all. | Carmack |

## See also

- [frontend.md](frontend.md) - what a build writes and what a browser fetches, and where the rest of the reader's surface is written up.
- [how-a-reader-finds-a-story.md](how-a-reader-finds-a-story.md) - the search control that downloads this encoder, and the scope it reads.
- [../../concepts/search-quality.md](../../concepts/search-quality.md) - what the ranking these vectors feed is measured against.
- [../../concepts/config/appearance.md](../../concepts/config/appearance.md) - the `assist` knobs: the token cap, the second origin, the digests and the deadline.
- [../../reference/github-actions.md](../../reference/github-actions.md#vector-backfill) - how the repair above is dispatched.
- [../contracts/schemas.md](../contracts/schemas.md) - `DigestEmbeddings`, and what a day records about its vectors.
