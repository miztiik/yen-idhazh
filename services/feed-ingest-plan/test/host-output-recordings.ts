/** Rebuild one captured host row with a genuine native receipt for its current delivery identity. */
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { HOST_FINGERPRINT_VERSION, HostFingerprintRowSchema } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerSettings } from "@idhazh/ledger-file-writer";
import { hostWriter } from "../scripts/feed-ingest-plan-metadata";
import type { ExecutionIdentity } from "../scripts/feed-ingest-plan-metadata";
import { WorkflowHostFingerprintSchema } from "../scripts/feed-ingest-plan-host-fingerprint";
import { metadataRegistrations } from "./host-recordings";

export async function writeRecordedHostOutput(directory: string, identity: ExecutionIdentity, ledgerSettings: LedgerSettings) {
  const captured = WorkflowHostFingerprintSchema.parse(await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/host-report.json", import.meta.url)).json());
  if (captured.host.status !== "recorded") throw new Error("The host output recording must contain a captured native row");
  const registrations = await metadataRegistrations();
  const registration = registrations["host-fingerprint"];
  const request = { date: identity.run_id.slice(0, 10), writer: hostWriter(identity) };
  const row = HostFingerprintRowSchema.parse({ ...captured.host.row, date: request.date, run_id: identity.run_id });
  const written = await persistLedger({
    ledger: registration.name, registryEntry: registration, outputRoot: join(directory, "state"),
    ledgerSettings, rowContract: { schema: HostFingerprintRowSchema, schemaVersion: HOST_FINGERPRINT_VERSION },
    writerContext: request.writer, period: { tier: "raw", covers: request.date }, rows: [row],
  });
  if (written.status !== "written") throw new Error(`Recorded host write was refused: ${written.status}`);
  const evidence = WorkflowHostFingerprintSchema.parse({
    host_request: request, host: { ...captured.host, row, files: written.files },
  });
  await writeFile(join(directory, "host-fingerprint.json"), JSON.stringify(evidence));
  return { response: written, evidence, identity, registrations };
}
