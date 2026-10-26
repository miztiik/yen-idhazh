/** Do the host API row and receipts match the caller's actual completed Parquet? */
import { isDeepStrictEqual } from "node:util";
import { FingerprintWrittenSchema } from "../../host-fingerprints/src/api/fingerprint-response";
import { verifyMetadataFile } from "./feed-ingest-plan-metadata";
import type { ExecutionIdentity, MetadataRegistrations } from "./feed-ingest-plan-metadata";

export async function verifyHostFingerprint(
  root: string, input: unknown, registrations: MetadataRegistrations, identity: ExecutionIdentity,
) {
  const response = FingerprintWrittenSchema.parse(input);
  const paths: string[] = [];
  for (const file of response.files) {
    const actual = await verifyMetadataFile(root, file.path, registrations, identity);
    if (actual.ledger !== "host-fingerprint" || actual.envelope.file_id !== file.file_id
      || !("unit_id" in actual.envelope) || actual.envelope.unit_id !== file.unit_id
      || actual.envelope.covers !== file.covers || actual.content_sha256 !== file.content_sha256
      || actual.row_count !== file.row_count || !isDeepStrictEqual(actual.rows, [response.row])) {
      throw new Error("Host API receipt or row differs from its completed Parquet");
    }
    paths.push(file.path);
  }
  return paths;
}
