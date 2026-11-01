/** Refuse unsafe URL names and literal addresses before source dispatch. */
import { isIP } from "node:net";
import ipaddr from "ipaddr.js";

export class UnsafeTargetError extends Error {
  constructor() { super("address is not on the public internet"); }
}

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
