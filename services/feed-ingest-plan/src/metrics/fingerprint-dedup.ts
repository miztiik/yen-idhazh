/** Which article identities remain after exact retry copies are removed? */
export function uniqueRecorded<T>(
  rows: readonly T[], identity: (row: T) => string, same: (left: T, right: T) => boolean,
): T[] {
  const held = new Map<string, T>();
  for (const row of rows) {
    const key = identity(row);
    const previous = held.get(key);
    if (previous !== undefined && !same(previous, row)) throw new Error(`Conflicting recorded identity: ${key}`);
    if (previous === undefined) held.set(key, row);
  }
  return [...held.values()];
}

export type PublishedArticle = Readonly<{
  date: string; run_id: string; item_id: string; url_key: string;
  source_id: string; source_kind: string | null; lead: boolean;
}>;

export function uniquePublishedArticles(rows: readonly PublishedArticle[]): PublishedArticle[] {
  const chronological = [...rows].sort((a, b) => a.date.localeCompare(b.date)
    || a.run_id.localeCompare(b.run_id) || a.item_id.localeCompare(b.item_id));
  const held = new Map<string, PublishedArticle>();
  for (const row of chronological) {
    const previous = held.get(row.url_key);
    if (previous === undefined) held.set(row.url_key, row);
    else if (previous.date === row.date && previous.item_id === row.item_id) {
      if (previous.run_id !== row.run_id || previous.source_id !== row.source_id || previous.source_kind !== row.source_kind) {
        throw new Error("Retry changed a published article's recorded attribution");
      }
      held.set(row.url_key, { ...previous, lead: previous.lead || row.lead });
    }
  }
  return [...held.values()];
}
