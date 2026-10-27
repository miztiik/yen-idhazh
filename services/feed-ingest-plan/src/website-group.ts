/** Which website group belongs to one validated canonical article URL? */
import { getDomain } from "tldts";
import { PlannerArticleEvidenceSchema, UrlSchema } from "@idhazh/common-contracts";
import type { FeedIngestCandidate, PlannerArticleEvidence } from "@idhazh/common-contracts";

export function websiteGroup(canonicalUrl: string, includePrivateSuffixes: boolean): string | null {
  const { hostname } = new URL(UrlSchema.parse(canonicalUrl));
  return getDomain(hostname, { allowPrivateDomains: includePrivateSuffixes });
}

export function resolveArticleEvidence(
  candidate: Pick<FeedIngestCandidate, "canonical_url" | "word_count">,
  supplied: PlannerArticleEvidence | undefined, includePrivateSuffixes: boolean,
) {
  const group = websiteGroup(candidate.canonical_url, includePrivateSuffixes);
  return PlannerArticleEvidenceSchema.parse({
    website_group: group === null ? null : { value: group, origin: "canonical_url" },
    estimated_work: supplied?.estimated_work ?? candidate.word_count,
  });
}
