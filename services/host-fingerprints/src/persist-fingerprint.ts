/** When permitted, how does one captured row become a completed shared ledger write? */
import { z } from "zod";
import { HostFingerprintRowSchema, HOST_FINGERPRINT_VERSION } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import { CaptureContextSchema, REPOSITORY_ROOT } from "./config";
import type { SelectedSettings, ServiceConfig } from "./config";
import type { Inspection } from "./inspect/bounded-input";
import { collectFingerprint } from "./collect-fingerprint";

const RegistrySchema = z.object({
  families: z.array(z.object({
    name: z.string(), lifecycle_status: z.enum(["active", "paused", "retired"]),
    ledgers: z.array(z.object({
      name: z.string(), grain: z.string(),
      prefix: z.array(z.string()).nullable(),
    })),
  })),
});
export type PersistenceOptions = {
  outputRoot: string;
  registryPath?: string | URL;
  inspection?: Inspection;
};
export async function persistFingerprint(input: unknown, config: ServiceConfig, settings: SelectedSettings, options: PersistenceOptions) {
  const capture = CaptureContextSchema.parse(input);
  if (!settings.observability.host_telemetry_enabled || !settings.observability.host_fingerprint) {
    return { status: "disabled" as const, row: null, files: [], unavailable: {} };
  }
  const registry = RegistrySchema.parse(await Bun.file(options.registryPath ?? new URL("config/ledgers.json", REPOSITORY_ROOT)).json());
  const family = registry.families.find((entry) => entry.ledgers.some((ledger) => ledger.name === "host-fingerprint"));
  const ledger = family?.ledgers.find((entry) => entry.name === "host-fingerprint");
  if (!family || !ledger || ledger.grain !== "raw-and-compact" || !ledger.prefix) throw new Error("host-fingerprint requires its registered raw-and-compact prefix");
  const captured = await collectFingerprint(capture, config, settings, options.inspection);
  const result = await persistLedger({
    ledger: "host-fingerprint",
    rowContract: { schema: HostFingerprintRowSchema, schemaVersion: HOST_FINGERPRINT_VERSION },
    outputRoot: options.outputRoot, writerContext: capture.writer,
    registryEntry: {
      name: ledger.name, family: family.name, grain: "raw-and-compact",
      lifecycle_status: family.lifecycle_status, prefix: ledger.prefix,
    },
    ledgerSettings: settings.ledger,
    period: { tier: "raw", covers: capture.date }, rows: [captured.row],
  });
  if (result.status !== "written") {
    throw new Error(`host-fingerprint was not persisted: ${result.status}`);
  }
  return { status: "written" as const, ...captured, files: result.files };
}
