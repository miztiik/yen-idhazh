/** Which configured category matches a feed entry's category tags? */
export function findBlockedCategory(categories: readonly string[], blocked: readonly string[]): string | null {
  const excluded = new Set(blocked.map(category => category.trim().toLowerCase()));
  return categories.find(category => excluded.has(category.trim().toLowerCase())) ?? null;
}
