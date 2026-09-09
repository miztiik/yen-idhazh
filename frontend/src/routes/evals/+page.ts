/** The scores address is a signpost, and a signpost has to be a document.
 *
 * `/evals/` carries a `meta refresh` to the console and a link under it for a
 * browser that ignores one. It has no load and no data, so until 2026-09-09 it
 * was prerendered by the flag on the root layout and needed no file of its own.
 * The layout is a universal load now and page options went with it.
 *
 * Without this the page is not written, `config/idhazh.json` names a `/evals/`
 * ceiling that matches no route in the build, and `scripts/bundle-gate.mjs`
 * fails - which is the gate working: a ceiling over nothing still reads as a
 * bound somebody checked.
 */
export const prerender = true;
