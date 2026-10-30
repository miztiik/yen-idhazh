/** Which downward three-decimal values describe this feed's measured reads? */
export function feedReliability(productive: number, attempted: number, floor: number) {
  if (!Number.isSafeInteger(productive) || !Number.isSafeInteger(attempted)
    || attempted <= 0 || productive < 0 || productive > attempted) {
    throw new RangeError("Feed reliability requires safe read counts with 0 <= productive <= attempted and attempted > 0");
  }
  if (!Number.isFinite(floor) || floor < 0 || floor > 1) {
    throw new RangeError("Feed reliability floor must be finite and between 0 and 1");
  }
  // These two saved fields use thousandths; this is not a score precision policy.
  const scale = 1000;
  const fractionUnits = Number(BigInt(productive) * BigInt(scale) / BigInt(attempted));
  const [whole, fraction = ""] = floor.toString().split(".");
  // Scientific notation occurs only below a thousandth for a valid ratio.
  const floorUnits = floor < 1 / scale ? 0 : Number(`${whole}${fraction.padEnd(3, "0").slice(0, 3)}`);
  return {
    success_fraction: fractionUnits / scale,
    production_factor: Math.max(floorUnits, fractionUnits) / scale,
  };
}
