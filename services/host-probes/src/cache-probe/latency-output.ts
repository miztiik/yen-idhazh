/** Does multichase output describe the requested working set and finite dependent-load samples? */
import { z } from "zod";

const MetadataSchema = z.strictObject({
  total_memory: z.int().positive(), stride: z.int().positive(),
  tlb_locality: z.int().positive(), nr_threads: z.literal(1), chase: z.literal("simple"),
});
export function parseMultichaseOutput(
  text: string, expected: { working_set_bytes: number; stride_bytes: number; tlb_locality_bytes: number; samples: number },
): { nanoseconds_per_load: number; sample_nanoseconds_per_load: number[] } {
  const metadata: Record<string, unknown> = {};
  const samples: number[] = [];
  let final: number | undefined;
  let sampling = false;
  for (const line of text.split("\n").map(line => line.trim()).filter(Boolean)) {
    const field = /^(total_memory|stride|tlb_locality|nr_threads|chase) = (\S+)(?: \([\d.]+ MiB\))?$/.exec(line);
    if (field) {
      if (field[1]! in metadata) throw new Error("Duplicate multichase metadata");
      metadata[field[1]!] = field[1] === "chase" ? field[2] : Number(field[2]);
      continue;
    }
    if (/^(nr_mixer_indices|base_object_size) = \d+$/.test(line) || /^page_size = \d+/.test(line)) continue;
    if (line === "samples (one column per thread, one row per sample):" && !sampling) { sampling = true; continue; }
    const sample = /^(\d+(?:\.\d+)?)\s+avg=(\d+(?:\.\d+)?)$/.exec(line);
    if (sampling && sample && final === undefined && sample[1] === sample[2]) { samples.push(Number(sample[1])); continue; }
    if (sampling && /^\d+(?:\.\d+)?$/.test(line) && final === undefined) { final = Number(line); continue; }
    throw new Error("Invalid multichase output");
  }
  const actual = MetadataSchema.parse(metadata);
  const result = z.strictObject({
    nanoseconds_per_load: z.number().finite().positive(),
    sample_nanoseconds_per_load: z.array(z.number().finite().positive()).length(expected.samples),
  }).parse({ nanoseconds_per_load: final, sample_nanoseconds_per_load: samples });
  if (actual.total_memory !== expected.working_set_bytes || actual.stride !== expected.stride_bytes
    || actual.tlb_locality !== expected.tlb_locality_bytes) throw new Error("Multichase changed the requested working set");
  return result;
}
