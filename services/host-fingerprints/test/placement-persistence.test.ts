/** Do unavailable metadata responses preserve hardware and its real Parquet receipt? */
import { expect, test } from "bun:test";
import { join } from "node:path";
import { z } from "zod";
import { createFingerprintHandler, FINGERPRINT_PATH } from "../src/api/server";
import { fixture } from "./fixture";
import { readTable, storedRow } from "./parquet-readback";

function request(input: unknown) {
  return new Request(`http://localhost${FINGERPRINT_PATH}`, { method: "POST", body: JSON.stringify(input) });
}

test("placement setting off skips the metadata body without disabling hardware or persistence", async () => {
  const f = await fixture();
  try {
    f.settings.observability.host_fingerprint_placement_enabled = false;
    const metadata = Response.json(f.input.metadata);
    const handler = createFingerprintHandler(f.config, f.settings, {
      outputRoot: join(f.directory, "disabled-placement"), inspection: { ...f.inspection, metadata },
    });
    const response = await handler(request(f.apiInput));
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.status).toBe("written");
    expect(body.row).toMatchObject(f.input.expected);
    expect(body.row.vm_size).toBeNull();
    expect(body.unavailable.placement).toBe("configured_off");
    expect(body.files).toHaveLength(1);
    expect(metadata.bodyUsed).toBe(false);
  } finally { await f.cleanup(); }
});

test("recorded HTTP and transport failures degrade only placement and still persist Parquet", async () => {
  const input = z.object({
    responses: z.array(z.object({
      name: z.string(), status: z.int(), body: z.string().nullable(), reason: z.string(),
    })),
    failures: z.array(z.object({
      name: z.enum(["TimeoutError", "AbortError", "TypeError", "ECONNREFUSED"]), reason: z.string(),
    })),
  }).parse(await Bun.file(new URL("../../../tests/fixtures/host-fingerprints/metadata-responses.json", import.meta.url)).json());
  const f = await fixture();
  try {
    const cases = [
      ...input.responses.map((entry) => ({
        ...entry, response: new Response(entry.body, { status: entry.status }),
      })),
      ...input.failures.map((entry) => ({
        ...entry,
        response: new Response(new ReadableStream<Uint8Array>({
          start(controller) {
            controller.error(entry.name === "TypeError" ? new TypeError("Recorded metadata transport failure") :
              entry.name === "ECONNREFUSED" ? Object.assign(new Error("Recorded connection failure"), { code: entry.name }) :
                new DOMException("Recorded metadata deadline", entry.name));
          },
        })),
      })),
    ];
    for (const [index, entry] of cases.entries()) {
      const outputRoot = join(f.directory, `failure-${index}`);
      const handler = createFingerprintHandler(f.config, f.settings, {
        outputRoot, inspection: { ...f.inspection, metadata: entry.response },
      });
      const response = await handler(request(f.apiInput));
      expect(response.status, entry.name).toBe(200);
      const body = await response.json();
      expect(body.status, entry.name).toBe("written");
      expect(body.row, entry.name).toMatchObject(f.input.expected);
      expect(body.row.vm_size, entry.name).toBeNull();
      expect(body.unavailable.placement, entry.name).toBe(entry.reason);
      expect(body.files, entry.name).toHaveLength(1);
      const { table } = await readTable(outputRoot, body.files[0].path);
      expect(storedRow(table), entry.name).toMatchObject(body.row);
    }
  } finally { await f.cleanup(); }
});

test("oversized metadata cannot stop the hardware ledger write", async () => {
  const f = await fixture();
  try {
    f.config.max_input_bytes = 4096;
    const handler = createFingerprintHandler(f.config, f.settings, {
      outputRoot: join(f.directory, "oversized-placement"),
      inspection: { ...f.inspection, metadata: new Response("x".repeat(f.config.max_input_bytes + 1)) },
    });
    const response = await handler(request(f.apiInput));
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.status).toBe("written");
    expect(body.row).toMatchObject(f.input.expected);
    expect(body.row.vm_size).toBeNull();
    expect(body.unavailable.placement).toBe("metadata_too_large");
    expect(body.files).toHaveLength(1);
  } finally { await f.cleanup(); }
});
