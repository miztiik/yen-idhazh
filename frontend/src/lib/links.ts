/** Where a topic lives, computed once.
 *
 * The pill and the section's own link point at the same route. Deriving that
 * path in two components is how they come to disagree.
 */

export function dayRoot(base: string, datePrefix: string): string {
	return datePrefix ? `${base}/${datePrefix}` : base || '/';
}

export function verticalHref(base: string, datePrefix: string, id: string): string {
	const root = dayRoot(base, datePrefix);
	return `${root}${root.endsWith('/') ? '' : '/'}${id}/`;
}
