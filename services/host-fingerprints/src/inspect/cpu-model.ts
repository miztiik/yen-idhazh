/** Which CPU identity and optional clock facts does Linux report? */
import { WATCHED_FLAGS } from "@idhazh/common-contracts";
import { parseInteger, parsePositive } from "./bounded-input";

export function parseCpuModel(text: string | null, frequency: boolean) {
  const fields = new Map<string, string>();
  const clocks: number[] = [];
  for (const line of (text ?? "").split("\n")) {
    const separator = line.indexOf(":");
    if (separator < 0) continue;
    const name = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim();
    if (!fields.has(name)) fields.set(name, value);
    if (name === "cpu MHz") {
      const mhz = parsePositive(value);
      if (mhz !== null) clocks.push(mhz);
    }
  }
  const present = new Set((fields.get("flags") ?? "").split(/\s+/));
  const identifier = (name: string) => {
    const value = parseInteger(fields.get(name));
    return value !== null && value >= 0 ? value : null;
  };
  return {
    cpu_model: fields.get("model name") || null, cpu_vendor: fields.get("vendor_id") || null,
    cpu_family: identifier("cpu family"), cpu_model_number: identifier("model"),
    cpu_stepping: identifier("stepping"), microcode: fields.get("microcode") || null,
    flags: WATCHED_FLAGS.filter((flag) => present.has(flag)).join(" "),
    cpu_observed_mhz: frequency && clocks.length ? clocks.reduce((sum, clock) => sum + clock, 0) / clocks.length : null,
  };
}
