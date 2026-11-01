/** Does attention distinguish current failures from paused coverage and absent evidence? */
import { expect, test } from "bun:test";
import { parseHTML } from "linkedom";
import { renderFailureEvidence } from "../src/reporting/failure-evidence-markdown";
import { renderPlanMarkdown } from "../src/reporting/plan-markdown";
import { readPlannerOutputRecording } from "./planner-output-recordings";

test("groups current failure counts without counting policy decisions as failures", async () => {
  const { response, health } = await readPlannerOutputRecording();
  const base = health.rows[0]!;
  const cause = { subject: "article" as const, stage: "harvest-feeds", attribution: "feed" as const };
  const rows = [{ ...base, feed_id: "failed-feed", rejection_counts: [
    { ...cause, reason_code: "FETCH_FAILED_HTTP", count: 3 },
    { ...cause, reason_code: "REJECTED_SCREENING_MIN_WORDS", count: 7 },
  ] }, { ...base, feed_id: "failed-feed", rejection_counts: [
    { ...cause, reason_code: "FETCH_FAILED_HTTP", count: 2 },
  ] }];
  const before = structuredClone(rows);
  const report = renderPlanMarkdown({ response, health: { ...health, rows } });
  const { document } = parseHTML(Bun.markdown.html(report.markdown));
  const attention = document.querySelectorAll("table")[1]!.textContent!;
  expect(attention).toContain("5 recorded article failures");
  expect(attention).not.toContain("minimum word");
  expect(attention).toContain("response status unavailable in report input");
  expect(attention).not.toContain("403");
  expect(document.querySelector("details summary")?.textContent).toBe("Per-feed article results");
  expect([...document.querySelectorAll("details")].map(node => node.textContent).join(" "))
    .toContain("Article below minimum word count");
  expect(report.notices).toEqual([]);
  expect(rows).toEqual(before);
});

test("paused feeds do not establish new requests or historical causes", async () => {
  const { health } = await readPlannerOutputRecording();
  const base = health.rows[0]!;
  const markdown = renderFailureEvidence([{ ...base, rejection_counts: [], feed_reads: 0 }], {
    eligible_feed_ids: [], feeds: [{
      feed_id: base.feed_id, endpoint_key: base.endpoint_key, availability: "resting",
      strikes: 5, failed_recovery_checks: 2, availability_complete: true,
      availability_updated_at: "2026-10-29T12:00:00Z",
      first_confirmed_failure_at: "2026-10-25T00:00:00Z",
      rest_until: "2026-10-30T12:00:00Z", retired_at: null, retirement_reason: null,
    }],
  }).markdown;
  const text = [...parseHTML(Bun.markdown.html(markdown)).document.querySelectorAll("td")].map(node => node.textContent).join(" ");
  expect(text).toContain("historical cause unavailable");
  expect(text).toContain("not a new HTTP failure");
  expect(text).toContain("Saved state at 2026-10-29T12:00:00Z UTC");
  expect(text).toContain("2026-10-30T12:00:00Z");
  expect(text).not.toContain("403");
});

test("missing evidence is an attention item while proven empty evidence has no empty table", () => {
  expect(renderFailureEvidence(undefined).markdown).toContain("Feed work evidence unavailable");
  const empty = renderFailureEvidence([], { feeds: [], eligible_feed_ids: [] }).markdown;
  expect(empty).toContain("No recorded problems");
  expect(Bun.markdown.html(empty)).not.toContain("<table>");
});
