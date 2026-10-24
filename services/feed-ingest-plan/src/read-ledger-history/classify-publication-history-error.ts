/** Which named data-read failures make optional publisher history unavailable? */
import { ZodError } from "zod";

// These messages belong to the shared native reader's integrity protocol, not tunable policy.
const INTEGRITY_FAILURES = new Set([
  "Ledger integer exceeds the safe numeric range",
  "Parquet metadata must contain string pairs",
  "Parquet ledger differs from the requested contract",
  "Parquet projection schema is newer than its declared fields",
  "Parquet row schema version differs from the requested contract",
  "Parquet file or unit identifier differs from its writer",
  "Raw filename differs from its envelope file identifier",
  "Stored row is not an object",
  "Parquet content digest differs from its rows",
  "Stored row belongs to another ledger or period",
  "Raw row identity differs from its writer envelope",
  "writer does not match the observed container",
  "Compact index schema is newer than the declared reader",
  "Named compact index belongs to another ledger or period",
  "Compact index declares no file but its named file exists",
  "Indexed compact file belongs to another period",
  "Compact index row count or byte size differs from its file",
  "Raw index schema is newer than the declared reader",
  "Raw index belongs to another ledger or day",
  "Raw index filename digest differs from its list",
  "Raw input names a file twice",
  "Raw file belongs to another day or tier",
  "Raw index byte size differs from its file",
  "Raw input repeats a file identifier",
  "Publication row differs from its named UTC day",
  "Publication health differs from its named UTC day",
  "Publisher snapshot differs from its named UTC day",
  "EOF: Unexpected EOF",
]);
const FIELD_FAILURES = [
  "Arrow nullability differs at ", "Arrow type differs at ",
  "Arrow columns differ from the declared stored schema: ", "Missing Arrow column ",
  "Arrow list has no item field at ", "Unsupported Arrow type at ",
  "Missing Parquet envelope key ", "Invalid Parquet envelope integer ",
  "Missing Arrow identity column ", "Missing Arrow projection column ",
  "Parquet error: ",
  "EOF: Parquet file too small. Size is ",
];
const FILE_READ_FAILURES = new Set(["ENOENT", "ENOTDIR", "EACCES", "EPERM", "EIO"]);

export function classifyPublicationHistoryError(error: unknown): string | null {
  if (error instanceof SyntaxError) return "invalid_json";
  if (error instanceof ZodError) return "invalid_schema";
  if (!(error instanceof Error)) return null;
  if ("code" in error && typeof error.code === "string" && FILE_READ_FAILURES.has(error.code)) {
    return error.code;
  }
  if (INTEGRITY_FAILURES.has(error.message)) return error.message;
  return FIELD_FAILURES.find(prefix => error.message.startsWith(prefix))?.trim() ?? null;
}
