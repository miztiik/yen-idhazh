/** The three widths the console is measured and pictured at, in CSS pixels.
 *
 * One list, because the console used to be measured at three different sets
 * and a panel that passed at one set was never seen at another. The date-axis
 * oracle, the panel captures and the sufficiency gates all read this list, so
 * a fourth width is added here once rather than forked into one spec.
 *
 * Widest first: 1440 is a desktop, 768 a tablet held upright, and 390 a phone.
 * The phone is the one a panel is judged at most strictly, because it is the
 * narrowest and the least looked at.
 */
export const CONSOLE_WIDTHS = [1440, 768, 390] as const;

export type ConsoleWidth = (typeof CONSOLE_WIDTHS)[number];

/** The window height a console page is opened at before anything is measured.
 *
 * On every route but the Data explorer, nothing is sized from the window's
 * height except the body's minimum height, so this decides only how much of
 * the page is on screen at once - and through that, which charts are near
 * enough to be drawn. The Data explorer's workbench is sized from it: it fills
 * the window from 1024 px, and its answer is one window tall below that.
 */
export const CONSOLE_WINDOW_HEIGHT = 900;
