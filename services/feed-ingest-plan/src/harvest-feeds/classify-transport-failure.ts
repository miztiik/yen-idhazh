/** Classify source failures without discarding body-limit evidence or safe error codes. */
import { constants as osConstants } from "node:os";
import { HarvestDiagnosticsSchema } from "@idhazh/common-contracts";
import { errors } from "playwright";
import type { FetchFailure } from "./harvest-types";
import { BodyLimitError, BrowserNetworkError, ChallengeUnresolvedError, ResponseReadError, readBodyLimitEvidence } from "./transport";
import { UnsafeTargetError } from "./safe-target";
import { InvalidArticleUrlError } from "./article-url";

export function classifyTransportFailure(error: unknown, signal: AbortSignal): FetchFailure {
  if (readBodyLimitEvidence(error) !== undefined) return "body-too-large";
  if (error instanceof AggregateError && error.cause !== undefined) return classifyTransportFailure(error.cause, signal);
  if (error instanceof ChallengeUnresolvedError) return "challenge-unresolved";
  if (error instanceof ResponseReadError) {
    const primary = error.cause instanceof AggregateError ? error.cause.cause : error.cause;
    if (signal.aborted || primary instanceof errors.TimeoutError
      || (primary instanceof DOMException && ["TimeoutError", "AbortError"].includes(primary.name))) return "timeout";
    return primary instanceof BrowserNetworkError ? classifyTransportFailure(primary, signal) : "network";
  }
  if (error instanceof UnsafeTargetError || error instanceof InvalidArticleUrlError) return "unsafe-target";
  if (signal.aborted || error instanceof errors.TimeoutError
    || (error instanceof DOMException && ["TimeoutError", "AbortError"].includes(error.name))) return "timeout";
  if (error instanceof BrowserNetworkError) {
    if (error.code === "ERR_TOO_MANY_REDIRECTS") return "redirect-loop";
    return error.code === "ERR_NAME_NOT_RESOLVED" ? "dns" : "network";
  }
  const cause = error instanceof Error && error.cause instanceof Error ? error.cause : error;
  if (cause && typeof cause === "object" && "code" in cause && typeof cause.code === "string") {
    if (["ENOTFOUND", "EAI_AGAIN", "ENODATA"].includes(cause.code)) return "dns";
    return cause.code === "ETIMEDOUT" ? "timeout" : "network";
  }
  throw error;
}

export function readTransportErrorCode(error: unknown): string | null {
  let cause = error instanceof ResponseReadError ? error.cause : error;
  if (cause instanceof AggregateError && cause.errors.length === 2
    && (cause.cause instanceof BodyLimitError || cause.cause === cause.errors[0])) cause = cause.errors[1];
  if (cause instanceof Error && cause.cause instanceof Error) cause = cause.cause;
  if (cause && typeof cause === "object" && "code" in cause && typeof cause.code === "string") {
    if (!(cause.code in osConstants.errno)
      && !["ENOTFOUND", "EAI_AGAIN", "ENODATA"].includes(cause.code)
      && !/^ERR_[A-Z0-9_]+$/.test(cause.code)
      && !/^(ERR_TLS_|ERR_SSL_|CERT_|DEPTH_|SELF_SIGNED_|UNABLE_TO_)/.test(cause.code)) return null;
    const parsed = HarvestDiagnosticsSchema.shape.error_code.safeParse(cause.code);
    if (parsed.success) return parsed.data;
  }
  return null;
}
