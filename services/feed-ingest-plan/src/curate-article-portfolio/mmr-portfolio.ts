/** Which next viable article contributes most under the configured set controls? */
import { PortfolioChoicePayloadSchema, ScoreEvidenceSchema } from "@idhazh/common-contracts";
import type { FeedIngestConfig, PortfolioChoicePayload, ScoreEvidence } from "@idhazh/common-contracts";
import { compareIdentity } from "./portfolio-input";
import type { OpportunityEvidence, PortfolioArticle } from "./portfolio-input";
import { measureArticle } from "./quality-decoupler";
import type { SourceAllowance } from "./quota-normalizer";
import type { CarrierGroup } from "./carrier-cluster";

type Penalty = ScoreEvidence["source"];
type Relaxation = ScoreEvidence["cap_relaxations"][number];
type Labels = readonly string[] | null;
const unavailable = (): Penalty => ({ available: false, value: null });

function penalty(
  article: PortfolioArticle, selected: readonly PortfolioArticle[], coefficient: number,
  values: (article: PortfolioArticle) => Labels,
): Penalty {
  const own = values(article);
  if (own === null) return unavailable();
  if (own.length === 0 || selected.length === 0) return { available: true, value: 0 };
  const prior = selected.map(values);
  if (prior.some(values => values === null)) return unavailable();
  const count = prior.filter(values => values!.some(value => own.includes(value))).length;
  return { available: true, value: coefficient * count / selected.length };
}

function scalar(value: string | null | undefined): Labels {
  return value === null || value === undefined ? null : [value];
}

export function scoreMarginal(
  article: PortfolioArticle, selected: readonly PortfolioArticle[], allowance: SourceAllowance,
  group: CarrierGroup, opportunity: OpportunityEvidence, exploration: boolean,
  relaxations: readonly Relaxation[],
): ScoreEvidence {
  const weights = article.policy.curate.mmr_weights;
  const terms = {
    source: penalty(article, selected, weights.lambda_source, a => [a.candidate.source_id]),
    source_kind: penalty(article, selected, weights.lambda_source_kind, a => [a.candidate.source.kind]),
    domain: penalty(article, selected, weights.lambda_domain, a => scalar(a.evidence.parent_domain?.value)),
    vertical: penalty(article, selected, weights.lambda_vertical, a => [a.candidate.vertical]),
    desk: penalty(article, selected, weights.lambda_desk, a => scalar(a.candidate.labels.assigned_desk)),
    lens: penalty(article, selected, weights.lambda_lens, a => a.candidate.labels.lenses),
    event_type: penalty(article, selected, weights.lambda_event_type, a => a.candidate.labels.event_types),
    event_cluster: penalty(article, selected, weights.lambda_event_cluster, a => scalar(a.candidate.labels.event_cluster_id)),
    entity: penalty(article, selected, weights.lambda_entity, a => a.candidate.labels.entities),
    coverage: article.candidate.labels.event_cluster_id === null || opportunity.covered_event_clusters === null
      ? unavailable() : {
        available: true,
        value: weights.lambda_coverage * Number(opportunity.covered_event_clusters.includes(article.candidate.labels.event_cluster_id)),
      },
  };
  const base = measureArticle(article).base_article_score;
  return ScoreEvidenceSchema.parse({
    base_article_score: base,
    marginal_score: base - Object.values(terms).reduce((sum, term) => sum + (term.value ?? 0), 0),
    ...terms,
    source_allowance: allowance.allowance,
    bonus_uncovered_event_cluster: allowance.witnesses.some(w => w.kind === "uncovered_event_cluster"),
    bonus_underrepresented_vertical: allowance.witnesses.some(w => w.kind === "underrepresented_vertical"),
    bonus_unique_evidence: allowance.witnesses.some(w => w.kind === "unique_evidence"),
    carrier_outlets: group.outlets,
    representative_url_key: group.representative.candidate.url_key,
    replacement_url_key: null, exploration_slot: exploration, cap_relaxations: relaxations,
  });
}

export type ChoiceStep = Readonly<{
  selected_before: readonly string[];
  evaluated: readonly Readonly<{ candidate_id: string; scores: ScoreEvidence; blocked_by: readonly string[] }>[];
  choice: PortfolioChoicePayload | null;
  relaxations: readonly Relaxation[];
}>;

export function choosePortfolio(
  articles: readonly PortfolioArticle[], config: FeedIngestConfig["curate"],
  allowances: ReadonlyMap<string, SourceAllowance>, groups: readonly CarrierGroup[],
  opportunity: OpportunityEvidence,
) {
  const groupById = new Map(groups.map(group => [group.representative.candidate.candidate_id, group]));
  const selected: PortfolioArticle[] = [];
  const choices: PortfolioChoicePayload[] = [];
  const trace: ChoiceStep[] = [];
  const remaining = [...articles].sort(compareIdentity);
  const target = Math.min(config.article_limit ?? remaining.length, remaining.length);
  const explorationSlots = Math.floor(target * config.exploration_slot_share);
  const relaxations: Relaxation[] = [];
  const caps = config.soft_caps;
  const sourceMaximum = Math.ceil(target * caps.max_source_share);
  const domainMaximum = Math.ceil(target * caps.max_parent_domain_share);
  let explorationUsed = 0;
  while (selected.length < target && remaining.length > 0) {
    const sources = new Set(selected.map(article => article.candidate.source_id));
    const newSources = remaining.filter(article => !sources.has(article.candidate.source_id));
    const exploration = selected.length >= target - explorationSlots
      && explorationUsed < explorationSlots && newSources.length > 0;
    const evaluated = remaining.map(article => {
      const sourceCount = selected.filter(a => a.candidate.source_id === article.candidate.source_id).length;
      const domain = article.evidence.parent_domain?.value;
      const cluster = article.candidate.labels.event_cluster_id;
      const blocked: string[] = [];
      if (!relaxations.includes("distinct_sources") && sources.size < Math.min(caps.min_distinct_sources, target)
        && sources.has(article.candidate.source_id)) blocked.push("distinct_sources");
      if (!relaxations.includes("source_share") && sourceCount >= sourceMaximum) blocked.push("source_share");
      if (domain !== undefined && selected.filter(a => a.evidence.parent_domain?.value === domain).length >= domainMaximum) {
        blocked.push("parent_domain_share");
      }
      if (cluster !== null && selected.filter(a => a.candidate.labels.event_cluster_id === cluster).length >= caps.max_event_cluster_items) {
        blocked.push("event_cluster_items");
      }
      const allowance = allowances.get(article.candidate.source_id);
      const group = groupById.get(article.candidate.candidate_id);
      if (allowance === undefined || group === undefined) throw new Error("Normalized candidate lacks allowance or carrier evidence");
      return {
        article, candidate_id: article.candidate.candidate_id,
        scores: scoreMarginal(article, selected, allowance, group, opportunity,
          exploration && !sources.has(article.candidate.source_id) && blocked.length === 0, relaxations),
        blocked_by: blocked,
      };
    });
    const viable = evaluated.filter(value => value.blocked_by.length === 0);
    const exploring = exploration ? viable.filter(value => !sources.has(value.article.candidate.source_id)) : [];
    const available = exploring.length > 0 ? exploring : viable;
    available.sort((a, b) => b.scores.marginal_score - a.scores.marginal_score || compareIdentity(a.article, b.article));
    const winner = available[0];
    if (winner === undefined) {
      trace.push({
        selected_before: selected.map(a => a.candidate.candidate_id),
        evaluated: evaluated.map(({ article: _article, ...entry }) => entry),
        choice: null, relaxations: [...relaxations],
      });
      const next = caps.relaxation_order.find(limit => !relaxations.includes(limit)
        && evaluated.some(value => value.blocked_by.includes(limit)));
      if (next === undefined) break;
      relaxations.push(next);
      continue;
    }
    winner.scores.exploration_slot = exploring.length > 0;
    if (winner.scores.exploration_slot) explorationUsed++;
    const choice = PortfolioChoicePayloadSchema.parse({
      kind: "portfolio_choice", candidate_id: winner.candidate_id,
      url_key: winner.article.candidate.url_key, editorial_rank: selected.length + 1,
      scores: winner.scores, labels: winner.article.candidate.labels,
      replaced_candidate_id: null, replacement_reason: "none",
    });
    trace.push({
      selected_before: selected.map(a => a.candidate.candidate_id),
      evaluated: evaluated.map(({ article: _article, ...entry }) => entry),
      choice, relaxations: [...relaxations],
    });
    choices.push(choice);
    selected.push(winner.article);
    remaining.splice(remaining.indexOf(winner.article), 1);
  }
  const cutoffs = remaining.map(article => {
    const evaluated = trace.at(-1)?.evaluated.find(entry => entry.candidate_id === article.candidate.candidate_id);
    const controls = selected.length >= target
      ? [{ control: "article_limit", observed_value: selected.length + 1, limit: target }]
      : (evaluated?.blocked_by ?? []).map(control => {
        switch (control) {
          case "source_share":
            return { control, observed_value: selected.filter(a => a.candidate.source_id === article.candidate.source_id).length + 1, limit: sourceMaximum };
          case "parent_domain_share":
            return { control, observed_value: selected.filter(a => a.evidence.parent_domain?.value === article.evidence.parent_domain?.value).length + 1, limit: domainMaximum };
          case "event_cluster_items":
            return { control, observed_value: selected.filter(a => a.candidate.labels.event_cluster_id === article.candidate.labels.event_cluster_id).length + 1, limit: caps.max_event_cluster_items };
          case "distinct_sources":
            return { control, observed_value: new Set(selected.map(a => a.candidate.source_id)).size, limit: Math.min(caps.min_distinct_sources, target) };
          default: throw new Error(`Unknown portfolio control: ${control}`);
        }
      });
    if (controls.length === 0) throw new Error("Unselected candidate lacks a terminal portfolio control");
    return { article, controls, last_evaluation: evaluated ?? null };
  });
  return { selected, choices, trace, remaining, relaxations, cutoffs };
}
