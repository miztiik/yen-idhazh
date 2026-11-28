/** Keep one source's pending fetches from filling the collection's document slots. */
import { sourcePacingKeys } from "./request-pacing";

export function documentAdmission(enabled: boolean, includePrivateSuffixes: boolean) {
  const active = new Set<string>();
  const waiting = new Map<string, Set<() => void>>();

  return async <T>(url: string, publisherId: string | null, execute: (release: () => void) => Promise<T>): Promise<T> => {
    if (!enabled) return execute(() => {});
    const keys = sourcePacingKeys(new URL(url), publisherId, includePrivateSuffixes);
    await new Promise<void>(resolve => {
      const admit = () => {
        const busy = keys.find(key => active.has(key));
        if (busy === undefined) {
          for (const key of keys) active.add(key);
          resolve();
        } else {
          const queue = waiting.get(busy) ?? new Set();
          queue.add(admit);
          waiting.set(busy, queue);
        }
      };
      admit();
    });
    let released = false;
    const release = () => {
      if (released) return;
      released = true;
      for (const key of keys) active.delete(key);
      for (const key of keys) {
        const queue = waiting.get(key);
        if (queue === undefined) continue;
        for (const admit of queue) {
          if (active.has(key)) break;
          queue.delete(admit);
          admit();
        }
        if (queue.size === 0) waiting.delete(key);
      }
    };
    try { return await execute(release); }
    finally { release(); }
  };
}
