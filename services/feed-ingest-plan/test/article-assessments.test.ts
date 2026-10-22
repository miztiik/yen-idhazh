/** Are real measurements preserved exactly, including refusal of unsupported clocks? */
import { expect, test } from "bun:test";
import { runFeedPlan } from "../src/run-feed-plan";
import { preflightMeasurements, translateArticleAssessments } from "../src/metrics/article-assessments";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";

test("real publication timing and separate article/set scores survive translation without semantic guesses", async () => {
  const recorded = await recordedPlan();
  try {
    const result = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    const before = structuredClone(result);
    const rows = translateArticleAssessments(result, recorded.inputs);
    expect(result).toEqual(before);
    expect(rows.length).toBe(result.evidence.harvest.articles.length
      + result.evidence.harvest.candidates.length + result.evidence.screening.admitted.length);
    for (const row of rows) {
      expect(row.informative_verdict_status).toBe("not_assessed");
      expect(row.informative_verdict).toBeNull();
      expect(row.informative_evaluator_version).toBeNull();
      expect(row.suitability_verdict_status).toBe("not_assessed");
      expect(row.suitability_verdict).toBeNull();
      if (row.stage !== "harvest-feeds") {
        const measured = result.evidence.screening.admitted.find(article => article.candidate.candidate_id === row.candidate_id)!;
        expect(row.timing_basis).toBe("published_at");
        expect(row.timing_at).toBe(measured.freshness.timing_at);
        expect(row.age_hours).toBe(measured.freshness.age_hours);
        expect(row.max_age_hours).toBe(measured.policy.triage.max_age_hours);
      }
      if (row.stage === "curate-article-portfolio" && row.score_evidence !== null) {
        const measured = result.evidence.curation.quality.find(item => item.candidate_id === row.candidate_id)!;
        expect(row.score_evidence.base_article_score).toBe(measured.base_article_score);
        const score = result.evidence.curation.assessments.find(item => item.candidate_id === row.candidate_id)!.score_evidence;
        if (score === null) throw new Error("Expected actual portfolio score evidence");
        expect(row.score_evidence).toEqual(score);
      }
    }
  } finally { await recorded.close(); }
}, 30000);

test("originally unmeasured timing remains unknown, not fetched_at or invented first sight", async () => {
  const recorded = await recordedPlan([source({ url: "https://news.example/article-failures.xml" })]);
  try {
    const result = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    const rows = translateArticleAssessments(result, recorded.inputs);
    const undated = result.evidence.harvest.candidates.filter(candidate => candidate.published_at === null);
    expect(undated.length).toBeGreaterThan(0);
    for (const candidate of undated) {
      for (const row of rows.filter(row => row.candidate_id === candidate.candidate_id)) {
        expect(row.timing_basis).toBe("unavailable");
        expect(row.timing_at).toBeNull();
        expect(row.age_hours).toBeNull();
        expect(row.max_age_hours).toBeNull();
      }
    }
  } finally { await recorded.close(); }
}, 30000);

test("preflight and translated assessments preserve signed ages for rejected candidates", async () => {
  const recorded = await recordedPlan();
  recorded.runtime.clock = () => new Date("2026-10-21T09:00:00Z");
  recorded.inputs.harvest.config.triage.min_words_article = 10000;
  try {
    const result = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    expect(result.evidence.screening.admitted).toHaveLength(0);
    expect(result.evidence.screening.rejections).toHaveLength(2);
    const first = result.evidence.harvest.candidates[0]!;
    expect(preflightMeasurements(result, recorded.inputs).get(first.candidate_id)?.age_hours).toBe(-0.25);
    const rows = translateArticleAssessments(result, recorded.inputs);
    expect(rows.filter(row => row.candidate_id === first.candidate_id)
      .some(row => row.age_hours === -0.25 && row.timing_basis === "published_at")).toBe(true);
  } finally { await recorded.close(); }
}, 30000);
