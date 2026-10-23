/** Which durable native feed receipts must one listener retain between planning requests? */
import type { PlanInputs } from "../load-plan-inputs";
import { HEALTH_RECORDED_DAYS, endpointKey } from "../read-ledger-history/read-feed-history";
import { OwnFeedReceiptSchema } from "../read-ledger-history/own-feed-receipts";
import type { FeedWriteReceipt, OwnFeedReceipt } from "../read-ledger-history/own-feed-receipts";

export function retainFeedReceipts(inputs: PlanInputs, initial: readonly OwnFeedReceipt[] = []) {
  const health = new Map<string, Set<string>>();
  const retired = new Map<string, Extract<OwnFeedReceipt, { ledger: "feed-retirements" }>>();
  const retainedDays = Math.max(HEALTH_RECORDED_DAYS, inputs.clock_config.collect.reliability_window_days);
  const currentEndpoints = () => new Set(inputs.harvest.sources.map(source => endpointKey(source.url)));
  const add = (raw: OwnFeedReceipt) => {
    const receipt = OwnFeedReceiptSchema.parse(raw);
    if (receipt.ledger === "feed-health") {
      const paths = health.get(receipt.day) ?? new Set<string>();
      for (const path of receipt.files) paths.add(path);
      health.set(receipt.day, paths);
      for (const day of [...health.keys()].sort().slice(0, -retainedDays)) health.delete(day);
    } else {
      for (const key of receipt.endpoint_keys) {
        if (currentEndpoints().has(key) && !retired.has(key)) retired.set(key, receipt);
      }
    }
  };
  initial.forEach(add);
  return {
    remember(receipt: FeedWriteReceipt) {
      if (receipt.files.length === 0) return;
      const files = receipt.files.map(file => file.path);
      add(receipt.ledger === "feed-health" ? { ledger: receipt.ledger, day: receipt.day, files } : {
        ledger: receipt.ledger, day: receipt.day, files, endpoint_keys: [...receipt.endpoint_keys],
      });
    },
    read(): OwnFeedReceipt[] {
      for (const key of retired.keys()) if (!currentEndpoints().has(key)) retired.delete(key);
      return [
        ...[...health].sort(([a], [b]) => a.localeCompare(b))
          .map(([day, files]) => ({ ledger: "feed-health" as const, day, files: [...files] })),
        ...new Set(retired.values()),
      ];
    },
  };
}
