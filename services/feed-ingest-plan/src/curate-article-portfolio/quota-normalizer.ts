/** How much source opportunity is earned by distinct recorded evidence? */
import { compareArticle } from "./quality-decoupler";
import type { OpportunityEvidence, PortfolioArticle, ReliabilityControls } from "./portfolio-input";

export type BonusWitness = Readonly<{
  kind: "uncovered_event_cluster" | "underrepresented_vertical" | "unique_evidence";
  candidate_id: string; url_key: string; evidence_id: string; origin: string;
}>;
export type SourceAllowance = Readonly<{
  source_id: string; allowance: number; witnesses: readonly BonusWitness[];
}>;

export function normalizeOpportunity(
  articles: readonly PortfolioArticle[], opportunity: OpportunityEvidence,
  controls: ReliabilityControls,
  evidenceArticles: readonly PortfolioArticle[] = articles,
) {
  const bySource = new Map<string, PortfolioArticle[]>();
  const primaryOwners = new Map<string, Set<string>>();
  for (const article of articles) {
    const source = article.candidate.source_id;
    const bucket = bySource.get(source) ?? [];
    bucket.push(article);
    bySource.set(source, bucket);
  }
  for (const article of evidenceArticles) {
    for (const id of article.evidence.primary_evidence?.ids ?? []) {
      const owners = primaryOwners.get(id) ?? new Set<string>();
      owners.add(article.candidate.url_key);
      primaryOwners.set(id, owners);
    }
  }
  const admitted: PortfolioArticle[] = [];
  const rejected: { article: PortfolioArticle; allowance: SourceAllowance; position: number }[] = [];
  const allowances = new Map<string, SourceAllowance>();
  for (const [source, bucket] of [...bySource].sort(([a], [b]) => a.localeCompare(b))) {
    const sorted = bucket.sort((left, right) => compareArticle(left, right, controls));
    const policy = sorted[0]!.policy.curate;
    const witnesses: BonusWitness[] = [];
    const used = new Set<string>();
    function award(
      kind: BonusWitness["kind"], amount: number,
      evidenceFor: (article: PortfolioArticle) => { id: string; origin: string } | null,
    ) {
      if (amount === 0) return;
      for (const article of sorted) {
        if (used.has(article.candidate.url_key)) continue;
        const evidence = evidenceFor(article);
        if (evidence === null) continue;
        witnesses.push({
          kind, candidate_id: article.candidate.candidate_id,
          url_key: article.candidate.url_key, evidence_id: evidence.id, origin: evidence.origin,
        });
        used.add(article.candidate.url_key);
        break;
      }
    }
    award("uncovered_event_cluster", policy.bonus_uncovered_event_cluster, article => {
      const cluster = article.candidate.labels.event_cluster_id;
      return cluster !== null && opportunity.covered_event_clusters !== null
        && !opportunity.covered_event_clusters.includes(cluster)
        ? { id: cluster, origin: article.candidate.labels.origin! } : null;
    });
    award("underrepresented_vertical", policy.bonus_underrepresented_vertical, article =>
      opportunity.underrepresented_verticals?.includes(article.candidate.vertical)
        ? { id: article.candidate.vertical, origin: opportunity.origin! } : null);
    award("unique_evidence", policy.bonus_unique_evidence, article => {
      const evidence = article.evidence.primary_evidence;
      const id = evidence?.ids.find(id => primaryOwners.get(id)?.size === 1);
      return id !== undefined && evidence !== null ? { id, origin: evidence.origin } : null;
    });
    const amount = (kind: BonusWitness["kind"], value: number) => witnesses.some(w => w.kind === kind) ? value : 0;
    const allowance: SourceAllowance = {
      source_id: source,
      allowance: policy.base_source_allowance
        + amount("uncovered_event_cluster", policy.bonus_uncovered_event_cluster)
        + amount("underrepresented_vertical", policy.bonus_underrepresented_vertical)
        + amount("unique_evidence", policy.bonus_unique_evidence),
      witnesses,
    };
    allowances.set(source, allowance);
    sorted.forEach((article, index) => {
      if (index < allowance.allowance) admitted.push(article);
      else rejected.push({ article, allowance, position: index + 1 });
    });
  }
  return { admitted, rejected, allowances };
}
