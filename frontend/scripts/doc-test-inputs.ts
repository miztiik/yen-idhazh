/** Which documentation pages a browser spec reads as its input.
 *
 * A spec that asserts against a page makes that page an input to the spec, so
 * an edit to the page can turn the spec red. The selector must then run the
 * spec rather than answer "documentation only". The spec reads its path from
 * here and the selector keys on the same string, so a page that moves takes
 * the selector with it, or the spec goes red on the change that moved it.
 */

/** The page whose table rules the eleven labels on the console's model cards. */
export const CONSOLE_MODEL_LABELS_PAGE = 'docs/concepts/console-design/what-the-quality-and-source-panels-draw.md';
