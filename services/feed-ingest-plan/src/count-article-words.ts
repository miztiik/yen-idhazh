/** Count article words with the shared Unicode whitespace definition. */
export function matchArticleWords(text: string) {
  return text.matchAll(/[^\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/gu);
}

export function countWords(text: string): number {
  let count = 0;
  for (const _word of matchArticleWords(text)) count++;
  return count;
}
