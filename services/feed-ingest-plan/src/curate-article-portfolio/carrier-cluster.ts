/** Which retained representative accounts for every suppressed carrier? */
import { compareArticle } from "./quality-decoupler";
import { compareStory } from "./story-evidence";
import type { StoryComparison } from "./story-evidence";
import type { PortfolioArticle } from "./portfolio-input";

export type CarrierGroup = Readonly<{
  representative: PortfolioArticle;
  members: readonly PortfolioArticle[];
  outlets: readonly string[];
  comparisons: readonly StoryComparison[];
}>;
export type CarrierSuppression = Readonly<{
  article: PortfolioArticle;
  representative: PortfolioArticle;
  reason: "DUPLICATE_CANONICAL_URL" | "REPLACED_BY_CARRIER";
}>;

export function groupCarriers(articles: readonly PortfolioArticle[]) {
  const groups: { members: PortfolioArticle[]; comparisons: StoryComparison[] }[] = [];
  const comparisons: StoryComparison[] = [];
  for (const article of [...articles].sort(compareArticle)) {
    let chosen: typeof groups[number] | undefined;
    let evidence: StoryComparison[] = [];
    for (const group of groups) {
      const pairs = group.members.map(member => compareStory(article, member));
      comparisons.push(...pairs);
      if (pairs.every(pair => pair.matches === true)) {
        chosen = group;
        evidence = pairs;
        break;
      }
    }
    if (chosen === undefined) groups.push({ members: [article], comparisons: [] });
    else {
      chosen.members.push(article);
      chosen.comparisons.push(...evidence);
    }
  }
  const carriers: CarrierGroup[] = groups.map(group => ({
    representative: group.members[0]!,
    members: group.members,
    outlets: [...new Set(group.members.flatMap(member =>
      member.evidence.publisher === null ? [] : [member.evidence.publisher.value]))].sort(),
    comparisons: group.comparisons,
  }));
  const suppressed: CarrierSuppression[] = carriers.flatMap(group =>
    group.members.slice(1).map(article => ({
      article,
      representative: group.representative,
      reason: article.candidate.url_key === group.representative.candidate.url_key
        ? "DUPLICATE_CANONICAL_URL" as const : "REPLACED_BY_CARRIER" as const,
    })));
  return { groups: carriers, representatives: carriers.map(group => group.representative), suppressed, comparisons };
}
