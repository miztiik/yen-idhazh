/* Generated from config/appearance.json by scripts/build-worker-switch.mjs.
   Do not hand-edit: the build regenerates it and a diff fails the gate. */

/** The version this build's offline reader carries. */
export const OFFLINE_VERSION = 1;

/** How many opened days the offline reader keeps on the reader's device. */
export const OFFLINE_DAYS_KEPT = 14;

/** The most bytes of kept days the offline reader leaves on the reader's
 * device. The second bound, because a day count cannot bound bytes. */
export const OFFLINE_BYTES_KEPT = 20000000;
