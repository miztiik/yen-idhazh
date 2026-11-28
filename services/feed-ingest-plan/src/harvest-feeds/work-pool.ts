/** Bound work across callers without charging time until an operation starts. */
import { PositiveCountSchema } from "@idhazh/common-contracts";

export function workPool(concurrency: number) {
  PositiveCountSchema.parse(concurrency);
  let active = 0;
  const waiting: (() => void)[] = [];
  return async <T>(execute: () => Promise<T>): Promise<T> => {
    if (active >= concurrency) await new Promise<void>(resolve => waiting.push(resolve));
    else active++;
    try { return await execute(); }
    finally {
      const next = waiting.shift();
      if (next === undefined) active--;
      else next();
    }
  };
}
