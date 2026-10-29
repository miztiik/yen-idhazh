/** Publish bounded planner progress events without work batches or article bodies. */
import { FeedIngestEventSchema } from "@idhazh/common-contracts";
import type { FeedIngestEvent } from "@idhazh/common-contracts";
import type { RunContext } from "../resolve-run-context";
// RFC 4122 DNS namespace identifies deterministic local work events.
export const EVENT_NAMESPACE = "6ba7b810-9dad-11d1-80b4-00c04fd430c8";

export function writeJsonLine(record: unknown): void { console.error(JSON.stringify(record)); }
const DETAIL_LIMITS = { depth: 6, entries: 128, stringLength: 512, bytes: 4096 } as const;
const SENSITIVE_DETAIL_KEY = /^(?:article_text|body|policy|headers?|authorization|cookie|secret|token|url|.*_(?:body|text|policy|headers?|authorization|cookie|secret|token|url))$/i;
type ComplianceViolation = Readonly<{ code: string; path: string }>;

/** A diagnostic address never retains credentials, query values or fragments. */
function diagnosticArticleUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return undefined;
    // Signed addresses must not be copied, even with their signature removed.
    if ([...url.searchParams.keys()].some(key => /token|secret|signature|credential|authorization|key|auth|sig/i.test(key))) return undefined;
    url.search = "";
    url.hash = "";
    return url.href.length <= DETAIL_LIMITS.stringLength ? url.href : undefined;
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    return undefined;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

export function prepareProgressEvent(raw: unknown, requiredDetails: readonly string[] = [], failureArticleUrl?: string): FeedIngestEvent {
  if (!isRecord(raw)) throw new TypeError("Progress event must be an object");
  const { details: rawDetails, ...envelope } = raw;
  const base = FeedIngestEventSchema.omit({ details: true }).parse(envelope);
  const violations = new Map<string, ComplianceViolation>();
  const addViolation = (code: string, path: string) => violations.set(`${code}:${path}`, { code, path });
  const ancestors = new WeakSet<object>();
  let entries = 0;

  function clean(value: unknown, depth: number): unknown {
    if (value === null || typeof value === "boolean") return value;
    if (typeof value === "number") {
      if (Number.isFinite(value)) return value;
      addViolation("invalid_detail_value", "details");
      return undefined;
    }
    if (typeof value === "string") {
      if (value.length <= DETAIL_LIMITS.stringLength && !/https?:\/\//i.test(value)) return value;
      addViolation("invalid_detail_value", "details");
      return undefined;
    }
    if (typeof value !== "object" || value === null || depth >= DETAIL_LIMITS.depth) {
      addViolation("invalid_detail_value", "details");
      return undefined;
    }
    if (ancestors.has(value)) {
      addViolation("invalid_detail_value", "details");
      return undefined;
    }
    ancestors.add(value);
    if (Array.isArray(value)) {
      if (entries + value.length > DETAIL_LIMITS.entries) {
        addViolation("details_too_large", "details");
        ancestors.delete(value);
        return undefined;
      }
      entries += value.length;
      const result = value.map(item => clean(item, depth + 1));
      ancestors.delete(value);
      return result.every(item => item !== undefined) ? result : undefined;
    }
    if (!isRecord(value)) {
      addViolation("invalid_detail_value", "details");
      ancestors.delete(value);
      return undefined;
    }
    const keys = Object.keys(value);
    if (entries + keys.length > DETAIL_LIMITS.entries) {
      addViolation("details_too_large", "details");
      ancestors.delete(value);
      return undefined;
    }
    entries += keys.length;
    const result: Record<string, unknown> = {};
    for (const key of keys) {
      if (key === "_compliance") {
        addViolation("reserved_publisher_field", "details");
        continue;
      }
      if (key.length > 128 || SENSITIVE_DETAIL_KEY.test(key)) {
        addViolation("unsafe_detail_key", "details");
        continue;
      }
      const child = clean(value[key], depth + 1);
      if (child !== undefined) result[key] = child;
    }
    ancestors.delete(value);
    return result;
  }

  let details: Record<string, unknown> = {};
  if (!isRecord(rawDetails)) addViolation("details_must_be_object", "details");
  else {
    const cleaned = clean(rawDetails, 0);
    if (isRecord(cleaned)) details = cleaned;
  }
  for (const key of requiredDetails) {
    if (!Object.hasOwn(details, key)) addViolation("required_detail_missing", `details.${key}`);
  }
  if (failureArticleUrl !== undefined) {
    const url = diagnosticArticleUrl(failureArticleUrl);
    if (base.phase === "failed" && (base.operation === "fetch" || base.operation === "parse") && url !== undefined) {
      details.article_url = url;
    } else addViolation("unsafe_article_url", "details.article_url");
  }
  let serialized = JSON.stringify(details);
  if (Buffer.byteLength(serialized, "utf8") > DETAIL_LIMITS.bytes) {
    details = {};
    addViolation("details_too_large", "details");
    serialized = JSON.stringify(details);
  }
  if (violations.size > 0) {
    details._compliance = { status: "NON_COMPLIANT", violations: [...violations.values()] };
    serialized = JSON.stringify(details);
    if (Buffer.byteLength(serialized, "utf8") > DETAIL_LIMITS.bytes) {
      details = { _compliance: { status: "NON_COMPLIANT", violations: [
        { code: "details_too_large", path: "details" },
      ] } };
    }
  }
  return FeedIngestEventSchema.parse({ ...base, details });
}

export function createStageLogger(
  context: Pick<RunContext, "run_id" | "correlation_id">,
  write: (event: FeedIngestEvent) => void = writeJsonLine,
) {
  return (operation: FeedIngestEvent["operation"], phase: FeedIngestEvent["phase"],
    details: Record<string, unknown> = {}, requiredDetails: readonly string[] = [], failureArticleUrl?: string) => {
    write(prepareProgressEvent({
      run_id: context.run_id, correlation_id: context.correlation_id, occurred_at: new Date().toISOString(),
      operation, phase, details,
    }, requiredDetails, failureArticleUrl));
  };
}
