/** Which shared scalar spellings do the Python contracts admit? */
import { createHash } from "node:crypto";
import { z } from "zod";
import { CONTRACT_VERSION } from "../version";

export const VersionSchema = z.literal(CONTRACT_VERSION).default(CONTRACT_VERSION);
export const SchemaVersionSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?)?$/);
export const DateStampSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
export const MonthStampSchema = z.string().regex(/^\d{4}-\d{2}$/);
export const YearStampSchema = z.string().regex(/^\d{4}$/);
export const TimestampSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
export const SlugSchema = z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
export const RunIdSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}-[0-9]+$/);
export const UrlSchema = z.string().max(2048).regex(/^https?:\/\/[^\s"'<>\\]+$/);
export const Sha256Schema = z.string().regex(/^[0-9a-f]{64}$/);
export const CommitShaSchema = z.string().regex(/^[0-9a-f]{40}$/);
export const JobNameSchema = z.string().min(1).max(64).regex(/^[a-z][a-z0-9_-]*$/);
export const ServerJobSchema = z.enum(["plan", "work", "assemble", "visuals", "runtime", "decide", "migrate", "run-tasks", "history", "save_council_results", "collect", "operator"]);
export const FiniteSchema = z.number().finite();
export const NonNegativeSchema = FiniteSchema.nonnegative();
export const PositiveSchema = FiniteSchema.positive();
export const CountSchema = z.int().nonnegative();
export const PositiveCountSchema = z.int().positive();
export const NonEmptySchema = z.string().min(1);
const relativePathSegment = "[A-Za-z0-9._-]*[A-Za-z0-9_-][A-Za-z0-9._-]*";
export const RelPathSchema = z.string().max(512).regex(new RegExp(`^${relativePathSegment}(?:/${relativePathSegment})*$`));
export const PlanningStageSchema = z.enum(["harvest-feeds", "screen-article-candidates", "curate-article-portfolio", "partition-article-shards", "seal-article-ledger"]);
export const RejectionStageSchema = z.enum(["harvest-feeds", "screen-article-candidates", "curate-article-portfolio"]);

export function deriveUrlKey(canonicalUrl: string): string {
  return createHash("sha256").update(canonicalUrl, "utf8").digest("hex");
}

export function deriveCandidateId(runId: string, sourceId: string, entryOrdinal: number): string {
  return deriveUrlKey(`${RunIdSchema.parse(runId)}\n${SlugSchema.parse(sourceId)}\n${CountSchema.parse(entryOrdinal)}`);
}

export function reject(ctx: z.RefinementCtx, message: string, path: PropertyKey[] = []): void {
  ctx.addIssue({ code: "custom", message, path });
}

export function checkUrlIdentity(value: { canonical_url: string; url_key: string }, ctx: z.RefinementCtx): void {
  if (deriveUrlKey(value.canonical_url) !== value.url_key) reject(ctx, "url_key must match canonical_url", ["url_key"]);
}
