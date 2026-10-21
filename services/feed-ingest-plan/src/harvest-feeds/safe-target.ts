/** Refuse non-public targets before a request and again at socket DNS lookup. */
import { lookup } from "node:dns/promises";
import { isIP } from "node:net";
import ipaddr from "ipaddr.js";

export class UnsafeTargetError extends Error {
  constructor() { super("address is not on the public internet"); }
}
export type ResolvedAddress = { address: string; family: 4 | 6 };
export type ResolveAddresses = (hostname: string) => Promise<readonly ResolvedAddress[]>;

export function isPublicAddress(address: string): boolean {
  if (!ipaddr.isValid(address)) return false;
  const parsed = ipaddr.parse(address);
  if (parsed.kind() === "ipv6" && parsed instanceof ipaddr.IPv6 && parsed.isIPv4MappedAddress()) {
    return isPublicAddress(parsed.toIPv4Address().toString());
  }
  return parsed.range() === "unicast";
}

export function validateTargetName(raw: string): URL {
  let url: URL;
  try { url = new URL(raw); } catch { throw new UnsafeTargetError(); }
  const hostname = url.hostname.replace(/^\[|\]$/g, "").toLowerCase().replace(/\.$/, "");
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password ||
    /[\s\\\x00-\x1f\x7f]/u.test(raw) || !hostname ||
    ["localhost", "ip6-localhost", "ip6-loopback"].includes(hostname) ||
    [".localhost", ".local", ".internal", ".localdomain"].some(suffix => hostname.endsWith(suffix)) ||
    (!isIP(hostname) && (!hostname.includes(".") || !/^[a-z0-9.-]+$/i.test(hostname)))) {
    throw new UnsafeTargetError();
  }
  if (isIP(hostname) && !isPublicAddress(hostname)) throw new UnsafeTargetError();
  return url;
}

export const resolveAddresses: ResolveAddresses = async hostname => {
  const addresses = await lookup(hostname, { all: true, verbatim: true });
  return addresses.map(({ address, family }) => {
    if (family !== 4 && family !== 6) throw new UnsafeTargetError();
    return { address, family };
  });
};

export async function validateTarget(
  raw: string, resolve: ResolveAddresses, signal: AbortSignal,
): Promise<{ url: URL; addresses: readonly ResolvedAddress[] }> {
  const url = validateTargetName(raw);
  const hostname = url.hostname.replace(/^\[|\]$/g, "");
  signal.throwIfAborted();
  const literalFamily = isIP(hostname);
  let addresses: readonly ResolvedAddress[];
  if (literalFamily === 4 || literalFamily === 6) {
    addresses = [{ address: hostname, family: literalFamily }];
  } else {
    let abort: () => void = () => {};
    try {
      addresses = await Promise.race([
        resolve(hostname),
        new Promise<never>((_, reject) => {
          abort = () => reject(signal.reason);
          signal.addEventListener("abort", abort, { once: true });
        }),
      ]);
    } finally { signal.removeEventListener("abort", abort); }
  }
  if (!addresses.length || addresses.some(({ address }) => !isPublicAddress(address))) {
    throw new UnsafeTargetError();
  }
  signal.throwIfAborted();
  return { url, addresses };
}
