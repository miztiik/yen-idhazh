/** Do combined summaries reconcile article identities, assignments and optional readable URLs? */
import { expect, test } from "bun:test";
import {
  PlanRunRowSchema, PlannerErrorResponseSchema, PlannerRunResponseSchema, PlannerSavedResponseSchema,
  SelectedArticleRowSchema, deriveUrlKey,
} from "../src";

async function recording() {
  const root = new URL("../../../tests/fixtures/feed-ingest-plan/entry-points/", import.meta.url);
  const response = PlannerRunResponseSchema.parse(await Bun.file(new URL("response.json", root)).json());
  const rows = SelectedArticleRowSchema.array().parse(await Bun.file(new URL("selected-articles.rows.json", root)).json());
  return { response, rows };
}

test("URLs are all present with matching digests or all omitted, without retired public aliases", async () => {
  const { response, rows } = await recording();
  const first = rows[0]!;
  const canonical_url = `${first.canonical_url}?edition=second`;
  const selected = [first, SelectedArticleRowSchema.parse({
    ...first, canonical_url, url_key: deriveUrlKey(canonical_url), editorial_rank: 2,
  })];
  const assignments = selected.map(row => ({
    article_id: row.url_key, canonical_url: row.canonical_url,
    editorial_rank: row.editorial_rank, worker_assignment: row.worker_assignment,
  }));
  const shown = PlannerRunResponseSchema.parse({
    ...response, selected_count: 2, selected_article_ids: selected.map(row => row.url_key),
    include_selected_urls: true, assignments,
  });
  const hidden = PlannerRunResponseSchema.parse({
    ...shown, include_selected_urls: false,
    assignments: assignments.map(({ canonical_url: _url, ...assignment }) => assignment),
  });
  expect(shown.assignments.map(row => row.canonical_url)).toEqual(selected.map(row => row.canonical_url));
  expect(hidden.assignments.every(row => !Object.hasOwn(row, "canonical_url"))).toBe(true);
  for (const invalid of [
    { ...shown, include_selected_urls: false },
    { ...hidden, include_selected_urls: true },
    { ...shown, include_selected_urls: "true" },
    { ...shown, include_selected_urls: undefined },
    { ...shown, assignments: [hidden.assignments[0], shown.assignments[1]] },
    { ...shown, assignments: [{ ...shown.assignments[0], canonical_url: null }, shown.assignments[1]] },
    { ...shown, assignments: [{ ...shown.assignments[0], canonical_url }, shown.assignments[1]] },
    { ...hidden, assignments: [{ ...hidden.assignments[0], canonical_url: undefined }, hidden.assignments[1]] },
    { ...hidden, selected_url_keys: hidden.selected_article_ids },
    { ...hidden, selected_article_ids: undefined, selected_url_keys: hidden.selected_article_ids },
    { ...hidden, assignments: hidden.assignments.map(({ article_id, ...row }) => ({ ...row, url_key: article_id })) },
    { ...hidden, selected_article_ids: [hidden.selected_article_ids[0], hidden.selected_article_ids[0]] },
    { ...hidden, selected_article_ids: [...hidden.selected_article_ids].reverse() },
    { ...hidden, assignments: hidden.assignments.slice(1) },
    { ...hidden, assignments: hidden.assignments.map(row => ({ ...row, editorial_rank: 1 })) },
    { ...hidden, assignments: hidden.assignments.map(row => ({ ...row, worker_assignment: hidden.dispatch_count })) },
  ]) expect(PlannerRunResponseSchema.safeParse(invalid).success).toBe(false);
  for (const key of Object.keys(PlanRunRowSchema.shape)) {
    expect(shown[key as keyof typeof shown]).toEqual(hidden[key as keyof typeof hidden]);
  }
});

test("partial and empty summaries retain the display choice without adding a run-ledger field", async () => {
  const { response, rows } = await recording();
  for (const include_selected_urls of [false, true]) {
    const assignments = rows.map(row => ({
      article_id: row.url_key, editorial_rank: row.editorial_rank, worker_assignment: null,
      ...(include_selected_urls ? { canonical_url: row.canonical_url } : {}),
    }));
    const partial = PlannerRunResponseSchema.parse({
      ...response, status: "partial", failure_code: "PERSIST_FAILED", planning_complete: false,
      dispatch_count: 0, strategy: "none", include_selected_urls, assignments,
    });
    expect(partial.assignments.every(row => row.worker_assignment === null)).toBe(true);
    expect(partial.include_selected_urls).toBe(include_selected_urls);
    const empty = PlannerRunResponseSchema.parse({
      ...response, selected_count: 0, selection_metrics: {
        selected_website_groups: 0, selected_feeds: 0, mean_substance_score: null,
      }, dispatch_count: 0, strategy: "none", include_selected_urls, selected_article_ids: [], assignments: [],
    });
    expect(empty.assignments).toEqual([]);
    expect(empty.include_selected_urls).toBe(include_selected_urls);
  }
  const run = PlanRunRowSchema.parse(Object.fromEntries(
    Object.keys(PlanRunRowSchema.shape).map(key => [key, response[key as keyof typeof response]]),
  ));
  expect(PlanRunRowSchema.safeParse({ ...run, include_selected_urls: false }).success).toBe(false);
  const refusal = PlannerErrorResponseSchema.parse({
    code: "INVALID_REQUEST", issues: [{ field: "include_selected_urls", message: "Expected a boolean" }],
  });
  expect(PlannerSavedResponseSchema.parse(refusal)).toEqual(refusal);
  expect(PlannerSavedResponseSchema.safeParse({ ...refusal, include_selected_urls: false }).success).toBe(false);
});
