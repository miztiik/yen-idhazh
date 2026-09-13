/** What a drawing has to be before it may enter the document, and what a
 * visual's data has to be before it may be drawn.
 *
 * Inside an `img` an SVG is a separate, inert document whatever it holds. The
 * moment it is inlined it is markup in our own origin - and a chart's labels
 * are written by a model that read a stranger's page, so this is the trust
 * boundary moving and it gets a check rather than a promise (Guardrail #11).
 *
 * `refusedVisualData` is the same boundary one step earlier. From 2026-09-13 the
 * reader's browser draws the chart and the pipeline never does, so what arrives
 * is data rather than a finished picture - and data that does not fit the type
 * it names is refused rather than guessed at.
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

/** A published visual's data file, as a file we are allowed to ask for.
 *
 * The value comes off a committed payload rather than off the web, and it is
 * still matched rather than trusted: it is about to be joined onto `base` and
 * fetched, and a path that walked out of the digest tree would be taken all the
 * same.
 *
 * **The name has to be an item's**, which the `.svg` pattern above never had to
 * say because no day payload was ever called `<something>.svg`. It is now: the
 * day's own `digest.json` and `run.json` sit in the same directory and carry the
 * same extension. An item id ends in a hyphen and a run of digits or sixteen
 * base32 symbols, so neither can ever look like one - and that is the same rule
 * the writer, the retention prune and the bundle staging read, rather than four
 * spellings of it.
 */
const VISUAL_DATA_PATH =
	/^digest\/\d{4}\/\d{2}\/\d{2}\/[a-z0-9]+(?:-[a-z0-9]+)*-(?:[0-9]{2,}|[0-9a-hjkmnp-tv-z]{16})\.json$/;

/** What a drawing may not carry into the document. */
const NOT_INERT = /<\s*(script|foreignObject|iframe|image|use|a|set|animate)\b|\son[a-z]+\s*=|javascript:/i;

/** Whether this is a path this site published a drawing at.
 *
 * **Nothing publishes one from 2026-09-13.** The build-time renderer is deleted
 * and the 495 committed drawings with it, so this and `refusedDrawing` below
 * are the read side of a day whose payload still names a `.svg`: the build asks
 * for a file that is not there and the story is simply shorter. They go with
 * the build-time inlining they serve, in the row that deletes it.
 */
export function publishedVisual(path: string): boolean {
	return VISUAL_PATH.test(path);
}

/** Whether this is a path this site published a visual's marks at. */
export function publishedVisualData(path: string): boolean {
	return VISUAL_DATA_PATH.test(path);
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

/** The drawing contracts this page knows how to read.
 *
 * A published visual states the `renderer_version` it was compiled for. A
 * version this page does not hold is refused rather than read: the shape is
 * allowed to move, and a page that guessed at a later one would draw a chart
 * from data that means something else.
 *
 * **A renderer bump re-draws whole days or none.** One page must not draw two
 * styles in one scroll, which reads as a broken site - so the set holds the
 * versions this build can draw and a day compiled for any other one is simply
 * shorter.
 */
const RENDERERS = new Set(['2026-09-13']);

/** The forms this page can check, and later draw.
 *
 * One member, because the compiler writes one. Every other member of the
 * declarable vocabulary is a type nobody can draw here, and drawing a `line` as
 * bars because bars are what we have would publish a picture nobody planned.
 */
const DRAWABLE = new Set(['bar']);

/** One mark as it arrives off the wire: checked rather than trusted. */
type Mark = { mark_id?: unknown; text?: unknown; value?: unknown };

function isObject(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function channel(encoding: Record<string, unknown>, role: string): string[] | null {
	const named = encoding[role];
	if (!Array.isArray(named)) return null;
	return named.every((id) => typeof id === 'string') ? (named as string[]) : null;
}

/** Why this visual data may not be drawn, or null when it may.
 *
 * **It refuses rather than guesses, and refusing is free.** A degrade path that
 * draws something approximate is how a wrong chart reaches a reader, and the
 * product is trust. A story with no visual is simply shorter - already the
 * shape 94.7 percent of stories have - so a refusal costs no layout and needs
 * no placeholder.
 *
 * The checks are the ones a shape can answer: the page knows this renderer, the
 * page knows this type, every channel names marks that are there, and the
 * channels of a `bar` pair into bars. Whether three bars are enough to be worth
 * the space is an editorial floor and the pipeline holds it; a drawing code that
 * re-decided one here would be a second opinion nobody could reconcile.
 */
export function refusedVisualData(data: unknown): string | null {
	if (!isObject(data)) return 'is not a visual-data document';

	const renderer = data.renderer_version;
	if (typeof renderer !== 'string' || !RENDERERS.has(renderer)) {
		return `was compiled for renderer ${JSON.stringify(renderer)}, which this page does not know`;
	}
	const type = data.type;
	if (typeof type !== 'string' || !DRAWABLE.has(type)) {
		return `names a type this page cannot draw: ${JSON.stringify(type)}`;
	}

	const marks = data.marks;
	if (!Array.isArray(marks) || marks.length === 0) return 'carries no marks';
	const held = new Map<string, Mark>();
	for (const mark of marks as Mark[]) {
		if (!isObject(mark) || typeof mark.mark_id !== 'string') return 'carries a mark with no id';
		held.set(mark.mark_id, mark);
	}

	const encoding = data.encoding;
	if (!isObject(encoding)) return 'carries no encoding';
	const names = channel(encoding, 'category');
	const figures = channel(encoding, 'quantity');
	if (names === null || figures === null) return 'carries a channel that is not a list of marks';
	for (const id of [...names, ...figures]) {
		if (!held.has(id)) return `draws a mark it does not carry: ${JSON.stringify(id)}`;
	}

	// The one type this build draws. A second type arrives with its own drawing
	// code and its own rule; until then every other one is refused above.
	if (names.length === 0 || names.length !== figures.length) {
		return `draws ${names.length} names against ${figures.length} figures, which do not pair into bars`;
	}
	for (const id of names) {
		if (typeof held.get(id)?.text !== 'string') return `draws a bar with no name: ${JSON.stringify(id)}`;
	}
	for (const id of figures) {
		if (typeof held.get(id)?.value !== 'string') {
			return `draws a bar with no figure: ${JSON.stringify(id)}`;
		}
	}
	return null;
}
