/** Which available story facts agree without claiming an embedding comparison? */
import type { PortfolioArticle } from "./portfolio-input";

// Written-number syntax and scales are the existing story_key format, not tuning knobs.
const scales: Readonly<Record<string, number>> = {
  k: 1e3, thousand: 1e3, m: 1e6, mn: 1e6, million: 1e6,
  b: 1e9, bn: 1e9, billion: 1e9, tn: 1e12, trillion: 1e12, lakh: 1e5, crore: 1e7,
};
type StoryKey = { shape: string; numbers: { value: number; significant: number }[] };
export type StoryComparison = Readonly<{
  left: string; right: string;
  method: "canonical-url" | "recorded-event-cluster" | "figure-clash" | "unavailable";
  matcher_version: string | null; matches: boolean | null;
  semantic_similarity: null; reason: string;
}>;

function reduceHeadline(title: string): StoryKey | null {
  const folded = title.normalize("NFKC").toLowerCase();
  // Full Unicode case-folding is not supplied here. Do not claim parity for it.
  if (/[^\x00-\x7f]/.test(folded)) return null;
  const numbers: StoryKey["numbers"] = [];
  const words = folded.replace(
    /(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(bn|b|k|m|mn|tn|thousand|million|billion|trillion|crore|lakh)?\b/gi,
    (_match, digits: string, scale: string | undefined) => {
      const plain = digits.replaceAll(",", "");
      numbers.push({
        value: Number(plain) * (scale === undefined ? 1 : scales[scale.toLowerCase()]!),
        significant: plain.replace(".", "").replace(/^0+/, "").length || 1,
      });
      return " ";
    },
  );
  if (numbers.some(number => !Number.isFinite(number.value))) return null;
  const shape = words.replace(/[^a-z0-9]/g, " ").replace(/\s+/g, " ").trim();
  return shape === "" || shape === "untitled item" ? null : { shape, numbers };
}

function roundWritten(value: number, significant: number): number {
  if (value === 0) return 0;
  const power = 10 ** (Math.floor(Math.log10(Math.abs(value))) - significant + 1);
  const scaled = value / power;
  const floor = Math.floor(scaled);
  // Match the existing nearest-even rule at exact halves.
  const rounded = scaled - floor === 0.5 ? floor + (floor % 2) : Math.round(scaled);
  return rounded * power;
}

export function compareStory(left: PortfolioArticle, right: PortfolioArticle): StoryComparison {
  const a = left.candidate;
  const b = right.candidate;
  const identity = { left: a.candidate_id, right: b.candidate_id, semantic_similarity: null };
  if (a.url_key === b.url_key) {
    return { ...identity, method: "canonical-url", matcher_version: "canonical-url-sha256", matches: true, reason: "same canonical identity" };
  }
  const one = reduceHeadline(a.title);
  const other = reduceHeadline(b.title);
  if (one !== null && other !== null && one.shape === other.shape
    && one.numbers.length === other.numbers.length
    && one.numbers.some((number, index) => {
      const second = other.numbers[index]!;
      const precision = Math.min(number.significant, second.significant);
      return roundWritten(number.value, precision) !== roundWritten(second.value, precision);
    })) {
    return { ...identity, method: "figure-clash", matcher_version: "story-key-ascii-numbers-v1", matches: false, reason: "same headline words disagree about a figure" };
  }
  const publisher = left.evidence.publisher?.value;
  const otherPublisher = right.evidence.publisher?.value;
  if (publisher === undefined || otherPublisher === undefined || publisher === otherPublisher) {
    return { ...identity, method: "unavailable", matcher_version: null, matches: null, reason: "distinct recorded mastheads unavailable" };
  }
  if (a.labels.event_cluster_id !== null && a.labels.event_cluster_id === b.labels.event_cluster_id
    && a.labels.origin === b.labels.origin && a.labels.matcher_version === b.labels.matcher_version) {
    // A figure veto cannot be checked on an unsupported headline, so keep it apart.
    if (one === null || other === null) {
      return { ...identity, method: "unavailable", matcher_version: null, matches: null, reason: "headline figure comparison unavailable" };
    }
    return { ...identity, method: "recorded-event-cluster", matcher_version: a.labels.matcher_version, matches: true, reason: "same validated occurrence; no conflicting headline figures" };
  }
  return { ...identity, method: "unavailable", matcher_version: null, matches: null, reason: "no semantic vectors or shared recorded occurrence" };
}
