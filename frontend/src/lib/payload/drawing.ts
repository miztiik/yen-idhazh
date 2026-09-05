/** What a drawing has to be before it may enter the document.
 *
 * Inside an `img` an SVG is a separate, inert document whatever it holds. The
 * moment it is inlined it is markup in our own origin - and a chart's labels
 * are written by a model that read a stranger's page, so this is the trust
 * boundary moving and it gets a check rather than a promise (Rule #11).
 *
 * **Both sides of the move import this file, and that is the whole reason it
 * exists.** The build inlines the stories a prerendered document carries; the
 * browser fetches the drawing for the stories past that seed. Two copies of one
 * refusal is how the two drift, and the browser's copy is the one that matters,
 * because that is the path a stranger's bytes travel without a person watching.
 *
 * It imports nothing. `node:fs` in this graph would put the build's file reader
 * in a browser bundle, and a `$lib` alias would put a Vite alias in a plain
 * `node` process - so the module has no imports at all and both callers get the
 * same code.
 *
 * Nothing here repairs a file that trips it. A drawing that fails is not drawn,
 * and the caller says which one.
 */

/** A published visual's path, as a file we are allowed to open or ask for.
 *
 * The value comes off a committed payload rather than off the web, and it is
 * still matched rather than trusted: it is about to be joined onto a directory
 * and read, or onto `base` and fetched, and a path that walked out of the
 * digest tree would be taken all the same. The shape is the one `route.py`
 * writes - the date the day was published on, then one file named for its desk.
 */
const VISUAL_PATH = /^digest\/\d{4}\/\d{2}\/\d{2}\/[a-z0-9][a-z0-9_-]*\.svg$/;

/** What a drawing may not carry into the document. */
const NOT_INERT = /<\s*(script|foreignObject|iframe|image|use|a|set|animate)\b|\son[a-z]+\s*=|javascript:/i;

/** Whether this is a path this site published a drawing at. */
export function publishedVisual(path: string): boolean {
	return VISUAL_PATH.test(path);
}

/** Why this markup may not be drawn, or null when it may.
 *
 * A sentence rather than a boolean, because both callers log it and the file it
 * came from is the other half of a message worth reading.
 */
export function refusedDrawing(markup: string): string | null {
	if (!markup.startsWith('<svg')) return 'does not open on an svg element';
	if (NOT_INERT.test(markup)) return 'carries markup a document may not run';
	return null;
}
