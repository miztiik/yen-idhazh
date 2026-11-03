/** Capture original project frames and safe causes once, without copying exception text. */
import { fileURLToPath } from "node:url";
import { z } from "zod";
import {
  MAX_PLANNER_ERROR_ISSUES, PlannerErrorResponseSchema, PlannerFailureDetailSchema,
  PlannerFailureExecutionSchema, PlannerFailureSchema,
} from "@idhazh/common-contracts";
import type {
  PlannerFailure, PlannerFailureDetail, PlannerFailureExecution, PlannerFailureOperation, PlannerStageContext,
} from "@idhazh/common-contracts";
import { FailureCaptureLimitsSchema } from "../config/service-settings";
import type { FailureCaptureLimits } from "../config/service-settings";
import { PlanError } from "./plan-error";

const sourceRoot = fileURLToPath(new URL("../../../../", import.meta.url)).replaceAll("\\", "/").replace(/\/$/, "");
export type FailureCaptureOptions = {
  operation: PlannerFailureOperation; limits?: FailureCaptureLimits;
  cancelled?: boolean;
  execution?: PlannerFailureExecution | Pick<PlannerStageContext, "run_id" | "correlation_id" | "writer">;
};
const unavailableExecution: PlannerFailureExecution = { run_id: null, attempt: null, correlation_id: null, git_sha: null };
const ownValue = (error: unknown, key: string): unknown =>
  error !== null && typeof error === "object" ? Object.getOwnPropertyDescriptor(error, key)?.value : undefined;

export function runtimeFailureExecution(runtime: {
  git_sha?: string; run_number?: string; correlation_id?: string; attempt?: number; captured_at?: string;
}): PlannerFailureExecution {
  const read = <T>(schema: z.ZodType<T>, value: unknown): T | null => {
    const result = schema.safeParse(value);
    return result.success ? result.data : null;
  };
  const fields = PlannerFailureExecutionSchema.shape;
  return {
    run_id: read(fields.run_id, runtime.captured_at && runtime.run_number
      ? `${runtime.captured_at.slice(0, 10)}-${runtime.run_number}` : null),
    attempt: read(fields.attempt, runtime.attempt), correlation_id: read(fields.correlation_id, runtime.correlation_id),
    git_sha: read(fields.git_sha, runtime.git_sha),
  };
}

function executionIdentity(options: FailureCaptureOptions): PlannerFailureExecution {
  const value = options.execution;
  return value === undefined ? unavailableExecution : "writer" in value ? {
    run_id: value.run_id, correlation_id: value.correlation_id,
    attempt: value.writer.attempt, git_sha: value.writer.git_sha,
  } : value;
}

function originalSource(error: unknown, limit: number): PlannerFailureDetail["source"] {
  const stack = error instanceof Error ? error.stack : undefined;
  if (typeof stack !== "string") return null;
  const message = ownValue(error, "message");
  const header = error instanceof Error && typeof message === "string" ? `${error.name}: ${message}` : "";
  // Remove the entire message, including any fake frame lines carried by source text.
  const frames = header && stack.startsWith(header) ? stack.slice(header.length, header.length + limit)
    : stack.slice(0, limit);
  for (const raw of frames.split("\n")) {
    const line = raw.replaceAll("\\", "/");
    if (!line.trimStart().startsWith("at ")) continue;
    const prefix = `${sourceRoot}/`;
    const position = line.indexOf(prefix);
    if (position < 0) continue;
    const match = line.slice(position + prefix.length).match(/^(.+):([0-9]+):[0-9]+\)?\s*$/);
    if (match === null || match[1]!.split("/").includes("node_modules")) continue;
    const source = PlannerFailureDetailSchema.shape.source.unwrap().safeParse({
      file: match[1], line: Number(match[2]),
    });
    if (source.success) return source.data;
  }
  return null;
}

function failureDetail(error: unknown, options: FailureCaptureOptions, limit: number): PlannerFailureDetail {
  const error_type: PlannerFailureDetail["error_type"] = error instanceof PlanError ? "PlanError"
    : error instanceof z.ZodError ? "ZodError" : error instanceof TypeError ? "TypeError"
    : error instanceof SyntaxError ? "SyntaxError" : error instanceof RangeError ? "RangeError"
    : error instanceof ReferenceError ? "ReferenceError" : error instanceof AggregateError ? "AggregateError"
    : (error instanceof DOMException || error instanceof Error) && error.name === "AbortError" ? "AbortError"
    : error instanceof Error ? "Error" : "UnknownError";
  const code = PlannerFailureDetailSchema.shape.system_code.safeParse(ownValue(error, "code"));
  const system_code = code.success ? code.data : null;
  const message = ownValue(error, "message");
  const safe_cause: PlannerFailureDetail["safe_cause"] = options.cancelled ? "cancelled" : error_type === "ZodError"
    || (error instanceof PlanError && ["INVALID_INPUT", "INVALID_REQUEST"].includes(error.code)) ? "invalid-input"
    : error_type === "AbortError" || (error instanceof PlanError && error.code.endsWith("_CANCELLED")) ? "cancelled"
    : system_code !== null ? "system-error"
    : error_type === "TypeError" && typeof message === "string"
      && /^(?:Cannot (?:read|set) properties of (?:undefined|null)|(?:undefined|null) is not an object)/.test(message) ? "undefined-value"
    : error_type === "TypeError" ? "invalid-type" : error_type === "SyntaxError" ? "invalid-syntax"
    : error_type === "RangeError" ? "out-of-range" : error_type === "ReferenceError" ? "missing-reference"
    : error_type === "PlanError" ? "invalid-state" : "execution-error";
  return { operation: options.operation, error_type, safe_cause, system_code, source: originalSource(error, limit) };
}

const detailOf = ({ operation, error_type, safe_cause, system_code, source }: PlannerFailure): PlannerFailureDetail =>
  ({ operation, error_type, safe_cause, system_code, source });

export function combinePlannerFailures(first: PlannerFailure, later: PlannerFailure, limits?: FailureCaptureLimits): PlannerFailure {
  const maximum = FailureCaptureLimitsSchema.parse(limits ?? {}).max_causes;
  const known = new Set([JSON.stringify(detailOf(first))]);
  const causes = [...first.causes, detailOf(later), ...later.causes].filter(cause => {
    const key = JSON.stringify(cause);
    if (known.has(key)) return false;
    known.add(key);
    return true;
  });
  return PlannerFailureSchema.parse({
    ...first, causes: causes.slice(0, maximum),
    omitted_causes: first.omitted_causes + later.omitted_causes + Math.max(0, causes.length - maximum),
  });
}

export function capturePlannerFailure(error: unknown, options: FailureCaptureOptions): PlannerFailure {
  const limits = FailureCaptureLimitsSchema.parse(options.limits ?? {});
  let result: PlannerFailure | undefined;
  const seen = new Set<unknown>();
  function collect(value: unknown, depth: number) {
    if (seen.has(value) || depth > limits.max_causes + 1) {
      if (result !== undefined) result.omitted_causes++;
      return;
    }
    seen.add(value);
    if (value instanceof AggregateError && value.errors.length) {
      const count = Math.min(value.errors.length, limits.max_causes + 1);
      for (const child of value.errors.slice(0, count)) collect(child, depth + 1);
      if (result !== undefined) result.omitted_causes += value.errors.length - count;
      return;
    }
    const cause = ownValue(value, "cause");
    if (cause !== undefined && !(value instanceof PlanError && value.failure !== null)) collect(cause, depth + 1);
    const current = value instanceof PlanError && value.failure !== null ? PlannerFailureSchema.parse(value.failure)
      : PlannerFailureSchema.parse({
        ...failureDetail(value, options, limits.max_stack_chars), execution: executionIdentity(options),
        causes: [], omitted_causes: 0,
      });
    result = result === undefined ? current : combinePlannerFailures(result, current, limits);
  }
  collect(error, 0);
  return result ?? PlannerFailureSchema.parse({
    ...failureDetail(error, options, limits.max_stack_chars), execution: executionIdentity(options),
    causes: [], omitted_causes: 1,
  });
}

export function withPlannerFailure(error: unknown, options: FailureCaptureOptions): PlanError {
  if (error instanceof PlanError && error.failure !== null) {
    const expected = executionIdentity(options);
    const execution = error.failure.execution;
    return new PlanError(error.code, error.message, error.field, { cause: error,
      failure: PlannerFailureSchema.parse({ ...error.failure, execution: {
        run_id: execution.run_id ?? expected.run_id, attempt: execution.attempt ?? expected.attempt,
        correlation_id: execution.correlation_id ?? expected.correlation_id, git_sha: execution.git_sha ?? expected.git_sha,
      } }),
    });
  }
  const code = error instanceof PlanError ? error.code : error instanceof z.ZodError ? "INVALID_INPUT" : "PLAN_FAILED";
  return new PlanError(code, `${code}: Planner operation did not complete`, error instanceof PlanError ? error.field : null,
    { cause: error, failure: capturePlannerFailure(error, options) });
}

export function readPlannerResponseError(raw: unknown, options: FailureCaptureOptions): PlanError {
  const response = PlannerErrorResponseSchema.parse(raw);
  return withPlannerFailure(new PlanError(response.code, "Planner HTTP operation did not complete", response.issues[0]?.field, {
    failure: response.failure ?? capturePlannerFailure(undefined, options),
  }), options);
}

export function describePlanError(error: unknown, _root?: string, options: FailureCaptureOptions = { operation: "plan" }) {
  const code = error instanceof PlanError ? error.code : error instanceof z.ZodError ? "INVALID_INPUT" : "PLAN_FAILED";
  const field = (value: string | null) => value !== null && /^[a-z][a-z0-9_.]*$/.test(value) && value.length <= 256 ? value : null;
  let issues = error instanceof z.ZodError ? error.issues.map(issue => ({
    field: field(issue.path.map(String).join(".")) ?? "body",
    message: issue.code === "unrecognized_keys" ? "Unknown request field" : "Input does not satisfy the declared contract",
  })) : [{
    field: error instanceof PlanError ? field(error.field) : null,
    message: code === "PLANNER_DISABLED" ? "Planner is disabled"
      : code === "INVALID_REQUEST" ? "Planner request is invalid"
      : code === "INVALID_INPUT" ? "Input is invalid or unavailable" : "Planner operation did not complete",
  }];
  if (issues.length > MAX_PLANNER_ERROR_ISSUES) issues = [
    ...issues.slice(0, MAX_PLANNER_ERROR_ISSUES - 1), { field: "body", message: "Additional input issues omitted" },
  ];
  return PlannerErrorResponseSchema.parse({ code, issues, failure: capturePlannerFailure(error, options) });
}
