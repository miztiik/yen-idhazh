/** Validate named planner files with their current TypeScript row contracts. */
import { lstat, realpath } from "node:fs/promises";
import { resolve } from "node:path";
import { z } from "zod";
import {
  PLANNER_FILE_VALIDATION_VERSION,
  PlannerFileValidationRequestSchema,
  PlannerFileValidationResultSchema,
} from "@idhazh/common-contracts";
import type {
  PlannerFileValidationRequest,
  PlannerFileValidationResult,
} from "@idhazh/common-contracts";
import { PLANNER_CONTRACTS } from "./registration";
import { PlannerLedgerFileError, readPlannerParquet } from "./read-planner-file";

function isMissing(error: unknown): boolean {
  return error instanceof Error && "code" in error && error.code === "ENOENT";
}

function readPlannerFile(path: string, ledger: PlannerFileValidationRequest["files"][number]["ledger"]) {
  switch (ledger) {
    case "discovered-articles":
      return readPlannerParquet(path, ledger, PLANNER_CONTRACTS["discovered-articles"]);
    case "selected-articles":
      return readPlannerParquet(path, ledger, PLANNER_CONTRACTS["selected-articles"]);
    case "rejected-articles":
      return readPlannerParquet(path, ledger, PLANNER_CONTRACTS["rejected-articles"]);
    case "feed-health-state":
      return readPlannerParquet(path, ledger, PLANNER_CONTRACTS["feed-health-state"]);
    case "plan-runs":
      return readPlannerParquet(path, ledger, PLANNER_CONTRACTS["plan-runs"]);
  }
}

async function assertRegularFile(root: string, path: string): Promise<string> {
  const segments = path.split("/");
  let current = await realpath(root);
  for (const [index, segment] of segments.entries()) {
    current = resolve(current, segment);
    const info = await lstat(current);
    const final = index === segments.length - 1;
    if (info.isSymbolicLink() || (final ? !info.isFile() : !info.isDirectory())) {
      throw new PlannerLedgerFileError("Planner file path is not a regular file beneath the site tree");
    }
  }
  return current;
}

export async function validatePlannerFiles(
  root: string,
  rawRequest: unknown,
): Promise<PlannerFileValidationResult> {
  const request: PlannerFileValidationRequest = PlannerFileValidationRequestSchema.parse(rawRequest);
  const files: PlannerFileValidationResult["files"] = [];
  for (const input of request.files) {
    try {
      const path = await assertRegularFile(root, input.path);
      const file = await readPlannerFile(path, input.ledger);
      files.push({
        ledger: input.ledger,
        path: input.path,
        status: "valid",
        row_count: file.rows.length,
        reason: null,
      });
    } catch (error) {
      if (isMissing(error)) {
        files.push({
          ledger: input.ledger,
          path: input.path,
          status: "invalid",
          row_count: null,
          reason: "missing",
        });
      } else if (error instanceof PlannerLedgerFileError || error instanceof z.ZodError) {
        files.push({
          ledger: input.ledger,
          path: input.path,
          status: "invalid",
          row_count: null,
          reason: "invalid",
        });
      } else {
        throw error;
      }
    }
  }
  return PlannerFileValidationResultSchema.parse({
    version: PLANNER_FILE_VALIDATION_VERSION,
    files,
  });
}
